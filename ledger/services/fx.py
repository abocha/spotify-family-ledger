"""FX rate service — lookup and insertion."""

from datetime import date

from sqlalchemy.orm import Session

from ledger.models import FxRate


def get_fx_rate(session: Session, rate_date: date) -> FxRate | None:
    """Return the FxRate for the exact date, or None if not found."""
    return session.get(FxRate, rate_date)


def get_latest_fx_rate(session: Session) -> FxRate | None:
    """Return the most recent FxRate row (for display-only RUB equivalent)."""
    return (
        session.query(FxRate)
        .order_by(FxRate.rate_date.desc())
        .first()
    )


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


def list_fx_rates(session: Session, limit: int = 100) -> list[FxRate]:
    """Return recent FX rates, newest first."""
    return (
        session.query(FxRate)
        .order_by(FxRate.rate_date.desc())
        .limit(limit)
        .all()
    )
