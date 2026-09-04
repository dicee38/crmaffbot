"""generalize deposits to mop actions

Revision ID: 3f8243572b2f
Revises: 7c91cf0ca61f
Create Date: 2026-09-05 01:44:46.908272

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f8243572b2f"
down_revision: Union[str, Sequence[str], None] = "7c91cf0ca61f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- new tables (ТЗ §11.4/§6) ---
    op.create_table(
        "platforms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("adapter_key", sa.String(), nullable=False),
        sa.Column("webhook_secret", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "slug", name="uq_platforms_org_slug"),
    )

    op.create_table(
        "channel_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
    )

    op.create_table(
        "channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("platform_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platforms.id"), nullable=False),
        sa.Column(
            "channel_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("channel_groups.id"), nullable=True
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("external_code", sa.String(), nullable=True),
    )

    op.create_table(
        "mop_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "action_type",
            sa.Enum("registration", "first_deposit", "repeat_deposit", "lead", name="action_type"),
            nullable=False,
        ),
        sa.Column("mop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("channels.id"), nullable=True),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("lead_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "source", sa.Enum("manual", "affiliate_api", name="action_source"), nullable=False
        ),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("confirmed", "pending_review", name="action_status"),
            nullable=False,
            server_default="confirmed",
        ),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("org_id", "external_id", name="uq_mop_actions_org_external_id"),
    )
    op.create_index("ix_mop_actions_org_mop_created", "mop_actions", ["org_id", "mop_id", "created_at"])
    op.create_index(
        "ix_mop_actions_org_channel_created", "mop_actions", ["org_id", "channel_id", "created_at"]
    )

    op.create_table(
        "action_events_raw",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("platform_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platforms.id"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "matched_action_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mop_actions.id"), nullable=True
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "action_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mop_actions.id"), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "action", postgresql.ENUM("create", "update", "delete", name="audit_action", create_type=False),
            nullable=False,
        ),
        sa.Column("diff", postgresql.JSONB(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "action_change_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mop_actions.id"), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "action", postgresql.ENUM("create", "update", "delete", name="audit_action", create_type=False),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "approved", "rejected", name="change_request_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_action_change_requests_status", "action_change_requests", ["status"])

    # --- data migration: preserve everything that exists in the v0.1 deposit tables ---

    # One placeholder platform per org that has raw affiliate events, so those events
    # (and their matched_action_id) keep a valid platform_id under the new NOT NULL FK.
    op.execute(
        """
        INSERT INTO platforms (id, org_id, slug, name, adapter_key, webhook_secret, is_active, created_at)
        SELECT gen_random_uuid(), org_id, 'legacy', 'Legacy (auto-migrated)', 'none', md5(random()::text), false, now()
        FROM (SELECT DISTINCT org_id FROM deposit_events_raw) sub
        """
    )

    # Deposits become "first_deposit" actions — v0.1 had no first/repeat distinction, and
    # client_ref (free-text) becomes player_id (closest available field pre-migration).
    op.execute(
        """
        INSERT INTO mop_actions
            (id, org_id, action_type, mop_id, channel_id, player_id, amount, currency,
             lead_count, source, external_id, status, warnings, created_by, created_at, deleted_at)
        SELECT id, org_id, 'first_deposit', manager_id, NULL, client_ref, amount, currency,
               1, source::text::action_source, external_id, status::text::action_status,
               NULL, manager_id, created_at, deleted_at
        FROM deposits
        """
    )

    op.execute(
        """
        INSERT INTO action_audit_log (id, action_id, changed_by, action, diff, changed_at)
        SELECT id, deposit_id, changed_by, action, diff, changed_at FROM deposit_audit_log
        """
    )

    op.execute(
        """
        INSERT INTO action_change_requests
            (id, action_id, requested_by, action, payload, status, reviewed_by, created_at, reviewed_at)
        SELECT id, deposit_id, requested_by, action, payload, status, reviewed_by, created_at, reviewed_at
        FROM deposit_change_requests
        """
    )

    op.execute(
        """
        INSERT INTO action_events_raw (id, org_id, platform_id, payload, matched_action_id, received_at)
        SELECT der.id, der.org_id, p.id, der.payload, der.matched_deposit_id, der.received_at
        FROM deposit_events_raw der
        JOIN platforms p ON p.org_id = der.org_id AND p.slug = 'legacy'
        """
    )

    # --- drop v0.1 tables (children before parent) and their now-unused enum types ---
    op.drop_table("deposit_change_requests")
    op.drop_table("deposit_audit_log")
    op.drop_table("deposit_events_raw")
    op.drop_index("ix_deposits_org_manager_created", table_name="deposits")
    op.drop_table("deposits")

    bind = op.get_bind()
    sa.Enum(name="deposit_status").drop(bind, checkfirst=True)
    sa.Enum(name="deposit_source").drop(bind, checkfirst=True)


def downgrade() -> None:
    op.drop_index("ix_action_change_requests_status", table_name="action_change_requests")
    op.drop_table("action_change_requests")
    op.drop_table("action_audit_log")
    op.drop_table("action_events_raw")
    op.drop_index("ix_mop_actions_org_channel_created", table_name="mop_actions")
    op.drop_index("ix_mop_actions_org_mop_created", table_name="mop_actions")
    op.drop_table("mop_actions")
    op.drop_table("channels")
    op.drop_table("channel_groups")
    op.drop_table("platforms")

    bind = op.get_bind()
    for enum_name in ("action_status", "action_source", "action_type"):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)

    # Note: this downgrade does not recreate deposits/deposit_* tables or restore their
    # data — v0.1 tables are gone once upgrade() has run. Restore from a DB backup instead.
