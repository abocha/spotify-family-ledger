"""Self-healing public ledger schema upgrade.

Revision ID: 5f2e4f5d30ea
Revises: 82e7e89440fa
Create Date: 2026-04-09 06:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5f2e4f5d30ea"
down_revision: Union[str, Sequence[str], None] = "82e7e89440fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("posted_charges")
    op.drop_table("payments")
    op.drop_table("legacy_snapshot")
    op.drop_table("charge_cycles")
    op.drop_table("members")
    op.drop_table("fx_rates")

    op.create_table(
        "fx_rates",
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("usd_rub", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("rate_date"),
    )
    op.create_table(
        "job_locks",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.String(length=100), nullable=False),
        sa.Column("acquired_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("active_from", sa.Date(), nullable=False),
        sa.Column("active_to", sa.Date(), nullable=True),
        sa.Column("counted_in_denominator", sa.Boolean(), nullable=False),
        sa.Column("billable_after_cutover", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_name"),
    )
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("from_cycle_date", sa.Date(), nullable=True),
        sa.Column("to_cycle_date", sa.Date(), nullable=True),
        sa.Column("last_successful_cycle_date", sa.Date(), nullable=True),
        sa.Column("error_cycle_date", sa.Date(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cycles_posted_count", sa.Integer(), nullable=False),
        sa.Column("alert_sent", sa.Boolean(), nullable=False),
        sa.Column("alert_error", sa.Text(), nullable=True),
        sa.Column("app_version", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "billing_cycles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cycle_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("subscription_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("fx_locked", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("subscription_rub", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("counted_active", sa.Integer(), nullable=False),
        sa.Column("billed_active", sa.Integer(), nullable=False),
        sa.Column("total_billed_rub", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("owner_subsidy_rub", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["reconciliation_run_id"], ["reconciliation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_date"),
    )
    op.create_table(
        "opening_balances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("opening_balance_rub", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("source_usd_balance", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", name="uq_opening_balance_member"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("rub_paid", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "member_charges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("charge_date", sa.Date(), nullable=False),
        sa.Column("active_count", sa.Integer(), nullable=False),
        sa.Column("subscription_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("charge_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("fx_locked", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("charge_rub", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["billing_cycles.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "member_id", name="uq_member_charge_cycle_member"),
    )
    op.create_table(
        "adjustments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("amount_rub", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("related_cycle_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["related_cycle_id"], ["billing_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("adjustments")
    op.drop_table("member_charges")
    op.drop_table("payments")
    op.drop_table("opening_balances")
    op.drop_table("billing_cycles")
    op.drop_table("reconciliation_runs")
    op.drop_table("members")
    op.drop_table("job_locks")
    op.drop_table("fx_rates")

    op.create_table(
        "fx_rates",
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("usd_rub", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("rate_date"),
    )
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("active_from", sa.Date(), nullable=False),
        sa.Column("active_to", sa.Date(), nullable=True),
        sa.Column("counted_in_denominator", sa.Boolean(), nullable=False),
        sa.Column("billable_after_cutover", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_name"),
    )
    op.create_table(
        "legacy_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("opening_balance_rub", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("source_usd_balance", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("rub_paid", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("fx_locked", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("usd_credit", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("edit_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "charge_cycles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cycle_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("subscription_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("subscription_rub", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("counted_active", sa.Integer(), nullable=True),
        sa.Column("billed_active", sa.Integer(), nullable=True),
        sa.Column("total_billed_rub", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("owner_subsidy_rub", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("fx_locked", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_date"),
    )
    op.create_table(
        "posted_charges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("charge_date", sa.Date(), nullable=False),
        sa.Column("active_count", sa.Integer(), nullable=False),
        sa.Column("subscription_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("charge_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("fx_locked", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("charge_rub", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("edit_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cycle_id"], ["charge_cycles.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "member_id", name="uq_cycle_member"),
    )
