from datetime import date

import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import auth_headers, settings

router = Router(name="team_top")


def _period() -> tuple[str, str]:
    today = date.today()
    return today.replace(day=1).isoformat(), today.isoformat()


async def _fetch_top(telegram_id: int, path: str, params: dict) -> tuple[int, list | str]:
    period_start, period_end = _period()
    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.get(
            path,
            headers=auth_headers(telegram_id),
            params={"period_start": period_start, "period_end": period_end, **params},
        )
    if response.status_code != 200:
        return response.status_code, response.text
    return response.status_code, response.json()


def _format_top(entries: list) -> str:
    if not entries:
        return "Пока нет данных за период."
    return "\n".join(
        f"{e['rank']}. {e['full_name']} — {e['total_amount']} ({e['deposit_count']} деп.)"
        for e in entries
    )


@router.message(F.text == "Топ команды")
async def team_top(message: Message, current_user: dict) -> None:
    if current_user["role"] == "teamlead":
        status_code, data = await _fetch_top(current_user["telegram_id"], "/stats/top/team", {})
        if status_code != 200:
            await message.answer("Недоступно для вашей роли.")
            return
        await message.answer(_format_top(data))
        return

    # admin/owner have no team of their own — let them pick which team to view.
    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.get(
            "/users/teams", headers=auth_headers(current_user["telegram_id"])
        )

    if response.status_code != 200:
        await message.answer("Недоступно для вашей роли.")
        return

    teams = response.json()
    if not teams:
        await message.answer("Команды ещё не созданы.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=team["name"], callback_data=f"team_top:{team['id']}")]
            for team in teams
        ]
    )
    await message.answer("Выберите команду:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("team_top:"))
async def team_top_selected(callback: CallbackQuery, current_user: dict) -> None:
    team_id = callback.data.split(":", maxsplit=1)[1]
    status_code, data = await _fetch_top(
        current_user["telegram_id"], "/stats/top/team", {"team_id": team_id}
    )
    await callback.answer()
    if status_code != 200:
        await callback.message.answer("Недоступно для вашей роли.")
        return
    await callback.message.answer(_format_top(data))


@router.message(F.text == "Топ компании")
async def company_top(message: Message, current_user: dict) -> None:
    status_code, data = await _fetch_top(current_user["telegram_id"], "/stats/top/company", {})
    if status_code != 200:
        await message.answer("Недоступно для вашей роли.")
        return
    await message.answer(_format_top(data))
