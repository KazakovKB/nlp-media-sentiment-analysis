from dataclasses import dataclass
from datetime import datetime
from src.app.domain.enums import JobStatus

@dataclass
class IngestionJob:
    id: int
    source_id: int
    status: JobStatus
    created_at: datetime