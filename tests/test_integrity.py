from datetime import date
from decimal import Decimal

from ledger.models import ChargeCycle, LegacySnapshot, PostedCharge
from ledger.schemas import RecordPaymentCommand
from ledger.services.cycles import post_cycle
from ledger.services.fx import add_fx_rate
from ledger.services.integrity import check_integrity
from ledger.services.payments import record_payment


def test_integrity_clean(session, active_member):
    snap = LegacySnapshot(
        member_id=active_member.id,
        snapshot_date=date(2026, 4, 1),
        opening_balance_usd=Decimal("10.00"),
    )
    session.add(snap)
    session.commit()

    issues = check_integrity(session)
    assert issues == []


def test_integrity_flags_mismatched_payment_math(session, active_member):
    cmd = RecordPaymentCommand(
        member_id=active_member.id,
        payment_date=date(2026, 1, 1),
        rub_paid=Decimal("1000"),
        usd_rub_effective=Decimal("100"),
    )
    p = record_payment(session, cmd)
    session.add(p)
    session.commit()

    p.usd_credit = Decimal("11.000000")
    session.commit()

    issues = check_integrity(session)
    assert any("payment(s) whose USD credit" in i.message for i in issues)


def test_integrity_flags_mismatched_charge_math(session, active_member):
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 5, 20), 100.0)
    session.commit()
    post_cycle(session, c.id)
    session.commit()

    charge = session.query(PostedCharge).first()
    assert charge is not None
    charge.charge_rub_equivalent = Decimal("999.0000")
    session.commit()

    issues = check_integrity(session)
    assert any("posted charge(s) whose RUB equivalent" in i.message for i in issues)
