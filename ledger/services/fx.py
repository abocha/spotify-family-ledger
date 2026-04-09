"""FX persistence helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from ledger.models import FxRate
from ledger.services.market_fx import fetch_historical_fx_rate


def get_fx_rate(session: Session, rate_date: date) -> FxRate | None:
    return session.get(FxRate, rate_date)


def get_or_fetch_fx_rate(session: Session, rate_date: date) -> FxRate:
    existing = get_fx_rate(session, rate_date)
    if existing is not None:
        return existing

    fetched = fetch_historical_fx_rate(rate_date)
    if fetched is None:
        raise ValueError(f"CurrencyBeacon returned no USD/RUB rate for {rate_date}.")

    rate = FxRate(
        rate_date=rate_date,
        usd_rub=Decimal(fetched),
        source="CurrencyBeacon historical",
    )
    session.add(rate)
    session.flush()
    return rate
