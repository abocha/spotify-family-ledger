from datetime import date
from decimal import Decimal

import pytest

from ledger.services.fx import add_fx_rate, get_fx_rate, get_latest_fx_rate


def test_add_and_get_fx_rate(session):
    d = date(2026, 4, 20)
    add_fx_rate(session, d, 95.5)
    session.commit()

    fx = get_fx_rate(session, d)
    assert fx is not None
    assert fx.usd_rub == Decimal("95.5")


def test_add_duplicate_fails(session):
    d = date(2026, 4, 20)
    add_fx_rate(session, d, 95.5)
    session.commit()

    with pytest.raises(ValueError, match="already exists"):
        add_fx_rate(session, d, 96.0)


def test_get_latest(session):
    add_fx_rate(session, date(2026, 4, 20), 95.0)
    add_fx_rate(session, date(2026, 4, 22), 96.0)
    session.commit()

    latest = get_latest_fx_rate(session)
    assert latest is not None
    assert latest.usd_rub == Decimal("96.0")
    assert latest.rate_date == date(2026, 4, 22)
