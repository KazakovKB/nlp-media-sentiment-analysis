from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os
import dotenv

dotenv.load_dotenv()

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    # Задаем naming convention для стабильных diff'ов и корректного drop/alter
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

def make_engine(dsn: str):
    return create_engine(dsn, pool_pre_ping=True)

def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine = make_engine(DATABASE_URL)
SessionLocal = make_session_factory(engine)