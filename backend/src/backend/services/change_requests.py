import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import deposits as deposit_service
from shared.enums import AuditAction, ChangeRequestStatus
from shared.models import Deposit, DepositChangeRequest


async def create_request(
    db: AsyncSession,
    *,
    deposit_id: uuid.UUID,
    requested_by: uuid.UUID,
    action: AuditAction,
    payload: dict[str, Any] | None,
) -> DepositChangeRequest:
    request = DepositChangeRequest(
        deposit_id=deposit_id,
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
    request: DepositChangeRequest,
    deposit: Deposit,
    *,
    reviewed_by: uuid.UUID,
) -> DepositChangeRequest:
    if request.action == AuditAction.UPDATE:
        fields: dict[str, Any] = dict(request.payload or {})
        if "amount" in fields:
            fields["amount"] = Decimal(fields["amount"])
        await deposit_service.update_deposit(db, deposit, changed_by=reviewed_by, **fields)
    else:
        await deposit_service.delete_deposit(db, deposit, changed_by=reviewed_by)

    request.status = ChangeRequestStatus.APPROVED
    request.reviewed_by = reviewed_by
    request.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(request)
    return request


async def reject_request(
    db: AsyncSession, request: DepositChangeRequest, *, reviewed_by: uuid.UUID
) -> DepositChangeRequest:
    request.status = ChangeRequestStatus.REJECTED
    request.reviewed_by = reviewed_by
    request.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(request)
    return request
