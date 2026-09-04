from datetime import date

import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from bot.config import settings

router = Router(name="reports")


@router.message(Command("export"))
async def export_report(message: Message, current_user: dict) -> None:
    role = current_user["role"]
    if role not in ("teamlead", "admin", "owner"):
        await message.answer("Экспорт недоступен для вашей роли.")
        return
    if role == "teamlead" and not current_user["team_id"]:
        await message.answer("Вы не привязаны ни к одной команде.")
        return

    today = date.today()
    period_start = today.replace(day=1)
    params = {"period_start": period_start.isoformat(), "period_end": today.isoformat()}
    if role == "teamlead":
        params["scope"] = "team"
        params["scope_id"] = current_user["team_id"]
    else:
        params["scope"] = "company"

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.get(
            "/reports/export",
            headers={"X-Telegram-User-Id": str(current_user["telegram_id"])},
            params=params,
        )

    if response.status_code != 200:
        await message.answer(f"Не удалось сформировать отчёт: {response.text}")
        return

    filename = f"deposits_{params['scope']}_{period_start}_{today}.xlsx"
    await message.answer_document(BufferedInputFile(response.content, filename=filename))
