import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.permissions import require_role
from shared.enums import Role
from shared.models import Deposit, DepositAuditLog, User
from shared.schemas import AuditLogOut

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_log(
    deposit_id: uuid.UUID | None = Query(None),
    period_start: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    period_end: date = Query(default_factory=date.today),
    user: User = Depends(require_role(Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[DepositAuditLog]:
    """ТЗ §4.6/§3: просмотр аудит-лога — тимлиду в рамках своей команды, админу всего."""
    conditions = [
        Deposit.org_id == user.org_id,
        DepositAuditLog.changed_at >= period_start,
        DepositAuditLog.changed_at < period_end + timedelta(days=1),
    ]
    if user.role == Role.TEAMLEAD:
        conditions.append(Deposit.manager_id.in_(select(User.id).where(User.team_id == user.team_id)))
    if deposit_id is not None:
        conditions.append(DepositAuditLog.deposit_id == deposit_id)

    result = await db.execute(
        select(DepositAuditLog)
        .join(Deposit, Deposit.id == DepositAuditLog.deposit_id)
        .where(*conditions)
        .order_by(DepositAuditLog.changed_at.desc())
    )
    return list(result.scalars().all())
