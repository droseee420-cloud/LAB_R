"""Separate administrative identities/sessions and optimistic note versions."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("notes_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("admins", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("username", sa.String(80), nullable=False, unique=True),
                    sa.Column("password_hash", sa.Text(), nullable=False),
                    sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                    sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("admin_sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
                    sa.Column("admin_id", sa.Uuid(), sa.ForeignKey("admins.id", ondelete="RESTRICT"), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_admin_sessions_admin_id", "admin_sessions", ["admin_id"])
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])


def downgrade():
    op.drop_table("admin_sessions")
    op.drop_table("admins")
    op.drop_column("leads", "notes_version")
