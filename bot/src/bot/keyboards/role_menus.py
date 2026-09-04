from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot.config import settings


def _dashboard_button() -> KeyboardButton | None:
    # Telegram rejects WebApp buttons with an invalid/empty URL, so only add it once configured.
    if not settings.miniapp_url:
        return None
    return KeyboardButton(text="📊 Дашборд", web_app=WebAppInfo(url=settings.miniapp_url))


def _menu(rows: list[list[KeyboardButton]], *, with_dashboard: bool = False) -> ReplyKeyboardMarkup:
    if with_dashboard and (button := _dashboard_button()) is not None:
        rows = [*rows, [button]]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def menu_for_role(role: str) -> ReplyKeyboardMarkup:
    if role == "manager":
        return _menu(
            [
                [KeyboardButton(text="Внести депозит")],
                [KeyboardButton(text="Моя статистика")],
            ]
        )
    if role == "teamlead":
        return _menu(
            [
                [KeyboardButton(text="Внести депозит")],
                [KeyboardButton(text="Моя статистика")],
                [KeyboardButton(text="Топ команды")],
            ]
        )
    if role == "admin":
        return _menu(
            [
                [KeyboardButton(text="Внести депозит")],
                [KeyboardButton(text="Топ команды"), KeyboardButton(text="Топ компании")],
            ],
            with_dashboard=True,
        )
    if role == "owner":
        return _menu([[KeyboardButton(text="Топ компании")]], with_dashboard=True)
    if role == "analytic":
        return _menu(
            [[KeyboardButton(text="Топ команды"), KeyboardButton(text="Топ компании")]],
            with_dashboard=True,
        )
    raise ValueError(f"Unknown role: {role}")
