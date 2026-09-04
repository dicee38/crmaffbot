from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MANAGER_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Внести депозит")],
        [KeyboardButton(text="Моя статистика")],
    ],
    resize_keyboard=True,
)

TEAMLEAD_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Внести депозит")],
        [KeyboardButton(text="Моя статистика")],
        [KeyboardButton(text="Топ команды")],
    ],
    resize_keyboard=True,
)

ADMIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Внести депозит")],
        [KeyboardButton(text="Топ команды"), KeyboardButton(text="Топ компании")],
    ],
    resize_keyboard=True,
)

OWNER_MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Топ компании")]],
    resize_keyboard=True,
)

_MENUS = {
    "manager": MANAGER_MENU,
    "teamlead": TEAMLEAD_MENU,
    "admin": ADMIN_MENU,
    "owner": OWNER_MENU,
}


def menu_for_role(role: str) -> ReplyKeyboardMarkup:
    return _MENUS[role]
