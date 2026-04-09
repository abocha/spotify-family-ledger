"""Wake-up reconciliation engine."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from ledger import __version__
from ledger.config import settings
from ledger.models import BillingCycle, JobLock, Member, MemberCharge, ReconciliationRun
from ledger.schemas import ReconciliationOutcome
from ledger.services.fx import get_or_fetch_fx_rate
from ledger.services.notifications import NotificationError, send_telegram_alert


JOB_LOCK_NAME = "reconcile_ledger"
ZERO = Decimal("0.00")


def reconcile_ledger(
    session: Session,
    *,
    today: date | None = None,
    trigger: str = "startup",
) -> ReconciliationOutcome:
    if today is None:
        today = date.today()

    owner_id = str(uuid4())
    if not _acquire_job_lock(session, owner_id):
        latest_cycle_date = session.query(func.max(BillingCycle.cycle_date)).scalar()
        return ReconciliationOutcome(
            state="running",
            exact_through_date=latest_cycle_date,
            last_attempted_cycle_date=None,
            failure_cycle_date=None,
            failure_message="Reconciliation is already running in another session.",
            cycles_posted_count=0,
            alert_sent=False,
        )

    last_successful = session.query(func.max(BillingCycle.cycle_date)).scalar()
    failure_cycle_date: date | None = None
    failure_message: str | None = None
    last_attempted_cycle_date: date | None = None
    alert_sent = False

    try:
        cycle_dates = _missing_cycle_dates(session, today)
        if not cycle_dates:
            return ReconciliationOutcome(
                state="healthy",
                exact_through_date=last_successful,
                last_attempted_cycle_date=None,
                failure_cycle_date=None,
                failure_message=None,
                cycles_posted_count=0,
                alert_sent=False,
            )

        run = ReconciliationRun(
            trigger=trigger,
            status="running",
            started_at=_utcnow(),
            from_cycle_date=cycle_dates[0],
            to_cycle_date=cycle_dates[-1],
            last_successful_cycle_date=last_successful,
            app_version=__version__,
        )
        session.add(run)
        session.commit()

        cycles_posted_count = 0

        for cycle_date in cycle_dates:
            last_attempted_cycle_date = cycle_date
            try:
                _post_cycle(session, cycle_date, run.id)
            except Exception as exc:
                session.rollback()
                failure_cycle_date = cycle_date
                failure_message = str(exc)
                break

            cycles_posted_count += 1
            last_successful = cycle_date
            run.cycles_posted_count = cycles_posted_count
            run.last_successful_cycle_date = last_successful
            session.commit()

        run.completed_at = _utcnow()
        if failure_cycle_date is None:
            run.status = "success"
            run.last_successful_cycle_date = last_successful
            session.commit()
            return ReconciliationOutcome(
                state="healthy",
                exact_through_date=last_successful,
                last_attempted_cycle_date=last_attempted_cycle_date,
                failure_cycle_date=None,
                failure_message=None,
                cycles_posted_count=cycles_posted_count,
                alert_sent=False,
            )

        run.status = "failed"
        run.error_cycle_date = failure_cycle_date
        run.error_message = failure_message
        run.last_successful_cycle_date = last_successful
        try:
            alert_sent = _notify_failure(run, failure_cycle_date, failure_message)
            run.alert_sent = alert_sent
            run.alert_error = None if alert_sent else "Telegram notification was not delivered."
        except NotificationError as exc:
            run.alert_sent = False
            run.alert_error = str(exc)
        session.commit()
        return ReconciliationOutcome(
            state="stale",
            exact_through_date=last_successful,
            last_attempted_cycle_date=last_attempted_cycle_date,
            failure_cycle_date=failure_cycle_date,
            failure_message=failure_message,
            cycles_posted_count=cycles_posted_count,
            alert_sent=run.alert_sent,
        )
    finally:
        _release_job_lock(session, owner_id)


def _missing_cycle_dates(session: Session, today: date) -> list[date]:
    existing = {cycle_date for (cycle_date,) in session.query(BillingCycle.cycle_date).all()}
    return [cycle_date for cycle_date in _iter_billing_dates(today) if cycle_date not in existing]


def _iter_billing_dates(today: date) -> list[date]:
    billing_day = settings.CUTOVER_DATE.day
    first_cycle = date(settings.CUTOVER_DATE.year, settings.CUTOVER_DATE.month, billing_day)
    if first_cycle < settings.CUTOVER_DATE:
        first_cycle += relativedelta(months=1)

    dates: list[date] = []
    current = first_cycle
    while current <= today:
        dates.append(current)
        current += relativedelta(months=1)
    return dates


def _post_cycle(session: Session, cycle_date: date, run_id: int) -> BillingCycle:
    if session.query(BillingCycle).filter(BillingCycle.cycle_date == cycle_date).first() is not None:
        return session.query(BillingCycle).filter(BillingCycle.cycle_date == cycle_date).one()

    members = session.query(Member).order_by(Member.display_name).all()
    counted = [member for member in members if member.is_active_on(cycle_date) and member.counted_in_denominator]
    billable = [member for member in members if member.is_active_on(cycle_date) and member.billable_after_cutover]
    if not counted:
        raise ValueError(f"Cannot post cycle for {cycle_date}: there are no active counted members.")

    denominator = len(counted)
    fx_rate = get_or_fetch_fx_rate(session, cycle_date).usd_rub
    subscription_usd = settings.SUBSCRIPTION_USD
    subscription_rub = (subscription_usd * fx_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rub_per_slot = (subscription_rub / Decimal(denominator)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    total_billed_rub = (rub_per_slot * Decimal(len(billable))).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    owner_subsidy_rub = (subscription_rub - total_billed_rub).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    cycle = BillingCycle(
        cycle_date=cycle_date,
        status="posted",
        subscription_usd=subscription_usd,
        fx_locked=fx_rate,
        subscription_rub=subscription_rub,
        counted_active=denominator,
        billed_active=len(billable),
        total_billed_rub=total_billed_rub,
        owner_subsidy_rub=owner_subsidy_rub,
        posted_at=_utcnow(),
        reconciliation_run_id=run_id,
    )
    session.add(cycle)
    session.flush()

    for member in billable:
        charge = MemberCharge(
            cycle_id=cycle.id,
            member_id=member.id,
            charge_date=cycle_date,
            active_count=denominator,
            subscription_usd=subscription_usd,
            charge_usd=(subscription_usd / Decimal(denominator)).quantize(
                Decimal("0.000001"),
                rounding=ROUND_HALF_UP,
            ),
            fx_locked=fx_rate,
            charge_rub=rub_per_slot,
        )
        session.add(charge)

    session.flush()
    _validate_cycle(cycle)
    session.commit()
    return cycle


def _validate_cycle(cycle: BillingCycle) -> None:
    total_charges = sum((charge.charge_rub for charge in cycle.charges), ZERO).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    if total_charges != cycle.total_billed_rub:
        raise ValueError(
            f"Posted charges for {cycle.cycle_date} sum to {total_charges} RUB "
            f"but the cycle total is {cycle.total_billed_rub} RUB."
        )
    if len(cycle.charges) != cycle.billed_active:
        raise ValueError(
            f"Posted charges for {cycle.cycle_date} count {len(cycle.charges)} "
            f"but billed_active is {cycle.billed_active}."
        )


def _notify_failure(run: ReconciliationRun, cycle_date: date, message: str | None) -> bool:
    body = (
        "Spotify Family Ledger reconciliation failed.\n"
        f"Run #{run.id}\n"
        f"Cycle: {cycle_date}\n"
        f"Error: {message or 'Unknown error'}"
    )
    return send_telegram_alert(body)


def _acquire_job_lock(session: Session, owner_id: str) -> bool:
    now = _utcnow()
    expires_at = now + relativedelta(seconds=settings.RECONCILIATION_LOCK_TTL_SECONDS)
    lock = session.get(JobLock, JOB_LOCK_NAME)

    if lock is not None and lock.expires_at > now:
        return False

    if lock is None:
        lock = JobLock(
            name=JOB_LOCK_NAME,
            owner_id=owner_id,
            acquired_at=now,
            expires_at=expires_at,
        )
        session.add(lock)
    else:
        lock.owner_id = owner_id
        lock.acquired_at = now
        lock.expires_at = expires_at

    session.commit()
    return True


def _release_job_lock(session: Session, owner_id: str) -> None:
    try:
        lock = session.get(JobLock, JOB_LOCK_NAME)
        if lock is None or lock.owner_id != owner_id:
            return
        session.delete(lock)
        session.commit()
    except Exception:
        session.rollback()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
