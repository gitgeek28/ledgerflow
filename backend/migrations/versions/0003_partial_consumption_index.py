"""Only ACTIVE consumptions must be unique per invoice line; released rows are kept as history.

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_consumption_invoice_line", "po_line_consumptions", type_="unique")
    op.execute("CREATE UNIQUE INDEX uq_consumption_active_invoice_line ON po_line_consumptions (invoice_line_id) "
               "WHERE status IN ('RESERVED', 'APPROVED')")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_consumption_active_invoice_line")
    op.create_unique_constraint("uq_consumption_invoice_line", "po_line_consumptions", ["invoice_line_id"])
