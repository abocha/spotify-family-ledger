from datetime import date
from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",  # optional fallback for non-Streamlit CLI use
        env_file_encoding="utf-8",
    )

    TURSO_URL: str = "sqlite:///local.db"
    TURSO_KEY: str = ""

    CURRENCYBEACON_API_KEY: str = ""
    EXCHANGERATE_API_KEY: str = ""

    SUBSCRIPTION_USD: Decimal = Decimal("8.00")
    CUTOVER_DATE: date = date(2026, 4, 20)
    FORECAST_HORIZON_MONTHS: int = 6


settings = Settings()