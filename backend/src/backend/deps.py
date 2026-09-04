from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from shared.db import make_engine, make_session_factory
from shared.enums import UserStatus
from shared.models import User

engine = make_engine(settings.database_url)
SessionFactory = make_session_factory(engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        yield session


async def get_current_user(
    x_telegram_user_id: int = Header(..., alias="X-Telegram-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.telegram_id == x_telegram_user_id))
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown or blocked user")
    return user
