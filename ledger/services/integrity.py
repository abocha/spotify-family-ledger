"""Integrity checks to surface errors to the owner."""

from sqlalchemy.orm import Session
from sqlalchemy import func

from ledger.models import ChargeCycle, Payment, PostedCharge
from ledger.schemas import IntegrityIssue


def check_integrity(session: Session) -> list[IntegrityIssue]:
    issues = []

    # Check 1: Payments without FX (should be prevented by DB constraints, but good to check)
    payments_no_fx = session.query(Payment).filter(Payment.fx_locked.is_(None)).count()
    if payments_no_fx > 0:
        issues.append(
            IntegrityIssue(
                severity="error",
                message=f"Found {payments_no_fx} payments with missing FX rates.",
            )
        )

    # Check 2: Posted cycles without FX (should also be prevented)
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
        
    # Check 3: Active denominator = 0 on posted cycles
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

    # Add more checks as needed:
    # - duplicate posted cycle (prevented by UniqueConstraint)
    # - duplicate member charge within cycle (prevented by UniqueConstraint)
    # - billable member missing charge
    # - inactive member charged

    return issues
