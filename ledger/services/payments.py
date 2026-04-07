"""Payment service — record member payments."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from ledger.models import Member, Payment
from ledger.schemas import EditPaymentCommand, PaymentPreview, PaymentRecord, RecordPaymentCommand


def preview_payment(session: Session, cmd: RecordPaymentCommand) -> PaymentPreview:
    member = _get_member(session, cmd.member_id)
    return PaymentPreview(
        member_id=member.id,
        display_name=member.display_name,
        payment_date=cmd.payment_date,
        rub_paid=cmd.rub_paid,
        fx_rate=Decimal("1.0"),
        fx_available=True,
        rub_credit=cmd.rub_paid,
    )


def record_payment(session: Session, cmd: RecordPaymentCommand) -> Payment:
    member = _get_member(session, cmd.member_id)
    preview = preview_payment(session, cmd)

    payment = Payment(
        member_id=member.id,
        payment_date=cmd.payment_date,
        rub_paid=cmd.rub_paid,
        fx_locked=Decimal("1.0"),
        usd_credit=preview.rub_credit or Decimal(0),
        note=cmd.note,
        created_at=datetime.now(timezone.utc),
    )
    session.add(payment)
    return payment


def list_payments(session: Session, limit: int = 100) -> list[PaymentRecord]:
    payments = (
        session.query(Payment, Member)
        .join(Member)
        .order_by(Payment.payment_date.desc(), Payment.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        PaymentRecord(
            id=p.id,
            member_id=p.member_id,
            display_name=m.display_name,
            payment_date=p.payment_date,
            rub_paid=p.rub_paid,
            fx_locked=p.fx_locked,
            rub_credit=p.usd_credit,
            note=p.note,
            created_at=p.created_at,
        )
        for p, m in payments
    ]


def edit_payment(session: Session, cmd: EditPaymentCommand) -> Payment:
    payment = session.get(Payment, cmd.payment_id)
    if not payment:
        raise ValueError(f"Payment with id {cmd.payment_id} not found")

    payment.rub_paid = cmd.rub_paid
    payment.usd_credit = cmd.rub_paid
    payment.fx_locked = Decimal("1.0")
    payment.note = cmd.note
    payment.edited_at = datetime.now(timezone.utc)
    payment.edit_reason = cmd.edit_reason
    return payment


def _get_member(session: Session, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if not member:
        raise ValueError(f"Member with id {member_id} not found")
    return member
