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


ZERO = Decimal("0")
USD_QUANT = Decimal("0.01")


def _member_balance_rows(session: Session, member_id: int | None = None):
    latest_legacy_date_sq = (
        session.query(
            LegacySnapshot.member_id.label("member_id"),
            func.max(LegacySnapshot.snapshot_date).label("latest_snapshot_date"),
        )
        .group_by(LegacySnapshot.member_id)
        .subquery()
    )

    legacy_sq = (
        session.query(
            LegacySnapshot.member_id.label("member_id"),
            LegacySnapshot.opening_balance_rub.label("legacy_opening_rub"),
        )
        .join(
            latest_legacy_date_sq,
            (LegacySnapshot.member_id == latest_legacy_date_sq.c.member_id)
            & (LegacySnapshot.snapshot_date == latest_legacy_date_sq.c.latest_snapshot_date),
        )
        .subquery()
    )

    payments_sq = (
        session.query(
            Payment.member_id.label("member_id"),
            func.sum(Payment.rub_paid).label("payment_credits_rub"),
        )
        .group_by(Payment.member_id)
        .subquery()
    )

    charges_sq = (
        session.query(
            PostedCharge.member_id.label("member_id"),
            func.sum(PostedCharge.charge_rub).label("posted_charges_rub"),
        )
        .group_by(PostedCharge.member_id)
        .subquery()
    )

    query = (
        session.query(
            Member,
            legacy_sq.c.legacy_opening_rub,
            payments_sq.c.payment_credits_rub,
            charges_sq.c.posted_charges_rub,
        )
        .outerjoin(legacy_sq, legacy_sq.c.member_id == Member.id)
        .outerjoin(payments_sq, payments_sq.c.member_id == Member.id)
        .outerjoin(charges_sq, charges_sq.c.member_id == Member.id)
        .order_by(Member.display_name)
    )

    if member_id is not None:
        query = query.filter(Member.id == member_id)

    return query.all()


def _to_member_balance(
    member: Member,
    legacy_opening_rub: Decimal | None,
    payment_credits_rub: Decimal | None,
    posted_charges_rub: Decimal | None,
    fx_rate: Decimal | None,
    today: date,
) -> MemberBalance:
    legacy_value = legacy_opening_rub or ZERO
    payment_value = payment_credits_rub or ZERO
    charges_value = posted_charges_rub or ZERO

    balance_rub = payment_value + legacy_value - charges_value

    balance_usd = None
    if fx_rate:
        balance_usd = (balance_rub / fx_rate).quantize(USD_QUANT)

    return MemberBalance(
        member_id=member.id,
        display_name=member.display_name,
        is_active=member.is_active_on(today),
        counted_in_denominator=member.counted_in_denominator,
        billable_after_cutover=member.billable_after_cutover,
        legacy_opening_rub=legacy_value,
        posted_charges_rub=charges_value,
        payment_credits_rub=payment_value,
        balance_rub=balance_rub,
        balance_usd_equivalent=balance_usd,
    )


def get_member_balances(session: Session) -> list[MemberBalance]:
    rows = _member_balance_rows(session)
    fx_obj = get_latest_fx_rate(session)
    fx_rate = fx_obj.usd_rub if fx_obj else None
    today = date.today()

    return [
        _to_member_balance(
            member=member,
            legacy_opening_rub=legacy_opening_rub,
            payment_credits_rub=payment_credits_rub,
            posted_charges_rub=posted_charges_rub,
            fx_rate=fx_rate,
            today=today,
        )
        for member, legacy_opening_rub, payment_credits_rub, posted_charges_rub in rows
    ]


def get_member_balance(session: Session, member_id: int) -> MemberBalance:
    rows = _member_balance_rows(session, member_id=member_id)
    if not rows:
        raise ValueError(f"Member with id {member_id} not found")

    member, legacy_opening_rub, payment_credits_rub, posted_charges_rub = rows[0]
    fx_obj = get_latest_fx_rate(session)
    fx_rate = fx_obj.usd_rub if fx_obj else None

    return _to_member_balance(
        member=member,
        legacy_opening_rub=legacy_opening_rub,
        payment_credits_rub=payment_credits_rub,
        posted_charges_rub=posted_charges_rub,
        fx_rate=fx_rate,
        today=date.today(),
    )


def get_total_owed_rub(session: Session) -> Decimal:
    balances = get_member_balances(session)
    return sum((-b.balance_rub for b in balances if b.balance_rub < 0), ZERO)