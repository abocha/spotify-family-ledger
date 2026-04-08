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


def test_preview_uses_estimate_when_exact_fx_missing(session, active_member):
    """Verify that estimated values are populated when exact FX is missing but latest stored FX exists."""
    # Create a prior FX rate (becomes the "latest")
    add_fx_rate(session, date(2026, 4, 15), 95.25)
    session.commit()

    # Create a future cycle with no exact-date FX
    c = ChargeCycle(cycle_date=date(2026, 6, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    session.commit()

    # Preview the future cycle (no exact FX for 2026-06-20)
    preview = preview_cycle(session, c.id)

    # Exact FX should be missing
    assert preview.fx_rate is None
    assert preview.subscription_rub is None

    # But estimated values should be present
    assert preview.uses_estimated_fx is True
    assert preview.estimated_fx_rate == Decimal("95.25")
    assert preview.estimated_subscription_rub == Decimal("762.00")  # 8 * 95.25
    assert preview.estimated_rub_per_slot == Decimal("762.00")  # 762 / 1
    assert preview.estimated_total_billed_rub == Decimal("762.00")
    assert preview.estimated_owner_subsidy_rub == Decimal("0.00")

    # Verify member estimated charges
    member_charge = preview.member_charges[0]
    assert member_charge.charge_rub is None
    assert member_charge.estimated_charge_rub == Decimal("762.00")


def test_preview_does_not_use_estimate_when_exact_fx_exists(session, active_member):
    """Verify that estimates are not used when exact-date FX is available."""
    # Create a prior FX rate
    add_fx_rate(session, date(2026, 4, 15), 95.25)
    session.commit()

    # Create a cycle and lock its exact FX
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 5, 20), 100.0)
    session.commit()

    # Preview the cycle (exact FX exists)
    preview = preview_cycle(session, c.id)

    # Exact FX should be available
    assert preview.fx_rate == Decimal("100.0")
    assert preview.subscription_rub == Decimal("800.00")

    # Estimated fields should be None and flag should be False
    assert preview.uses_estimated_fx is False
    assert preview.estimated_fx_rate is None
    assert preview.estimated_subscription_rub is None
    assert preview.estimated_rub_per_slot is None
    assert preview.estimated_total_billed_rub is None
    assert preview.estimated_owner_subsidy_rub is None

    # Verify member charges
    member_charge = preview.member_charges[0]
    assert member_charge.charge_rub == Decimal("800.00")
    assert member_charge.estimated_charge_rub is None


def test_preview_no_estimates_when_no_latest_fx(session, active_member):
    """Verify that estimates are not used if no latest FX exists at all."""
    # Don't add any FX rates
    
    # Create a cycle
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    session.commit()

    # Preview the cycle
    preview = preview_cycle(session, c.id)

    # Both exact and estimated should be missing
    assert preview.fx_rate is None
    assert preview.uses_estimated_fx is False
    assert preview.estimated_fx_rate is None
    assert preview.estimated_subscription_rub is None
