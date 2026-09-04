import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_current_user, get_db
from backend.permissions import require_role
from backend.services import stats as stats_service
from shared.enums import Role
from shared.models import User
from shared.schemas import MyStatsOut, TopEntry

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/me", response_model=MyStatsOut)
async def my_stats(
    period_start: date = Query(...),
    period_end: date = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MyStatsOut:
    return await stats_service.get_manager_stats(db, user, period_start, period_end)


@router.get("/top/team", response_model=list[TopEntry])
async def top_team(
    period_start: date = Query(...),
    period_end: date = Query(...),
    order_by: str = Query("amount", pattern="^(amount|count)$"),
    team_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_role(Role.TEAMLEAD, Role.ADMIN, Role.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> list[TopEntry]:
    if user.role == Role.TEAMLEAD:
        resolved_team_id = user.team_id
    elif team_id is not None:
        resolved_team_id = team_id
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "team_id is required")

    return await stats_service.get_top(db, user.org_id, resolved_team_id, period_start, period_end, order_by)


@router.get("/top/company", response_model=list[TopEntry])
async def top_company(
    period_start: date = Query(...),
    period_end: date = Query(...),
    order_by: str = Query("amount", pattern="^(amount|count)$"),
    user: User = Depends(require_role(Role.ADMIN, Role.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> list[TopEntry]:
    return await stats_service.get_top(db, user.org_id, None, period_start, period_end, order_by)
