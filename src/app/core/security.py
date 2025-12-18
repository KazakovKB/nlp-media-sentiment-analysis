from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import jwt, JWTError
from passlib.context import CryptContext

from src.app.core.settings import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, extra: Dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {"sub": subject, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    if extra:
        payload.update(extra)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        return payload
    except JWTError as e:
        raise ValueError("Invalid token") from e