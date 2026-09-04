"""deposit change requests

Revision ID: 1df89ed759d7
Revises: 4b3a32e71980
Create Date: 2026-09-04 18:30:04.312704

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1df89ed759d7"
down_revision: Union[str, Sequence[str], None] = "4b3a32e71980"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deposit_change_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deposit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deposits.id"), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "action",
            postgresql.ENUM("create", "update", "delete", name="audit_action", create_type=False),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="change_request_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_deposit_change_requests_status", "deposit_change_requests", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_deposit_change_requests_status", table_name="deposit_change_requests")
    op.drop_table("deposit_change_requests")

    bind = op.get_bind()
    sa.Enum(name="change_request_status").drop(bind, checkfirst=True)
