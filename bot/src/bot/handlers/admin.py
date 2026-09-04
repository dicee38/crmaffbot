import httpx
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.config import settings

router = Router(name="admin")


@router.message(Command("add_manager"))
async def add_manager(message: Message, command: CommandObject, current_user: dict) -> None:
    if current_user["role"] != "admin":
        await message.answer("Только для администратора.")
        return
    if not command.args:
        await message.answer("Использование: /add_manager <telegram_id> <Имя Фамилия>")
        return

    parts = command.args.split(maxsplit=1)
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Использование: /add_manager <telegram_id> <Имя Фамилия>")
        return

    telegram_id, full_name = int(parts[0]), parts[1]
    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.post(
            "/users",
            headers={"X-Telegram-User-Id": str(current_user["telegram_id"])},
            json={"telegram_id": telegram_id, "full_name": full_name, "role": "manager"},
        )

    if response.status_code == 201:
        await message.answer(f"Менеджер {full_name} добавлен.")
    else:
        await message.answer(f"Ошибка: {response.text}")


@router.message(Command("block"))
async def block_user(message: Message, command: CommandObject, current_user: dict) -> None:
    if current_user["role"] != "admin":
        await message.answer("Только для администратора.")
        return
    if not command.args or not command.args.isdigit():
        await message.answer("Использование: /block <telegram_id>")
        return

    telegram_id = int(command.args)
    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        list_response = await client.get(
            "/users", headers={"X-Telegram-User-Id": str(current_user["telegram_id"])}
        )
        target = next((u for u in list_response.json() if u["telegram_id"] == telegram_id), None)
        if target is None:
            await message.answer("Пользователь не найден.")
            return

        await client.post(
            f"/users/{target['id']}/block",
            headers={"X-Telegram-User-Id": str(current_user["telegram_id"])},
        )

    await message.answer("Пользователь заблокирован.")
