"""FX rate service — lookup and insertion."""

from datetime import date

from sqlalchemy.orm import Session

from ledger.models import FxRate
from ledger.services.market_fx import fetch_historical_fx_rate


def get_fx_rate(session: Session, rate_date: date) -> FxRate | None:
    """Return the FxRate for the exact date, or None if not found."""
    return session.get(FxRate, rate_date)


def get_latest_fx_rate(session: Session) -> FxRate | None:
    """Return the most recent FxRate row (for display-only RUB equivalent)."""
    return session.query(FxRate).order_by(FxRate.rate_date.desc()).first()


def ensure_fx_rate(session: Session, rate_date: date) -> FxRate:
    """Ensure a rate exists for the given date, fetching historical data if needed."""
    existing = get_fx_rate(session, rate_date)
    if existing is not None:
        return existing

    fetched = fetch_historical_fx_rate(rate_date)
    if fetched is None:
        raise ValueError(f"CurrencyBeacon returned no USD/RUB rate for {rate_date}.")

    rate = FxRate(rate_date=rate_date, usd_rub=fetched, source="CurrencyBeacon historical")
    session.add(rate)
    session.flush()
    return rate


def add_fx_rate(
    session: Session,
    rate_date: date,
    usd_rub: float,
    source: str | None = None,
) -> FxRate:
    """Insert a new FX rate. Raises ValueError if a rate already exists for that date."""
    existing = get_fx_rate(session, rate_date)
    if existing is not None:
        raise ValueError(
            f"An FX rate for {rate_date} already exists ({existing.usd_rub} USD/RUB). "
            "Delete it first if you need to correct it."
        )
    rate = FxRate(rate_date=rate_date, usd_rub=usd_rub, source=source)
    session.add(rate)
    return rate


def delete_fx_rate(session: Session, rate_date: date) -> None:
    """Delete an FX rate. Does not affect already-posted cycles or payments which lock their own copy."""
    rate = get_fx_rate(session, rate_date)
    if not rate:
        raise ValueError(f"No FX rate found for {rate_date}.")
    session.delete(rate)


def list_fx_rates(session: Session, limit: int = 100) -> list[FxRate]:
    """Return recent FX rates, newest first."""
    return session.query(FxRate).order_by(FxRate.rate_date.desc()).limit(limit).all()
