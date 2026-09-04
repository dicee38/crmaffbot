import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Deposit


async def find_duplicate(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    client_ref: str,
    amount: Decimal,
    occurred_at: datetime,
    window_minutes: int,
    external_id: str | None,
) -> Deposit | None:
    if external_id:
        result = await db.execute(
            select(Deposit).where(Deposit.org_id == org_id, Deposit.external_id == external_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

    window = timedelta(minutes=window_minutes)
    result = await db.execute(
        select(Deposit).where(
            Deposit.org_id == org_id,
            Deposit.client_ref == client_ref,
            Deposit.amount == amount,
            Deposit.deleted_at.is_(None),
            Deposit.created_at >= occurred_at - window,
            Deposit.created_at <= occurred_at + window,
        )
    )
    return result.scalars().first()
