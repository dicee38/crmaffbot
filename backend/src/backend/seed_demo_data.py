"""Generate a large randomized dataset (managers, channels, actions of every type)
for testing stats/leaderboards/salary calculations end-to-end.

Usage:
    uv run --package backend python -m backend.seed_demo_data <admin_telegram_id> [--count N]

<admin_telegram_id> must belong to an existing admin (see backend.seed) — its
organization is where the demo data gets created.
"""

import argparse
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from backend.config import settings
from shared.db import make_engine, make_session_factory
from shared.enums import ActionSource, ActionStatus, ActionType, Role, UserStatus
from shared.models import Channel, ChannelGroup, MopAction, Platform, Team, User

MANAGER_NAMES = [
    "Алина Соколова",
    "Данил Морозов",
    "Егор Волков",
    "Ирина Смирнова",
    "Максим Кузнецов",
    "Полина Орлова",
    "Роман Ковалёв",
    "Светлана Лебедева",
]

CHANNEL_NAMES = ["Telegram Ads", "YouTube", "Instagram", "Referral"]
TEAM_NAMES = ["Команда Альфа", "Команда Бета"]

ACTION_TYPE_WEIGHTS = {
    ActionType.REGISTRATION: 35,
    ActionType.FIRST_DEPOSIT: 20,
    ActionType.REPEAT_DEPOSIT: 25,
    ActionType.LEAD: 12,
    ActionType.WITHDRAWAL: 8,
}


async def seed_demo_data(admin_telegram_id: int, count: int) -> None:
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    async with session_factory() as db:
        admin = (
            await db.execute(select(User).where(User.telegram_id == admin_telegram_id))
        ).scalar_one_or_none()
        if admin is None:
            print(f"No user with telegram_id={admin_telegram_id} — run backend.seed first.")
            return
        org_id = admin.org_id

        platform = (
            await db.execute(select(Platform).where(Platform.org_id == org_id, Platform.slug == "demo"))
        ).scalar_one_or_none()
        if platform is None:
            platform = Platform(
                org_id=org_id,
                slug="demo",
                name="Demo Platform",
                adapter_key="manual",
                webhook_secret=uuid.uuid4().hex,
            )
            db.add(platform)
            await db.flush()

        group = (
            await db.execute(
                select(ChannelGroup).where(ChannelGroup.org_id == org_id, ChannelGroup.name == "Demo Channels")
            )
        ).scalar_one_or_none()
        if group is None:
            group = ChannelGroup(org_id=org_id, name="Demo Channels")
            db.add(group)
            await db.flush()

        channels = list(
            (
                await db.execute(
                    select(Channel).where(Channel.org_id == org_id, Channel.channel_group_id == group.id)
                )
            )
            .scalars()
            .all()
        )
        if not channels:
            for name in CHANNEL_NAMES:
                channel = Channel(
                    org_id=org_id, platform_id=platform.id, channel_group_id=group.id, name=name
                )
                db.add(channel)
                channels.append(channel)
            await db.flush()

        teams = list((await db.execute(select(Team).where(Team.org_id == org_id))).scalars().all())
        if not teams:
            for name in TEAM_NAMES:
                team = Team(org_id=org_id, name=name)
                db.add(team)
                teams.append(team)
            await db.flush()

        managers = list(
            (await db.execute(select(User).where(User.org_id == org_id, User.role == Role.MANAGER)))
            .scalars()
            .all()
        )
        existing_names = {m.full_name for m in managers}
        base_tg_id = 900_000_000
        for i, name in enumerate(MANAGER_NAMES):
            if name in existing_names:
                continue
            manager = User(
                org_id=org_id,
                telegram_id=base_tg_id + i,
                full_name=name,
                role=Role.MANAGER,
                team_id=teams[i % len(teams)].id,
                status=UserStatus.ACTIVE,
                fd_commission_rate=Decimal("10.00"),
                rd_commission_rate=Decimal("7.00"),
            )
            db.add(manager)
            managers.append(manager)
        await db.flush()

        action_types = list(ACTION_TYPE_WEIGHTS.keys())
        weights = list(ACTION_TYPE_WEIGHTS.values())
        now = datetime.now(timezone.utc)

        for _ in range(count):
            manager = random.choice(managers)
            channel = random.choice(channels)
            created_at = now - timedelta(
                days=random.randint(0, 89), hours=random.randint(0, 23), minutes=random.randint(0, 59)
            )
            player_id = f"player-{random.randint(10000, 99999)}"
            action_type = random.choices(action_types, weights=weights)[0]

            amount = None
            currency = None
            lead_count = 1
            if action_type == ActionType.FIRST_DEPOSIT:
                amount, currency = Decimal(random.randint(50, 500)), "USD"
            elif action_type == ActionType.REPEAT_DEPOSIT:
                amount, currency = Decimal(random.randint(20, 300)), "USD"
            elif action_type == ActionType.WITHDRAWAL:
                amount, currency = Decimal(random.randint(10, 200)), "USD"
            elif action_type == ActionType.LEAD:
                lead_count = random.randint(1, 5)

            db.add(
                MopAction(
                    org_id=org_id,
                    action_type=action_type,
                    mop_id=manager.id,
                    channel_id=channel.id,
                    player_id=player_id,
                    amount=amount,
                    currency=currency,
                    lead_count=lead_count,
                    source=ActionSource.MANUAL,
                    status=ActionStatus.CONFIRMED,
                    created_by=manager.id,
                    created_at=created_at,
                )
            )

        await db.commit()
        print(f"Seeded {len(managers)} managers, {len(channels)} channels, {count} actions in org {org_id}.")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("admin_telegram_id", type=int)
    parser.add_argument("--count", type=int, default=1500)
    args = parser.parse_args()
    asyncio.run(seed_demo_data(args.admin_telegram_id, args.count))


if __name__ == "__main__":
    main()
