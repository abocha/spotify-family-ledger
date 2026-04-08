"""Pydantic schemas for commands (inputs) and views (outputs)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


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


class EditPaymentCommand(BaseModel):
    payment_id: int
    rub_paid: Decimal
    note: str | None = None
    edit_reason: str

    @field_validator("rub_paid")
    @classmethod
    def rub_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("RUB amount must be positive")
        return v

    @field_validator("edit_reason")
    @classmethod
    def reason_must_exist(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Edit reason is required")
        return " ".join(v.split())


class EditChargeCommand(BaseModel):
    charge_id: int
    charge_rub: Decimal
    edit_reason: str

    @field_validator("charge_rub")
    @classmethod
    def positive_decimal(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Charge amount must be positive")
        return v

    @field_validator("edit_reason")
    @classmethod
    def reason_must_exist(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Edit reason is required")
        return " ".join(v.split())


class PostCycleCommand(BaseModel):
    cycle_id: int


class MemberBalance(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: int
    display_name: str
    is_active: bool
    counted_in_denominator: bool
    billable_after_cutover: bool
    legacy_opening_rub: Decimal
    posted_charges_rub: Decimal
    payment_credits_rub: Decimal
    balance_rub: Decimal
    balance_usd_equivalent: Decimal | None


class CyclePreview(BaseModel):
    cycle_id: int
    cycle_date: date
    subscription_usd: Decimal
    subscription_rub: Decimal | None
    counted_active: int
    billed_active: int
    rub_per_slot: Decimal | None
    total_billed_rub: Decimal | None
    owner_subsidy_rub: Decimal | None
    fx_rate: Decimal | None
    fx_available: bool
    estimated_fx_rate: Decimal | None = None
    estimated_subscription_rub: Decimal | None = None
    estimated_rub_per_slot: Decimal | None = None
    estimated_total_billed_rub: Decimal | None = None
    estimated_owner_subsidy_rub: Decimal | None = None
    uses_estimated_fx: bool = False
    member_charges: list["MemberChargePreview"]


class MemberChargePreview(BaseModel):
    member_id: int
    display_name: str
    counted: bool
    billable: bool
    charge_usd: Decimal
    charge_rub: Decimal | None
    estimated_charge_rub: Decimal | None = None


class PaymentPreview(BaseModel):
    member_id: int
    display_name: str
    payment_date: date
    rub_paid: Decimal
    fx_rate: Decimal | None
    fx_available: bool
    rub_credit: Decimal | None


class CycleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_date: date
    status: str
    subscription_usd: Decimal
    subscription_rub: Decimal | None
    counted_active: int | None
    billed_active: int | None
    total_billed_rub: Decimal | None
    owner_subsidy_rub: Decimal | None
    fx_locked: Decimal | None
    posted_at: datetime | None


class PaymentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_id: int
    display_name: str
    payment_date: date
    rub_paid: Decimal
    fx_locked: Decimal | None
    rub_credit: Decimal
    note: str | None
    created_at: datetime


class IntegrityIssue(BaseModel):
    severity: str
    message: str
