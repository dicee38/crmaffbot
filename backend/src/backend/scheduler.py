from datetime import date, timedelta

from sqlalchemy import func, select

from backend.config import settings
from backend.deps import SessionFactory
from backend.services.notifications import send_telegram_message
from backend.services.stats import get_top
from shared.enums import DEPOSIT_ACTION_TYPES, Role
from shared.models import MopAction, Organization, Team, User


def _format_top(entries: list) -> str:
    if not entries:
        return "депозитов не было."
    return "\n".join(f"{e.rank}. {e.full_name} — {e.total_amount}" for e in entries)


async def _send_period_digest(period_start: date, period_end: date, label: str) -> None:
    """ТЗ §4.4: периодическая сводка (день/неделя) тимлидам и админу."""
    async with SessionFactory() as db:
        orgs = (await db.execute(select(Organization))).scalars().all()
        for org in orgs:
            teams = (await db.execute(select(Team).where(Team.org_id == org.id))).scalars().all()
            for team in teams:
                if team.teamlead_id is None:
                    continue
                teamlead = await db.get(User, team.teamlead_id)
                if teamlead is None:
                    continue
                top = await get_top(db, org.id, team.id, period_start, period_end, "amount")
                await send_telegram_message(
                    teamlead.telegram_id,
                    f"Сводка по команде «{team.name}» {label}:\n{_format_top(top)}",
                )

            admins = (
                await db.execute(select(User).where(User.org_id == org.id, User.role == Role.ADMIN))
            ).scalars().all()
            if admins:
                company_top = await get_top(db, org.id, None, period_start, period_end, "amount")
                text = f"Сводка по компании «{org.name}» {label}:\n{_format_top(company_top)}"
                for admin in admins:
                    await send_telegram_message(admin.telegram_id, text)


async def send_daily_digest() -> None:
    yesterday = date.today() - timedelta(days=1)
    await _send_period_digest(yesterday, yesterday, f"за {yesterday.isoformat()}")


async def send_weekly_digest() -> None:
    today = date.today()
    week_start = today - timedelta(days=7)
    week_end = today - timedelta(days=1)
    await _send_period_digest(
        week_start, week_end, f"за неделю {week_start.isoformat()}–{week_end.isoformat()}"
    )


async def check_idle_managers() -> None:
    """ТЗ §8 (этап 3): оповещение тимлида о простое в активности менеджера."""
    cutoff = date.today() - timedelta(days=settings.idle_days_threshold)

    async with SessionFactory() as db:
        managers = (await db.execute(select(User).where(User.role == Role.MANAGER))).scalars().all()
        for manager in managers:
            if manager.team_id is None:
                continue

            last_deposit_at = (
                await db.execute(
                    select(func.max(MopAction.created_at)).where(
                        MopAction.mop_id == manager.id,
                        MopAction.action_type.in_(DEPOSIT_ACTION_TYPES),
                        MopAction.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

            if last_deposit_at is not None and last_deposit_at.date() >= cutoff:
                continue

            team = await db.get(Team, manager.team_id)
            if team is None or team.teamlead_id is None:
                continue
            teamlead = await db.get(User, team.teamlead_id)
            if teamlead is None:
                continue

            since = last_deposit_at.date().isoformat() if last_deposit_at else "начала работы"
            await send_telegram_message(
                teamlead.telegram_id,
                f"{manager.full_name}: нет новых депозитов с {since} "
                f"(порог — {settings.idle_days_threshold} дн.).",
            )
