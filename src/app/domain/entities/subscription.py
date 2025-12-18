from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from src.app.domain.enums import PlanType, SubscriptionStatus

@dataclass
class Subscription:
    account_id: int
    plan: PlanType
    status: SubscriptionStatus
    started_at: datetime
    ends_at: Optional[datetime]