from datetime import date
from decimal import Decimal

from ledger.models import BillingCycle, MemberCharge, OpeningBalance
from ledger.services.integrity import check_integrity


def test_integrity_is_clean_for_consistent_cycle(session, active_member):
    session.add(
        OpeningBalance(
            member_id=active_member.id,
            snapshot_date=date(2026, 4, 20),
            opening_balance_rub=Decimal("-100.00"),
            source_note="Cutover",
        )
    )
    cycle = BillingCycle(
        cycle_date=date(2026, 4, 20),
        status="posted",
        subscription_usd=Decimal("8.00"),
        fx_locked=Decimal("100.00"),
        subscription_rub=Decimal("800.00"),
        counted_active=1,
        billed_active=1,
        total_billed_rub=Decimal("800.00"),
        owner_subsidy_rub=Decimal("0.00"),
        posted_at=date(2026, 4, 20),
    )
    session.add(cycle)
    session.flush()
    session.add(
        MemberCharge(
            cycle_id=cycle.id,
            member_id=active_member.id,
            charge_date=cycle.cycle_date,
            active_count=1,
            subscription_usd=Decimal("8.00"),
            charge_usd=Decimal("8.00"),
            fx_locked=Decimal("100.00"),
            charge_rub=Decimal("800.00"),
        )
    )
    session.commit()

    assert check_integrity(session) == []


def test_integrity_flags_cycle_total_mismatch(session, active_member):
    cycle = BillingCycle(
        cycle_date=date(2026, 4, 20),
        status="posted",
        subscription_usd=Decimal("8.00"),
        fx_locked=Decimal("100.00"),
        subscription_rub=Decimal("800.00"),
        counted_active=1,
        billed_active=1,
        total_billed_rub=Decimal("700.00"),
        owner_subsidy_rub=Decimal("100.00"),
        posted_at=date(2026, 4, 20),
    )
    session.add(cycle)
    session.flush()
    session.add(
        MemberCharge(
            cycle_id=cycle.id,
            member_id=active_member.id,
            charge_date=cycle.cycle_date,
            active_count=1,
            subscription_usd=Decimal("8.00"),
            charge_usd=Decimal("8.00"),
            fx_locked=Decimal("100.00"),
            charge_rub=Decimal("800.00"),
        )
    )
    session.commit()

    issues = check_integrity(session)
    assert any("total_billed_rub" in issue.message for issue in issues)
