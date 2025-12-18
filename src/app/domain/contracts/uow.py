from typing import Protocol
from src.app.domain.contracts.repositories import (
    UserRepo, AccountRepo, SubscriptionRepo,
    SourceRepo, DocumentRepo, AnalysisJobRepo,
    OverviewRepo, TrendRepo, AccountSourceRepo
)

class UoW(Protocol):
    users: UserRepo
    accounts: AccountRepo
    subscriptions: SubscriptionRepo
    sources: SourceRepo
    documents: DocumentRepo
    analysis: AnalysisJobRepo
    overview: OverviewRepo
    trend: TrendRepo
    account_sources: AccountSourceRepo

    def commit(self) -> None: ...
    def rollback(self) -> None: ...