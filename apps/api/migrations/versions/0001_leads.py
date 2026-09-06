"""Initial submitted briefs and private file metadata (no visitor records)."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("name", sa.String(120)),
        sa.Column("contact_method", sa.String(8), nullable=False),
        sa.Column("contact", sa.String(180), nullable=False),
        sa.Column("contact_normalized", sa.String(180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("product_link", sa.String(1000)),
        sa.Column("no_product", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("browser_hash", sa.String(64), unique=True),
        sa.Column("idempotency_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("consent_version", sa.String(40), nullable=False),
        sa.CheckConstraint("contact_method IN ('email', 'telegram')", name="contact_method_valid"),
        sa.CheckConstraint("language IN ('en', 'es', 'ca')", name="language_valid"),
        sa.CheckConstraint("status = 'new'", name="status_valid"),
        sa.CheckConstraint("consent", name="consent_required"),
        sa.CheckConstraint("char_length(message) BETWEEN 12 AND 5000", name="message_length"),
    )
    op.create_index("ix_leads_created", "leads", ["created_at"])
    op.create_index("ix_leads_status_created", "leads", ["status", "created_at"])
    op.create_index("ix_leads_contact", "leads", ["contact_method", "contact_normalized"])
    op.create_table(
        "lead_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lead_id", sa.Uuid(), sa.ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("storage_key", sa.String(100), nullable=False, unique=True),
        sa.Column("filename", sa.String(240), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("size_bytes BETWEEN 1 AND 10485760", name="file_size_valid"),
    )
    op.create_index("ix_lead_files_lead_id", "lead_files", ["lead_id"])


def downgrade():
    op.drop_table("lead_files")
    op.drop_table("leads")
