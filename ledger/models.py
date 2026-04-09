"""SQLAlchemy ORM models for Spotify Family Ledger v2."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    active_from: Mapped[date] = mapped_column(Date, nullable=False)
    active_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    counted_in_denominator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    billable_after_cutover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    opening_balance: Mapped["OpeningBalance | None"] = relationship(
        "OpeningBalance",
        back_populates="member",
        uselist=False,
    )
    charges: Mapped[list["MemberCharge"]] = relationship("MemberCharge", back_populates="member")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="member")
    adjustments: Mapped[list["Adjustment"]] = relationship("Adjustment", back_populates="member")

    def is_active_on(self, value: date) -> bool:
        if value < self.active_from:
            return False
        if self.active_to is not None and value >= self.active_to:
            return False
        return True


class OpeningBalance(Base):
    __tablename__ = "opening_balances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance_rub: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    source_usd_balance: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    member: Mapped["Member"] = relationship("Member", back_populates="opening_balance")

    __table_args__ = (
        UniqueConstraint("member_id", name="uq_opening_balance_member"),
    )


class FxRate(Base):
    __tablename__ = "fx_rates"

    rate_date: Mapped[date] = mapped_column(Date, primary_key=True)
    usd_rub: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    from_cycle_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    to_cycle_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_successful_cycle_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    error_cycle_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cycles_posted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alert_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alert_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    cycles: Mapped[list["BillingCycle"]] = relationship("BillingCycle", back_populates="reconciliation_run")

    __table_args__ = (
        Index("ix_reconciliation_runs_started_at", "started_at"),
    )


class BillingCycle(Base):
    __tablename__ = "billing_cycles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="posted")
    subscription_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    fx_locked: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    subscription_rub: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    counted_active: Mapped[int] = mapped_column(Integer, nullable=False)
    billed_active: Mapped[int] = mapped_column(Integer, nullable=False)
    total_billed_rub: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    owner_subsidy_rub: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reconciliation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("reconciliation_runs.id"),
        nullable=True,
    )

    reconciliation_run: Mapped["ReconciliationRun | None"] = relationship(
        "ReconciliationRun",
        back_populates="cycles",
    )
    charges: Mapped[list["MemberCharge"]] = relationship("MemberCharge", back_populates="cycle")
    adjustments: Mapped[list["Adjustment"]] = relationship("Adjustment", back_populates="related_cycle")


class MemberCharge(Base):
    __tablename__ = "member_charges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("billing_cycles.id"), nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    charge_date: Mapped[date] = mapped_column(Date, nullable=False)
    active_count: Mapped[int] = mapped_column(Integer, nullable=False)
    subscription_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    charge_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    fx_locked: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    charge_rub: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    cycle: Mapped["BillingCycle"] = relationship("BillingCycle", back_populates="charges")
    member: Mapped["Member"] = relationship("Member", back_populates="charges")

    __table_args__ = (
        UniqueConstraint("cycle_id", "member_id", name="uq_member_charge_cycle_member"),
        Index("ix_member_charges_member_id", "member_id"),
        Index("ix_member_charges_charge_date", "charge_date"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    rub_paid: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    member: Mapped["Member"] = relationship("Member", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_member_id", "member_id"),
        Index("ix_payments_payment_date", "payment_date"),
    )


class Adjustment(Base):
    __tablename__ = "adjustments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_rub: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    related_cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("billing_cycles.id"),
        nullable=True,
    )

    member: Mapped["Member"] = relationship("Member", back_populates="adjustments")
    related_cycle: Mapped["BillingCycle | None"] = relationship(
        "BillingCycle",
        back_populates="adjustments",
    )

    __table_args__ = (
        Index("ix_adjustments_member_id", "member_id"),
        Index("ix_adjustments_effective_date", "effective_date"),
    )


class JobLock(Base):
    __tablename__ = "job_locks"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
