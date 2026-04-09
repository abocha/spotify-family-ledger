"""Add read-path indexes for remote latency reduction.

Revision ID: 77d4f6e2c9ab
Revises: 5f2e4f5d30ea
Create Date: 2026-04-09 16:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "77d4f6e2c9ab"
down_revision: Union[str, Sequence[str], None] = "5f2e4f5d30ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_reconciliation_runs_started_at", "reconciliation_runs", ["started_at"])
    op.create_index("ix_member_charges_member_id", "member_charges", ["member_id"])
    op.create_index("ix_member_charges_charge_date", "member_charges", ["charge_date"])
    op.create_index("ix_payments_member_id", "payments", ["member_id"])
    op.create_index("ix_payments_payment_date", "payments", ["payment_date"])
    op.create_index("ix_adjustments_member_id", "adjustments", ["member_id"])
    op.create_index("ix_adjustments_effective_date", "adjustments", ["effective_date"])


def downgrade() -> None:
    op.drop_index("ix_adjustments_effective_date", table_name="adjustments")
    op.drop_index("ix_adjustments_member_id", table_name="adjustments")
    op.drop_index("ix_payments_payment_date", table_name="payments")
    op.drop_index("ix_payments_member_id", table_name="payments")
    op.drop_index("ix_member_charges_charge_date", table_name="member_charges")
    op.drop_index("ix_member_charges_member_id", table_name="member_charges")
    op.drop_index("ix_reconciliation_runs_started_at", table_name="reconciliation_runs")
