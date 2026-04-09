"""Read-model queries for the public ledger."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from ledger.models import Adjustment, BillingCycle, Member, MemberCharge, OpeningBalance, Payment, ReconciliationRun
from ledger.schemas import LedgerStatus, MemberBalance, MemberStatement, PaymentRecord, ReconciliationRunRecord, StatementEntry


ZERO = Decimal("0")


def get_ledger_status(session: Session) -> LedgerStatus:
    latest = session.query(ReconciliationRun).order_by(ReconciliationRun.started_at.desc()).first()
    last_cycle_date = session.query(func.max(BillingCycle.cycle_date)).scalar()

    if latest is None:
        return LedgerStatus(
            state="healthy",
            exact_through_date=last_cycle_date,
            last_attempted_cycle_date=None,
            failure_cycle_date=None,
            failure_message=None,
            cycles_posted_count=0,
            alert_sent=False,
            last_completed_at=None,
            last_run_trigger=None,
        )

    state = "healthy" if latest.status == "success" else ("running" if latest.status == "running" else "stale")
    return LedgerStatus(
        state=state,
        exact_through_date=latest.last_successful_cycle_date or last_cycle_date,
        last_attempted_cycle_date=latest.to_cycle_date,
        failure_cycle_date=latest.error_cycle_date,
        failure_message=latest.error_message,
        cycles_posted_count=latest.cycles_posted_count,
        alert_sent=latest.alert_sent,
        last_completed_at=latest.completed_at,
        last_run_trigger=latest.trigger,
    )


def list_member_balances(session: Session) -> list[MemberBalance]:
    members = session.query(Member).order_by(Member.display_name).all()
    if not members:
        return []

    opening_balances = {
        opening.member_id: opening
        for opening in session.query(OpeningBalance).all()
    }
    charge_totals = {
        member_id: total or ZERO
        for member_id, total in (
            session.query(MemberCharge.member_id, func.sum(MemberCharge.charge_rub))
            .group_by(MemberCharge.member_id)
            .all()
        )
    }
    payment_totals = {
        member_id: total or ZERO
        for member_id, total in (
            session.query(Payment.member_id, func.sum(Payment.rub_paid))
            .group_by(Payment.member_id)
            .all()
        )
    }
    adjustment_totals = {
        member_id: total or ZERO
        for member_id, total in (
            session.query(Adjustment.member_id, func.sum(Adjustment.amount_rub))
            .group_by(Adjustment.member_id)
            .all()
        )
    }
    last_payment_dates = {
        member_id: payment_date
        for member_id, payment_date in (
            session.query(Payment.member_id, func.max(Payment.payment_date))
            .group_by(Payment.member_id)
            .all()
        )
    }
    last_charge_dates = {
        member_id: charge_date
        for member_id, charge_date in (
            session.query(MemberCharge.member_id, func.max(MemberCharge.charge_date))
            .group_by(MemberCharge.member_id)
            .all()
        )
    }

    today = date.today()
    balances: list[MemberBalance] = []
    for member in members:
        opening = opening_balances.get(member.id)
        opening_value = opening.opening_balance_rub if opening is not None else ZERO
        charge_value = charge_totals.get(member.id, ZERO)
        payment_value = payment_totals.get(member.id, ZERO)
        adjustment_value = adjustment_totals.get(member.id, ZERO)
        balance = opening_value + payment_value + adjustment_value - charge_value
        balances.append(
            MemberBalance(
                member_id=member.id,
                display_name=member.display_name,
                is_active=member.is_active_on(today),
                counted_in_denominator=member.counted_in_denominator,
                billable_after_cutover=member.billable_after_cutover,
                opening_balance_rub=opening_value,
                charges_rub=charge_value,
                payments_rub=payment_value,
                adjustments_rub=adjustment_value,
                balance_rub=balance,
                last_payment_date=last_payment_dates.get(member.id),
                last_charge_date=last_charge_dates.get(member.id),
            )
        )

    return balances


def get_member_statement(session: Session, member_id: int) -> MemberStatement:
    member = session.get(Member, member_id)
    if member is None:
        raise ValueError(f"Member with id {member_id} not found.")

    status = get_ledger_status(session)
    entries: list[tuple[date, str, Decimal, str, Decimal | None, Decimal | None, str | None]] = []

    opening = (
        session.query(OpeningBalance)
        .filter(OpeningBalance.member_id == member_id)
        .one_or_none()
    )
    if opening is not None:
        entries.append(
            (
                opening.snapshot_date,
                "opening_balance",
                opening.opening_balance_rub,
                "Opening balance",
                None,
                None,
                opening.source_note,
            )
        )

    for charge in (
        session.query(MemberCharge)
        .filter(MemberCharge.member_id == member_id)
        .order_by(MemberCharge.charge_date, MemberCharge.id)
        .all()
    ):
        entries.append(
            (
                charge.charge_date,
                "charge",
                -charge.charge_rub,
                f"Monthly charge for {charge.charge_date.strftime('%B %Y')}",
                charge.fx_locked,
                charge.subscription_usd,
                None,
            )
        )

    for payment in (
        session.query(Payment)
        .filter(Payment.member_id == member_id)
        .order_by(Payment.payment_date, Payment.id)
        .all()
    ):
        entries.append(
            (
                payment.payment_date,
                "payment",
                payment.rub_paid,
                "Payment received",
                None,
                None,
                payment.note,
            )
        )

    for adjustment in (
        session.query(Adjustment)
        .filter(Adjustment.member_id == member_id)
        .order_by(Adjustment.effective_date, Adjustment.id)
        .all()
    ):
        entries.append(
            (
                adjustment.effective_date,
                "adjustment",
                adjustment.amount_rub,
                "Adjustment",
                None,
                None,
                adjustment.reason,
            )
        )

    entries.sort(key=lambda value: (value[0], _entry_sort_rank(value[1])))

    running_balance = ZERO
    statement_entries: list[StatementEntry] = []
    for entry_date, entry_type, amount_rub, description, fx_locked, subscription_usd, note in entries:
        running_balance += amount_rub
        statement_entries.append(
            StatementEntry(
                entry_date=entry_date,
                entry_type=entry_type,
                description=description,
                amount_rub=amount_rub,
                balance_rub=running_balance,
                fx_locked=fx_locked,
                subscription_usd=subscription_usd,
                note=note,
            )
        )

    last_payment_date = (
        session.query(func.max(Payment.payment_date))
        .filter(Payment.member_id == member_id)
        .scalar()
    )
    return MemberStatement(
        member_id=member.id,
        display_name=member.display_name,
        current_balance_rub=running_balance,
        last_payment_date=last_payment_date,
        exact_through_date=status.exact_through_date,
        entries=statement_entries,
    )


def list_recent_payments(session: Session, limit: int = 10) -> list[PaymentRecord]:
    rows = (
        session.query(Payment, Member)
        .join(Member)
        .order_by(Payment.payment_date.desc(), Payment.id.desc())
        .limit(limit)
        .all()
    )
    return [
        PaymentRecord(
            id=payment.id,
            member_id=payment.member_id,
            display_name=member.display_name,
            payment_date=payment.payment_date,
            rub_paid=payment.rub_paid,
            note=payment.note,
            created_at=payment.created_at,
        )
        for payment, member in rows
    ]


def list_admin_reconciliation_history(session: Session, limit: int = 20) -> list[ReconciliationRunRecord]:
    rows = (
        session.query(ReconciliationRun)
        .order_by(ReconciliationRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [
        ReconciliationRunRecord(
            id=row.id,
            trigger=row.trigger,
            status=row.status,
            started_at=row.started_at,
            completed_at=row.completed_at,
            from_cycle_date=row.from_cycle_date,
            to_cycle_date=row.to_cycle_date,
            last_successful_cycle_date=row.last_successful_cycle_date,
            error_cycle_date=row.error_cycle_date,
            error_message=row.error_message,
            cycles_posted_count=row.cycles_posted_count,
            alert_sent=row.alert_sent,
            alert_error=row.alert_error,
        )
        for row in rows
    ]


def _entry_sort_rank(entry_type: str) -> int:
    order = {
        "opening_balance": 0,
        "charge": 1,
        "adjustment": 2,
        "payment": 3,
    }
    return order.get(entry_type, 99)
