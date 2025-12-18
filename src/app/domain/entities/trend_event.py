from dataclasses import dataclass
from datetime import datetime
from src.app.domain.enums import SentimentLabel

@dataclass(frozen=True)
class TrendEvent:
    job_id: int
    start: datetime
    end: datetime
    label: SentimentLabel
    score: float