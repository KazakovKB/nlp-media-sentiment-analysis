import os
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from src.app.main import app as fastapi_app
from src.app.infra.db import SessionLocal

from src.app.infra.models import SourceORM, DocumentORM, AccountSourceORM


@pytest.fixture(scope="session", autouse=True)
def _test_env():
    """
    Глобально выставляем env для тестов один раз на сессию.
    """
    os.environ.setdefault("SENTIMENT_ENABLED", "0")
    os.environ.setdefault("SENTIMENT_FAIL_OPEN", "1")


@pytest.fixture(scope="session")
def app():
    # FastAPI app (app = FastAPI(...)) у тебя называется `app` в src/app/main.py
    return fastapi_app


@pytest.fixture
async def client(app):
    """
    HTTP client поверх ASGI приложения (без реального поднятия сервера).
    Важно: для httpx>=0.28 нужно использовать ASGITransport.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def db_session() -> Session:
    """
    Отдельная DB-сессия для прямого вызова сервисов (run_job).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def random_email():
    def _make(prefix: str = "user") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}@test.local"

    return _make


@pytest.fixture
def auth_headers():
    def _make(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
async def register_user(client, random_email):
    """
    Регистрирует пользователя через реальный API /api/auth/register
    и возвращает (token, account_id).
    """
    async def _call(
        email: str | None = None,
        password: str = "pass1234",
        account_name: str = "Test Account",
    ):
        if email is None:
            email = random_email("u")

        r = await client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "account_name": account_name},
        )
        assert r.status_code in (200, 201), r.text
        token = r.json()["access_token"]

        # достаём account_id из БД по user_id из токена
        from src.app.core.security import decode_token
        from src.app.infra.models import AccountUserORM

        payload = decode_token(token)
        user_id = int(payload["sub"])

        db = SessionLocal()
        try:
            au = db.query(AccountUserORM).filter(AccountUserORM.user_id == user_id).first()
            assert au is not None, "AccountUser not found for created user"
            account_id = int(au.account_id)
        finally:
            db.close()

        return token, account_id

    return _call


@pytest.fixture
async def seed_source_and_docs(register_user):
    """
    Создаёт:
    - пользователя (через API)
    - глобальный SourceORM
    - ACL-связку AccountSourceORM
    - документы DocumentORM

    Возвращает: (token, source_id, account_id)
    """
    token, account_id = await register_user()

    db = SessionLocal()
    try:
        # GLOBAL SOURCE
        src = SourceORM(
            name=f"test-source-{uuid.uuid4().hex[:6]}",
            source_type="test",
            ingestion_mode="manual",
            config={},
        )
        db.add(src)
        db.commit()
        db.refresh(src)

        # ACCOUNT / SOURCE ACL
        link = AccountSourceORM(
            account_id=account_id,
            source_id=src.id,
            is_enabled=True,
        )
        db.add(link)
        db.commit()

        # DOCUMENTS
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        docs = [
            DocumentORM(
                source_id=src.id,
                published_at=now - timedelta(days=i + 1),
                title=f"doc {i}",
                text=f"some text {i}",
            )
            for i in range(5)
        ]
        db.add_all(docs)
        db.commit()

        return token, int(src.id), int(account_id)

    finally:
        db.close()