"""Cycle service — forecasting, previewing, and posting charge cycles."""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from ledger.config import settings
from ledger.models import ChargeCycle, Member, PostedCharge
from ledger.schemas import CyclePreview, CycleSummary, MemberChargePreview
from ledger.services.fx import get_fx_rate


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_next_unposted_cycle(session: Session) -> ChargeCycle | None:
    """Return the earliest forecast cycle, or None if all are posted."""
    return (
        session.query(ChargeCycle)
        .filter(ChargeCycle.status == "forecast")
        .order_by(ChargeCycle.cycle_date)
        .first()
    )


def get_cycle(session: Session, cycle_id: int) -> ChargeCycle:
    cycle = session.get(ChargeCycle, cycle_id)
    if cycle is None:
        raise ValueError(f"Cycle {cycle_id} not found")
    return cycle


def list_posted_cycles(session: Session) -> list[ChargeCycle]:
    return (
        session.query(ChargeCycle)
        .filter(ChargeCycle.status == "posted")
        .order_by(ChargeCycle.cycle_date.desc())
        .all()
    )


def list_all_cycles(session: Session) -> list[CycleSummary]:
    cycles = session.query(ChargeCycle).order_by(ChargeCycle.cycle_date.desc()).all()
    return [CycleSummary.model_validate(c) for c in cycles]


# ---------------------------------------------------------------------------
# Forecast generation
# ---------------------------------------------------------------------------


def ensure_forecast_cycles(session: Session) -> list[ChargeCycle]:
    """Create forecast cycles up to FORECAST_HORIZON_MONTHS ahead if missing.

    Cycles are anchored to the 20th of each month starting from CUTOVER_DATE.
    Returns the list of newly created cycles.
    """
    horizon = settings.FORECAST_HORIZON_MONTHS
    cutover = settings.CUTOVER_DATE
    today = date.today()
    # Start from whichever is later: cutover or today
    start = max(cutover, date(today.year, today.month, 1))
    created = []

    for i in range(horizon + 1):
        month_start = start + relativedelta(months=i)
        cycle_date = date(month_start.year, month_start.month, 20)

        existing = (
            session.query(ChargeCycle)
            .filter(ChargeCycle.cycle_date == cycle_date)
            .first()
        )
        if existing is None:
            cycle = ChargeCycle(
                cycle_date=cycle_date,
                status="forecast",
                subscription_usd=settings.SUBSCRIPTION_USD,
            )
            session.add(cycle)
            created.append(cycle)

    return created


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def preview_cycle(session: Session, cycle_id: int) -> CyclePreview:
    """Compute what posting this cycle would produce, without writing anything."""
    cycle = get_cycle(session, cycle_id)
    if cycle.status == "posted":
        raise ValueError(f"Cycle {cycle.cycle_date} is already posted.")

    active_members = _active_members_on(session, cycle.cycle_date)
    counted = [m for m in active_members if m.counted_in_denominator]
    billable = [m for m in active_members if m.billable_after_cutover]

    denominator = len(counted)
    if denominator == 0:
        raise ValueError(
            f"No active counted members on {cycle.cycle_date}. Cannot compute charges."
        )

    per_slot = (cycle.subscription_usd / Decimal(denominator)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    total_billed = (per_slot * Decimal(len(billable))).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    owner_subsidy = cycle.subscription_usd - total_billed

    fx = get_fx_rate(session, cycle.cycle_date)
    fx_rate = fx.usd_rub if fx else None

    member_charges = []
    for m in active_members:
        is_billable = m.billable_after_cutover
        charge_usd = per_slot if is_billable else Decimal("0")
        rub_eq = None
        if fx_rate is not None:
            rub_eq = (charge_usd * fx_rate).quantize(Decimal("0.01"))
        member_charges.append(
            MemberChargePreview(
                member_id=m.id,
                display_name=m.display_name,
                counted=m.counted_in_denominator,
                billable=is_billable,
                charge_usd=charge_usd,
                charge_rub_equivalent=rub_eq,
            )
        )

    return CyclePreview(
        cycle_id=cycle_id,
        cycle_date=cycle.cycle_date,
        subscription_usd=cycle.subscription_usd,
        counted_active=denominator,
        billed_active=len(billable),
        usd_per_counted_slot=per_slot,
        total_billed_usd=total_billed,
        owner_subsidy_usd=owner_subsidy,
        fx_rate=fx_rate,
        fx_available=fx is not None,
        member_charges=member_charges,
    )


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------


def post_cycle(session: Session, cycle_id: int) -> list[PostedCharge]:
    """Post a forecast cycle. Writes immutable posted_charges rows.

    Raises ValueError for:
    - cycle already posted
    - no FX rate on the cycle date
    - no active counted members (denominator = 0)
    """
    cycle = get_cycle(session, cycle_id)

    if cycle.status == "posted":
        raise ValueError(
            f"{cycle.cycle_date.strftime('%B %Y')} cycle is already posted."
        )

    fx = get_fx_rate(session, cycle.cycle_date)
    if fx is None:
        raise ValueError(
            f"No FX rate exists for {cycle.cycle_date}. "
            "Add the rate before posting this cycle."
        )

    active_members = _active_members_on(session, cycle.cycle_date)
    counted = [m for m in active_members if m.counted_in_denominator]
    billable = [m for m in active_members if m.billable_after_cutover]

    denominator = len(counted)
    if denominator == 0:
        raise ValueError(
            f"No active counted members on {cycle.cycle_date}. Cannot post cycle."
        )

    per_slot = (cycle.subscription_usd / Decimal(denominator)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    total_billed = (per_slot * Decimal(len(billable))).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    owner_subsidy = cycle.subscription_usd - total_billed

    charges: list[PostedCharge] = []
    for m in active_members:
        is_billable = m.billable_after_cutover
        charge_usd = per_slot if is_billable else Decimal("0")
        rub_eq = (charge_usd * fx.usd_rub).quantize(Decimal("0.0001"))

        charge = PostedCharge(
            cycle_id=cycle_id,
            member_id=m.id,
            charge_date=cycle.cycle_date,
            counted=m.counted_in_denominator,
            billable=is_billable,
            active_count=denominator,
            subscription_usd=cycle.subscription_usd,
            charge_usd=charge_usd,
            fx_locked=fx.usd_rub,
            charge_rub_equivalent=rub_eq,
        )
        session.add(charge)
        charges.append(charge)

    # Update cycle row
    cycle.status = "posted"
    cycle.counted_active = denominator
    cycle.billed_active = len(billable)
    cycle.usd_per_counted_slot = per_slot
    cycle.total_billed_usd = total_billed
    cycle.owner_subsidy_usd = owner_subsidy
    cycle.fx_locked = fx.usd_rub
    cycle.posted_at = datetime.now(timezone.utc)

    return charges


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _active_members_on(session: Session, d: date) -> list[Member]:
    """Return all members active on the given date, ordered by name."""
    members = session.query(Member).order_by(Member.display_name).all()
    return [m for m in members if m.is_active_on(d)]
