import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values


IMPORT_KIND = "LENTA_IMPORT_V1"
REQUIRED_COLUMNS = {"url", "title", "text", "topic", "tags", "date"}


# utils
def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse_date_yyyy_mm_dd(s: str) -> datetime:
    dt = datetime.strptime(s.strip(), "%Y/%m/%d")
    return dt.replace(tzinfo=timezone.utc)


# source (GLOBAL)
def ensure_source_global(conn, name: str) -> int:
    """
    Создаёт глобальный Source (без account_id), если его нет.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select id
            from sources
            where name = %s
            limit 1
            """,
            (name,),
        )
        row = cur.fetchone()
        if row:
            return int(row[0])

        cur.execute(
            """
            insert into sources(name, source_type, ingestion_mode, config)
            values (%s, %s, %s, %s::jsonb)
            returning id
            """,
            (
                name,
                "news_corpus",
                "historical",
                json.dumps(
                    {
                        "provider": "kaggle",
                        "dataset": "yutkin/corpus-of-russian-news-articles-from-lenta",
                    }
                ),
            ),
        )
        source_id = int(cur.fetchone()[0])

    conn.commit()
    return source_id


# ingestion job
def has_done_ingestion(conn, source_id: int, kind: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            select 1
            from ingestion_jobs
            where source_id = %s
              and kind = %s
              and status = 'DONE'
            limit 1
            """,
            (source_id, kind),
        )
        return cur.fetchone() is not None


def start_ingestion_job(conn, source_id: int, kind: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into ingestion_jobs(source_id, kind, status, created_at)
            values (%s, %s, 'RUNNING', now())
            returning id
            """,
            (source_id, kind),
        )
        job_id = int(cur.fetchone()[0])

    conn.commit()
    return job_id


def finish_ingestion_ok(conn, job_id: int, stats: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update ingestion_jobs
            set status = 'DONE',
                finished_at = now(),
                error = null,
                stats = %s::jsonb
            where id = %s
            """,
            (json.dumps(stats), job_id),
        )
    conn.commit()


def finish_ingestion_error(conn, job_id: int, error: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update ingestion_jobs
            set status = 'ERROR',
                finished_at = now(),
                error = %s
            where id = %s
            """,
            (error, job_id),
        )
    conn.commit()


# documents import
def flush_batch(conn, batch) -> int:
    """
    Вставка батча в documents с дедупом по (source_id, url_hash).
    """
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            insert into documents(
                source_id,
                published_at,
                title,
                text,
                topic,
                url,
                url_hash,
                meta
            )
            values %s
            on conflict (source_id, url_hash) do nothing
            """,
            batch,
            page_size=2000,
        )
        inserted = cur.rowcount or 0

    conn.commit()
    return inserted


def import_csv(
    conn,
    csv_path: str,
    source_id: int,
    batch_size: int,
    limit: Optional[int],
) -> tuple[int, int]:
    processed = 0
    inserted_total = 0
    batch = []

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError("CSV has no header")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing columns: {sorted(missing)}")

        for row in reader:
            processed += 1
            if limit and processed > limit:
                break

            url = (row.get("url") or "").strip()
            text = (row.get("text") or "").strip()
            date_s = (row.get("date") or "").strip()

            if not url or not text or not date_s:
                continue

            try:
                published_at = parse_date_yyyy_mm_dd(date_s)
            except Exception:
                continue

            title = (row.get("title") or "").strip() or None
            topic = (row.get("topic") or "").strip() or None
            tags = (row.get("tags") or "").strip() or None

            meta = {}
            if tags:
                meta["tags"] = tags

            batch.append(
                (
                    source_id,
                    published_at,
                    title,
                    text,
                    topic,
                    url,
                    sha256_hex(url),
                    json.dumps(meta),
                )
            )

            if len(batch) >= batch_size:
                inserted_total += flush_batch(conn, batch)
                batch.clear()

        if batch:
            inserted_total += flush_batch(conn, batch)

    return processed, inserted_total


# main
def main() -> None:
    ap = argparse.ArgumentParser(description="One-time Lenta corpus importer (GLOBAL source)")

    ap.add_argument("--dsn", default=os.getenv("DATABASE_URL"), help="DATABASE_URL")
    ap.add_argument("--csv", default=os.getenv("LENTA_CSV_PATH", "/data/corpus/lenta-ru-news.csv"), help="LENTA_CSV_PATH")
    ap.add_argument("--source-name", default=os.getenv("SOURCE_NAME", "Lenta (historical)"))
    ap.add_argument("--batch-size", type=int, default=int(os.getenv("BATCH_SIZE", "2000")))
    ap.add_argument("--limit", type=int, default=None if os.getenv("LIMIT") is None else int(os.getenv("LIMIT")))

    args = ap.parse_args()

    if not args.dsn:
        raise ValueError("DSN is required: pass --dsn or set DATABASE_URL")
    if not args.csv:
        raise ValueError("CSV path is required: pass --csv or set LENTA_CSV_PATH")

    conn = psycopg2.connect(args.dsn)
    try:
        source_id = ensure_source_global(conn, args.source_name)

        if has_done_ingestion(conn, source_id, IMPORT_KIND):
            print(f"[SKIP] Ingestion already DONE for source_id={source_id}, kind={IMPORT_KIND}")
            return

        ingestion_job_id = start_ingestion_job(conn, source_id, IMPORT_KIND)
        print(f"[START] ingestion_job_id={ingestion_job_id}, source_id={source_id}")

        try:
            processed, inserted = import_csv(
                conn,
                csv_path=args.csv,
                source_id=source_id,
                batch_size=args.batch_size,
                limit=args.limit,
            )

            finish_ingestion_ok(
                conn,
                ingestion_job_id,
                stats={
                    "processed_rows": processed,
                    "inserted_rows": inserted,
                    "csv_path": args.csv,
                    "source_id": source_id,
                    "kind": IMPORT_KIND,
                },
            )

            print("[DONE]")
            print(f"Processed rows: {processed}")
            print(f"Inserted rows:  {inserted}")

        except Exception as e:
            finish_ingestion_error(conn, ingestion_job_id, str(e))
            raise

    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)