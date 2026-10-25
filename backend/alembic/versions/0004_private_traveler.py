"""Add encrypted traveler details without altering existing trip/recovery tables."""
from alembic import op
import sqlalchemy as sa

revision = "0004_private_traveler"
down_revision = "0003_domino_rescue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("traveler_vaults",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("salt", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("revision", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table("traveler_vault_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_traveler_vault_audit_user_id", "traveler_vault_audit", ["user_id"])


def downgrade():
    raise RuntimeError("Destructive downgrades are disabled. Use a reviewed forward migration.")
