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
        opening_balance_rub=Decimal("10.00"),
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
    )
    p = record_payment(session, cmd)
    session.add(p)
    session.commit()

    p.usd_credit = Decimal("1100.0000")  # Corrupt credit field
    session.commit()

    issues = check_integrity(session)
    assert any("payment(s) whose RUB credit" in i.message for i in issues)


def test_integrity_flags_mismatched_charge_math(session, active_member):
    c = ChargeCycle(cycle_date=date(2026, 5, 20), subscription_usd=Decimal("8.00"))
    session.add(c)
    add_fx_rate(session, date(2026, 5, 20), 100.0)
    session.commit()
    post_cycle(session, c.id)
    session.commit()

    charge = session.query(PostedCharge).first()
    assert charge is not None
    # No charge_rub_equivalent anymore, renamed to charge_rub
    charge.charge_rub = Decimal("999.0000")
    session.commit()

    issues = check_integrity(session)
    # The error message in integrity.py says "whose RUB amount is inconsistent"
    assert any("posted charge(s) whose RUB amount" in i.message for i in issues)
