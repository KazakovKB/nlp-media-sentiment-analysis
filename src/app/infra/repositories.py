from __future__ import annotations

from typing import Optional, Sequence, Any
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.app.infra.models import (
    UserORM, AccountORM, AccountUserORM, SubscriptionORM,
    SourceORM, AccountSourceORM,
    DocumentORM,
    AnalysisJobORM, OverviewReportORM, TrendEventORM,
)

from src.app.domain.enums import JobStatus
from src.app.domain.value_objects import AnalysisScope, DateRange, AuthCredentials, ModelRef
from src.app.domain.entities.user import User
from src.app.domain.entities.source import Source
from src.app.domain.entities.document import Document
from src.app.domain.entities.analysis_job import AnalysisJob
from src.app.domain.entities.overview_report import OverviewReport


# mappers ORM -> Domain
def _user_dom(u: UserORM) -> User:
    return User(
        id=int(u.id),
        email=str(u.email),
        is_active=bool(u.is_active),
        created_at=u.created_at,
    )


def _auth_creds_dom(u: UserORM) -> AuthCredentials:
    return AuthCredentials(
        user_id=int(u.id),
        password_hash=str(u.password_hash),
    )


def _source_dom(s: SourceORM) -> Source:
    return Source(
        id=int(s.id),
        name=str(s.name),
        source_type=str(s.source_type),
        ingestion_mode=str(s.ingestion_mode),
        config=s.config or {},
        created_at=s.created_at,
    )


def _doc_dom(d: DocumentORM) -> Document:
    return Document(
        id=int(d.id),
        source_id=int(d.source_id),
        published_at=d.published_at,
        title=d.title,
        text=d.text,
        topic=d.topic,
        url=d.url,
        url_hash=d.url_hash,
        meta=d.meta or {},
    )


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _scope_from_dict(d: dict) -> AnalysisScope:
    dr = d.get("date_range") or {}
    return AnalysisScope(
        source_ids=[int(x) for x in d.get("source_ids", [])],
        date_range=DateRange(
            start=_parse_dt(dr["start"]),
            end=_parse_dt(dr["end"]),
        ),
        query=d.get("query"),
    )


def _scope_to_dict(scope: AnalysisScope) -> dict:
    return {
        "source_ids": [int(x) for x in scope.source_ids],
        "date_range": {
            "start": scope.date_range.start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "end": scope.date_range.end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "query": scope.query,
    }


def _job_dom(j: AnalysisJobORM) -> AnalysisJob:
    return AnalysisJob(
        id=int(j.id),
        account_id=int(j.account_id),
        scope=_scope_from_dict(j.scope),
        model=ModelRef(name=str(j.model_name), version=str(j.model_version)),
        status=JobStatus(str(j.status)),
        created_at=j.created_at,
        params=j.params or {},
        error=j.error or "",
        finished_at=j.finished_at,
    )


def _overview_dom(r: OverviewReportORM) -> OverviewReport:
    return OverviewReport(
        job_id=int(r.job_id),
        total_documents=int(r.total_documents),
        sentiment_share=r.sentiment_share,
        metrics=r.metrics,
        created_at=r.created_at,
    )

# repos
class SqlUserRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        u = self.db.query(UserORM).filter(UserORM.email == email).first()
        return _user_dom(u) if u else None

    def get_by_id(self, user_id: int) -> Optional[User]:
        u = self.db.query(UserORM).filter(UserORM.id == user_id).first()
        return _user_dom(u) if u else None

    def get_auth_credentials(self, email: str) -> Optional[AuthCredentials]:
        u = self.db.query(UserORM).filter(UserORM.email == email).first()
        return _auth_creds_dom(u) if u else None

    def create(self, email: str, password_hash: str) -> User:
        u = UserORM(email=email, password_hash=password_hash, is_active=True)
        self.db.add(u)
        self.db.flush()
        return _user_dom(u)


class SqlAccountRepo:
    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str) -> int:
        acc = AccountORM(name=name)
        self.db.add(acc)
        self.db.flush()
        return int(acc.id)

    def add_user(self, account_id: int, user_id: int, role: str) -> None:
        link = AccountUserORM(account_id=account_id, user_id=user_id, role=role)
        self.db.add(link)
        self.db.flush()

    def get_user_link(self, user_id: int) -> Optional[tuple[int, str]]:
        row = self.db.query(AccountUserORM).filter(AccountUserORM.user_id == user_id).first()
        if not row:
            return None
        return int(row.account_id), str(row.role)


class SqlSubscriptionRepo:
    def __init__(self, db: Session):
        self.db = db

    def ensure_free_active(self, account_id: int) -> None:
        sub = self.db.query(SubscriptionORM).filter(SubscriptionORM.account_id == account_id).first()
        if sub:
            return
        self.db.add(SubscriptionORM(account_id=account_id, plan="free", status="active"))
        self.db.flush()


class SqlAccountSourceRepo:
    """
    Репозиторий для управления доступом аккаунтов к глобальным источникам.
    """

    def __init__(self, db: Session):
        self.db = db

    def grant_many(self, account_id: int, source_id: int, enabled: bool = True) -> None:
        row = (
            self.db.query(AccountSourceORM)
            .filter(
                AccountSourceORM.account_id == account_id,
                AccountSourceORM.source_id == source_id,
            )
            .first()
        )
        if row:
            row.is_enabled = bool(enabled)
        else:
            self.db.add(
                AccountSourceORM(
                    account_id=account_id,
                    source_id=source_id,
                    is_enabled=bool(enabled),
                )
            )
        self.db.flush()

    def grant_all_global(self, account_id: int) -> None:
        """
        Выдаёт доступ ко всем существующим sources (enabled=True).
        """
        source_ids = [int(x[0]) for x in self.db.query(SourceORM.id).all()]
        for sid in source_ids:
            self.grant_many(account_id, sid, enabled=True)


class SqlSourceRepo:
    def __init__(self, db: Session):
        self.db = db

    def list_by_account(self, account_id: int) -> list[Source]:
        """
        Возвращает только sources, доступные аккаунту (account_sources).
        """
        rows = (
            self.db.query(SourceORM)
            .join(AccountSourceORM, AccountSourceORM.source_id == SourceORM.id)
            .filter(
                AccountSourceORM.account_id == account_id,
                AccountSourceORM.is_enabled.is_(True),
            )
            .order_by(SourceORM.created_at.desc())
            .all()
        )
        return [_source_dom(s) for s in rows]

    def get_by_id(self, account_id: int, source_id: int) -> Optional[Source]:
        """
        Возвращает source только если он доступен аккаунту.
        """
        s = (
            self.db.query(SourceORM)
            .join(AccountSourceORM, AccountSourceORM.source_id == SourceORM.id)
            .filter(
                SourceORM.id == source_id,
                AccountSourceORM.account_id == account_id,
                AccountSourceORM.is_enabled.is_(True),
            )
            .first()
        )
        return _source_dom(s) if s else None


class SqlDocumentRepo:
    def __init__(self, db: Session):
        self.db = db

    def count_by_sources_and_period(self, source_ids, date_from, date_to, query=None) -> int:
        q = (
            self.db.query(func.count(DocumentORM.id))
            .filter(
                DocumentORM.source_id.in_(list(source_ids)),
                DocumentORM.published_at >= date_from,
                DocumentORM.published_at <= date_to,
            )
        )

        if query:
            qq = f"%{query.strip().lower()}%"
            q = q.filter(
                or_(
                    func.lower(func.coalesce(DocumentORM.title, "")).like(qq),
                    func.lower(DocumentORM.text).like(qq),
                )
            )

        return int(q.scalar() or 0)

    def list_by_sources_and_period(
        self,
        source_ids: Sequence[int],
        date_from: datetime,
        date_to: datetime,
        limit: Optional[int] = None,
    ) -> list[Document]:
        q = (
            self.db.query(DocumentORM)
            .filter(
                DocumentORM.source_id.in_([int(x) for x in source_ids]),
                DocumentORM.published_at >= date_from,
                DocumentORM.published_at <= date_to,
            )
            .order_by(DocumentORM.published_at.asc())
        )
        if limit:
            q = q.limit(limit)
        return [_doc_dom(d) for d in q.all()]

    def stats_by_source(self, account_id: int, source_id: int) -> dict:
        """
        Статистика по source – только если source доступен аккаунту.
        """
        access = (
            self.db.query(AccountSourceORM)
            .filter(
                AccountSourceORM.account_id == account_id,
                AccountSourceORM.source_id == source_id,
                AccountSourceORM.is_enabled.is_(True),
            )
            .first()
        )
        if not access:
            raise ValueError("Источник не найден или запрещён.")

        total, dmin, dmax = (
            self.db.query(
                func.count(DocumentORM.id),
                func.min(DocumentORM.published_at),
                func.max(DocumentORM.published_at),
            )
            .filter(DocumentORM.source_id == source_id)
            .one()
        )
        return {
            "total_documents": int(total or 0),
            "date_min": dmin,
            "date_max": dmax,
        }


class SqlAnalysisJobRepo:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        account_id: int,
        model: ModelRef,
        scope: AnalysisScope,
        params: dict[str, Any],
    ) -> AnalysisJob:
        j = AnalysisJobORM(
            account_id=account_id,
            status=JobStatus.PENDING.value,
            model_name=model.name,
            model_version=model.version,
            scope=_scope_to_dict(scope),
            params=params or {},
        )
        self.db.add(j)
        self.db.flush()
        return _job_dom(j)

    def set_status(self, job_id: int, status: JobStatus, error: str | None = None) -> None:
        j = self.db.query(AnalysisJobORM).filter(AnalysisJobORM.id == job_id).first()
        if not j:
            raise ValueError("Job not found")

        j.status = status.value

        if status in (JobStatus.DONE, JobStatus.ERROR):
            j.finished_at = datetime.now(timezone.utc)

        if error is not None:
            j.error = error or None

        self.db.flush()


    def set_done(self, job_id: int) -> None:
        self.set_status(job_id, JobStatus.DONE, error="")

    def set_error(self, job_id: int, error: str) -> None:
        self.set_status(job_id, JobStatus.ERROR, error=error)

    def list_by_account(self, account_id: int, limit: int = 50) -> list[AnalysisJob]:
        rows = (
            self.db.query(AnalysisJobORM)
            .filter(AnalysisJobORM.account_id == account_id)
            .order_by(AnalysisJobORM.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_job_dom(j) for j in rows]

    def get_by_id(self, account_id: int, job_id: int) -> Optional[AnalysisJob]:
        j = (
            self.db.query(AnalysisJobORM)
            .filter(AnalysisJobORM.id == job_id, AnalysisJobORM.account_id == account_id)
            .first()
        )
        return _job_dom(j) if j else None

    def get_by_id_any(self, job_id: int) -> Optional[AnalysisJob]:
        j = self.db.query(AnalysisJobORM).filter(AnalysisJobORM.id == job_id).first()
        return _job_dom(j) if j else None


class SqlOverviewRepo:
    def __init__(self, db: Session):
        self.db = db

    def upsert(self, report: OverviewReport) -> None:
        row = self.db.query(OverviewReportORM).filter(OverviewReportORM.job_id == report.job_id).first()
        if not row:
            row = OverviewReportORM(
                job_id=report.job_id,
                total_documents=report.total_documents,
                sentiment_share=report.sentiment_share,
                metrics=report.metrics,
            )
            self.db.add(row)
        else:
            row.total_documents = report.total_documents
            row.sentiment_share = report.sentiment_share
            row.metrics = report.metrics
        self.db.flush()

    def get_by_job(self, job_id: int) -> Optional[OverviewReport]:
        r = self.db.query(OverviewReportORM).filter(OverviewReportORM.job_id == job_id).first()
        return _overview_dom(r) if r else None


class SqlTrendRepo:
    def __init__(self, db: Session):
        self.db = db

    def save_many(self, job_id: int, events: list[dict]) -> None:
        for ev in events:
            self.db.add(
                TrendEventORM(
                    job_id=job_id,
                    start_ts=ev["start_ts"],
                    end_ts=ev["end_ts"],
                    label=ev.get("label", "spike"),
                    score=float(ev.get("score", 0.0)),
                    top_doc_ids=ev.get("top_doc_ids", []),
                )
            )
        self.db.flush()