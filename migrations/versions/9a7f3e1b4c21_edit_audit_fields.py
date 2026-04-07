"""edit audit fields

Revision ID: 9a7f3e1b4c21
Revises: 4eec9bcdad53
Create Date: 2026-04-07 18:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a7f3e1b4c21"
down_revision: Union[str, Sequence[str], None] = "4eec9bcdad53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("edited_at", sa.DateTime(), nullable=True))
    op.add_column("payments", sa.Column("edit_reason", sa.Text(), nullable=True))
    op.add_column("posted_charges", sa.Column("edited_at", sa.DateTime(), nullable=True))
    op.add_column("posted_charges", sa.Column("edit_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("posted_charges", "edit_reason")
    op.drop_column("posted_charges", "edited_at")
    op.drop_column("payments", "edit_reason")
    op.drop_column("payments", "edited_at")
