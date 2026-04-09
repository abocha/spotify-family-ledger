"""Payment and adjustment write service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ledger.models import Adjustment, Member, Payment
from ledger.schemas import CreateAdjustmentCommand, RecordPaymentCommand


def record_payment(session: Session, cmd: RecordPaymentCommand) -> Payment:
    member = session.get(Member, cmd.member_id)
    if member is None:
        raise ValueError(f"Member with id {cmd.member_id} not found.")

    payment = Payment(
        member_id=member.id,
        payment_date=cmd.payment_date,
        rub_paid=cmd.rub_paid,
        note=cmd.note,
    )
    session.add(payment)
    session.flush()
    return payment


def create_adjustment(session: Session, cmd: CreateAdjustmentCommand) -> Adjustment:
    member = session.get(Member, cmd.member_id)
    if member is None:
        raise ValueError(f"Member with id {cmd.member_id} not found.")

    adjustment = Adjustment(
        member_id=member.id,
        effective_date=cmd.effective_date,
        amount_rub=cmd.amount_rub,
        reason=cmd.reason,
        related_cycle_id=cmd.related_cycle_id,
    )
    session.add(adjustment)
    session.flush()
    return adjustment
