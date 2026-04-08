"""Cycle service — automatic monthly processing of charges."""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from ledger.config import settings
from ledger.models import ChargeCycle, Member, PostedCharge
from ledger.schemas import CyclePreview, CycleSummary, EditChargeCommand, MemberChargePreview
from ledger.services.fx import ensure_fx_rate, get_fx_rate, get_latest_fx_rate


def get_next_unposted_cycle(session: Session) -> ChargeCycle | None:
    return (
        session.query(ChargeCycle)
        .filter(ChargeCycle.status == "forecast")
        .order_by(ChargeCycle.cycle_date)
        .first()
    )


def ensure_forecast_cycles(session: Session) -> list[ChargeCycle]:
    """Generate forecast cycles up to the horizon.
    
    Returns only newly created forecast cycles.
    An empty list means no DB mutations occurred (safe signal for cache invalidation).
    """
    today = date.today()
    cutover = settings.CUTOVER_DATE
    first_cycle = date(cutover.year, cutover.month, 20)
    if first_cycle < cutover:
        first_cycle += relativedelta(months=1)

    # We want a fixed rolling horizon ahead of "today", not ahead of the latest row in DB.
    current_cycle_anchor = date(today.year, today.month, 20)
    if today >= current_cycle_anchor:
        horizon_start = current_cycle_anchor + relativedelta(months=1)
    else:
        horizon_start = current_cycle_anchor

    horizon_start = max(horizon_start, first_cycle)
    horizon_end = horizon_start + relativedelta(months=settings.FORECAST_HORIZON_MONTHS - 1)

    existing_last = session.query(ChargeCycle).order_by(ChargeCycle.cycle_date.desc()).first()
    if existing_last:
        start_date = max(existing_last.cycle_date + relativedelta(months=1), first_cycle)
    else:
        start_date = first_cycle

    if start_date > horizon_end:
        return []

    new_cycles = []
    cycle_date = start_date
    while cycle_date <= horizon_end:
        session.add(
            ChargeCycle(
                cycle_date=cycle_date,
                subscription_usd=settings.SUBSCRIPTION_USD,
                status="forecast",
            )
        )
        new_cycles.append(cycle_date)
        cycle_date += relativedelta(months=1)

    if new_cycles:
        session.commit()

    return session.query(ChargeCycle).filter(ChargeCycle.cycle_date.in_(new_cycles)).all()


def _cycle_members(session: Session, cycle_date: date) -> tuple[list[Member], list[Member], list[Member]]:
    members = session.query(Member).all()
    counted = [m for m in members if m.is_active_on(cycle_date) and m.counted_in_denominator]
    billable = [m for m in members if m.is_active_on(cycle_date) and m.billable_after_cutover]
    return members, counted, billable


def _calculate_rub_values(
    subscription_usd: Decimal,
    denominator: int,
    billable_count: int,
    fx_rate: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Helper to compute RUB-based values from FX rate.
    
    Returns: (subscription_rub, rub_per_slot, total_billed_rub, owner_subsidy_rub)
    """
    subscription_rub = (subscription_usd * fx_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rub_per_slot = (subscription_rub / Decimal(denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_billed_rub = (rub_per_slot * Decimal(billable_count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    owner_subsidy_rub = subscription_rub - total_billed_rub
    return subscription_rub, rub_per_slot, total_billed_rub, owner_subsidy_rub


def _calculate_cycle_preview(
    cycle: ChargeCycle,
    members: list[Member],
    counted: list[Member],
    billable: list[Member],
    fx_rate: Decimal | None,
    estimated_fx_rate: Decimal | None = None,
) -> CyclePreview:
    if not counted:
        raise ValueError(
            f"Cannot calculate cycle for {cycle.cycle_date}: there are no active counted members."
        )

    denominator = len(counted)
    billable_count = len(billable)
    
    # Actual values from exact FX
    subscription_rub = None
    rub_per_slot = None
    total_billed_rub = None
    owner_subsidy_rub = None
    uses_estimated_fx = False
    
    # Estimated values from latest stored FX
    estimated_subscription_rub = None
    estimated_rub_per_slot = None
    estimated_total_billed_rub = None
    estimated_owner_subsidy_rub = None

    if fx_rate is not None:
        subscription_rub, rub_per_slot, total_billed_rub, owner_subsidy_rub = _calculate_rub_values(
            cycle.subscription_usd, denominator, billable_count, fx_rate
        )
    elif estimated_fx_rate is not None:
        # Use estimated values when exact FX is missing but latest stored FX exists
        estimated_subscription_rub, estimated_rub_per_slot, estimated_total_billed_rub, estimated_owner_subsidy_rub = _calculate_rub_values(
            cycle.subscription_usd, denominator, billable_count, estimated_fx_rate
        )
        uses_estimated_fx = True

    member_charges = []
    for m in members:
        is_counted = m.is_active_on(cycle.cycle_date) and m.counted_in_denominator
        is_billable = m.is_active_on(cycle.cycle_date) and m.billable_after_cutover
        charge_usd = (cycle.subscription_usd / Decimal(denominator)) if is_billable else Decimal(0)
        charge_rub = rub_per_slot if (is_billable and rub_per_slot is not None) else None
        estimated_charge_rub = None
        if is_billable and estimated_rub_per_slot is not None:
            estimated_charge_rub = estimated_rub_per_slot
        member_charges.append(
            MemberChargePreview(
                member_id=m.id,
                display_name=m.display_name,
                counted=is_counted,
                billable=is_billable,
                charge_usd=charge_usd,
                charge_rub=charge_rub,
                estimated_charge_rub=estimated_charge_rub,
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
        estimated_fx_rate=estimated_fx_rate,
        estimated_subscription_rub=estimated_subscription_rub,
        estimated_rub_per_slot=estimated_rub_per_slot,
        estimated_total_billed_rub=estimated_total_billed_rub,
        estimated_owner_subsidy_rub=estimated_owner_subsidy_rub,
        uses_estimated_fx=uses_estimated_fx,
        member_charges=member_charges,
    )


def preview_cycle(session: Session, cycle_id: int) -> CyclePreview:
    cycle = session.get(ChargeCycle, cycle_id)
    if not cycle:
        raise ValueError(f"Cycle with id {cycle_id} not found")

    fx_obj = get_fx_rate(session, cycle.cycle_date)
    fx_rate = fx_obj.usd_rub if fx_obj else None
    
    # If exact FX is missing, try to get latest stored FX for estimates
    estimated_fx_rate = None
    if fx_rate is None:
        latest_fx_obj = get_latest_fx_rate(session)
        estimated_fx_rate = latest_fx_obj.usd_rub if latest_fx_obj else None
    
    members, counted, billable = _cycle_members(session, cycle.cycle_date)
    return _calculate_cycle_preview(cycle, members, counted, billable, fx_rate, estimated_fx_rate)


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
    """Process all due cycles up to a given date.
    
    Returns only cycles that were actually changed from forecast to posted.
    An empty list means no DB mutations occurred (safe signal for cache invalidation).
    """
    if up_to is None:
        up_to = date.today()

    mutated: list[ChargeCycle] = []
    first_cycle = date(settings.CUTOVER_DATE.year, settings.CUTOVER_DATE.month, 20)
    if first_cycle < settings.CUTOVER_DATE:
        first_cycle += relativedelta(months=1)

    cycle_date = first_cycle
    while cycle_date <= up_to:
        cycle_before = session.query(ChargeCycle).filter(ChargeCycle.cycle_date == cycle_date).one_or_none()
        status_before = cycle_before.status if cycle_before else None
        
        cycle_after = run_cycle_for_date(session, cycle_date)
        
        # Only include cycles that were changed: (None -> posted) or (forecast -> posted)
        if (status_before is None or status_before == "forecast") and cycle_after.status == "posted":
            mutated.append(cycle_after)
        
        cycle_date += relativedelta(months=1)

    session.commit()
    return mutated


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
