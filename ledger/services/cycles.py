"""Cycle service — automatic monthly processing of charges."""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from ledger.config import settings
from ledger.models import ChargeCycle, Member, PostedCharge
from ledger.schemas import CyclePreview, CycleSummary, EditChargeCommand, MemberChargePreview
from ledger.services.fx import ensure_fx_rate, get_fx_rate


def get_next_unposted_cycle(session: Session) -> ChargeCycle | None:
    return (
        session.query(ChargeCycle)
        .filter(ChargeCycle.status == "forecast")
        .order_by(ChargeCycle.cycle_date)
        .first()
    )


def ensure_forecast_cycles(session: Session) -> list[ChargeCycle]:
    today = date.today()
    cutover = settings.CUTOVER_DATE
    start_date = date(cutover.year, cutover.month, 20)

    existing = session.query(ChargeCycle).order_by(ChargeCycle.cycle_date.desc()).first()
    if existing:
        start_date = existing.cycle_date + relativedelta(months=1)
    elif today >= start_date:
        start_date = date(today.year, today.month, 20)
        if today >= start_date:
            start_date += relativedelta(months=1)

    new_cycles = []
    needed = settings.FORECAST_HORIZON_MONTHS
    for i in range(needed + 1 if not existing else needed):
        target_date = start_date + relativedelta(months=i)
        if target_date < settings.CUTOVER_DATE:
            continue
        cycle = ChargeCycle(
            cycle_date=target_date,
            subscription_usd=settings.SUBSCRIPTION_USD,
            status="forecast",
        )
        session.add(cycle)
        new_cycles.append(cycle)

    if new_cycles:
        session.commit()
    return new_cycles


def _cycle_members(session: Session, cycle_date: date) -> tuple[list[Member], list[Member], list[Member]]:
    members = session.query(Member).all()
    counted = [m for m in members if m.is_active_on(cycle_date) and m.counted_in_denominator]
    billable = [m for m in members if m.is_active_on(cycle_date) and m.billable_after_cutover]
    return members, counted, billable


def _calculate_cycle_preview(cycle: ChargeCycle, members: list[Member], counted: list[Member], billable: list[Member], fx_rate: Decimal | None) -> CyclePreview:
    if not counted:
        raise ValueError(
            f"Cannot calculate cycle for {cycle.cycle_date}: there are no active counted members."
        )

    denominator = len(counted)
    subscription_rub = None
    rub_per_slot = None
    total_billed_rub = None
    owner_subsidy_rub = None

    if fx_rate is not None:
        subscription_rub = (cycle.subscription_usd * fx_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rub_per_slot = (subscription_rub / Decimal(denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_billed_rub = (rub_per_slot * Decimal(len(billable))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        owner_subsidy_rub = subscription_rub - total_billed_rub

    member_charges = []
    for m in members:
        is_counted = m.is_active_on(cycle.cycle_date) and m.counted_in_denominator
        is_billable = m.is_active_on(cycle.cycle_date) and m.billable_after_cutover
        charge_usd = (cycle.subscription_usd / Decimal(denominator)) if is_billable else Decimal(0)
        charge_rub = rub_per_slot if (is_billable and rub_per_slot is not None) else None
        member_charges.append(
            MemberChargePreview(
                member_id=m.id,
                display_name=m.display_name,
                counted=is_counted,
                billable=is_billable,
                charge_usd=charge_usd,
                charge_rub=charge_rub,
            )
        )

    return CyclePreview(
        cycle_id=cycle.id,
        cycle_date=cycle.cycle_date,
        subscription_usd=cycle.subscription_usd,
        subscription_rub=subscription_rub,
        counted_active=len(counted),
        billed_active=len(billable),
        rub_per_slot=rub_per_slot,
        total_billed_rub=total_billed_rub,
        owner_subsidy_rub=owner_subsidy_rub,
        fx_rate=fx_rate,
        fx_available=fx_rate is not None,
        member_charges=member_charges,
    )


def preview_cycle(session: Session, cycle_id: int) -> CyclePreview:
    cycle = session.get(ChargeCycle, cycle_id)
    if not cycle:
        raise ValueError(f"Cycle with id {cycle_id} not found")

    fx_obj = get_fx_rate(session, cycle.cycle_date)
    fx_rate = fx_obj.usd_rub if fx_obj else None
    members, counted, billable = _cycle_members(session, cycle.cycle_date)
    return _calculate_cycle_preview(cycle, members, counted, billable, fx_rate)


def post_cycle(session: Session, cycle_id: int) -> ChargeCycle:
    """Manual post override (mostly for tests/compatibility)."""
    cycle = session.get(ChargeCycle, cycle_id)
    if not cycle:
        raise ValueError(f"Cycle with id {cycle_id} not found")
    return run_cycle_for_date(session, cycle.cycle_date)


def run_cycle_for_date(session: Session, cycle_date: date) -> ChargeCycle:
    """Automatic monthly processing for a specific date."""
    cycle = session.query(ChargeCycle).filter(ChargeCycle.cycle_date == cycle_date).one_or_none()
    if cycle is None:
        cycle = ChargeCycle(cycle_date=cycle_date, subscription_usd=settings.SUBSCRIPTION_USD, status="forecast")
        session.add(cycle)
        session.flush()

    if cycle.status != "forecast":
        return cycle

    fx_obj = ensure_fx_rate(session, cycle_date)
    fx_rate = fx_obj.usd_rub
    members, counted, billable = _cycle_members(session, cycle.cycle_date)
    preview = _calculate_cycle_preview(cycle, members, counted, billable, fx_rate)

    cycle.status = "posted"
    cycle.posted_at = datetime.now(timezone.utc)
    cycle.fx_locked = fx_rate
    cycle.counted_active = preview.counted_active
    cycle.billed_active = preview.billed_active
    cycle.subscription_rub = preview.subscription_rub
    cycle.total_billed_rub = preview.total_billed_rub
    cycle.owner_subsidy_rub = preview.owner_subsidy_rub

    for mc in preview.member_charges:
        if mc.billable:
            session.add(
                PostedCharge(
                    cycle_id=cycle.id,
                    member_id=mc.member_id,
                    charge_date=cycle.cycle_date,
                    active_count=preview.counted_active,
                    subscription_usd=cycle.subscription_usd,
                    charge_usd=mc.charge_usd,
                    fx_locked=fx_rate,
                    charge_rub=mc.charge_rub or Decimal(0),
                    billable=True,
                )
            )

    session.flush()
    _recompute_cycle_totals(session, cycle)
    return cycle


def run_due_cycles(session: Session, up_to: date | None = None) -> list[ChargeCycle]:
    if up_to is None:
        up_to = date.today()

    processed: list[ChargeCycle] = []
    first_cycle = date(settings.CUTOVER_DATE.year, settings.CUTOVER_DATE.month, 20)
    if first_cycle < settings.CUTOVER_DATE:
        first_cycle += relativedelta(months=1)

    cycle_date = first_cycle
    while cycle_date <= up_to:
        processed.append(run_cycle_for_date(session, cycle_date))
        cycle_date += relativedelta(months=1)

    session.commit()
    return processed


def process_backlog(session: Session) -> list[ChargeCycle]:
    """On startup, catch up any monthly cycles we missed while the app was offline."""
    return run_due_cycles(session, up_to=date.today())


def list_all_cycles(session: Session) -> list[CycleSummary]:
    cycles = session.query(ChargeCycle).order_by(ChargeCycle.cycle_date.desc()).all()
    return [CycleSummary.model_validate(c) for c in cycles]


def edit_posted_charge(session: Session, cmd: EditChargeCommand) -> PostedCharge:
    charge = session.get(PostedCharge, cmd.charge_id)
    if not charge:
        raise ValueError(f"Charge with id {cmd.charge_id} not found")

    charge.charge_rub = cmd.charge_rub
    charge.edited_at = datetime.now(timezone.utc)
    charge.edit_reason = cmd.edit_reason
    session.flush()
    _recompute_cycle_totals(session, charge.cycle)
    return charge


def _recompute_cycle_totals(session: Session, cycle: ChargeCycle) -> None:
    """Keep denormalized cycle summary fields aligned with posted charges."""
    session.flush()

    billable_charges = [charge for charge in cycle.charges if charge.billable]
    total_billed_rub = sum((charge.charge_rub for charge in billable_charges), Decimal(0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    cycle.billed_active = len(billable_charges)
    cycle.total_billed_rub = total_billed_rub

    if cycle.subscription_rub is not None:
        cycle.owner_subsidy_rub = (cycle.subscription_rub - total_billed_rub).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
