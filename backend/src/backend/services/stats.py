import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import DepositStatus, Role
from shared.models import Deposit, User
from shared.schemas import MyStatsOut, TopEntry


async def get_top(
    db: AsyncSession,
    org_id: uuid.UUID,
    team_id: uuid.UUID | None,
    period_start: date,
    period_end: date,
    order_by: str,
) -> list[TopEntry]:
    total_amount_expr = func.coalesce(func.sum(Deposit.amount), 0).label("total_amount")
    deposit_count_expr = func.count(Deposit.id).label("deposit_count")

    query = (
        select(User.id, User.full_name, total_amount_expr, deposit_count_expr)
        .select_from(User)
        .outerjoin(
            Deposit,
            (Deposit.manager_id == User.id)
            & (Deposit.status == DepositStatus.CONFIRMED)
            & Deposit.deleted_at.is_(None)
            & (Deposit.created_at >= period_start)
            & (Deposit.created_at < period_end + timedelta(days=1)),
        )
        .where(User.org_id == org_id, User.role == Role.MANAGER)
        .group_by(User.id, User.full_name)
    )
    if team_id is not None:
        query = query.where(User.team_id == team_id)

    order_expr = total_amount_expr if order_by == "amount" else deposit_count_expr
    query = query.order_by(order_expr.desc())

    rows = (await db.execute(query)).all()
    return [
        TopEntry(
            manager_id=row.id,
            full_name=row.full_name,
            total_amount=row.total_amount,
            deposit_count=row.deposit_count,
            rank=index + 1,
        )
        for index, row in enumerate(rows)
    ]


async def _sum_and_count(
    db: AsyncSession, manager_id: uuid.UUID, start: date, end: date
) -> tuple[Decimal, int]:
    result = await db.execute(
        select(func.coalesce(func.sum(Deposit.amount), 0), func.count(Deposit.id)).where(
            Deposit.manager_id == manager_id,
            Deposit.status == DepositStatus.CONFIRMED,
            Deposit.deleted_at.is_(None),
            Deposit.created_at >= start,
            Deposit.created_at < end + timedelta(days=1),
        )
    )
    total, count = result.one()
    return Decimal(total), count


async def _rank_in_team(
    db: AsyncSession, user: User, start: date, end: date
) -> tuple[int | None, int | None]:
    if user.team_id is None:
        return None, None
    top = await get_top(db, user.org_id, user.team_id, start, end, "amount")
    team_size = len(top)
    rank = next((entry.rank for entry in top if entry.manager_id == user.id), None)
    return rank, team_size


async def get_manager_stats(
    db: AsyncSession, user: User, period_start: date, period_end: date
) -> MyStatsOut:
    period_length = (period_end - period_start) + timedelta(days=1)
    previous_start = period_start - period_length
    previous_end = period_start - timedelta(days=1)

    current_amount, current_count = await _sum_and_count(db, user.id, period_start, period_end)
    previous_amount, _ = await _sum_and_count(db, user.id, previous_start, previous_end)

    change_percent: float | None = None
    if previous_amount:
        change_percent = float((current_amount - previous_amount) / previous_amount * 100)

    rank, team_size = await _rank_in_team(db, user, period_start, period_end)

    commission_amount = None
    if user.commission_rate is not None:
        commission_amount = current_amount * user.commission_rate / 100

    return MyStatsOut(
        total_amount=current_amount,
        deposit_count=current_count,
        rank=rank,
        team_size=team_size,
        previous_period_amount=previous_amount,
        change_percent=change_percent,
        commission_rate=user.commission_rate,
        commission_amount=commission_amount,
    )
