from datetime import date
from decimal import Decimal

import pytest

from ledger.models import ChargeCycle
from ledger.services.cycles import post_cycle
from ledger.services.fx import add_fx_rate, ensure_fx_rate, get_fx_rate, get_latest_fx_rate
import ledger.services.fx as fx_service


def test_add_and_get_fx_rate(session):
    d = date(2026, 4, 20)
    add_fx_rate(session, d, 95.5)
    session.commit()

    fx = get_fx_rate(session, d)
    assert fx is not None
    assert fx.usd_rub == Decimal("95.5")


def test_add_duplicate_fails(session):
    d = date(2026, 4, 20)
    add_fx_rate(session, d, 95.5)
    session.commit()

    with pytest.raises(ValueError, match="already exists"):
        add_fx_rate(session, d, 96.0)


def test_get_latest(session):
    add_fx_rate(session, date(2026, 4, 20), 95.0)
    add_fx_rate(session, date(2026, 4, 22), 96.0)
    session.commit()

    latest = get_latest_fx_rate(session)
    assert latest is not None
    assert latest.usd_rub == Decimal("96.0")
    assert latest.rate_date == date(2026, 4, 22)


def test_ensure_fx_rate_flushes_new_rate_for_same_session(session, monkeypatch):
    target_date = date(2026, 5, 20)

    def fake_fetch(rate_date):
        assert rate_date == target_date
        return Decimal("101.25")

    monkeypatch.setattr(fx_service, "fetch_historical_fx_rate", fake_fetch)

    fx = ensure_fx_rate(session, target_date)
    queried = get_fx_rate(session, target_date)

    assert fx.rate_date == target_date
    assert queried is not None
    assert queried.usd_rub == Decimal("101.25")


def test_post_cycle_uses_fetched_rate_in_same_session(session, active_member, monkeypatch):
    target_date = date(2026, 5, 20)
    cycle = ChargeCycle(cycle_date=target_date, subscription_usd=Decimal("8.00"))
    session.add(cycle)
    session.commit()

    monkeypatch.setattr(fx_service, "fetch_historical_fx_rate", lambda _: Decimal("99.50"))

    post_cycle(session, cycle.id)
    session.commit()

    assert cycle.fx_locked == Decimal("99.50")
    assert cycle.subscription_rub == Decimal("796.00")
