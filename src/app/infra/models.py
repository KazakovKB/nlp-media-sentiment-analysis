from sqlalchemy import (
    Column, String, Boolean,
    DateTime, BigInteger, ForeignKey,
    Text, Float, Integer,
    UniqueConstraint, Index, Identity, text as sa_text,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from src.app.infra.db import Base


class UserORM(Base):
    __tablename__ = "users"

    id = Column(BigInteger, Identity(), primary_key=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=sa_text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccountORM(Base):
    __tablename__ = "accounts"

    id = Column(BigInteger, Identity(), primary_key=True)
    name = Column(String, nullable=False)
    is_white_label = Column(Boolean, nullable=False, server_default=sa_text("false"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccountUserORM(Base):
    __tablename__ = "account_users"

    account_id = Column(BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_account_users_user", "user_id"),
        Index("idx_account_users_account", "account_id"),
    )


class SubscriptionORM(Base):
    __tablename__ = "subscriptions"

    id = Column(BigInteger, Identity(), primary_key=True)
    account_id = Column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    plan = Column(String, nullable=False)
    status = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=True)


class SourceORM(Base):
    """
    Глобальный источник (не принадлежит конкретному аккаунту).
    Доступ аккаунта к источнику регулируется таблицей account_sources.
    """
    __tablename__ = "sources"

    id = Column(BigInteger, Identity(), primary_key=True)
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    ingestion_mode = Column(String, nullable=False)
    config = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_type", "name", name="uq_sources_type_name"),
        Index("idx_sources_type", "source_type"),
    )


class AccountSourceORM(Base):
    """
    ACL-связка: какой аккаунт имеет доступ к какому источнику.
    """
    __tablename__ = "account_sources"

    account_id = Column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_id = Column(
        BigInteger,
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    )

    is_enabled = Column(Boolean, nullable=False, server_default=sa_text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # Быстрый list_by_account(account_id)
        Index("idx_account_sources_account_enabled", "account_id", "is_enabled"),
        # каким аккаунтам доступен source
        Index("idx_account_sources_source", "source_id"),
    )


class DocumentORM(Base):
    __tablename__ = "documents"

    id = Column(BigInteger, Identity(), primary_key=True)
    source_id = Column(
        BigInteger,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    published_at = Column(DateTime(timezone=True), nullable=False)
    title = Column(Text, nullable=True)
    text = Column(Text, nullable=False)
    topic = Column(String, nullable=True)
    url = Column(Text, nullable=True)
    url_hash = Column(String, nullable=False)
    meta = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("source_id", "url_hash", name="uq_documents_source_url_hash"),
        Index("idx_documents_source_published", "source_id", "published_at"),
        Index("idx_documents_topic", "topic"),
    )


class AnalysisJobORM(Base):
    __tablename__ = "analysis_jobs"

    id = Column(BigInteger, Identity(), primary_key=True)
    account_id = Column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    scope = Column(JSONB, nullable=False)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_analysis_jobs_account_created", "account_id", "created_at"),
    )


class PredictionORM(Base):
    __tablename__ = "predictions"

    id = Column(BigInteger, Identity(), primary_key=True)
    job_id = Column(
        BigInteger,
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id = Column(
        BigInteger,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    label = Column(String, nullable=False)
    p_neg = Column(Float, nullable=False)
    p_neu = Column(Float, nullable=False)
    p_pos = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("job_id", "document_id", name="uq_predictions_job_document"),
        Index("idx_predictions_job", "job_id"),
    )


class OverviewReportORM(Base):
    __tablename__ = "overview_reports"

    job_id = Column(
        BigInteger,
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_documents = Column(Integer, nullable=False)
    sentiment_share = Column(JSONB, nullable=False)
    metrics = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TrendEventORM(Base):
    __tablename__ = "trend_events"

    id = Column(BigInteger, Identity(), primary_key=True)

    job_id = Column(
        BigInteger,
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ts = Column(DateTime(timezone=True), nullable=False)
    kind = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    baseline = Column(Float, nullable=False)
    z = Column(Float, nullable=False)
    top_doc_ids = Column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))

    __table_args__ = (
        Index("idx_trend_events_job_ts", "job_id", "ts"),
    )


class IngestionJobORM(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(BigInteger, Identity(), primary_key=True)
    source_id = Column(
        BigInteger,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )

    kind = Column(String, nullable=False, server_default=sa_text("'GENERIC'"))
    status = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    error = Column(Text, nullable=True)
    stats = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))

    __table_args__ = (
        Index("idx_ingestion_jobs_source_kind", "source_id", "kind"),
    )