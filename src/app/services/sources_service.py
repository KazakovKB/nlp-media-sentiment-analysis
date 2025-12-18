from typing import Any, Optional
from src.app.domain.contracts.uow import UoW


class SourcesService:
    def __init__(self, uow: UoW):
        self.uow = uow

    def list_sources(self, account_id: int):
        return self.uow.sources.list_by_account(account_id)

    def get_source(self, account_id: int, source_id: int):
        return self.uow.sources.get_by_id(account_id, source_id)

    def source_stats(self, account_id: int, source_id: int) -> Optional[dict[str, Any]]:
        s = self.uow.sources.get_by_id(account_id, source_id)
        if not s:
            return None

        st = self.uow.documents.stats_by_source(account_id, source_id)
        return {"source_id": source_id, **st}