import io
import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_current_user, get_db
from shared.enums import Role
from shared.models import Channel, MopAction, User

router = APIRouter(prefix="/reports", tags=["reports"])


async def _assert_can_export(
    db: AsyncSession, user: User, scope: str, scope_id: uuid.UUID | None
) -> None:
    if user.role in (Role.ADMIN, Role.OWNER, Role.ANALYTIC):
        return
    if user.role == Role.TEAMLEAD:
        if scope == "team" and scope_id == user.team_id:
            return
        if scope == "user" and scope_id is not None:
            target = await db.get(User, scope_id)
            if target is not None and target.team_id == user.team_id:
                return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to export this scope")


@router.get("/export")
async def export_actions(
    scope: Literal["user", "team", "company"] = Query(...),
    scope_id: uuid.UUID | None = Query(None),
    period_start: date = Query(...),
    period_end: date = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if scope != "company" and scope_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "scope_id is required for user/team scope")

    await _assert_can_export(db, user, scope, scope_id)

    conditions = [
        MopAction.org_id == user.org_id,
        MopAction.deleted_at.is_(None),
        MopAction.created_at >= period_start,
        MopAction.created_at < period_end + timedelta(days=1),
    ]
    if scope == "user":
        conditions.append(MopAction.mop_id == scope_id)
    elif scope == "team":
        conditions.append(MopAction.mop_id.in_(select(User.id).where(User.team_id == scope_id)))

    result = await db.execute(
        select(MopAction, User.full_name, Channel.name)
        .join(User, User.id == MopAction.mop_id)
        .outerjoin(Channel, Channel.id == MopAction.channel_id)
        .where(*conditions)
        .order_by(MopAction.created_at)
    )
    rows = result.all()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Actions"
    sheet.append(
        [
            "MOP",
            "Action Type",
            "Player ID",
            "Channel",
            "Amount",
            "Currency",
            "Lead Count",
            "Source",
            "Status",
            "Created At",
        ]
    )
    for action, full_name, channel_name in rows:
        sheet.append(
            [
                full_name,
                action.action_type.value,
                action.player_id or "",
                channel_name or "",
                float(action.amount) if action.amount is not None else "",
                action.currency or "",
                action.lead_count,
                action.source.value,
                action.status.value,
                # openpyxl can't write timezone-aware datetimes, so store as plain text.
                action.created_at.replace(tzinfo=None).isoformat(sep=" "),
            ]
        )

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    filename = f"actions_{scope}_{period_start}_{period_end}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
