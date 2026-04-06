from datetime import date
from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TURSO_URL: str
    TURSO_KEY: str

    # Monthly Spotify Family subscription cost in USD
    SUBSCRIPTION_USD: Decimal = Decimal("8.00")

    # From 2026-04-20 onward, this app is the contractual source of truth
    CUTOVER_DATE: date = date(2026, 4, 20)

    # How many months ahead to keep forecast cycles generated
    FORECAST_HORIZON_MONTHS: int = 6


settings = Settings()
