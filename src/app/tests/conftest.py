import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.app.main import app as fastapi_app
from src.app.api.deps import get_db

from src.app.infra.models import SourceORM, DocumentORM, AccountSourceORM
from src.app.core.security import decode_token
from src.app.infra.models import AccountUserORM


@pytest.fixture(scope="session", autouse=True)
def _test_env():
    os.environ["SENTIMENT_ENABLED"] = "0"
    os.environ["SENTIMENT_FAIL_OPEN"] = "1"


@pytest.fixture(scope="session")
def engine():
    test_db_url = os.getenv("DATABASE_URL_TEST")
    assert test_db_url, "Set DATABASE_URL_TEST env var"
    return create_engine(test_db_url, future=True)


@pytest.fixture(scope="session")
def session_testing(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


@pytest.fixture(scope="session")
def app():
    return fastapi_app


@pytest.fixture
def db_session(engine, session_testing):
    connection = engine.connect()
    transaction = connection.begin()

    session = session_testing(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
async def client(app, db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()

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
async def register_user(client, db_session, random_email):
    """
    Регистрирует пользователя через API и возвращает (token, account_id).
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

        payload = decode_token(token)
        user_id = int(payload["sub"])

        au = (
            db_session.query(AccountUserORM)
            .filter(AccountUserORM.user_id == user_id)
            .first()
        )
        assert au is not None, "AccountUser not found for created user"
        return token, int(au.account_id)

    return _call

@pytest.fixture
async def seed_source_and_docs(db_session, register_user):
    """
    Создает:
    - пользователя
    - SourceORM
    - AccountSourceORM (доступ аккаунта к источнику)
    - документы DocumentORM
    """
    token, account_id = await register_user()

    src = SourceORM(
        name=f"test-source-{uuid.uuid4().hex[:6]}",
        source_type="test",
        ingestion_mode="manual",
        config={},
    )
    db_session.add(src)
    db_session.commit()
    db_session.refresh(src)

    link = AccountSourceORM(
        account_id=account_id,
        source_id=src.id,
        is_enabled=True,
    )
    db_session.add(link)
    db_session.commit()

    now = datetime(2015, 12, 31, 12, 0, 0, tzinfo=timezone.utc)
    docs = []
    for i in range(5):
        url = f"https://example.com/{src.id}/{i}"
        url_hash = uuid.uuid5(uuid.NAMESPACE_URL, url).hex

        docs.append(
            DocumentORM(
                source_id=src.id,
                published_at=now - timedelta(days=i + 1),
                title=f"doc {i}",
                text=f"some text {i}",
                url=url,
                url_hash=url_hash,
            )
        )

    db_session.add_all(docs)
    db_session.commit()

    return token, int(src.id), int(account_id), now