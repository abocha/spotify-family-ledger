from datetime import date
from decimal import Decimal

from ledger.schemas import RecordPaymentCommand
from ledger.services.balances import get_member_balance
from ledger.services.payments import preview_payment, record_payment


def test_preview_payment(session, active_member):
    cmd = RecordPaymentCommand(
        member_id=active_member.id,
        payment_date=date(2026, 1, 1),
        rub_paid=Decimal("1000"),
    )
    preview = preview_payment(session, cmd)
    assert preview.fx_available is True
    assert preview.rub_credit == Decimal("1000")


def test_record_payment_success(session, active_member):
    cmd = RecordPaymentCommand(
        member_id=active_member.id,
        payment_date=date(2026, 1, 1),
        rub_paid=Decimal("1000"),
    )
    record_payment(session, cmd)
    session.commit()

    bal = get_member_balance(session, active_member.id)
    assert bal.payment_credits_rub == Decimal("1000")
    assert bal.balance_rub == Decimal("1000")


def test_record_payment_credits_balance(session, active_member):
    cmd = RecordPaymentCommand(
        member_id=active_member.id,
        payment_date=date(2026, 2, 1),
        rub_paid=Decimal("500"),
    )
    record_payment(session, cmd)
    session.commit()

    bal = get_member_balance(session, active_member.id)
    assert bal.balance_rub == Decimal("500")
