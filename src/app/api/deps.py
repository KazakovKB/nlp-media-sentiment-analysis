from dataclasses import dataclass
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.app.infra.db import SessionLocal
from src.app.infra.models import UserORM, AccountUserORM
from src.app.core.security import decode_token

from src.app.infra.uow import SqlAlchemyUoW
from src.app.domain.contracts.uow import UoW

from src.app.services.auth_service import AuthService
from src.app.services.sources_service import SourcesService
from src.app.services.analysis_service import AnalysisService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@dataclass(frozen=True)
class UserContext:
    """Контекст аутентифицированного пользователя."""
    user_id: int
    account_id: int
    role: str


def get_db() -> Generator[Session, None, None]:
    """
    Dependency для SQLAlchemy-сессии.
    Сессия создаётся на запрос и гарантированно закрывается.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_ctx(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> UserContext:
    """
    Возвращает контекст текущего пользователя:
    - декодирует JWT,
    - проверяет, что пользователь активен,
    - проверяет привязку к аккаунту.
    """
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или просроченный токен.",
        )

    user = (
        db.query(UserORM)
        .filter(UserORM.id == user_id, UserORM.is_active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или неактивен.",
        )

    au = (
        db.query(AccountUserORM)
        .filter(AccountUserORM.user_id == user.id)
        .first()
    )
    if not au:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У пользователя нет привязанного аккаунта.",
        )

    return UserContext(
        user_id=int(user.id),
        account_id=int(au.account_id),
        role=str(au.role),
    )


def get_uow(db: Session = Depends(get_db)) -> UoW:
    """
    Dependency для Unit of Work.
    """
    return SqlAlchemyUoW(db)


# Service factories (composition root)
def get_auth_service(uow: UoW = Depends(get_uow)) -> AuthService:
    return AuthService(uow)

def get_sources_service(uow: UoW = Depends(get_uow)) -> SourcesService:
    return SourcesService(uow)

def get_analysis_service(uow: UoW = Depends(get_uow)) -> AnalysisService:
    return AnalysisService(uow)