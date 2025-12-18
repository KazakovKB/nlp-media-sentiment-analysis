from datetime import datetime, timezone
from collections import defaultdict, Counter
import os
import torch

from src.app.domain.contracts.uow import UoW
from src.app.domain.value_objects import AnalysisScope, ModelRef
from src.app.domain.services.scope_filter import filter_documents
from src.app.domain.services.trend_detection import detect_trends
from src.app.domain.entities.overview_report import OverviewReport
from src.app.domain.enums import JobStatus
from src.app.ml.registry import get_sentiment_model


class AnalysisService:
    def __init__(self, uow: UoW):
        self.uow = uow

        # FEATURE FLAGS
        self.sentiment_enabled = os.getenv("SENTIMENT_ENABLED", "0") == "1"
        self.sentiment_fail_open = os.getenv("SENTIMENT_FAIL_OPEN", "1") == "1"

        self._tokenizer = None
        self._model = None
        self._id2label = None

    def _get_model(self):
        if self._model is None:
            tok, mdl, id2lbl = get_sentiment_model()
            mdl.eval()
            self._tokenizer, self._model, self._id2label = tok, mdl, id2lbl
        return self._tokenizer, self._model, self._id2label

    def estimate_scope_docs_count(self, account_id: int, scope: AnalysisScope) -> int:
        for sid in scope.source_ids:
            if not self.uow.sources.get_by_id(account_id, int(sid)):
                raise ValueError(f"Источник не найден или запрещен: {sid}")

        return self.uow.documents.count_by_sources_and_period(
            source_ids=scope.source_ids,
            date_from=scope.date_range.start,
            date_to=scope.date_range.end,
            query=scope.query,
        )

    def create_job(self, account_id: int, model: ModelRef, scope: AnalysisScope, params: dict):
        cnt = self.estimate_scope_docs_count(account_id, scope)
        if cnt == 0:
            raise ValueError("За выбранный период документов не найдено. Измените даты или источники.")

        job = self.uow.analysis.create(account_id, model, scope, params)
        self.uow.analysis.set_status(job.id, JobStatus.PENDING)
        self.uow.commit()
        return self.uow.analysis.get_by_id(account_id, job.id)

    def run_job(self, job_id: int) -> None:
        job = self.uow.analysis.get_by_id_any(job_id)
        if not job:
            return

        if job.status in (JobStatus.DONE, JobStatus.ERROR):
            return

        if job.status == JobStatus.RUNNING:
            return

        try:
            self.uow.analysis.set_status(job.id, JobStatus.RUNNING)
            self.uow.commit()

            self._run_overview(job_id=job.id, account_id=job.account_id, scope=job.scope)

            self.uow.analysis.set_done(job.id)
            self.uow.commit()

        except Exception as e:
            try:
                self.uow.analysis.set_error(job.id, str(e))
                self.uow.commit()
            except Exception:
                self.uow.rollback()
            raise

    def _run_overview(self, job_id: int, account_id: int, scope: AnalysisScope) -> None:
        for sid in scope.source_ids:
            if not self.uow.sources.get_by_id(account_id, int(sid)):
                raise ValueError(f"Источник не найден или запрещен: {sid}")

        docs = self.uow.documents.list_by_sources_and_period(
            source_ids=scope.source_ids,
            date_from=scope.date_range.start,
            date_to=scope.date_range.end,
        )

        filtered = filter_documents(docs, scope)

        if scope.query:
            q = scope.query.strip().lower()
            filtered = [d for d in filtered if q in (d.title or "").lower() or q in d.text.lower()]

        texts = [d.text for d in filtered if d.text]
        total = len(texts)

        # --- SENTIMENT ---
        sentiment_share = None
        sentiment_mode = "disabled"
        sentiment_error = None

        if total == 0:
            sentiment_share = {"negative": 0.0, "neutral": 1.0, "positive": 0.0}
            sentiment_mode = "empty"
        elif not self.sentiment_enabled:
            # Заглушка
            sentiment_share = {"negative": 0.0, "neutral": 1.0, "positive": 0.0}
            sentiment_mode = "stub"
        else:
            try:
                tokenizer, model, id2label = self._get_model()
                counts = Counter({"negative": 0, "neutral": 0, "positive": 0})

                device = next(model.parameters()).device

                for batch in _batch(texts, size=32):
                    inputs = tokenizer(
                        batch,
                        padding=True,
                        truncation=True,
                        max_length=384,
                        return_tensors="pt",
                    )
                    inputs = {k: v.to(device) for k, v in inputs.items()}

                    with torch.no_grad():
                        out = model(**inputs)
                        logits = out.logits if hasattr(out, "logits") else out["logits"]
                        pred_ids = torch.argmax(logits, dim=-1).tolist()

                    for pid in pred_ids:
                        lbl = self._normalize_label(id2label[int(pid)])
                        counts[lbl] += 1

                sentiment_share = {k: counts[k] / total for k in counts}
                sentiment_mode = "model"

            except Exception as e:
                sentiment_error = str(e)
                if not self.sentiment_fail_open:
                    raise
                # fail-open: не валим job, даём заглушку
                sentiment_share = {"negative": 0.0, "neutral": 1.0, "positive": 0.0}
                sentiment_mode = "fallback"

        # TRENDS
        ts = _build_daily_count_series(filtered)
        events = detect_trends(ts)
        self.uow.trend.save_many(job_id, events)

        # OVERVIEW
        metrics = {
            "source_ids": list(scope.source_ids),
            "date_from": scope.date_range.start.isoformat(),
            "date_to": scope.date_range.end.isoformat(),
            "query": scope.query,
            "timeseries_days": len(ts),
            "trends_found": len(events),
            "sentiment_mode": sentiment_mode,
        }
        if sentiment_error:
            metrics["sentiment_error"] = sentiment_error  # чтобы видеть в UI причину

        report = OverviewReport(
            job_id=job_id,
            total_documents=total,
            sentiment_share=sentiment_share,
            metrics=metrics,
            created_at=datetime.now(timezone.utc),
        )
        self.uow.overview.upsert(report)

    def _normalize_label(self, lbl: str) -> str:
        lbl = lbl.lower()
        if "neg" in lbl:
            return "negative"
        if "pos" in lbl:
            return "positive"
        return "neutral"

    def list_jobs(self, account_id: int, limit: int = 50):
        return self.uow.analysis.list_by_account(account_id, limit)

    def get_job(self, account_id: int, job_id: int):
        return self.uow.analysis.get_by_id(account_id, job_id)

    def get_overview(self, account_id: int, job_id: int):
        j = self.uow.analysis.get_by_id(account_id, job_id)
        if not j or j.status != JobStatus.DONE:
            return None
        return self.uow.overview.get_by_job(job_id)


def _batch(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _build_daily_count_series(docs) -> list[dict]:
    buckets = defaultdict(int)
    for d in docs:
        dt = d.published_at.astimezone(timezone.utc)
        day = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
        buckets[day] += 1
    return [{"ts": ts, "value": buckets[ts]} for ts in sorted(buckets)]