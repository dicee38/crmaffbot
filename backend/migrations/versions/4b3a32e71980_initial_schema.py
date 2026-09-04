"""initial schema

Revision ID: 4b3a32e71980
Revises:
Create Date: 2026-09-04 16:54:43.833047

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b3a32e71980"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("teamlead_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("manager", "teamlead", "admin", "owner", name="role"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "blocked", name="user_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    # FK cycle: teams.teamlead_id -> users.id, users.team_id -> teams.id. Added after both tables exist.
    op.create_foreign_key(
        "fk_teams_teamlead_id", "teams", "users", ["teamlead_id"], ["id"]
    )

    op.create_table(
        "deposits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_ref", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
        sa.Column(
            "source",
            sa.Enum("manual", "affiliate_api", name="deposit_source"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("confirmed", "pending_review", name="deposit_status"),
            nullable=False,
            server_default="confirmed",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("org_id", "external_id", name="uq_deposits_org_external_id"),
    )
    op.create_index(
        "ix_deposits_org_manager_created", "deposits", ["org_id", "manager_id", "created_at"]
    )

    op.create_table(
        "deposit_events_raw",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "matched_deposit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deposits.id"), nullable=True
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "deposit_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deposit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deposits.id"), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "action",
            sa.Enum("create", "update", "delete", name="audit_action"),
            nullable=False,
        ),
        sa.Column("diff", postgresql.JSONB(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("scope", sa.Enum("user", "team", name="goal_scope"), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("target_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("goals")
    op.drop_table("deposit_audit_log")
    op.drop_table("deposit_events_raw")
    op.drop_index("ix_deposits_org_manager_created", table_name="deposits")
    op.drop_table("deposits")
    op.drop_constraint("fk_teams_teamlead_id", "teams", type_="foreignkey")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
    op.drop_table("teams")
    op.drop_table("organizations")

    bind = op.get_bind()
    for enum_name in ("goal_scope", "audit_action", "deposit_status", "deposit_source", "user_status", "role"):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
