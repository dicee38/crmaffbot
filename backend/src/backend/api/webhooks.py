import hashlib
import hmac
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.deps import get_db
from shared.models import DepositEventRaw

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_signature(body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = hmac.new(settings.affiliate_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/affiliate/{provider}", status_code=status.HTTP_202_ACCEPTED)
async def receive_affiliate_event(
    provider: str,
    request: Request,
    x_org_id: uuid.UUID = Header(..., alias="X-Org-Id"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Приём сырых событий партнёрки (ТЗ §4.5). Сопоставление с депозитом по sub-ID/метке
    не реализовано — конкретный провайдер ещё не выбран, см. §9. Событие только сохраняется."""
    body = await request.body()
    if not _verify_signature(body, request.headers.get("X-Signature")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

    payload = await request.json()
    event = DepositEventRaw(org_id=x_org_id, provider=provider, payload=payload)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return {"status": "accepted", "event_id": str(event.id)}
