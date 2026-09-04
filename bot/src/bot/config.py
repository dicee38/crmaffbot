from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    backend_url: str = "http://localhost:8000"
    # Must match backend's INTERNAL_API_SECRET — proves requests come from this trusted
    # process rather than a browser forging X-Telegram-User-Id (see backend/deps.py).
    internal_api_secret: str = "dev-internal-secret"
    miniapp_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def auth_headers(telegram_id: int) -> dict[str, str]:
    return {
        "X-Telegram-User-Id": str(telegram_id),
        "X-Internal-Secret": settings.internal_api_secret,
    }
