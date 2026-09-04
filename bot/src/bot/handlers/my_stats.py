from datetime import date

import httpx
from aiogram import F, Router
from aiogram.types import Message

from bot.config import auth_headers, settings

router = Router(name="my_stats")


@router.message(F.text == "Моя статистика")
async def my_stats(message: Message, current_user: dict) -> None:
    today = date.today()
    period_start = today.replace(day=1)

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.get(
            "/stats/me",
            headers=auth_headers(current_user["telegram_id"]),
            params={"period_start": period_start.isoformat(), "period_end": today.isoformat()},
        )

    if response.status_code != 200:
        await message.answer("Не удалось получить статистику.")
        return

    stats = response.json()
    rank_text = f"{stats['rank']} из {stats['team_size']}" if stats["rank"] else "нет команды"
    text = (
        f"Депозитов за месяц: {stats['deposit_count']}\n"
        f"Сумма: {stats['total_amount']}\n"
        f"Место в команде: {rank_text}"
    )
    if stats["commission_rate"] is not None:
        text += f"\nКомиссия ({stats['commission_rate']}%): {stats['commission_amount']}"
    await message.answer(text)
