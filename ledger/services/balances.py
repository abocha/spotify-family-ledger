"""Balance calculation service.

Bank-style sign convention:
    balance_usd = payment_credits_usd - legacy_opening_usd - posted_charges_usd

Positive balance means the member has credit.
Negative balance means the member owes the owner.
RUB equivalent is display-only and always uses the latest FX rate.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from ledger.models import LegacySnapshot, Member, Payment, PostedCharge
from ledger.schemas import MemberBalance
from ledger.services.fx import get_latest_fx_rate


def get_member_balances(session: Session) -> list[MemberBalance]:
    """Return current balances for all members, sorted by display_name."""
    members = session.query(Member).order_by(Member.display_name).all()
    latest_fx = get_latest_fx_rate(session)
    latest_fx_rate = latest_fx.usd_rub if latest_fx else None

    results = []
    for member in members:
        balance = _compute_balance(session, member, latest_fx_rate)
        results.append(balance)
    return results


def get_member_balance(session: Session, member_id: int) -> MemberBalance:
    """Return balance for a single member. Raises ValueError if not found."""
    member = session.get(Member, member_id)
    if member is None:
        raise ValueError(f"Member {member_id} not found")
    latest_fx = get_latest_fx_rate(session)
    latest_fx_rate = latest_fx.usd_rub if latest_fx else None
    return _compute_balance(session, member, latest_fx_rate)


def _compute_balance(
    session: Session,
    member: Member,
    latest_fx_rate: Decimal | None,
) -> MemberBalance:
    snapshot = session.query(LegacySnapshot).filter_by(member_id=member.id).first()
    legacy_opening_usd = snapshot.opening_balance_usd if snapshot else Decimal("0")

    charges_result = (
        session.query(func.coalesce(func.sum(PostedCharge.charge_usd), 0))
        .filter(PostedCharge.member_id == member.id)
        .scalar()
    )
    posted_charges_usd = Decimal(str(charges_result))

    payments_result = (
        session.query(func.coalesce(func.sum(Payment.usd_credit), 0))
        .filter(Payment.member_id == member.id)
        .scalar()
    )
    payment_credits_usd = Decimal(str(payments_result))

    balance_usd = payment_credits_usd - legacy_opening_usd - posted_charges_usd

    balance_rub_equivalent: Decimal | None = None
    if latest_fx_rate is not None:
        balance_rub_equivalent = (balance_usd * Decimal(str(latest_fx_rate))).quantize(
            Decimal("0.01")
        )

    today = date.today()

    return MemberBalance(
        member_id=member.id,
        display_name=member.display_name,
        is_active=member.is_active_on(today),
        counted_in_denominator=member.counted_in_denominator,
        billable_after_cutover=member.billable_after_cutover,
        legacy_opening_usd=legacy_opening_usd,
        posted_charges_usd=posted_charges_usd,
        payment_credits_usd=payment_credits_usd,
        balance_usd=balance_usd,
        balance_rub_equivalent=balance_rub_equivalent,
    )


def get_total_owed_usd(session: Session) -> Decimal:
    """Sum of all negative member balances, expressed as a positive amount owed to the owner."""
    balances = get_member_balances(session)
    return sum(
        (-b.balance_usd for b in balances if b.balance_usd < 0),
        Decimal("0"),
    )
