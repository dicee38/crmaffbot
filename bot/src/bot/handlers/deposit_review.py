from datetime import date, timedelta

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import auth_headers, settings

router = Router(name="deposit_review")


@router.message(Command("my_deposits"))
async def my_deposits(message: Message, current_user: dict) -> None:
    period_start = (date.today() - timedelta(days=30)).isoformat()
    period_end = date.today().isoformat()

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.get(
            "/deposits",
            headers=auth_headers(current_user["telegram_id"]),
            params={"period_start": period_start, "period_end": period_end, "limit": 10},
        )

    if response.status_code != 200:
        await message.answer("Не удалось получить список депозитов.")
        return

    deposits = response.json()
    if not deposits:
        await message.answer("За последние 30 дней депозитов нет.")
        return

    for deposit in deposits:
        text = f"{deposit['client_ref']} — {deposit['amount']} {deposit['currency']}"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🗑 Запросить удаление", callback_data=f"req_del:{deposit['id']}")]
            ]
        )
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("req_del:"))
async def request_delete(callback: CallbackQuery, current_user: dict) -> None:
    deposit_id = callback.data.split(":", maxsplit=1)[1]

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.post(
            f"/deposits/{deposit_id}/change-requests",
            headers=auth_headers(current_user["telegram_id"]),
            json={"action": "delete"},
        )

    await callback.answer()
    if response.status_code == 201:
        await callback.message.edit_text(f"{callback.message.text}\n\n⏳ Запрос на удаление отправлен на согласование.")
    else:
        await callback.message.answer(f"Не удалось отправить запрос: {response.text}")


@router.message(Command("pending"))
async def pending_requests(message: Message, current_user: dict) -> None:
    if current_user["role"] not in ("teamlead", "admin"):
        await message.answer("Согласование доступно только тимлиду и админу.")
        return

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.get(
            "/change-requests",
            headers=auth_headers(current_user["telegram_id"]),
            params={"status": "pending"},
        )

    if response.status_code != 200:
        await message.answer("Не удалось получить список запросов.")
        return

    requests = response.json()
    if not requests:
        await message.answer("Нет запросов, ожидающих согласования.")
        return

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        headers = auth_headers(current_user["telegram_id"])
        for req in requests:
            deposit_response = await client.get(f"/deposits/{req['deposit_id']}", headers=headers)
            deposit = deposit_response.json() if deposit_response.status_code == 200 else None

            action_label = "правку" if req["action"] == "update" else "удаление"
            deposit_line = (
                f"{deposit['client_ref']} — {deposit['amount']} {deposit['currency']}"
                if deposit
                else "депозит не найден"
            )
            text = f"Запрос на {action_label}: {deposit_line}"
            if req["action"] == "update" and req["payload"]:
                text += f"\nНовые значения: {req['payload']}"

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"cr_ok:{req['id']}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"cr_no:{req['id']}"),
                    ]
                ]
            )
            await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("cr_ok:") | F.data.startswith("cr_no:"))
async def review_request(callback: CallbackQuery, current_user: dict) -> None:
    action, request_id = callback.data.split(":", maxsplit=1)
    endpoint = "approve" if action == "cr_ok" else "reject"

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.post(
            f"/change-requests/{request_id}/{endpoint}",
            headers=auth_headers(current_user["telegram_id"]),
        )

    await callback.answer()
    if response.status_code == 200:
        verdict = "подтверждён" if endpoint == "approve" else "отклонён"
        await callback.message.edit_text(f"{callback.message.text}\n\n✔️ Запрос {verdict}.")
    else:
        await callback.message.answer(f"Не удалось обработать запрос: {response.text}")
