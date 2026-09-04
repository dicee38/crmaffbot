import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_current_user, get_db
from backend.services import change_requests as change_request_service
from shared.enums import ChangeRequestStatus, Role
from shared.models import ActionChangeRequest, MopAction, User
from shared.schemas import ChangeRequestOut

router = APIRouter(prefix="/change-requests", tags=["change-requests"])


def _visible_action_ids_subquery(user: User):
    """Restricts the request queue to actions the reviewer is allowed to approve for."""
    if user.role == Role.ADMIN:
        return select(MopAction.id).where(MopAction.org_id == user.org_id)
    if user.role == Role.TEAMLEAD:
        return select(MopAction.id).where(
            MopAction.org_id == user.org_id,
            MopAction.mop_id.in_(select(User.id).where(User.team_id == user.team_id)),
        )
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to review change requests")


@router.get("", response_model=list[ChangeRequestOut])
async def list_change_requests(
    status_filter: ChangeRequestStatus = Query(ChangeRequestStatus.PENDING, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActionChangeRequest]:
    action_ids = _visible_action_ids_subquery(user)
    result = await db.execute(
        select(ActionChangeRequest)
        .where(
            ActionChangeRequest.status == status_filter,
            ActionChangeRequest.action_id.in_(action_ids),
        )
        .order_by(ActionChangeRequest.created_at)
    )
    return list(result.scalars().all())


async def _get_request_and_action(
    db: AsyncSession, request_id: uuid.UUID
) -> tuple[ActionChangeRequest, MopAction]:
    request = await db.get(ActionChangeRequest, request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change request not found")
    if request.status != ChangeRequestStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Change request already reviewed")

    action = await db.get(MopAction, request.action_id)
    if action is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    return request, action


def _assert_can_review(user: User, owner: User | None) -> None:
    if user.role == Role.ADMIN:
        return
    if user.role == Role.TEAMLEAD and owner is not None and owner.team_id == user.team_id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to review this request")


@router.post("/{request_id}/approve", response_model=ChangeRequestOut)
async def approve_change_request(
    request_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionChangeRequest:
    request, action = await _get_request_and_action(db, request_id)
    owner = await db.get(User, action.mop_id)
    _assert_can_review(user, owner)

    return await change_request_service.approve_request(db, request, action, reviewed_by=user.id)


@router.post("/{request_id}/reject", response_model=ChangeRequestOut)
async def reject_change_request(
    request_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionChangeRequest:
    request, action = await _get_request_and_action(db, request_id)
    owner = await db.get(User, action.mop_id)
    _assert_can_review(user, owner)

    return await change_request_service.reject_request(db, request, reviewed_by=user.id)
