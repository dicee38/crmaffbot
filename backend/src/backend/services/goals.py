import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import DEPOSIT_ACTION_TYPES, ActionStatus, GoalScope
from shared.models import Goal, MopAction, User


def month_bounds(period: date) -> tuple[date, date]:
    start = period.replace(day=1)
    last_day = calendar.monthrange(start.year, start.month)[1]
    return start, start.replace(day=last_day)


async def upsert_goal(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    scope: GoalScope,
    scope_id: uuid.UUID,
    period: date,
    target_amount: Decimal,
    created_by: uuid.UUID,
) -> Goal:
    """Setting a goal again for the same (scope, scope_id, month) updates the target
    rather than creating a duplicate row — the schema (ТЗ §6) has no unique constraint for this."""
    period_start = period.replace(day=1)
    result = await db.execute(
        select(Goal).where(
            Goal.org_id == org_id,
            Goal.scope == scope,
            Goal.scope_id == scope_id,
            Goal.period == period_start,
        )
    )
    goal = result.scalar_one_or_none()
    if goal is not None:
        goal.target_amount = target_amount
        goal.created_by = created_by
    else:
        goal = Goal(
            org_id=org_id,
            scope=scope,
            scope_id=scope_id,
            period=period_start,
            target_amount=target_amount,
            created_by=created_by,
        )
        db.add(goal)

    await db.commit()
    await db.refresh(goal)
    return goal


async def _current_amount(
    db: AsyncSession, org_id: uuid.UUID, scope: GoalScope, scope_id: uuid.UUID, start: date, end: date
) -> Decimal:
    conditions = [
        MopAction.org_id == org_id,
        MopAction.action_type.in_(DEPOSIT_ACTION_TYPES),
        MopAction.status == ActionStatus.CONFIRMED,
        MopAction.deleted_at.is_(None),
        MopAction.created_at >= start,
        MopAction.created_at < end + timedelta(days=1),
    ]
    if scope == GoalScope.USER:
        conditions.append(MopAction.mop_id == scope_id)
    else:
        conditions.append(MopAction.mop_id.in_(select(User.id).where(User.team_id == scope_id)))

    result = await db.execute(select(func.coalesce(func.sum(MopAction.amount), 0)).where(*conditions))
    return Decimal(result.scalar_one())


async def get_progress(db: AsyncSession, goal: Goal) -> tuple[Decimal, float, bool]:
    start, end = month_bounds(goal.period)
    current = await _current_amount(db, goal.org_id, goal.scope, goal.scope_id, start, end)
    percent = float(current / goal.target_amount * 100) if goal.target_amount else 0.0

    today = date.today()
    period_length = (end - start).days + 1
    midpoint = start + timedelta(days=period_length // 2)
    # ТЗ §4.3: soft flag only once we're past the midpoint and still under halfway to target.
    behind_pace = midpoint <= today <= end and percent < 50.0

    return current, percent, behind_pace
