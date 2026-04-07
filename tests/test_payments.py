from datetime import date
from decimal import Decimal
import pytest

from ledger.schemas import RecordPaymentCommand
from ledger.services.fx import add_fx_rate
from ledger.services.payments import preview_payment, record_payment
from ledger.services.balances import get_member_balance

def test_preview_payment_no_fx(session, active_member):
    cmd = RecordPaymentCommand(member_id=active_member.id, payment_date=date(2026, 1, 1), rub_paid=Decimal("1000"))
    preview = preview_payment(session, cmd)
    assert preview.fx_available is False
    assert preview.usd_credit is None

def test_record_payment_success(session, active_member):
    add_fx_rate(session, date(2026, 1, 1), 100.0)
    session.commit()
    
    cmd = RecordPaymentCommand(member_id=active_member.id, payment_date=date(2026, 1, 1), rub_paid=Decimal("1000"))
    record_payment(session, cmd)
    session.commit()
    
    bal = get_member_balance(session, active_member.id)
    assert bal.payment_credits_usd == Decimal("10.000000")
    assert bal.balance_usd == Decimal("-10.000000") # Started at 0, paid 10 -> -10
