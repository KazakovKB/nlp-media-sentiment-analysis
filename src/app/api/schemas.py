from datetime import datetime
from typing import Any, Optional, Sequence

from pydantic import BaseModel, Field, ConfigDict


# Auth
class AuthRegisterRequest(BaseModel):
    email: str
    password: str
    account_name: str = Field(..., description="Название аккаунта при регистрации")


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Sources
class SourceResponse(BaseModel):
    id: int
    name: str
    source_type: str
    ingestion_mode: str
    config: dict[str, Any]
    created_at: datetime

class SourceStatsResponse(BaseModel):
    source_id: int
    total_documents: int
    date_min: Optional[datetime] = None
    date_max: Optional[datetime] = None


# Analysis
class DateRangeRequest(BaseModel):
    start: datetime
    end: datetime


class AnalysisScopeRequest(BaseModel):
    source_ids: Sequence[int]
    date_range: DateRangeRequest
    query: Optional[str] = None


class ModelRefRequest(BaseModel):
    name: str
    version: str


class CreateAnalysisJobRequest(BaseModel):
    model: ModelRefRequest
    scope: AnalysisScopeRequest
    params: dict[str, Any] = Field(default_factory=dict)


class AnalysisJobResponse(BaseModel):
    """
    Возвращаем job как доменный объект (dataclass).
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    status: str
    created_at: datetime
    finished_at: Optional[datetime] = None

    model: dict[str, str]
    scope: dict[str, Any]
    params: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class OverviewReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: int
    total_documents: int
    sentiment_share: dict[str, Any]
    metrics: dict[str, Any]
    created_at: datetime


# Мапперы домен -> API DTO
def job_to_response(job) -> AnalysisJobResponse:
    """
    Унифицированный маппер, чтобы не зависеть от конкретной структуры dataclass в роутерах.
    """
    model = getattr(job, "model", None)
    scope = getattr(job, "scope", None)

    model_payload = {
        "name": getattr(model, "name", None) if model else getattr(job, "model_name", None),
        "version": getattr(model, "version", None) if model else getattr(job, "model_version", None),
    }

    if hasattr(scope, "__dict__"):
        date_range = getattr(scope, "date_range", None)
        scope_payload = {
            "source_ids": list(getattr(scope, "source_ids", []) or []),
            "date_range": {
                "start": getattr(date_range, "start", None).isoformat() if date_range and getattr(date_range, "start", None) else None,
                "end": getattr(date_range, "end", None).isoformat() if date_range and getattr(date_range, "end", None) else None,
            },
            "query": getattr(scope, "query", None),
        }
    else:
        scope_payload = scope if isinstance(scope, dict) else {}

    return AnalysisJobResponse(
        id=int(job.id),
        account_id=int(job.account_id),
        status=str(job.status),
        created_at=job.created_at,
        finished_at=getattr(job, "finished_at", None),
        model=model_payload,
        scope=scope_payload,
        params=getattr(job, "params", {}) or {},
        error=getattr(job, "error", None),
    )