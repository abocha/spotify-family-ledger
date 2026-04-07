"""Balance calculation service.

RUB-first sign convention:
    balance_rub = payment_rub_total + legacy_opening_rub - posted_charges_rub

Legacy snapshots are stored as negative debt balances.
Positive balance means the member has credit.
Negative balance means the member owes the owner.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from ledger.models import LegacySnapshot, Member, Payment, PostedCharge
from ledger.schemas import MemberBalance
from ledger.services.fx import get_latest_fx_rate


def get_member_balances(session: Session) -> list[MemberBalance]:
    members = session.query(Member).order_by(Member.display_name).all()
    return [get_member_balance(session, m.id) for m in members]


def get_member_balance(session: Session, member_id: int) -> MemberBalance:
    member = session.get(Member, member_id)
    if not member:
        raise ValueError(f"Member with id {member_id} not found")

    legacy = (
        session.query(LegacySnapshot)
        .filter(LegacySnapshot.member_id == member_id)
        .order_by(LegacySnapshot.snapshot_date.desc())
        .first()
    )
    legacy_opening_rub = legacy.opening_balance_rub if legacy else Decimal(0)

    payment_credits_rub = (
        session.query(func.sum(Payment.rub_paid))
        .filter(Payment.member_id == member_id)
        .scalar()
        or Decimal(0)
    )

    posted_charges_rub = (
        session.query(func.sum(PostedCharge.charge_rub))
        .filter(PostedCharge.member_id == member_id)
        .scalar()
        or Decimal(0)
    )

    balance_rub = payment_credits_rub + legacy_opening_rub - posted_charges_rub

    fx_obj = get_latest_fx_rate(session)
    balance_usd = None
    if fx_obj:
        balance_usd = (balance_rub / fx_obj.usd_rub).quantize(Decimal("0.01"))

    return MemberBalance(
        member_id=member.id,
        display_name=member.display_name,
        is_active=member.is_active_on(date.today()),
        counted_in_denominator=member.counted_in_denominator,
        billable_after_cutover=member.billable_after_cutover,
        legacy_opening_rub=legacy_opening_rub,
        posted_charges_rub=posted_charges_rub,
        payment_credits_rub=payment_credits_rub,
        balance_rub=balance_rub,
        balance_usd_equivalent=balance_usd,
    )


def get_total_owed_rub(session: Session) -> Decimal:
    balances = get_member_balances(session)
    # Return total amount members owe (negative balances)
    return sum((-b.balance_rub for b in balances if b.balance_rub < 0), Decimal(0))
