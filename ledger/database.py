from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ledger.config import settings


def _make_engine() -> Engine:
    url = f"{settings.TURSO_URL}?authToken={settings.TURSO_KEY}"
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
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager yielding a database session with auto rollback on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine() -> Engine:
    """Return the engine — used by Alembic."""
    return engine
