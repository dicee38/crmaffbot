import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.permissions import require_role
from backend.services import deposits as deposit_service
from shared.enums import Role
from shared.models import Deposit, User
from shared.schemas import DepositCreate, DepositOut, DepositUpdate

router = APIRouter(prefix="/deposits", tags=["deposits"])


def _to_out(deposit: Deposit) -> DepositOut:
    return DepositOut.model_validate(deposit)


@router.post("", response_model=DepositOut, status_code=status.HTTP_201_CREATED)
async def create_deposit(
    payload: DepositCreate,
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> DepositOut:
    target_manager_id = payload.manager_id or user.id

    if user.role == Role.MANAGER and target_manager_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager can only enter own deposits")

    if user.role == Role.TEAMLEAD:
        result = await db.execute(select(User).where(User.id == target_manager_id))
        target = result.scalar_one_or_none()
        if target is None or target.team_id != user.team_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager is outside your team")

    deposit = await deposit_service.create_manual_deposit(
        db,
        org_id=user.org_id,
        manager_id=target_manager_id,
        client_ref=payload.client_ref,
        amount=payload.amount,
        currency=payload.currency,
        created_by=user.id,
    )
    return _to_out(deposit)


async def _get_deposit_or_404(db: AsyncSession, deposit_id: uuid.UUID) -> Deposit:
    result = await db.execute(
        select(Deposit).where(Deposit.id == deposit_id, Deposit.deleted_at.is_(None))
    )
    deposit = result.scalar_one_or_none()
    if deposit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deposit not found")
    return deposit


def _assert_can_modify(user: User, deposit: Deposit, owner: User | None) -> None:
    if user.role == Role.ADMIN:
        return
    if user.role == Role.TEAMLEAD:
        if owner is not None and owner.team_id == user.team_id:
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Deposit is outside your team")
    if user.role == Role.MANAGER:
        if deposit.manager_id == user.id:
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your deposit")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")


@router.patch("/{deposit_id}", response_model=DepositOut)
async def edit_deposit(
    deposit_id: uuid.UUID,
    payload: DepositUpdate,
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> DepositOut:
    deposit = await _get_deposit_or_404(db, deposit_id)
    owner = await db.get(User, deposit.manager_id)
    _assert_can_modify(user, deposit, owner)

    fields = payload.model_dump(exclude_unset=True)
    if fields:
        deposit = await deposit_service.update_deposit(db, deposit, changed_by=user.id, **fields)
    return _to_out(deposit)


@router.delete("/{deposit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_deposit(
    deposit_id: uuid.UUID,
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    deposit = await _get_deposit_or_404(db, deposit_id)
    owner = await db.get(User, deposit.manager_id)
    _assert_can_modify(user, deposit, owner)
    await deposit_service.delete_deposit(db, deposit, changed_by=user.id)
