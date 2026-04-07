"""Pydantic schemas for commands (inputs) and views (outputs)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Command schemas (inputs validated before hitting services)
# ---------------------------------------------------------------------------


class RecordPaymentCommand(BaseModel):
    member_id: int
    payment_date: date
    rub_paid: Decimal
    note: str | None = None

    @field_validator("rub_paid")
    @classmethod
    def rub_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("RUB amount must be positive")
        return v


class PostCycleCommand(BaseModel):
    cycle_id: int


# ---------------------------------------------------------------------------
# View schemas (outputs returned from services to pages)
# ---------------------------------------------------------------------------


class MemberBalance(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: int
    display_name: str
    is_active: bool
    counted_in_denominator: bool
    billable_after_cutover: bool
    legacy_opening_usd: Decimal
    posted_charges_usd: Decimal
    payment_credits_usd: Decimal
    # balance = legacy_opening_usd + posted_charges_usd - payment_credits_usd
    balance_usd: Decimal
    # Display-only: balance_usd * latest_fx (None if no FX rate available)
    balance_rub_equivalent: Decimal | None


class CyclePreview(BaseModel):
    cycle_id: int
    cycle_date: date
    subscription_usd: Decimal
    counted_active: int
    billed_active: int
    usd_per_counted_slot: Decimal
    total_billed_usd: Decimal
    owner_subsidy_usd: Decimal
    fx_rate: Decimal | None
    fx_available: bool
    # Per-member breakdown
    member_charges: list["MemberChargePreview"]


class MemberChargePreview(BaseModel):
    member_id: int
    display_name: str
    counted: bool
    billable: bool
    charge_usd: Decimal
    charge_rub_equivalent: Decimal | None


class PaymentPreview(BaseModel):
    member_id: int
    display_name: str
    payment_date: date
    rub_paid: Decimal
    fx_rate: Decimal | None
    fx_available: bool
    usd_credit: Decimal | None


class CycleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_date: date
    status: str
    subscription_usd: Decimal
    counted_active: int | None
    billed_active: int | None
    total_billed_usd: Decimal | None
    owner_subsidy_usd: Decimal | None
    fx_locked: Decimal | None
    posted_at: datetime | None


class PaymentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_id: int
    display_name: str
    payment_date: date
    rub_paid: Decimal
    fx_locked: Decimal
    usd_credit: Decimal
    note: str | None
    created_at: datetime


class IntegrityIssue(BaseModel):
    severity: str  # 'error' or 'warning'
    message: str
