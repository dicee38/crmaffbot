import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import AuditAction, DepositSource, DepositStatus
from shared.models import Deposit, DepositAuditLog


def _serialize(deposit: Deposit) -> dict:
    return {
        "client_ref": deposit.client_ref,
        "amount": str(deposit.amount),
        "currency": deposit.currency,
        "source": deposit.source.value,
        "external_id": deposit.external_id,
        "status": deposit.status.value,
    }


async def create_manual_deposit(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    manager_id: uuid.UUID,
    client_ref: str,
    amount: Decimal,
    currency: str,
    created_by: uuid.UUID,
) -> Deposit:
    deposit = Deposit(
        org_id=org_id,
        manager_id=manager_id,
        client_ref=client_ref,
        amount=amount,
        currency=currency,
        source=DepositSource.MANUAL,
        status=DepositStatus.CONFIRMED,
    )
    db.add(deposit)
    await db.flush()

    db.add(
        DepositAuditLog(
            deposit_id=deposit.id,
            changed_by=created_by,
            action=AuditAction.CREATE,
            diff={"before": None, "after": _serialize(deposit)},
        )
    )
    await db.commit()
    await db.refresh(deposit)
    return deposit


async def update_deposit(
    db: AsyncSession,
    deposit: Deposit,
    *,
    changed_by: uuid.UUID,
    **fields,
) -> Deposit:
    before = _serialize(deposit)
    for key, value in fields.items():
        setattr(deposit, key, value)
    await db.flush()
    after = _serialize(deposit)

    db.add(
        DepositAuditLog(
            deposit_id=deposit.id,
            changed_by=changed_by,
            action=AuditAction.UPDATE,
            diff={"before": before, "after": after},
        )
    )
    await db.commit()
    await db.refresh(deposit)
    return deposit


async def delete_deposit(db: AsyncSession, deposit: Deposit, *, changed_by: uuid.UUID) -> None:
    before = _serialize(deposit)
    deposit.deleted_at = datetime.now(UTC)
    await db.flush()

    db.add(
        DepositAuditLog(
            deposit_id=deposit.id,
            changed_by=changed_by,
            action=AuditAction.DELETE,
            diff={"before": before, "after": None},
        )
    )
    await db.commit()
