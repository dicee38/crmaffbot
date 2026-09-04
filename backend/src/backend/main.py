from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from backend.api import deposits, goals, reports, stats, users, webhooks
from backend.config import settings
from backend.scheduler import check_idle_managers, send_daily_digest, send_weekly_digest


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_digest, CronTrigger(hour=settings.digest_hour_utc, minute=0), id="daily_digest"
    )
    scheduler.add_job(
        send_weekly_digest,
        CronTrigger(day_of_week="mon", hour=settings.digest_hour_utc, minute=0),
        id="weekly_digest",
    )
    scheduler.add_job(
        check_idle_managers,
        CronTrigger(hour=settings.digest_hour_utc, minute=5),
        id="idle_check",
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(title="Sales CRM Bot Backend", lifespan=lifespan)

app.include_router(deposits.router)
app.include_router(stats.router)
app.include_router(users.router)
app.include_router(webhooks.router)
app.include_router(goals.router)
app.include_router(reports.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
