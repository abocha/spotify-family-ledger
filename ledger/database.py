from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ledger.config import settings


def _make_engine() -> Engine:
    raw_url = settings.TURSO_URL.strip()
    token = settings.TURSO_KEY.strip()

    # Remote Turso / libSQL
    if raw_url.startswith("libsql://"):
        connect_args = {}
        if token:
            connect_args["auth_token"] = token

        return create_engine(
            f"sqlite+{raw_url}?secure=true",
            connect_args=connect_args,
        )

    # Local SQLite
    if raw_url.startswith("sqlite:///"):
        engine = create_engine(
            raw_url,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _set_pragmas(dbapi_conn, _connection_record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            dbapi_conn.execute("PRAGMA journal_mode=WAL")

        return engine

    raise ValueError(
        "TURSO_URL must start with either 'sqlite:///' for local dev "
        "or 'libsql://' for a remote Turso database."
    )


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine() -> Engine:
    return engine