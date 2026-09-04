import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.config import settings
from bot.handlers import admin, deposit_entry, deposit_review, goals, my_stats, reports, team_top
from bot.keyboards.role_menus import menu_for_role
from bot.middlewares.auth import AuthMiddleware


async def cmd_start(message: Message, current_user: dict) -> None:
    await message.answer(
        f"Привет, {current_user['full_name']}!",
        reply_markup=menu_for_role(current_user["role"]),
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.update.middleware(AuthMiddleware())
    dp.message.register(cmd_start, CommandStart())
    dp.include_router(deposit_entry.router)
    dp.include_router(deposit_review.router)
    dp.include_router(my_stats.router)
    dp.include_router(team_top.router)
    dp.include_router(goals.router)
    dp.include_router(reports.router)
    dp.include_router(admin.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
