from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass(frozen=True)
class DateRange:
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.end <= self.start:
            raise ValueError("Неверный диапазон дат.")

@dataclass(frozen=True)
class SentimentProbs:
    p_neg: float
    p_neu: float
    p_pos: float

    def __post_init__(self):
        s = self.p_neg + self.p_neu + self.p_pos
        if not (0.99 <= s <= 1.01):
            raise ValueError("Probabilities must sum to 1")

@dataclass(frozen=True)
class AnalysisScope:
    source_ids: List[int]
    date_range: DateRange
    query: Optional[str] = None

@dataclass(frozen=True)
class PlanCapabilities:
    max_sources: int
    max_documents_per_month: int
    allow_exports: bool
    allow_trends: bool
    allow_white_label: bool


@dataclass(frozen=True)
class AuthCredentials:
    user_id: int
    password_hash: str