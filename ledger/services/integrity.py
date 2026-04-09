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

    cycle_charge_totals = (
        session.query(
            MemberCharge.cycle_id.label("cycle_id"),
            func.sum(MemberCharge.charge_rub).label("total_billed"),
            func.count(MemberCharge.id).label("charge_count"),
        )
        .group_by(MemberCharge.cycle_id)
        .subquery()
    )

    cycle_rows = (
        session.query(
            BillingCycle.cycle_date,
            BillingCycle.total_billed_rub,
            BillingCycle.billed_active,
            cycle_charge_totals.c.total_billed,
            cycle_charge_totals.c.charge_count,
        )
        .outerjoin(cycle_charge_totals, cycle_charge_totals.c.cycle_id == BillingCycle.id)
        .all()
    )
    for cycle_date, cycle_total, billed_active, charge_total, charge_count in cycle_rows:
        total_billed = (charge_total or ZERO).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        if total_billed != cycle_total:
            issues.append(
                IntegrityIssue(
                    severity="error",
                    message=(
                        f"Cycle {cycle_date} total_billed_rub is {cycle_total} "
                        f"but charges sum to {total_billed}."
                    ),
                )
            )
        if (charge_count or 0) != billed_active:
            issues.append(
                IntegrityIssue(
                    severity="error",
                    message=(
                        f"Cycle {cycle_date} billed_active is {billed_active} "
                        f"but there are {(charge_count or 0)} member charge rows."
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
