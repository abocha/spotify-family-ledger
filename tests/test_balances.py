from datetime import date
from decimal import Decimal
import pytest

from ledger.models import LegacySnapshot
from ledger.services.balances import get_member_balance, get_total_owed_usd


def test_balance_legacy_only(session, active_member):
    snap = LegacySnapshot(
        member_id=active_member.id,
        snapshot_date=date(2026, 4, 1),
        opening_balance_usd=Decimal("10.50"),
        source_note="test"
    )
    session.add(snap)
    session.commit()

    bal = get_member_balance(session, active_member.id)
    assert bal.balance_usd == Decimal("10.50")
    assert bal.balance_rub_equivalent is None # No FX rate yet

def test_total_owed(session, active_member):
    snap = LegacySnapshot(
        member_id=active_member.id,
        snapshot_date=date(2026, 4, 1),
        opening_balance_usd=Decimal("15.00")
    )
    session.add(snap)
    session.commit()
    
    assert get_total_owed_usd(session) == Decimal("15.00")
