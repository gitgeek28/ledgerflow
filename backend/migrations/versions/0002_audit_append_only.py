"""audit_events is append-only: reject UPDATE and DELETE at the database level

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_events_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only (% blocked)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_events_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_immutable()")
