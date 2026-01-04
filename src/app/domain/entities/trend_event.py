from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class TrendEvent:
    job_id: int
    ts: datetime
    kind: str
    value: float
    baseline: float
    z: float