import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from shared.enums import DEPOSIT_ACTION_TYPES, Role
from shared.models import ActionChangeRequest, MopAction, Team, User


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


async def notify_action_created(db: AsyncSession, action: MopAction, created_by: User) -> None:
    """ТЗ §4.4: менеджеру о зачислении депозита, тимлиду о крупной сделке. Только для
    FD/RD (регистрация/лид не несут суммы). Best-effort — сбой отправки в Telegram
    не должен ронять запрос создания действия."""
    if action.action_type not in DEPOSIT_ACTION_TYPES or action.amount is None:
        return

    manager = await db.get(User, action.mop_id)
    if manager is None:
        return

    if created_by.id != manager.id:
        await send_telegram_message(
            manager.telegram_id,
            f"Вам зачислен депозит {action.amount} {action.currency}"
            + (f" (игрок: {action.player_id})" if action.player_id else "") + ".",
        )

    if action.amount < settings.large_deposit_threshold or manager.team_id is None:
        return

    team = await db.get(Team, manager.team_id)
    if team is None or team.teamlead_id is None:
        return

    teamlead = await db.get(User, team.teamlead_id)
    if teamlead is None:
        return

    await send_telegram_message(
        teamlead.telegram_id,
        f"Крупная сделка в команде: {manager.full_name} внёс депозит {action.amount} {action.currency}.",
    )


async def notify_change_request_created(
    db: AsyncSession, request: ActionChangeRequest, action: MopAction
) -> None:
    """ТЗ §4.8: тимлид/админ должны узнать о новом запросе, иначе очередь /pending
    просто не проверят."""
    action_label = f"{action.action_type.value}"
    if action.amount is not None:
        action_label += f" {action.amount} {action.currency}"
    text = (
        f"Новый запрос на {'правку' if request.action.value == 'update' else 'удаление'} "
        f"действия ({action_label}). Проверить: /pending"
    )

    recipients: set[int] = set()

    manager = await db.get(User, action.mop_id)
    if manager is not None and manager.team_id is not None:
        team = await db.get(Team, manager.team_id)
        if team is not None and team.teamlead_id is not None:
            teamlead = await db.get(User, team.teamlead_id)
            if teamlead is not None:
                recipients.add(teamlead.telegram_id)

    admins = (
        await db.execute(select(User).where(User.org_id == action.org_id, User.role == Role.ADMIN))
    ).scalars().all()
    recipients.update(admin.telegram_id for admin in admins)

    for telegram_id in recipients:
        await send_telegram_message(telegram_id, text)
