import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from shared.models import ActionEventRaw, Platform

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_signature(body: bytes, secret: str, signature: str | None) -> bool:
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/affiliate/{platform_slug}", status_code=status.HTTP_202_ACCEPTED)
async def receive_affiliate_event(
    platform_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Приём сырых событий партнёрской платформы (ТЗ §4.5, §11.4). Сопоставление с
    действием по sub-ID/метке не реализовано — конкретный провайдер ещё не выбран,
    см. §9. Событие сохраняется как есть, привязка по platform_slug (уникален в
    рамках организации — при появлении второй организации потребуется дизамбигуация)."""
    result = await db.execute(
        select(Platform).where(Platform.slug == platform_slug, Platform.is_active.is_(True))
    )
    platform = result.scalar_one_or_none()
    if platform is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown or inactive platform")

    body = await request.body()
    if not _verify_signature(body, platform.webhook_secret, request.headers.get("X-Signature")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

    payload = await request.json()
    event = ActionEventRaw(org_id=platform.org_id, platform_id=platform.id, payload=payload)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return {"status": "accepted", "event_id": str(event.id)}
