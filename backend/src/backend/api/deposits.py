import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.permissions import require_role
from backend.services import change_requests as change_request_service
from backend.services import deposits as deposit_service
from backend.services import notifications
from shared.enums import AuditAction, Role
from shared.models import Deposit, User
from shared.schemas import ChangeRequestCreate, ChangeRequestOut, DepositCreate, DepositOut

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
    await notifications.notify_deposit_created(db, deposit, created_by=user)
    return _to_out(deposit)


def _visible_deposits_conditions(user: User):
    if user.role == Role.ADMIN:
        return [Deposit.org_id == user.org_id]
    if user.role == Role.TEAMLEAD:
        return [
            Deposit.org_id == user.org_id,
            Deposit.manager_id.in_(select(User.id).where(User.team_id == user.team_id)),
        ]
    return [Deposit.org_id == user.org_id, Deposit.manager_id == user.id]


@router.get("", response_model=list[DepositOut])
async def list_deposits(
    period_start: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    period_end: date = Query(default_factory=date.today),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[Deposit]:
    conditions = _visible_deposits_conditions(user)
    conditions += [
        Deposit.deleted_at.is_(None),
        Deposit.created_at >= period_start,
        Deposit.created_at < period_end + timedelta(days=1),
    ]
    result = await db.execute(
        select(Deposit).where(*conditions).order_by(Deposit.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{deposit_id}", response_model=DepositOut)
async def get_deposit(
    deposit_id: uuid.UUID,
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Deposit:
    deposit = await _get_deposit_or_404(db, deposit_id)
    owner = await db.get(User, deposit.manager_id)
    _assert_can_request_change(user, deposit, owner)
    return deposit


async def _get_deposit_or_404(db: AsyncSession, deposit_id: uuid.UUID) -> Deposit:
    result = await db.execute(
        select(Deposit).where(Deposit.id == deposit_id, Deposit.deleted_at.is_(None))
    )
    deposit = result.scalar_one_or_none()
    if deposit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deposit not found")
    return deposit


def _assert_can_request_change(user: User, deposit: Deposit, owner: User | None) -> None:
    """ТЗ §3: менеджер/тимлид/админ могут запросить правку/удаление депозита в своей
    видимости — менеджер только своего, тимлид своей команды, админ любого."""
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


@router.post(
    "/{deposit_id}/change-requests",
    response_model=ChangeRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def request_deposit_change(
    deposit_id: uuid.UUID,
    payload: ChangeRequestCreate,
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ChangeRequestOut:
    """ТЗ §4.8: правка или удаление ЛЮБОГО депозита, включая свой, — только через
    запрос на согласование. Тимлид/админ подтверждает, см. api/change_requests.py."""
    if payload.action not in (AuditAction.UPDATE, AuditAction.DELETE):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "action must be update or delete")
    if payload.action == AuditAction.UPDATE and payload.payload is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "payload is required for update")

    deposit = await _get_deposit_or_404(db, deposit_id)
    owner = await db.get(User, deposit.manager_id)
    _assert_can_request_change(user, deposit, owner)

    fields = payload.payload.model_dump(exclude_unset=True, mode="json") if payload.payload else None
    if fields is not None and not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")

    request = await change_request_service.create_request(
        db,
        deposit_id=deposit.id,
        requested_by=user.id,
        action=payload.action,
        payload=fields,
    )
    await notifications.notify_change_request_created(db, request, deposit)
    return ChangeRequestOut.model_validate(request)
