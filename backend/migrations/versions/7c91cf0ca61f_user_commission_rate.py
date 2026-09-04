"""user commission rate

Revision ID: 7c91cf0ca61f
Revises: 1df89ed759d7
Create Date: 2026-09-04 20:14:15.135441

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c91cf0ca61f"
down_revision: Union[str, Sequence[str], None] = "1df89ed759d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("commission_rate", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "commission_rate")
