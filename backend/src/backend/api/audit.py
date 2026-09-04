import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.permissions import require_role
from shared.enums import Role
from shared.models import ActionAuditLog, MopAction, User
from shared.schemas import AuditLogOut

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_log(
    action_id: uuid.UUID | None = Query(None),
    period_start: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    period_end: date = Query(default_factory=date.today),
    user: User = Depends(require_role(Role.TEAMLEAD, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[ActionAuditLog]:
    """ТЗ §4.6/§3: просмотр аудит-лога — тимлиду в рамках своей команды, админу всего.
    Аналитик по ТЗ §3 сюда доступа не имеет (только статистика/отчёты)."""
    conditions = [
        MopAction.org_id == user.org_id,
        ActionAuditLog.changed_at >= period_start,
        ActionAuditLog.changed_at < period_end + timedelta(days=1),
    ]
    if user.role == Role.TEAMLEAD:
        conditions.append(MopAction.mop_id.in_(select(User.id).where(User.team_id == user.team_id)))
    if action_id is not None:
        conditions.append(ActionAuditLog.action_id == action_id)

    result = await db.execute(
        select(ActionAuditLog)
        .join(MopAction, MopAction.id == ActionAuditLog.action_id)
        .where(*conditions)
        .order_by(ActionAuditLog.changed_at.desc())
    )
    return list(result.scalars().all())
