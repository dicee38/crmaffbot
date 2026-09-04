from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.config import settings


class AuthMiddleware(BaseMiddleware):
    """Резолвит роль пользователя по telegram_id через backend перед каждым апдейтом (ТЗ §7.1:
    права проверяются по факту записи в users, а не по знанию команды)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        async with httpx.AsyncClient(base_url=settings.backend_url) as client:
            response = await client.get(
                "/users/me", headers={"X-Telegram-User-Id": str(tg_user.id)}
            )

        if response.status_code != 200:
            return None

        data["current_user"] = response.json()
        return await handler(event, data)
