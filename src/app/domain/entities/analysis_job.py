from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any
from src.app.domain.value_objects import AnalysisScope, ModelRef
from src.app.domain.enums import JobStatus

@dataclass
class AnalysisJob:
    id: int
    account_id: int
    scope: AnalysisScope
    model: ModelRef
    status: JobStatus
    created_at: datetime
    params: dict[str, Any]
    error: Optional[str]
    finished_at: Optional[datetime] = None