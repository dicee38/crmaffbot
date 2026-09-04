import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import ActionType
from shared.models import MopAction


async def find_duplicate(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    action_type: ActionType,
    player_id: str | None,
    amount: Decimal | None,
    occurred_at: datetime,
    window_minutes: int,
    external_id: str | None,
) -> MopAction | None:
    if external_id:
        result = await db.execute(
            select(MopAction).where(MopAction.org_id == org_id, MopAction.external_id == external_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

    if not player_id:
        return None

    window = timedelta(minutes=window_minutes)
    result = await db.execute(
        select(MopAction).where(
            MopAction.org_id == org_id,
            MopAction.action_type == action_type,
            MopAction.player_id == player_id,
            MopAction.amount == amount,
            MopAction.deleted_at.is_(None),
            MopAction.created_at >= occurred_at - window,
            MopAction.created_at <= occurred_at + window,
        )
    )
    return result.scalars().first()
