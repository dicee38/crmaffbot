import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_current_user, get_db
from backend.permissions import require_role
from shared.enums import Role, UserStatus
from shared.models import Team, User
from shared.schemas import CommissionRateUpdate, TeamCreate, TeamOut, TeamUpdate, UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("", response_model=list[UserOut])
async def list_users(
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    result = await db.execute(select(User).where(User.org_id == admin.org_id))
    return list(result.scalars().all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> User:
    existing = await db.execute(select(User).where(User.telegram_id == payload.telegram_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "telegram_id already registered")

    user = User(
        org_id=admin.org_id,
        telegram_id=payload.telegram_id,
        full_name=payload.full_name,
        role=payload.role,
        team_id=payload.team_id,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _get_user_in_org_or_404(db: AsyncSession, admin: User, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None or user.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.post("/{user_id}/block", response_model=UserOut)
async def block_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await _get_user_in_org_or_404(db, admin, user_id)
    user.status = UserStatus.BLOCKED
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/unblock", response_model=UserOut)
async def unblock_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await _get_user_in_org_or_404(db, admin, user_id)
    user.status = UserStatus.ACTIVE
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/commission-rate", response_model=UserOut)
async def set_commission_rate(
    user_id: uuid.UUID,
    payload: CommissionRateUpdate,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await _get_user_in_org_or_404(db, admin, user_id)
    if user.role != Role.MANAGER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Commission only applies to managers")
    user.commission_rate = payload.commission_rate
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/teams", response_model=list[TeamOut])
async def list_teams(
    user: User = Depends(require_role(Role.ADMIN, Role.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> list[Team]:
    result = await db.execute(select(Team).where(Team.org_id == user.org_id))
    return list(result.scalars().all())


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Team:
    team = Team(org_id=admin.org_id, name=payload.name, teamlead_id=payload.teamlead_id)
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


@router.patch("/teams/{team_id}", response_model=TeamOut)
async def update_team(
    team_id: uuid.UUID,
    payload: TeamUpdate,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Team:
    team = await db.get(Team, team_id)
    if team is None or team.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")

    if payload.teamlead_id is not None:
        teamlead = await _get_user_in_org_or_404(db, admin, payload.teamlead_id)
        if teamlead.role != Role.TEAMLEAD:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "User is not a teamlead")

    team.teamlead_id = payload.teamlead_id
    await db.commit()
    await db.refresh(team)
    return team
