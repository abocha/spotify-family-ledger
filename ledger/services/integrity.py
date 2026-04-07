"""Integrity checks to surface errors to the owner."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ledger.models import ChargeCycle, Payment, PostedCharge
from ledger.schemas import IntegrityIssue


def _table_exists(session: Session, table_name: str) -> bool:
    try:
        return (
            session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
                {"name": table_name},
            ).scalar()
            is not None
        )
    except OperationalError:
        return False


def check_integrity(session: Session) -> list[IntegrityIssue]:
    issues = []

    if not _table_exists(session, "payments") or not _table_exists(session, "posted_charges"):
        issues.append(
            IntegrityIssue(
                severity="warning",
                message="Ledger tables are not fully initialized yet; some integrity checks were skipped.",
            )
        )
        return issues

    cycles_no_fx = (
        session.query(ChargeCycle)
        .filter(ChargeCycle.status == "posted", ChargeCycle.fx_locked.is_(None))
        .count()
    )
    if cycles_no_fx > 0:
        issues.append(
            IntegrityIssue(
                severity="error",
                message=f"Found {cycles_no_fx} posted cycles with missing FX rates.",
            )
        )

    cycles_zero_den = (
        session.query(ChargeCycle)
        .filter(ChargeCycle.status == "posted", ChargeCycle.counted_active == 0)
        .count()
    )
    if cycles_zero_den > 0:
        issues.append(
            IntegrityIssue(
                severity="error",
                message=f"Found {cycles_zero_den} posted cycles with 0 counted members.",
            )
        )

    bad_payment_math = 0
    for payment in session.query(Payment).all():
        if payment.rub_paid is None or payment.usd_credit is None:
            bad_payment_math += 1
            continue
        # In RUB-first, rub_paid must match usd_credit (which is RUB credit)
        if Decimal(payment.rub_paid).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != Decimal(payment.usd_credit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
            bad_payment_math += 1
    if bad_payment_math:
        issues.append(
            IntegrityIssue(
                severity="error",
                message=f"Found {bad_payment_math} payment(s) whose RUB credit does not match recorded RUB paid.",
            )
        )

    bad_charge_math = 0
    for charge in session.query(PostedCharge).all():
        if charge.charge_rub is None or charge.fx_locked is None or charge.charge_usd is None:
            bad_charge_math += 1
            continue
        # Expected charge_rub is charge_usd * fx_locked (rounded to 2 decimal places as in cycles.py)
        expected = (Decimal(charge.charge_usd) * Decimal(charge.fx_locked)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        if Decimal(charge.charge_rub).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != expected:
            bad_charge_math += 1
    if bad_charge_math:
        issues.append(
            IntegrityIssue(
                severity="error",
                message=f"Found {bad_charge_math} posted charge(s) whose RUB amount is inconsistent with USD reference.",
            )
        )

    edited_payments = session.query(Payment).filter(Payment.edited_at.isnot(None)).count()
    edited_charges = session.query(PostedCharge).filter(PostedCharge.edited_at.isnot(None)).count()
    if edited_payments or edited_charges:
        issues.append(
            IntegrityIssue(
                severity="warning",
                message=(
                    f"Audit trail present: {edited_payments} edited payment(s), "
                    f"{edited_charges} edited charge(s)."
                ),
            )
        )

    return issues
