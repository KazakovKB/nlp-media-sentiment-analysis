from sqlalchemy.orm import Session

from src.app.infra.repositories import (
    SqlUserRepo, SqlAccountRepo, SqlSubscriptionRepo,
    SqlSourceRepo, SqlDocumentRepo, SqlAnalysisJobRepo,
    SqlOverviewRepo, SqlTrendRepo, SqlAccountSourceRepo
)

class SqlAlchemyUoW:
    def __init__(self, db: Session):
        self.db = db

        self.users = SqlUserRepo(db)
        self.accounts = SqlAccountRepo(db)
        self.subscriptions = SqlSubscriptionRepo(db)
        self.sources = SqlSourceRepo(db)
        self.documents = SqlDocumentRepo(db)
        self.analysis = SqlAnalysisJobRepo(db)
        self.overview = SqlOverviewRepo(db)
        self.trend = SqlTrendRepo(db)
        self.account_sources = SqlAccountSourceRepo(db)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()