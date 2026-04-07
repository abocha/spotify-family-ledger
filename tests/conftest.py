import pytest
from datetime import date

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
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback() # wipe data for next test
        session.close()

@pytest.fixture
def active_member(session):
    m = Member(
        display_name="Test Active",
        active_from=date(2023, 1, 1),
        counted_in_denominator=True,
        billable_after_cutover=True
    )
    session.add(m)
    session.commit()
    return m

@pytest.fixture
def inactive_member(session):
    m = Member(
        display_name="Test Inactive",
        active_from=date(2023, 1, 1),
        active_to=date(2024, 1, 1),
        counted_in_denominator=False,
        billable_after_cutover=False
    )
    session.add(m)
    session.commit()
    return m
