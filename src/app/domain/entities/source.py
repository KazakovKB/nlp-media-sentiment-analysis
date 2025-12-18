from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class Source:
    id: int
    name: str
    source_type: str
    ingestion_mode: str
    config: dict[str, Any]
    created_at: datetime