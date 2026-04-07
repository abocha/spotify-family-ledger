from datetime import date
from decimal import Decimal

import pytest

from ledger.models import ChargeCycle
from ledger.services.cycles import ensure_forecast_cycles, post_cycle
from ledger.services.fx import add_fx_rate


def test_ensure_forecast(session):
    cycles = ensure_forecast_cycles(session)
    assert len(cycles) == 7  # Start + 6 months
    assert all(c.status == "forecast" for c in cycles)


def test_post_cycle_fails_no_fx(session, active_member):
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    session.commit()

    with pytest.raises(ValueError, match="No FX rate exists"):
        post_cycle(session, c.id)


def test_post_cycle_success(session, active_member):
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 5, 20), 90.0)
    session.commit()

    charges = post_cycle(session, c.id)
    session.commit()
    assert len(charges) == 1
    assert charges[0].charge_usd == Decimal("8.00")
    assert charges[0].member_id == active_member.id

    session.refresh(c)
    assert c.status == "posted"
    assert c.fx_locked == Decimal("90.0")


def test_post_cycle_excludes_inactive(session, active_member, inactive_member):
    c = ChargeCycle(cycle_date=date(2026, 6, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 6, 20), 100.0)
    session.commit()

    charges = post_cycle(session, c.id)
    assert len(charges) == 1
    assert charges[0].member_id == active_member.id  # only active member charged


def test_post_cycle_fails_double_post(session, active_member):
    c = ChargeCycle(cycle_date=date(2026, 7, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 7, 20), 100.0)
    session.commit()

    post_cycle(session, c.id)  # First post
    session.commit()

    with pytest.raises(ValueError, match="already posted"):
        post_cycle(session, c.id)  # Second post should fail
