from decimal import Decimal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://crm:crm@localhost:5432/crm"
    affiliate_webhook_secret: str = "dev-secret"
    dedup_window_minutes: int = 15
    # Same bot token as bot/.env — backend pushes Telegram notifications directly,
    # independent of the aiogram long-polling process (ТЗ §4.4).
    bot_token: str | None = None
    # Shared secret only the bot process knows — required alongside X-Telegram-User-Id so a
    # browser (e.g. the Mini App) can't just forge that header to impersonate any user.
    internal_api_secret: str = "dev-internal-secret"
    # Exact value is an open question (ТЗ §9) until the business sets one; configurable for now.
    large_deposit_threshold: Decimal = Decimal("1000")
    # Hour (UTC) the daily/weekly digest and idle-manager check run at.
    digest_hour_utc: int = 6
    idle_days_threshold: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, value: str) -> str:
        # Railway's managed Postgres (and most hosts) hand out a plain postgres(ql):// URL;
        # SQLAlchemy's async engine needs the +asyncpg driver suffix to use it.
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value


settings = Settings()
