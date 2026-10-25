"""Add accounts linked to existing owners; no user/trip/vault rewrites or seeding."""
from alembic import op
import sqlalchemy as sa

revision = "0005_accounts"
down_revision = "0004_private_traveler"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("accounts",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("username", sa.String(30), nullable=False),
        sa.Column("password_hash", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_accounts_username", "accounts", ["username"], unique=True)
    op.create_table("account_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("accounts.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_account_sessions_user_id", "account_sessions", ["user_id"])
    op.create_index("ix_account_sessions_token_hash", "account_sessions", ["token_hash"], unique=True)
    op.create_table("account_attempts",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),
    )
    op.create_table("account_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_account_audit_user_id", "account_audit", ["user_id"])


def downgrade():
    raise RuntimeError("Destructive downgrades are disabled. Use a reviewed forward migration.")
