import httpx
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import auth_headers, settings
from bot.keyboards.role_menus import menu_for_role

router = Router(name="deposit_entry")


class DepositForm(StatesGroup):
    amount = State()
    client_ref = State()


@router.message(F.text == "Внести депозит")
async def start_deposit(message: Message, state: FSMContext) -> None:
    await state.set_state(DepositForm.amount)
    await message.answer("Сумма депозита?")


@router.message(StateFilter(DepositForm.amount))
async def deposit_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = float((message.text or "").replace(",", "."))
    except ValueError:
        await message.answer("Введите число, например 150.50")
        return
    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля")
        return

    await state.update_data(amount=amount)
    await state.set_state(DepositForm.client_ref)
    await message.answer("Клиент (имя или ID)?")


@router.message(StateFilter(DepositForm.client_ref))
async def deposit_client(message: Message, state: FSMContext, current_user: dict) -> None:
    data = await state.get_data()
    async with httpx.AsyncClient(base_url=settings.backend_url) as client:
        response = await client.post(
            "/deposits",
            headers=auth_headers(current_user["telegram_id"]),
            json={"client_ref": message.text, "amount": data["amount"], "currency": "USD"},
        )
    await state.clear()

    if response.status_code == 201:
        await message.answer("Депозит сохранён.", reply_markup=menu_for_role(current_user["role"]))
    else:
        await message.answer(f"Не удалось сохранить: {response.text}")
