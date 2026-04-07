from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ledger.config import settings


def _make_engine() -> Engine:
    url = settings.TURSO_URL
    if settings.TURSO_KEY:
        url = f"{url}?authToken={settings.TURSO_KEY}"
        
    if url.startswith("libsql://") or url.startswith("https://") or url.startswith("http://"):
        url = url.replace("libsql://", "sqlite+libsql://").replace("https://", "sqlite+libsql://https://").replace("http://", "sqlite+libsql://http://")
    
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
    )
    # Enable WAL mode and foreign keys for every new connection
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
