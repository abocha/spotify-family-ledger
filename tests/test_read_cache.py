from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest

import ledger.read_cache as read_cache
from ledger.models import ChargeCycle, Member
from ledger.services.fx import add_fx_rate


@pytest.fixture(autouse=True)
def clear_preview_cache():
    read_cache.load_next_cycle_preview_data.clear()
    yield
    read_cache.load_next_cycle_preview_data.clear()


@pytest.fixture
def bind_read_cache_session(session, monkeypatch):
    @contextmanager
    def fake_get_db():
        yield session

    monkeypatch.setattr(read_cache, "get_db", fake_get_db)


def test_load_next_cycle_preview_returns_error_for_invalid_preview(session, bind_read_cache_session):
    session.add(
        Member(
            display_name="Billable Only",
            active_from=date(2023, 1, 1),
            counted_in_denominator=False,
            billable_after_cutover=True,
        )
    )
    session.add(ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00")))
    session.commit()

    preview = read_cache.load_next_cycle_preview_data()

    assert preview["state"] == "error"
    assert "no active counted members" in preview["message"]


def test_load_next_cycle_preview_preserves_zero_owner_subsidy_for_exact_fx(
    session,
    active_member,
    bind_read_cache_session,
):
    session.add(ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00")))
    add_fx_rate(session, date(2026, 5, 20), 100.0)
    session.commit()

    preview = read_cache.load_next_cycle_preview_data()

    assert preview["state"] == "ok"
    assert preview["uses_estimated_fx"] is False
    assert preview["owner_subsidy_rub"] == 0.0
    assert preview["member_charges"][0]["charge_rub"] == 800.0


def test_load_next_cycle_preview_preserves_zero_owner_subsidy_for_estimated_fx(
    session,
    active_member,
    bind_read_cache_session,
):
    add_fx_rate(session, date(2026, 4, 15), 95.25)
    session.add(ChargeCycle(cycle_date=date(2026, 6, 20), subscription_usd=Decimal("8.00")))
    session.commit()

    preview = read_cache.load_next_cycle_preview_data()

    assert preview["state"] == "ok"
    assert preview["uses_estimated_fx"] is True
    assert preview["estimated_owner_subsidy_rub"] == 0.0
    assert preview["member_charges"][0]["estimated_charge_rub"] == 762.0
