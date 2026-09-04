"""Bootstrap the first organization and admin user (§10 ТЗ needs at least one admin to manage everything else).

Usage:
    uv run --package backend python -m backend.seed "Org Name" <admin_telegram_id> "Admin Full Name"
"""

import asyncio
import sys

from sqlalchemy import select

from backend.config import settings
from shared.db import make_engine, make_session_factory
from shared.enums import Role, UserStatus
from shared.models import Organization, User


async def seed(org_name: str, admin_telegram_id: int, admin_full_name: str) -> None:
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    async with session_factory() as db:
        existing = await db.execute(select(User).where(User.telegram_id == admin_telegram_id))
        if existing.scalar_one_or_none() is not None:
            print(f"User with telegram_id={admin_telegram_id} already exists, nothing to do.")
            return

        org = Organization(name=org_name)
        db.add(org)
        await db.flush()

        admin = User(
            org_id=org.id,
            telegram_id=admin_telegram_id,
            full_name=admin_full_name,
            role=Role.ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.add(admin)
        await db.commit()

        print(f"Created organization '{org_name}' ({org.id}) and admin '{admin_full_name}' ({admin_telegram_id}).")

    await engine.dispose()


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        raise SystemExit(1)

    org_name, telegram_id_raw, admin_full_name = sys.argv[1:4]
    asyncio.run(seed(org_name, int(telegram_id_raw), admin_full_name))


if __name__ == "__main__":
    main()
