from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from src.app.domain.value_objects import AnalysisScope
from src.app.domain.enums import JobStatus

@dataclass
class AnalysisJob:
    id: int
    account_id: int
    scope: AnalysisScope
    status: JobStatus
    created_at: datetime
    error: Optional[str]
    finished_at: Optional[datetime] = None