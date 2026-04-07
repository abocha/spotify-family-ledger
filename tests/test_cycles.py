from datetime import date
from decimal import Decimal

import pytest

from ledger.models import ChargeCycle, Member, PostedCharge
from ledger.services.cycles import edit_posted_charge, ensure_forecast_cycles, post_cycle, preview_cycle
from ledger.services.fx import add_fx_rate
from ledger.schemas import EditChargeCommand


def test_ensure_forecast(session):
    cycles = ensure_forecast_cycles(session)
    assert len(cycles) > 0
    assert all(c.status == "forecast" for c in cycles)
    assert all(c.cycle_date >= date(2026, 4, 20) for c in cycles)


def test_post_cycle_fails_without_fx(session, active_member):
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    session.commit()

    with pytest.raises(ValueError, match="USD/RUB rate"):
        post_cycle(session, c.id)


def test_post_cycle_fails_when_no_counted_members(session):
    member = Member(
        display_name="Billable Only",
        active_from=date(2023, 1, 1),
        counted_in_denominator=False,
        billable_after_cutover=True,
    )
    session.add(member)
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 5, 20), 100.0)
    session.commit()

    with pytest.raises(ValueError, match="no active counted members"):
        preview_cycle(session, c.id)


def test_post_cycle_fails_double_post(session, active_member):
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 5, 20), 100.0)
    session.commit()

    post_cycle(session, c.id)
    session.commit()

    res = post_cycle(session, c.id)
    assert res.status == "posted"


def test_post_cycle_success(session, active_member):
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 5, 20), 100.0)
    session.commit()

    post_cycle(session, c.id)
    session.commit()

    assert c.status == "posted"
    assert c.fx_locked == Decimal("100.0")
    assert c.subscription_rub == Decimal("800.0")

    charge = session.query(PostedCharge).filter_by(member_id=active_member.id).first()
    assert charge is not None
    assert charge.charge_rub == Decimal("800.0")
    assert charge.fx_locked == Decimal("100.0")


def test_edit_posted_charge_recomputes_cycle_totals(session, active_member):
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 5, 20), 100.0)
    session.commit()

    post_cycle(session, c.id)
    session.commit()

    charge = session.query(PostedCharge).filter_by(member_id=active_member.id).one()
    edit_posted_charge(
        session,
        EditChargeCommand(
            charge_id=charge.id,
            charge_rub=Decimal("750.00"),
            edit_reason="Corrected manual split",
        ),
    )
    session.commit()

    assert c.total_billed_rub == Decimal("750.00")
    assert c.owner_subsidy_rub == Decimal("50.00")
