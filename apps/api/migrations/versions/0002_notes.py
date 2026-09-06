"""Prepare optional team notes without adding an administrative API."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("notes", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("leads", "notes")
