from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://crm:crm@localhost:5432/crm"
    affiliate_webhook_secret: str = "dev-secret"
    dedup_window_minutes: int = 15
    # Same bot token as bot/.env — backend pushes Telegram notifications directly,
    # independent of the aiogram long-polling process (ТЗ §4.4).
    bot_token: str | None = None
    # Exact value is an open question (ТЗ §9) until the business sets one; configurable for now.
    large_deposit_threshold: Decimal = Decimal("1000")
    # Hour (UTC) the daily/weekly digest and idle-manager check run at.
    digest_hour_utc: int = 6
    idle_days_threshold: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
