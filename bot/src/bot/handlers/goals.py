from datetime import date
from decimal import Decimal, InvalidOperation

import httpx
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.config import settings

router = Router(name="goals")


def _bar(percent: float, width: int = 10) -> str:
    filled = min(width, max(0, round(percent / 100 * width)))
    return "▓" * filled + "░" * (width - filled)


@router.message(Command("goal"))
async def goal_progress(message: Message, current_user: dict) -> None:
    role = current_user["role"]
    if role == "manager":
        scope, scope_id = "user", current_user["id"]
    elif role == "teamlead":
        if not current_user["team_id"]:
            await message.answer("Вы не привязаны ни к одной команде.")
            return
        scope, scope_id = "team", current_user["team_id"]
    else:
        await message.answer("Используйте API (GET /goals/progress) — команда не привязана к конкретной цели.")
        return

    period = date.today().replace(day=1).isoformat()
    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.get(
            "/goals/progress",
            headers={"X-Telegram-User-Id": str(current_user["telegram_id"])},
            params={"scope": scope, "scope_id": scope_id, "period": period},
        )

    if response.status_code == 404:
        await message.answer("На этот месяц план не задан.")
        return
    if response.status_code != 200:
        await message.answer("Не удалось получить прогресс по плану.")
        return

    data = response.json()
    percent = min(data["percent"], 999.0)
    text = (
        f"{_bar(percent)} {percent:.0f}%\n"
        f"{data['current_amount']} / {data['goal']['target_amount']}"
    )
    if data["behind_pace"]:
        text += "\n⚠️ Отстаём от графика к середине периода."
    await message.answer(text)


@router.message(Command("set_goal"))
async def set_goal(message: Message, command: CommandObject, current_user: dict) -> None:
    if current_user["role"] != "teamlead":
        await message.answer("Задать план команды может только тимлид. Использование: /set_goal <сумма>")
        return
    if not current_user["team_id"]:
        await message.answer("Вы не привязаны ни к одной команде.")
        return
    if not command.args:
        await message.answer("Использование: /set_goal <сумма>")
        return

    try:
        amount = Decimal(command.args.strip().replace(",", "."))
    except InvalidOperation:
        await message.answer("Сумма должна быть числом, например 10000")
        return
    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля")
        return

    period = date.today().replace(day=1).isoformat()
    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.post(
            "/goals",
            headers={"X-Telegram-User-Id": str(current_user["telegram_id"])},
            json={
                "scope": "team",
                "scope_id": current_user["team_id"],
                "period": period,
                "target_amount": str(amount),
            },
        )

    if response.status_code == 201:
        await message.answer(f"План команды на месяц: {amount}.")
    else:
        await message.answer(f"Не удалось задать план: {response.text}")
