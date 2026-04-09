"""Read-model queries for the public ledger."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Numeric, Text, func, literal, select, union_all
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


def list_member_options(session: Session) -> list[tuple[int, str]]:
    rows = (
        session.query(Member.id, Member.display_name)
        .order_by(Member.display_name)
        .all()
    )
    return [(member_id, display_name) for member_id, display_name in rows]


def get_member_statement(
    session: Session,
    member_id: int,
    *,
    exact_through_date: date | None = None,
) -> MemberStatement:
    member_row = (
        session.query(Member.id, Member.display_name)
        .filter(Member.id == member_id)
        .one_or_none()
    )
    if member_row is None:
        raise ValueError(f"Member with id {member_id} not found.")

    opening_select = select(
        OpeningBalance.snapshot_date.label("entry_date"),
        literal("opening_balance").label("entry_type"),
        OpeningBalance.opening_balance_rub.label("amount_rub"),
        literal(None, type_=Numeric(12, 6)).label("fx_locked"),
        literal(None, type_=Numeric(10, 6)).label("subscription_usd"),
        OpeningBalance.source_note.label("note"),
        literal(0).label("sort_rank"),
        OpeningBalance.id.label("entry_id"),
    ).where(OpeningBalance.member_id == member_id)

    charges_select = select(
        MemberCharge.charge_date.label("entry_date"),
        literal("charge").label("entry_type"),
        (-MemberCharge.charge_rub).label("amount_rub"),
        MemberCharge.fx_locked.label("fx_locked"),
        MemberCharge.subscription_usd.label("subscription_usd"),
        literal(None, type_=Text()).label("note"),
        literal(1).label("sort_rank"),
        MemberCharge.id.label("entry_id"),
    ).where(MemberCharge.member_id == member_id)

    payments_select = select(
        Payment.payment_date.label("entry_date"),
        literal("payment").label("entry_type"),
        Payment.rub_paid.label("amount_rub"),
        literal(None, type_=Numeric(12, 6)).label("fx_locked"),
        literal(None, type_=Numeric(10, 6)).label("subscription_usd"),
        Payment.note.label("note"),
        literal(3).label("sort_rank"),
        Payment.id.label("entry_id"),
    ).where(Payment.member_id == member_id)

    adjustments_select = select(
        Adjustment.effective_date.label("entry_date"),
        literal("adjustment").label("entry_type"),
        Adjustment.amount_rub.label("amount_rub"),
        literal(None, type_=Numeric(12, 6)).label("fx_locked"),
        literal(None, type_=Numeric(10, 6)).label("subscription_usd"),
        Adjustment.reason.label("note"),
        literal(2).label("sort_rank"),
        Adjustment.id.label("entry_id"),
    ).where(Adjustment.member_id == member_id)

    entries_query = union_all(
        opening_select,
        charges_select,
        payments_select,
        adjustments_select,
    ).subquery()

    rows = session.execute(
        select(
            entries_query.c.entry_date,
            entries_query.c.entry_type,
            entries_query.c.amount_rub,
            entries_query.c.fx_locked,
            entries_query.c.subscription_usd,
            entries_query.c.note,
        ).order_by(
            entries_query.c.entry_date,
            entries_query.c.sort_rank,
            entries_query.c.entry_id,
        )
    ).all()

    running_balance = ZERO
    last_payment_date: date | None = None
    statement_entries: list[StatementEntry] = []
    for entry_date, entry_type, amount_rub, fx_locked, subscription_usd, note in rows:
        amount = amount_rub or ZERO
        running_balance += amount
        if entry_type == "charge":
            description = f"Monthly charge for {entry_date.strftime('%B %Y')}"
        elif entry_type == "payment":
            description = "Payment received"
            last_payment_date = entry_date
        elif entry_type == "adjustment":
            description = "Adjustment"
        else:
            description = "Opening balance"

        statement_entries.append(
            StatementEntry(
                entry_date=entry_date,
                entry_type=entry_type,
                description=description,
                amount_rub=amount,
                balance_rub=running_balance,
                fx_locked=fx_locked,
                subscription_usd=subscription_usd,
                note=note,
            )
        )

    if exact_through_date is None:
        exact_through_date = get_ledger_status(session).exact_through_date

    return MemberStatement(
        member_id=member_row.id,
        display_name=member_row.display_name,
        current_balance_rub=running_balance,
        last_payment_date=last_payment_date,
        exact_through_date=exact_through_date,
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

