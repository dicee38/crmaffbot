import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deps import get_db
from backend.permissions import require_role
from shared.enums import Role
from shared.models import Channel, ChannelGroup, Platform, User
from shared.schemas import (
    ChannelCreate,
    ChannelGroupCreate,
    ChannelGroupOut,
    ChannelOut,
    PlatformCreate,
    PlatformOut,
    PlatformUpdate,
)

router = APIRouter(tags=["platforms"])


@router.get("/platforms", response_model=list[PlatformOut])
async def list_platforms(
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYTIC, Role.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> list[Platform]:
    result = await db.execute(select(Platform).where(Platform.org_id == user.org_id))
    return list(result.scalars().all())


@router.post("/platforms", response_model=PlatformOut, status_code=status.HTTP_201_CREATED)
async def create_platform(
    payload: PlatformCreate,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Platform:
    existing = await db.execute(
        select(Platform).where(Platform.org_id == admin.org_id, Platform.slug == payload.slug)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already used in this organization")

    platform = Platform(
        org_id=admin.org_id,
        slug=payload.slug,
        name=payload.name,
        adapter_key=payload.adapter_key,
        webhook_secret=payload.webhook_secret,
    )
    db.add(platform)
    await db.commit()
    await db.refresh(platform)
    return platform


@router.patch("/platforms/{platform_id}", response_model=PlatformOut)
async def update_platform(
    platform_id: uuid.UUID,
    payload: PlatformUpdate,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Platform:
    platform = await db.get(Platform, platform_id)
    if platform is None or platform.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Platform not found")

    if payload.name is not None:
        platform.name = payload.name
    if payload.is_active is not None:
        platform.is_active = payload.is_active

    await db.commit()
    await db.refresh(platform)
    return platform


@router.get("/channel-groups", response_model=list[ChannelGroupOut])
async def list_channel_groups(
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYTIC, Role.OWNER, Role.TEAMLEAD)),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelGroup]:
    result = await db.execute(select(ChannelGroup).where(ChannelGroup.org_id == user.org_id))
    return list(result.scalars().all())


@router.post("/channel-groups", response_model=ChannelGroupOut, status_code=status.HTTP_201_CREATED)
async def create_channel_group(
    payload: ChannelGroupCreate,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ChannelGroup:
    group = ChannelGroup(org_id=admin.org_id, name=payload.name)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("/channels", response_model=list[ChannelOut])
async def list_channels(
    user: User = Depends(require_role(Role.ADMIN, Role.ANALYTIC, Role.OWNER, Role.TEAMLEAD, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> list[Channel]:
    result = await db.execute(select(Channel).where(Channel.org_id == user.org_id))
    return list(result.scalars().all())


@router.post("/channels", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
async def create_channel(
    payload: ChannelCreate,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Channel:
    platform = await db.get(Platform, payload.platform_id)
    if platform is None or platform.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Platform not found")

    if payload.channel_group_id is not None:
        group = await db.get(ChannelGroup, payload.channel_group_id)
        if group is None or group.org_id != admin.org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel group not found")

    channel = Channel(
        org_id=admin.org_id,
        platform_id=payload.platform_id,
        channel_group_id=payload.channel_group_id,
        name=payload.name,
        external_code=payload.external_code,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel
