import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from shared.models import Deposit, Team, User


async def send_telegram_message(telegram_id: int, text: str) -> None:
    if not settings.bot_token:
        return
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(
                f"https://api.telegram.org/bot{settings.bot_token}/sendMessage",
                json={"chat_id": telegram_id, "text": text},
            )
        except httpx.HTTPError:
            pass


async def notify_deposit_created(db: AsyncSession, deposit: Deposit, created_by: User) -> None:
    """ТЗ §4.4: менеджеру о зачислении депозита, тимлиду о крупной сделке. Best-effort —
    сбой отправки в Telegram не должен ронять запрос создания депозита."""
    manager = await db.get(User, deposit.manager_id)
    if manager is None:
        return

    if created_by.id != manager.id:
        await send_telegram_message(
            manager.telegram_id,
            f"Вам зачислен депозит {deposit.amount} {deposit.currency} (клиент: {deposit.client_ref}).",
        )

    if deposit.amount < settings.large_deposit_threshold or manager.team_id is None:
        return

    team = await db.get(Team, manager.team_id)
    if team is None or team.teamlead_id is None:
        return

    teamlead = await db.get(User, team.teamlead_id)
    if teamlead is None:
        return

    await send_telegram_message(
        teamlead.telegram_id,
        f"Крупная сделка в команде: {manager.full_name} внёс депозит {deposit.amount} {deposit.currency}.",
    )
