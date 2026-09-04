import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_current_user, get_db
from backend.services import goals as goal_service
from shared.enums import GoalScope, Role
from shared.models import Goal, User
from shared.schemas import GoalCreate, GoalOut, GoalProgressOut

router = APIRouter(prefix="/goals", tags=["goals"])


async def _assert_can_set(db: AsyncSession, user: User, scope: GoalScope, scope_id: uuid.UUID) -> None:
    if user.role == Role.ADMIN:
        return
    if user.role == Role.TEAMLEAD:
        if scope == GoalScope.TEAM and scope_id == user.team_id:
            return
        if scope == GoalScope.USER:
            target = await db.get(User, scope_id)
            if target is not None and target.team_id == user.team_id:
                return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to set this goal")


async def _assert_can_view(db: AsyncSession, user: User, scope: GoalScope, scope_id: uuid.UUID) -> None:
    if user.role in (Role.ADMIN, Role.OWNER):
        return
    if user.role == Role.TEAMLEAD:
        if scope == GoalScope.TEAM and scope_id == user.team_id:
            return
        if scope == GoalScope.USER:
            target = await db.get(User, scope_id)
            if target is not None and target.team_id == user.team_id:
                return
    elif user.role == Role.MANAGER and scope == GoalScope.USER and scope_id == user.id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this goal")


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def set_goal(
    payload: GoalCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Goal:
    await _assert_can_set(db, user, payload.scope, payload.scope_id)
    return await goal_service.upsert_goal(
        db,
        org_id=user.org_id,
        scope=payload.scope,
        scope_id=payload.scope_id,
        period=payload.period,
        target_amount=payload.target_amount,
        created_by=user.id,
    )


@router.get("/progress", response_model=GoalProgressOut)
async def goal_progress(
    scope: GoalScope = Query(...),
    scope_id: uuid.UUID = Query(...),
    period: date = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalProgressOut:
    await _assert_can_view(db, user, scope, scope_id)

    result = await db.execute(
        select(Goal).where(
            Goal.org_id == user.org_id,
            Goal.scope == scope,
            Goal.scope_id == scope_id,
            Goal.period == period.replace(day=1),
        )
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found for this period")

    current_amount, percent, behind_pace = await goal_service.get_progress(db, goal)
    return GoalProgressOut(
        goal=GoalOut.model_validate(goal),
        current_amount=current_amount,
        percent=percent,
        behind_pace=behind_pace,
    )
