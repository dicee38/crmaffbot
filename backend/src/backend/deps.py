from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api_keys import hash_api_key
from backend.config import settings
from backend.telegram_auth import InvalidInitData, verify_init_data
from shared.db import make_engine, make_session_factory
from shared.enums import UserStatus
from shared.models import ApiKey, User

engine = make_engine(settings.database_url)
SessionFactory = make_session_factory(engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        yield session


def _resolve_telegram_id(request: Request) -> int:
    init_data = request.headers.get("X-Telegram-Init-Data")
    if init_data:
        # Mini App path: the browser can't be trusted, so the request must carry data
        # cryptographically signed by Telegram itself.
        try:
            user_payload = verify_init_data(init_data, settings.bot_token or "")
        except InvalidInitData as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid init data: {exc}") from exc
        return int(user_payload["id"])

    # Bot path: our own aiogram process is the only holder of internal_api_secret.
    if request.headers.get("X-Internal-Secret") != settings.internal_api_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid credentials")

    raw_id = request.headers.get("X-Telegram-User-Id")
    if raw_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Telegram-User-Id")
    try:
        return int(raw_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid X-Telegram-User-Id") from exc


async def _resolve_user_from_api_key(request: Request, db: AsyncSession) -> User | None:
    # External integrations (website widgets, Chatterfy, ...) authenticate as a service
    # account via a static Bearer key instead of Telegram — no telegram_id involved.
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    key = auth_header.removeprefix("Bearer ").strip()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == hash_api_key(key), ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    api_key.last_used_at = datetime.now(timezone.utc)
    user = await db.get(User, api_key.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown or blocked user")
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    api_key_user = await _resolve_user_from_api_key(request, db)
    if api_key_user is not None:
        await db.commit()
        return api_key_user

    telegram_id = _resolve_telegram_id(request)
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown or blocked user")
    return user
