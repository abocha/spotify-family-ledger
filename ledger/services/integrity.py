"""Integrity checks to guard public balance views."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session

from ledger.models import BillingCycle, MemberCharge, OpeningBalance
from ledger.schemas import IntegrityIssue


ZERO = Decimal("0.00")


def check_integrity(session: Session) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []

    duplicate_opening_members = (
        session.query(OpeningBalance.member_id)
        .group_by(OpeningBalance.member_id)
        .having(func.count(OpeningBalance.id) > 1)
        .count()
    )
    if duplicate_opening_members:
        issues.append(
            IntegrityIssue(
                severity="error",
                message=(
                    f"Found {duplicate_opening_members} member(s) with more than one opening balance. "
                    "Opening balances must be a single frozen cutover import."
                ),
            )
        )

    for cycle in session.query(BillingCycle).all():
        charges = [charge for charge in cycle.charges]
        total_billed = sum((charge.charge_rub for charge in charges), ZERO).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        if total_billed != cycle.total_billed_rub:
            issues.append(
                IntegrityIssue(
                    severity="error",
                    message=(
                        f"Cycle {cycle.cycle_date} total_billed_rub is {cycle.total_billed_rub} "
                        f"but charges sum to {total_billed}."
                    ),
                )
            )
        if len(charges) != cycle.billed_active:
            issues.append(
                IntegrityIssue(
                    severity="error",
                    message=(
                        f"Cycle {cycle.cycle_date} billed_active is {cycle.billed_active} "
                        f"but there are {len(charges)} member charge rows."
                    ),
                )
            )

    duplicate_cycle_members = (
        session.query(MemberCharge.cycle_id, MemberCharge.member_id)
        .group_by(MemberCharge.cycle_id, MemberCharge.member_id)
        .having(func.count(MemberCharge.id) > 1)
        .count()
    )
    if duplicate_cycle_members:
        issues.append(
            IntegrityIssue(
                severity="error",
                message=(
                    f"Found {duplicate_cycle_members} duplicate cycle/member charge pair(s)."
                ),
            )
        )

    return issues
