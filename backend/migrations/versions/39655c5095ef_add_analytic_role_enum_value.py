"""add analytic role enum value

The Analytic role was added to shared.enums.Role in an earlier revision, but no
migration ever added it to Postgres's "role" enum type — it only had
manager/teamlead/admin/owner. Creating or assigning an analytic-role user has
been failing with "invalid input value for enum role: analytic" ever since.

Revision ID: 39655c5095ef
Revises: 16779690e123
Create Date: 2026-09-05 02:28:28.488763

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '39655c5095ef'
down_revision: Union[str, Sequence[str], None] = '16779690e123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'analytic'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums — 'analytic' stays in role on downgrade.
    pass
