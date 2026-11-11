"""Sequence for human-friendly invoice references (LF-000123)

Revision ID: 0004
Revises: 0003
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS invoice_reference_seq START 1001")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS invoice_reference_seq")
