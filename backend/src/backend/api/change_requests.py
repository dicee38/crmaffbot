import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_current_user, get_db
from backend.services import change_requests as change_request_service
from shared.enums import ChangeRequestStatus, Role
from shared.models import Deposit, DepositChangeRequest, User
from shared.schemas import ChangeRequestOut

router = APIRouter(prefix="/change-requests", tags=["change-requests"])


def _visible_deposit_ids_subquery(user: User):
    """Restricts the request queue to deposits the reviewer is allowed to approve for."""
    if user.role == Role.ADMIN:
        return select(Deposit.id).where(Deposit.org_id == user.org_id)
    if user.role == Role.TEAMLEAD:
        return select(Deposit.id).where(
            Deposit.org_id == user.org_id,
            Deposit.manager_id.in_(select(User.id).where(User.team_id == user.team_id)),
        )
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to review change requests")


@router.get("", response_model=list[ChangeRequestOut])
async def list_change_requests(
    status_filter: ChangeRequestStatus = Query(ChangeRequestStatus.PENDING, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DepositChangeRequest]:
    deposit_ids = _visible_deposit_ids_subquery(user)
    result = await db.execute(
        select(DepositChangeRequest)
        .where(
            DepositChangeRequest.status == status_filter,
            DepositChangeRequest.deposit_id.in_(deposit_ids),
        )
        .order_by(DepositChangeRequest.created_at)
    )
    return list(result.scalars().all())


async def _get_request_and_deposit(
    db: AsyncSession, request_id: uuid.UUID
) -> tuple[DepositChangeRequest, Deposit]:
    request = await db.get(DepositChangeRequest, request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change request not found")
    if request.status != ChangeRequestStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Change request already reviewed")

    deposit = await db.get(Deposit, request.deposit_id)
    if deposit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deposit not found")
    return request, deposit


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
) -> DepositChangeRequest:
    request, deposit = await _get_request_and_deposit(db, request_id)
    owner = await db.get(User, deposit.manager_id)
    _assert_can_review(user, owner)

    return await change_request_service.approve_request(db, request, deposit, reviewed_by=user.id)


@router.post("/{request_id}/reject", response_model=ChangeRequestOut)
async def reject_change_request(
    request_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DepositChangeRequest:
    request, deposit = await _get_request_and_deposit(db, request_id)
    owner = await db.get(User, deposit.manager_id)
    _assert_can_review(user, owner)

    return await change_request_service.reject_request(db, request, reviewed_by=user.id)
