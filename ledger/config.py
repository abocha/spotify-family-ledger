from datetime import date
from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TURSO_URL: str = "sqlite:///local.db"
    TURSO_KEY: str = ""

    CURRENCYBEACON_API_KEY: str = ""
    EXCHANGERATE_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    SUBSCRIPTION_USD: Decimal = Decimal("8.00")
    CUTOVER_DATE: date = date(2026, 4, 20)
    RECONCILIATION_LOCK_TTL_SECONDS: int = 300


settings = Settings()
