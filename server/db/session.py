import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://hows_your_day:hows_your_day@localhost:5432/hows_your_day"
)

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


def database_url() -> str:
    return os.environ.get("DATABASE_URL") or _env_file_value("DATABASE_URL") or DEFAULT_DATABASE_URL


def get_engine() -> Engine:
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is None:
        _ENGINE = create_engine(
            database_url(),
            pool_pre_ping=True,
            connect_args=_connect_args(database_url()),
        )
        _SESSION_FACTORY = sessionmaker(
            bind=_ENGINE,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _ENGINE


def _connect_args(url: str) -> dict:
    if url.startswith("postgresql"):
        return {"connect_timeout": 2}
    return {}


def init_db() -> None:
    from db.models import Base

    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    if _SESSION_FACTORY is None:
        get_engine()
    assert _SESSION_FACTORY is not None

    db = _SESSION_FACTORY()
    try:
        yield db
    finally:
        db.close()


def _env_file_value(name: str) -> str | None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip().lstrip("\ufeff") == name:
            cleaned = raw_value.strip().strip('"').strip("'")
            return cleaned or None
    return None
