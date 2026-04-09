from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ledger.models import Base, Member


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:", echo=False)


@pytest.fixture
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine, tables):
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def active_member(session):
    member = Member(
        display_name="Test Active",
        active_from=date(2026, 4, 20),
        counted_in_denominator=True,
        billable_after_cutover=True,
    )
    session.add(member)
    session.commit()
    return member


@pytest.fixture
def second_active_member(session):
    member = Member(
        display_name="Second Active",
        active_from=date(2026, 4, 20),
        counted_in_denominator=True,
        billable_after_cutover=True,
    )
    session.add(member)
    session.commit()
    return member
