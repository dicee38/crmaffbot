from datetime import date

import httpx
from aiogram import F, Router
from aiogram.types import Message

from bot.config import settings

router = Router(name="team_top")


async def _send_top(message: Message, current_user: dict, path: str) -> None:
    today = date.today()
    period_start = today.replace(day=1)

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.get(
            path,
            headers={"X-Telegram-User-Id": str(current_user["telegram_id"])},
            params={"period_start": period_start.isoformat(), "period_end": today.isoformat()},
        )

    if response.status_code != 200:
        await message.answer("Недоступно для вашей роли.")
        return

    entries = response.json()
    if not entries:
        await message.answer("Пока нет данных за период.")
        return

    lines = [
        f"{e['rank']}. {e['full_name']} — {e['total_amount']} ({e['deposit_count']} деп.)"
        for e in entries
    ]
    await message.answer("\n".join(lines))


@router.message(F.text == "Топ команды")
async def team_top(message: Message, current_user: dict) -> None:
    await _send_top(message, current_user, "/stats/top/team")


@router.message(F.text == "Топ компании")
async def company_top(message: Message, current_user: dict) -> None:
    await _send_top(message, current_user, "/stats/top/company")
