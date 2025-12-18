from dataclasses import dataclass
from datetime import datetime
from src.app.domain.enums import SentimentLabel
from src.app.domain.value_objects import SentimentProbs, ModelRef

@dataclass(frozen=True)
class Prediction:
    document_id: int
    label: SentimentLabel
    probs: SentimentProbs
    model: ModelRef
    created_at: datetime