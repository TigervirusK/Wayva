"""Add simulated reservation recovery without rebuilding existing tables."""
from alembic import op
import sqlalchemy as sa

revision = "0003_domino_rescue"
down_revision = "0002_itinerary_proposals"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("itinerary_item_id", sa.String(36), sa.ForeignKey("itinerary_items.id", ondelete="SET NULL")),
        sa.Column("key", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("booking_reference", sa.String(80), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("kind IN ('flight','pickup','hotel','tour')", name="ck_reservation_kind"),
        sa.CheckConstraint("status IN ('confirmed','at_risk','cancelled')", name="ck_reservation_status"),
        sa.CheckConstraint("end_at > start_at", name="ck_reservation_times"),
        sa.CheckConstraint("estimated_cost >= 0", name="ck_reservation_cost"),
    )
    op.create_index("ix_reservations_trip_id", "reservations", ["trip_id"])
    op.create_index("ix_reservation_trip_key", "reservations", ["trip_id", "key"], unique=True)
    op.create_table("reservation_dependencies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("reservations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("reservations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.CheckConstraint("source_id != target_id", name="ck_dependency_not_self"),
    )
    op.create_index("ix_reservation_dependencies_trip_id", "reservation_dependencies", ["trip_id"])
    op.create_index("ix_dependency_pair", "reservation_dependencies", ["source_id", "target_id"], unique=True)
    op.create_table("disruption_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reservation_id", sa.String(36), sa.ForeignKey("reservations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('open','resolved')", name="ck_disruption_status"),
    )
    op.create_index("ix_disruption_events_trip_id", "disruption_events", ["trip_id"])
    op.create_table("recovery_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("disruption_id", sa.String(36), sa.ForeignKey("disruption_events.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("strategy", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("base_fingerprint", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.String(300)),
        sa.CheckConstraint("status IN ('pending','applied','failed','stale')", name="ck_recovery_status"),
        sa.CheckConstraint("strategy IN ('fastest','cheapest','balanced')", name="ck_recovery_strategy"),
    )
    op.create_index("ix_recovery_plans_trip_id", "recovery_plans", ["trip_id"])
    op.create_index("ix_recovery_plans_disruption_id", "recovery_plans", ["disruption_id"])
    op.create_table("rescue_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("trips.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("disruption_id", sa.String(36), sa.ForeignKey("disruption_events.id", ondelete="RESTRICT")),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("recovery_plans.id", ondelete="RESTRICT")),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rescue_audit_logs_trip_id", "rescue_audit_logs", ["trip_id"])


def downgrade():
    raise RuntimeError("Destructive downgrades are disabled. Use a reviewed forward migration.")
