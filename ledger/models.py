"""SQLAlchemy ORM models for the Spotify Family Ledger.

Six tables:
  members, legacy_snapshot, fx_rates, charge_cycles, posted_charges, payments

All posted history is immutable unless explicitly edited with audit metadata.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
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
    # counted_in_denominator: affects subscription split
    counted_in_denominator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # billable_after_cutover: receives a posted_charge each cycle
    billable_after_cutover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    legacy_snapshot: Mapped["LegacySnapshot | None"] = relationship(
        "LegacySnapshot", back_populates="member", uselist=False
    )
    posted_charges: Mapped[list["PostedCharge"]] = relationship(
        "PostedCharge", back_populates="member"
    )
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="member")

    def is_active_on(self, d: date) -> bool:
        if d < self.active_from:
            return False
        if self.active_to is not None and d >= self.active_to:
            return False
        return True


class LegacySnapshot(Base):
    """Frozen opening balance from the legacy spreadsheet as of cutover."""

    __tablename__ = "legacy_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, unique=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Positive = member owes owner. Negative = owner owes member.
    opening_balance_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    member: Mapped["Member"] = relationship("Member", back_populates="legacy_snapshot")


class FxRate(Base):
    """One USD/RUB rate per date. rate_date is the primary key — no duplicates allowed."""

    __tablename__ = "fx_rates"

    rate_date: Mapped[date] = mapped_column(Date, primary_key=True)
    usd_rub: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class ChargeCycle(Base):
    """One row per monthly billing cycle. cycle_date is unique — no double-posting."""

    __tablename__ = "charge_cycles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # The 20th of the billing month
    cycle_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    # 'forecast' or 'posted'
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="forecast")
    subscription_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    # Number of members counted in the denominator when forecasted
    counted_active: Mapped[int | None] = mapped_column(nullable=True)
    # Number of billable members
    billed_active: Mapped[int | None] = mapped_column(nullable=True)
    # subscription_usd / counted_active
    usd_per_counted_slot: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    # usd_per_counted_slot * billed_active
    total_billed_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    # subscription_usd - total_billed_usd
    owner_subsidy_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    # FX rate locked at posting time (NULL until posted)
    fx_locked: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    posted_charges: Mapped[list["PostedCharge"]] = relationship(
        "PostedCharge", back_populates="cycle"
    )


class PostedCharge(Base):
    """Immutable posted member-level charge. One row per member per cycle."""

    __tablename__ = "posted_charges"
    __table_args__ = (
        UniqueConstraint("cycle_id", "member_id", name="uq_charge_cycle_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("charge_cycles.id"), nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    charge_date: Mapped[date] = mapped_column(Date, nullable=False)
    counted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Denominator used for this cycle
    active_count: Mapped[int] = mapped_column(nullable=False)
    subscription_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    # charge_usd = 0 if not billable
    charge_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    fx_locked: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    # Display-only RUB equivalent at posting time
    charge_rub_equivalent: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    edit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    cycle: Mapped["ChargeCycle"] = relationship("ChargeCycle", back_populates="posted_charges")
    member: Mapped["Member"] = relationship("Member", back_populates="posted_charges")


class Payment(Base):
    """Payment record. FX and USD credit are locked at save time."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    rub_paid: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    # NOT NULL enforced: cannot save without a locked FX rate
    fx_locked: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    usd_credit: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    edit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    member: Mapped["Member"] = relationship("Member", back_populates="payments")
