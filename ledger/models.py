"""SQLAlchemy ORM models for the Spotify Family Ledger.

The ledger is RUB-first.

Main tables:
  members, legacy_snapshot, fx_rates, charge_cycles, posted_charges, payments

Legacy USD balances are imported once and converted to RUB on import.
All ongoing accounting is in RUB.
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

    # If true, the member is counted in the total slot denominator
    counted_in_denominator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # If true, the member receives a personal charge row when a cycle is posted
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
        """True if the member is within their active date range on the given date."""
        if d < self.active_from:
            return False
        if self.active_to is not None and d >= self.active_to:
            return False
        return True


class LegacySnapshot(Base):
    """Frozen opening balance imported once from the legacy spreadsheet."""

    __tablename__ = "legacy_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, unique=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    # All monetary fields in RUB
    opening_balance_rub: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    source_usd_balance: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    member: Mapped["Member"] = relationship("Member", back_populates="legacy_snapshot")


class FxRate(Base):
    __tablename__ = "fx_rates"

    rate_date: Mapped[date] = mapped_column(Date, primary_key=True)
    usd_rub: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class ChargeCycle(Base):
    __tablename__ = "charge_cycles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="forecast")

    # The subscription cost is defined in USD but charged in RUB
    subscription_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    subscription_rub: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    counted_active: Mapped[int | None] = mapped_column(nullable=True)
    billed_active: Mapped[int | None] = mapped_column(nullable=True)

    total_billed_rub: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    owner_subsidy_rub: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)

    # The FX rate used to lock the RUB cost for this cycle
    fx_locked: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    charges: Mapped[list["PostedCharge"]] = relationship("PostedCharge", back_populates="cycle")


class PostedCharge(Base):
    """Immutable record of a charge applied to a member for a specific cycle."""

    __tablename__ = "posted_charges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("charge_cycles.id"), nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)

    charge_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Denominator used at the time of posting
    active_count: Mapped[int] = mapped_column(nullable=False)

    # Original USD reference
    subscription_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    charge_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)

    # Effective RUB charge
    fx_locked: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    charge_rub: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Audit trail for rare manual edits
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    edit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    member: Mapped["Member"] = relationship("Member", back_populates="posted_charges")
    cycle: Mapped["ChargeCycle"] = relationship("ChargeCycle", back_populates="charges")

    __table_args__ = (UniqueConstraint("cycle_id", "member_id", name="uq_cycle_member"),)


class Payment(Base):
    """Immutable record of a payment made by a member."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)

    # RUB amount actually paid
    rub_paid: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    # For RUB-first, fx_locked is effectively 1.0
    fx_locked: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal(1))
    usd_credit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Audit trail
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    edit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    member: Mapped["Member"] = relationship("Member", back_populates="payments")
