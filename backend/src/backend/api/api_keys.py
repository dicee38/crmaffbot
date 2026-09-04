import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api_keys import generate_api_key
from backend.deps import get_db
from backend.permissions import require_role
from shared.enums import Role
from shared.models import ApiKey, User
from shared.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    admin: User = Depends(require_role(Role.ADMIN, Role.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKey]:
    result = await db.execute(select(ApiKey).where(ApiKey.org_id == admin.org_id))
    return list(result.scalars().all())


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    admin: User = Depends(require_role(Role.ADMIN, Role.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    target = await db.get(User, payload.user_id)
    if target is None or target.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(
        org_id=admin.org_id,
        user_id=target.id,
        name=payload.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        created_by=admin.id,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return ApiKeyCreated(key=key, **ApiKeyOut.model_validate(api_key).model_dump())


@router.post("/{api_key_id}/revoke", response_model=ApiKeyOut)
async def revoke_api_key(
    api_key_id: uuid.UUID,
    admin: User = Depends(require_role(Role.ADMIN, Role.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    api_key = await db.get(ApiKey, api_key_id)
    if api_key is None or api_key.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    api_key.is_active = False
    await db.commit()
    await db.refresh(api_key)
    return api_key
