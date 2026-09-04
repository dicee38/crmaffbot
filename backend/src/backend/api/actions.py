import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.permissions import require_role
from backend.services import actions as action_service
from backend.services import change_requests as change_request_service
from backend.services import notifications
from shared.enums import ActionType, AuditAction, Role
from shared.models import Channel, MopAction, User
from shared.schemas import ActionCreate, ActionOut, ChangeRequestCreate, ChangeRequestOut

router = APIRouter(prefix="/actions", tags=["actions"])


def _to_out(action: MopAction) -> ActionOut:
    return ActionOut.model_validate(action)


@router.post("", response_model=ActionOut, status_code=status.HTTP_201_CREATED)
async def create_action(
    payload: ActionCreate,
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ActionOut:
    target_mop_id = payload.mop_id or user.id

    if user.role == Role.MANAGER and target_mop_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager can only enter own actions")

    if user.role == Role.TEAMLEAD:
        result = await db.execute(select(User).where(User.id == target_mop_id))
        target = result.scalar_one_or_none()
        if target is None or target.team_id != user.team_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "MOP is outside your team")

    if payload.channel_id is not None:
        channel = await db.get(Channel, payload.channel_id)
        if channel is None or channel.org_id != user.org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel not found")

    action = await action_service.create_manual_action(
        db,
        org_id=user.org_id,
        mop_id=target_mop_id,
        action_type=payload.action_type,
        channel_id=payload.channel_id,
        player_id=payload.player_id,
        amount=payload.amount,
        currency=payload.currency if payload.amount is not None else None,
        lead_count=payload.lead_count,
        created_by=user.id,
    )
    await notifications.notify_action_created(db, action, created_by=user)
    return _to_out(action)


def _visible_actions_conditions(user: User):
    if user.role in (Role.ADMIN, Role.ANALYTIC, Role.OWNER):
        return [MopAction.org_id == user.org_id]
    if user.role == Role.TEAMLEAD:
        return [
            MopAction.org_id == user.org_id,
            MopAction.mop_id.in_(select(User.id).where(User.team_id == user.team_id)),
        ]
    return [MopAction.org_id == user.org_id, MopAction.mop_id == user.id]


@router.get("", response_model=list[ActionOut])
async def list_actions(
    period_start: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    period_end: date = Query(default_factory=date.today),
    action_type: ActionType | None = Query(None),
    player_id: str | None = Query(None),
    channel_id: uuid.UUID | None = Query(None),
    mop_id: uuid.UUID | None = Query(None),
    amount_min: Decimal | None = Query(None),
    amount_max: Decimal | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN, Role.ANALYTIC, Role.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> list[MopAction]:
    conditions = _visible_actions_conditions(user)
    conditions += [
        MopAction.deleted_at.is_(None),
        MopAction.created_at >= period_start,
        MopAction.created_at < period_end + timedelta(days=1),
    ]
    if action_type is not None:
        conditions.append(MopAction.action_type == action_type)
    if player_id:
        conditions.append(MopAction.player_id == player_id)
    if channel_id is not None:
        conditions.append(MopAction.channel_id == channel_id)
    if mop_id is not None:
        conditions.append(MopAction.mop_id == mop_id)
    if amount_min is not None:
        conditions.append(MopAction.amount >= amount_min)
    if amount_max is not None:
        conditions.append(MopAction.amount <= amount_max)

    result = await db.execute(
        select(MopAction).where(*conditions).order_by(MopAction.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{action_id}", response_model=ActionOut)
async def get_action(
    action_id: uuid.UUID,
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN, Role.ANALYTIC, Role.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> MopAction:
    action = await _get_action_or_404(db, action_id)
    owner = await db.get(User, action.mop_id)
    _assert_can_view_or_modify(user, action, owner)
    return action


async def _get_action_or_404(db: AsyncSession, action_id: uuid.UUID) -> MopAction:
    result = await db.execute(
        select(MopAction).where(MopAction.id == action_id, MopAction.deleted_at.is_(None))
    )
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    return action


def _assert_can_view_or_modify(user: User, action: MopAction, owner: User | None) -> None:
    """ТЗ §3: менеджер/тимлид/админ видят и могут запросить правку/удаление действия
    в своей видимости — менеджер только своего, тимлид своей команды, админ любого.
    Аналитик/собственник — только чтение всей организации."""
    if user.role in (Role.ADMIN, Role.ANALYTIC, Role.OWNER):
        return
    if user.role == Role.TEAMLEAD:
        if owner is not None and owner.team_id == user.team_id:
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action is outside your team")
    if user.role == Role.MANAGER:
        if action.mop_id == user.id:
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your action")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")


@router.post(
    "/{action_id}/change-requests",
    response_model=ChangeRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def request_action_change(
    action_id: uuid.UUID,
    payload: ChangeRequestCreate,
    user: User = Depends(require_role(Role.MANAGER, Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ChangeRequestOut:
    """ТЗ §4.8: правка или удаление ЛЮБОГО действия, включая своё, — только через
    запрос на согласование. Тимлид/админ подтверждает, см. api/change_requests.py."""
    if payload.action not in (AuditAction.UPDATE, AuditAction.DELETE):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "action must be update or delete")
    if payload.action == AuditAction.UPDATE and payload.payload is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "payload is required for update")

    action = await _get_action_or_404(db, action_id)
    owner = await db.get(User, action.mop_id)
    _assert_can_view_or_modify(user, action, owner)
    if user.role == Role.OWNER or user.role == Role.ANALYTIC:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Read-only role")

    fields = payload.payload.model_dump(exclude_unset=True, mode="json") if payload.payload else None
    if fields is not None and not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")

    request = await change_request_service.create_request(
        db,
        action_id=action.id,
        requested_by=user.id,
        action=payload.action,
        payload=fields,
    )
    await notifications.notify_change_request_created(db, request, action)
    return ChangeRequestOut.model_validate(request)
