from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

@dataclass
class OverviewReport:
    job_id: int
    total_documents: int
    sentiment_share: Dict[str, float]
    metrics: Dict[str, Any]
    created_at: datetime