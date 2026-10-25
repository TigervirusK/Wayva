"""Add local profiles, owned trips, and itinerary items without changing existing tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_saved_trips"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("communication_style", sa.String(20), nullable=False, server_default="friendly"),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("communication_style IN ('friendly','professional','enthusiastic','concise')", name="ck_users_style"),
    )
    op.create_index("ix_users_token_hash", "users", ["token_hash"], unique=True)
    op.create_table(
        "trips",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("destination", sa.String(120), nullable=False),
        sa.Column("departure_location", sa.String(120), nullable=False, server_default=""),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("travelers", sa.Integer(), nullable=False),
        sa.Column("budget", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("end_date >= start_date AND julianday(end_date) - julianday(start_date) <= 366", name="ck_trips_dates"),
        sa.CheckConstraint("travelers >= 1 AND travelers <= 50", name="ck_trips_travelers"),
        sa.CheckConstraint("budget >= 0 AND budget <= 10000000", name="ck_trips_budget"),
        sa.CheckConstraint("currency IN ('USD','EUR','GBP','JPY','CAD','AUD','INR')", name="ck_trips_currency"),
        sa.CheckConstraint("status IN ('planned','active','completed')", name="ck_trips_status"),
    )
    op.create_index("ix_trips_owner_id", "trips", ["owner_id"])
    op.create_table(
        "itinerary_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("location", sa.String(200), nullable=False, server_default=""),
        sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.CheckConstraint("end_time > start_time", name="ck_itinerary_times"),
        sa.CheckConstraint("estimated_cost >= 0 AND estimated_cost <= 10000000", name="ck_itinerary_cost"),
        sa.CheckConstraint("item_type IN ('activity','food','transport','accommodation','other')", name="ck_itinerary_type"),
        sa.CheckConstraint("status IN ('planned','cancelled')", name="ck_itinerary_status"),
    )
    op.create_index("ix_itinerary_items_trip_id", "itinerary_items", ["trip_id"])
    op.create_index("ix_itinerary_items_trip_schedule", "itinerary_items", ["trip_id", "date", "start_time"])


def downgrade():
    raise RuntimeError("Destructive downgrades are disabled. Use a reviewed forward migration.")
