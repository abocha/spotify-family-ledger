"""Payment service — preview and record member payments."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from ledger.models import Member, Payment
from ledger.schemas import EditPaymentCommand, PaymentPreview, PaymentRecord, RecordPaymentCommand


def preview_payment(session: Session, cmd: RecordPaymentCommand) -> PaymentPreview:
    """Preview a payment using an operator-locked effective FX."""
    member = _get_member(session, cmd.member_id)
    usd_credit: Decimal | None = (cmd.rub_paid / cmd.usd_rub_effective).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    return PaymentPreview(
        member_id=member.id,
        display_name=member.display_name,
        payment_date=cmd.payment_date,
        rub_paid=cmd.rub_paid,
        fx_rate=cmd.usd_rub_effective,
        fx_available=True,
        usd_credit=usd_credit,
    )


def record_payment(session: Session, cmd: RecordPaymentCommand) -> Payment:
    """Record an immutable payment row with operator-locked effective FX."""
    member = _get_member(session, cmd.member_id)
    usd_credit = (cmd.rub_paid / cmd.usd_rub_effective).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )

    payment = Payment(
        member_id=member.id,
        payment_date=cmd.payment_date,
        rub_paid=cmd.rub_paid,
        fx_locked=cmd.usd_rub_effective,
        usd_credit=usd_credit,
        note=cmd.note,
    )
    session.add(payment)
    return payment


def edit_payment(session: Session, cmd: EditPaymentCommand) -> Payment:
    payment = session.get(Payment, cmd.payment_id)
    if payment is None:
        raise ValueError(f"Payment {cmd.payment_id} not found")
    payment.rub_paid = cmd.rub_paid
    payment.fx_locked = cmd.usd_rub_effective
    payment.usd_credit = (cmd.rub_paid / cmd.usd_rub_effective).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    payment.note = cmd.note
    payment.edited_at = datetime.now(timezone.utc)
    payment.edit_reason = cmd.edit_reason
    return payment


def list_payments(
    session: Session,
    member_id: int | None = None,
    limit: int = 200,
) -> list[PaymentRecord]:
    """List payments, newest first. Optionally filter by member."""
    q = session.query(Payment, Member).join(Member, Payment.member_id == Member.id)
    if member_id is not None:
        q = q.filter(Payment.member_id == member_id)
    rows = q.order_by(Payment.payment_date.desc()).limit(limit).all()

    return [
        PaymentRecord(
            id=p.id,
            member_id=p.member_id,
            display_name=m.display_name,
            payment_date=p.payment_date,
            rub_paid=p.rub_paid,
            fx_locked=p.fx_locked,
            usd_credit=p.usd_credit,
            note=p.note,
            created_at=p.created_at,
        )
        for p, m in rows
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_member(session: Session, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise ValueError(f"Member {member_id} not found")
    return member
