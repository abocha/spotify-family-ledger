from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ledger.config import settings


def _normalize_database_url(raw_url: str, auth_token: str) -> str:
    url = raw_url
    if auth_token:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}authToken={auth_token}"

    if url.startswith("libsql://"):
        return url.replace("libsql://", "sqlite+libsql://", 1)
    if url.startswith("https://"):
        return url.replace("https://", "sqlite+libsql://https://", 1)
    if url.startswith("http://"):
        return url.replace("http://", "sqlite+libsql://http://", 1)
    return url


def _make_engine() -> Engine:
    url = _normalize_database_url(settings.TURSO_URL, settings.TURSO_KEY)
    is_local_sqlite = url.startswith("sqlite://") and "+libsql" not in url

    engine_kwargs = {}
    if is_local_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(url, **engine_kwargs)

    if is_local_sqlite:
        # Enable local SQLite integrity defaults for each new connection.
        @event.listens_for(engine, "connect")
        def _set_pragmas(dbapi_conn, _connection_record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            dbapi_conn.execute("PRAGMA journal_mode=WAL")

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Yield a database session.

    IMPORTANT:
    - Pages/services should explicitly call `session.commit()` for writes.
    - This context manager should *only* roll back on exceptions.

    This avoids fragile interactions with Streamlit's rerun semantics.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine() -> Engine:
    """Return the engine — used by Alembic."""
    return engine
