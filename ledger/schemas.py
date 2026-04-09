"""Pydantic schemas for commands and read models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class SaveMemberCommand(BaseModel):
    member_id: int | None = None
    display_name: str
    active_from: date
    active_to: date | None = None
    counted_in_denominator: bool
    billable_after_cutover: bool
    note: str | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Display name is required.")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = "\n".join(line.rstrip() for line in value.strip().splitlines())
        return normalized or None


class RecordPaymentCommand(BaseModel):
    member_id: int
    payment_date: date
    rub_paid: Decimal
    note: str | None = None

    @field_validator("rub_paid")
    @classmethod
    def positive_amount(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Payment amount must be positive.")
        return value

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class CreateAdjustmentCommand(BaseModel):
    member_id: int
    effective_date: date
    amount_rub: Decimal
    reason: str
    related_cycle_id: int | None = None

    @field_validator("amount_rub")
    @classmethod
    def non_zero_amount(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("Adjustment amount must be non-zero.")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Adjustment reason is required.")
        return normalized


class ReconciliationOutcome(BaseModel):
    state: str
    exact_through_date: date | None
    last_attempted_cycle_date: date | None
    failure_cycle_date: date | None
    failure_message: str | None
    cycles_posted_count: int
    alert_sent: bool


class LedgerStatus(BaseModel):
    state: str
    exact_through_date: date | None
    last_attempted_cycle_date: date | None
    failure_cycle_date: date | None
    failure_message: str | None
    cycles_posted_count: int
    alert_sent: bool
    last_completed_at: datetime | None
    last_run_trigger: str | None


class MemberBalance(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: int
    display_name: str
    is_active: bool
    counted_in_denominator: bool
    billable_after_cutover: bool
    opening_balance_rub: Decimal
    charges_rub: Decimal
    payments_rub: Decimal
    adjustments_rub: Decimal
    balance_rub: Decimal
    last_payment_date: date | None
    last_charge_date: date | None


class StatementEntry(BaseModel):
    entry_date: date
    entry_type: str
    description: str
    amount_rub: Decimal
    balance_rub: Decimal
    fx_locked: Decimal | None = None
    subscription_usd: Decimal | None = None
    note: str | None = None


class MemberStatement(BaseModel):
    member_id: int
    display_name: str
    current_balance_rub: Decimal
    last_payment_date: date | None
    exact_through_date: date | None
    entries: list[StatementEntry]


class PaymentRecord(BaseModel):
    id: int
    member_id: int
    display_name: str
    payment_date: date
    rub_paid: Decimal
    note: str | None
    created_at: datetime


class ReconciliationRunRecord(BaseModel):
    id: int
    trigger: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    from_cycle_date: date | None
    to_cycle_date: date | None
    last_successful_cycle_date: date | None
    error_cycle_date: date | None
    error_message: str | None
    cycles_posted_count: int
    alert_sent: bool
    alert_error: str | None


class IntegrityIssue(BaseModel):
    severity: str
    message: str
