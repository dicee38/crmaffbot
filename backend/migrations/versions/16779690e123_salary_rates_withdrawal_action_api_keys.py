"""salary rates, withdrawal action, api keys

Revision ID: 16779690e123
Revises: 3f8243572b2f
Create Date: 2026-09-05 02:08:02.187152

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "16779690e123"
down_revision: Union[str, Sequence[str], None] = "3f8243572b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New action type: "withdrawal" — reduces the manager's cashbox but is not commissioned.
    op.execute("ALTER TYPE action_type ADD VALUE IF NOT EXISTS 'withdrawal'")

    # Replace the flat commission_rate with two rates — salary = fd_rate% of FD total
    # + rd_rate% of RD total for the period. Existing commission_rate (if set) becomes
    # the migrated user's fd_commission_rate; there's no historical equivalent for RD.
    op.add_column("users", sa.Column("fd_commission_rate", sa.Numeric(5, 2), nullable=True))
    op.add_column("users", sa.Column("rd_commission_rate", sa.Numeric(5, 2), nullable=True))
    op.execute(
        """
        UPDATE users
        SET fd_commission_rate = COALESCE(commission_rate, 10.00),
            rd_commission_rate = 7.00
        """
    )
    op.alter_column("users", "fd_commission_rate", nullable=False, server_default="10.00")
    op.alter_column("users", "rd_commission_rate", nullable=False, server_default="7.00")
    op.drop_column("users", "commission_rate")

    # API keys for non-Telegram integrations (website widgets, Chatterfy, ...).
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_table("api_keys")

    op.add_column("users", sa.Column("commission_rate", sa.Numeric(5, 2), nullable=True))
    op.execute("UPDATE users SET commission_rate = fd_commission_rate")
    op.drop_column("users", "rd_commission_rate")
    op.drop_column("users", "fd_commission_rate")

    # Postgres has no DROP VALUE for enums — 'withdrawal' stays in action_type on downgrade.
