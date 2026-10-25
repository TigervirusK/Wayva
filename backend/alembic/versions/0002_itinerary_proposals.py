"""Persist itinerary suggestions separately from approved trip activities."""
from alembic import op
import sqlalchemy as sa

revision = "0002_itinerary_proposals"
down_revision = "0001_saved_trips"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("base_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','approved','rejected','stale')", name="ck_proposals_status"),
        sa.CheckConstraint("mode IN ('demo','openai')", name="ck_proposals_mode"),
    )
    op.create_index("ix_proposals_trip_id", "proposals", ["trip_id"])


def downgrade():
    raise RuntimeError("Destructive downgrades are disabled. Use a reviewed forward migration.")
