from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

@dataclass(frozen=True)
class Document:
    id: int
    source_id: int
    published_at: datetime
    title: Optional[str]
    text: str
    url_hash: str
    topic: Optional[str]
    url: str
    meta: dict[str, Any]