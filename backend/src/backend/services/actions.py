import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import ActionSource, ActionStatus, ActionType, AuditAction
from shared.models import ActionAuditLog, MopAction


def _serialize(action: MopAction) -> dict:
    return {
        "action_type": action.action_type.value,
        "player_id": action.player_id,
        "channel_id": str(action.channel_id) if action.channel_id else None,
        "amount": str(action.amount) if action.amount is not None else None,
        "currency": action.currency,
        "lead_count": action.lead_count,
        "source": action.source.value,
        "external_id": action.external_id,
        "status": action.status.value,
    }


async def create_manual_action(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    mop_id: uuid.UUID,
    action_type: ActionType,
    channel_id: uuid.UUID | None,
    player_id: str | None,
    amount: Decimal | None,
    currency: str | None,
    lead_count: int,
    created_by: uuid.UUID,
) -> MopAction:
    action = MopAction(
        org_id=org_id,
        mop_id=mop_id,
        action_type=action_type,
        channel_id=channel_id,
        player_id=player_id,
        amount=amount,
        currency=currency,
        lead_count=lead_count,
        source=ActionSource.MANUAL,
        status=ActionStatus.CONFIRMED,
        created_by=created_by,
    )
    db.add(action)
    await db.flush()

    db.add(
        ActionAuditLog(
            action_id=action.id,
            changed_by=created_by,
            action=AuditAction.CREATE,
            diff={"before": None, "after": _serialize(action)},
        )
    )
    await db.commit()
    await db.refresh(action)
    return action


async def update_action(
    db: AsyncSession,
    action: MopAction,
    *,
    changed_by: uuid.UUID,
    **fields,
) -> MopAction:
    before = _serialize(action)
    for key, value in fields.items():
        setattr(action, key, value)
    await db.flush()
    after = _serialize(action)

    db.add(
        ActionAuditLog(
            action_id=action.id,
            changed_by=changed_by,
            action=AuditAction.UPDATE,
            diff={"before": before, "after": after},
        )
    )
    await db.commit()
    await db.refresh(action)
    return action


async def delete_action(db: AsyncSession, action: MopAction, *, changed_by: uuid.UUID) -> None:
    before = _serialize(action)
    action.deleted_at = datetime.now(UTC)
    await db.flush()

    db.add(
        ActionAuditLog(
            action_id=action.id,
            changed_by=changed_by,
            action=AuditAction.DELETE,
            diff={"before": before, "after": None},
        )
    )
    await db.commit()
