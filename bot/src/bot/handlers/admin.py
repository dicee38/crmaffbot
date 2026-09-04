import httpx
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.config import auth_headers, settings

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
            headers=auth_headers(current_user["telegram_id"]),
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
            "/users", headers=auth_headers(current_user["telegram_id"])
        )
        target = next((u for u in list_response.json() if u["telegram_id"] == telegram_id), None)
        if target is None:
            await message.answer("Пользователь не найден.")
            return

        await client.post(
            f"/users/{target['id']}/block",
            headers=auth_headers(current_user["telegram_id"]),
        )

    await message.answer("Пользователь заблокирован.")


@router.message(Command("add_team"))
async def add_team(message: Message, command: CommandObject, current_user: dict) -> None:
    if current_user["role"] != "admin":
        await message.answer("Только для администратора.")
        return
    if not command.args:
        await message.answer("Использование: /add_team <название команды>")
        return

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.post(
            "/users/teams",
            headers=auth_headers(current_user["telegram_id"]),
            json={"name": command.args.strip()},
        )

    if response.status_code == 201:
        await message.answer(f"Команда «{command.args.strip()}» создана.")
    else:
        await message.answer(f"Ошибка: {response.text}")


@router.message(Command("add_teamlead"))
async def add_teamlead(message: Message, command: CommandObject, current_user: dict) -> None:
    if current_user["role"] != "admin":
        await message.answer("Только для администратора.")
        return

    usage = "Использование: /add_teamlead <telegram_id> <название команды> / <Имя Фамилия>"
    if not command.args or "/" not in command.args:
        await message.answer(usage)
        return

    left, _, full_name = command.args.partition("/")
    left_parts = left.strip().split(maxsplit=1)
    full_name = full_name.strip()
    if len(left_parts) != 2 or not left_parts[0].isdigit() or not full_name:
        await message.answer(usage)
        return

    telegram_id, team_name = int(left_parts[0]), left_parts[1].strip()

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        headers = auth_headers(current_user["telegram_id"])

        teams_response = await client.get("/users/teams", headers=headers)
        team = next(
            (t for t in teams_response.json() if t["name"].lower() == team_name.lower()), None
        )
        if team is None:
            await message.answer(f"Команда «{team_name}» не найдена. Сначала: /add_team {team_name}")
            return

        create_response = await client.post(
            "/users",
            headers=headers,
            json={
                "telegram_id": telegram_id,
                "full_name": full_name,
                "role": "teamlead",
                "team_id": team["id"],
            },
        )
        if create_response.status_code != 201:
            await message.answer(f"Ошибка создания пользователя: {create_response.text}")
            return

        new_user = create_response.json()
        link_response = await client.patch(
            f"/users/teams/{team['id']}",
            headers=headers,
            json={"teamlead_id": new_user["id"]},
        )

    if link_response.status_code == 200:
        await message.answer(f"{full_name} назначен(а) тимлидом команды «{team_name}».")
    else:
        await message.answer(f"Пользователь создан, но не удалось назначить тимлидом: {link_response.text}")


@router.message(Command("set_commission"))
async def set_commission(message: Message, command: CommandObject, current_user: dict) -> None:
    if current_user["role"] != "admin":
        await message.answer("Только для администратора.")
        return

    usage = "Использование: /set_commission <telegram_id> <ставка в %>"
    parts = command.args.split() if command.args else []
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer(usage)
        return

    telegram_id = int(parts[0])
    try:
        rate = float(parts[1].replace(",", "."))
    except ValueError:
        await message.answer(usage)
        return

    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        headers = auth_headers(current_user["telegram_id"])
        list_response = await client.get("/users", headers=headers)
        target = next((u for u in list_response.json() if u["telegram_id"] == telegram_id), None)
        if target is None:
            await message.answer("Пользователь не найден.")
            return

        response = await client.post(
            f"/users/{target['id']}/commission-rate",
            headers=headers,
            json={"commission_rate": rate},
        )

    if response.status_code == 200:
        await message.answer(f"Комиссия {target['full_name']}: {rate}%.")
    else:
        await message.answer(f"Ошибка: {response.text}")
