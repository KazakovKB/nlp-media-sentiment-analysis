from dataclasses import dataclass
from datetime import datetime

@dataclass
class Account:
    id: int
    name: str
    is_white_label: bool
    created_at: datetime