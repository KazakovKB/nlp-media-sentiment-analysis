from dataclasses import dataclass
from typing import Generator, Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse, Response

from src.app.infra.db import SessionLocal
from src.app.infra.uow import SqlAlchemyUoW
from src.app.domain.contracts.uow import UoW
from src.app.core.security import decode_token


@dataclass(frozen=True)
class UserContext:
    user_id: int
    account_id: int
    role: str


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_uow(db: Session = Depends(get_db)) -> UoW:
    return SqlAlchemyUoW(db)

def _redirect_to_login(request: Request, reason: str = "required") -> Response:
    url = f"/login?reason={reason}"

    if request.headers.get("HX-Request") == "true":
        resp = Response(status_code=401)
        resp.headers["HX-Redirect"] = url
        return resp

    return RedirectResponse(url=url, status_code=303)

def get_current_user_ctx_ui(request: Request) -> UserContext | Response:
    token: Optional[str] = request.session.get("access_token")
    if not token:
        return _redirect_to_login(request, "required")

    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
        account_id = int(payload.get("account_id") or payload.get("extra", {}).get("account_id") or 0)
    except Exception:
        return _redirect_to_login(request, "invalid")

    if account_id <= 0:
        return _redirect_to_login(request, "invalid")

    role = str(request.session.get("role") or "member")
    return UserContext(user_id=user_id, account_id=account_id, role=role)