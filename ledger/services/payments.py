"""Payment service — preview and record member payments."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from ledger.models import Member, Payment
from ledger.schemas import PaymentPreview, PaymentRecord, RecordPaymentCommand
from ledger.services.fx import get_fx_rate


def preview_payment(session: Session, cmd: RecordPaymentCommand) -> PaymentPreview:
    """Look up FX and compute USD credit without writing anything."""
    member = _get_member(session, cmd.member_id)
    fx = get_fx_rate(session, cmd.payment_date)

    usd_credit: Decimal | None = None
    if fx is not None:
        usd_credit = (cmd.rub_paid / fx.usd_rub).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

    return PaymentPreview(
        member_id=member.id,
        display_name=member.display_name,
        payment_date=cmd.payment_date,
        rub_paid=cmd.rub_paid,
        fx_rate=fx.usd_rub if fx else None,
        fx_available=fx is not None,
        usd_credit=usd_credit,
    )


def record_payment(session: Session, cmd: RecordPaymentCommand) -> Payment:
    """Record an immutable payment row with locked FX and USD credit.

    Raises ValueError if:
    - Member not found
    - No FX rate exists for the payment date
    """
    member = _get_member(session, cmd.member_id)
    fx = get_fx_rate(session, cmd.payment_date)
    if fx is None:
        raise ValueError(
            f"No FX rate exists for {cmd.payment_date}. "
            "Add the rate before recording this payment."
        )

    usd_credit = (cmd.rub_paid / fx.usd_rub).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )

    payment = Payment(
        member_id=member.id,
        payment_date=cmd.payment_date,
        rub_paid=cmd.rub_paid,
        fx_locked=fx.usd_rub,
        usd_credit=usd_credit,
        note=cmd.note,
    )
    session.add(payment)
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
