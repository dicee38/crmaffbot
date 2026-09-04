import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import actions as action_service
from shared.enums import AuditAction, ChangeRequestStatus
from shared.models import ActionChangeRequest, MopAction


async def create_request(
    db: AsyncSession,
    *,
    action_id: uuid.UUID,
    requested_by: uuid.UUID,
    action: AuditAction,
    payload: dict[str, Any] | None,
) -> ActionChangeRequest:
    request = ActionChangeRequest(
        action_id=action_id,
        requested_by=requested_by,
        action=action,
        payload=payload,
        status=ChangeRequestStatus.PENDING,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


async def approve_request(
    db: AsyncSession,
    request: ActionChangeRequest,
    mop_action: MopAction,
    *,
    reviewed_by: uuid.UUID,
) -> ActionChangeRequest:
    if request.action == AuditAction.UPDATE:
        fields: dict[str, Any] = dict(request.payload or {})
        if "amount" in fields and fields["amount"] is not None:
            fields["amount"] = Decimal(fields["amount"])
        if "channel_id" in fields and fields["channel_id"] is not None:
            fields["channel_id"] = uuid.UUID(fields["channel_id"])
        await action_service.update_action(db, mop_action, changed_by=reviewed_by, **fields)
    else:
        await action_service.delete_action(db, mop_action, changed_by=reviewed_by)

    request.status = ChangeRequestStatus.APPROVED
    request.reviewed_by = reviewed_by
    request.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(request)
    return request


async def reject_request(
    db: AsyncSession, request: ActionChangeRequest, *, reviewed_by: uuid.UUID
) -> ActionChangeRequest:
    request.status = ChangeRequestStatus.REJECTED
    request.reviewed_by = reviewed_by
    request.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(request)
    return request
