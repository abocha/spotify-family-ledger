from datetime import date
from decimal import Decimal


from ledger.schemas import RecordPaymentCommand
from ledger.services.balances import get_member_balance
from ledger.services.payments import preview_payment, record_payment


def test_preview_payment_no_fx(session, active_member):
    cmd = RecordPaymentCommand(
        member_id=active_member.id,
        payment_date=date(2026, 1, 1),
        rub_paid=Decimal("1000"),
        usd_rub_effective=Decimal("100"),
    )
    preview = preview_payment(session, cmd)
    assert preview.fx_available is True
    assert preview.usd_credit == Decimal("10.000000")


def test_record_payment_success(session, active_member):
    cmd = RecordPaymentCommand(
        member_id=active_member.id,
        payment_date=date(2026, 1, 1),
        rub_paid=Decimal("1000"),
        usd_rub_effective=Decimal("100"),
    )
    record_payment(session, cmd)
    session.commit()

    bal = get_member_balance(session, active_member.id)
    assert bal.payment_credits_usd == Decimal("10.000000")
    assert bal.balance_usd == Decimal("-10.000000")


def test_record_payment_fails_no_fx_is_not_required_anymore(session, active_member):
    cmd = RecordPaymentCommand(
        member_id=active_member.id,
        payment_date=date(2026, 2, 1),
        rub_paid=Decimal("1000"),
        usd_rub_effective=Decimal("100"),
    )
    payment = record_payment(session, cmd)
    session.commit()
    assert payment.usd_credit == Decimal("10.000000")
