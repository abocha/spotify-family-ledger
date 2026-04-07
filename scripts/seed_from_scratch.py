#!/usr/bin/env python3
"""Seed the database from scratch with corrected legacy balances."""

import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.getcwd())

from ledger.database import SessionLocal
from ledger.models import FxRate, LegacySnapshot, Member

# Corrected USD balances from the fixed legacy spreadsheet.
# These are debts, so they stay negative.
CORRECTED_LEGACY_USD = {
    "Андрей": Decimal("0.00"),
    "Даша": Decimal("0.00"),
    "Гала": Decimal("-6.67"),
    "Семен": Decimal("-10.06"),
    "Луиза": Decimal("-10.67"),
    "Даня": Decimal("-7.99"),
}

TODAY = date.today()
FX_RATE = Decimal("79.00")  # USD/RUB as of today


def main():
    print(f"Seeding database for {TODAY} at FX rate {FX_RATE}")

    with SessionLocal() as session:
        fx = session.get(FxRate, TODAY)
        if fx:
            fx.usd_rub = FX_RATE
            print(f"Updated today's FX rate: {FX_RATE}")
        else:
            session.add(
                FxRate(
                    rate_date=TODAY,
                    usd_rub=FX_RATE,
                    source="manual seed",
                )
            )
            print(f"Added today's FX rate: {FX_RATE}")

        for name, usd_balance in CORRECTED_LEGACY_USD.items():
            rub_balance = (usd_balance * FX_RATE).quantize(Decimal("0.01"))

            member = session.query(Member).filter_by(display_name=name).first()
            if not member:
                member = Member(
                    display_name=name,
                    active_from=date(2023, 5, 20),
                    active_to=None,
                    counted_in_denominator=True,
                    billable_after_cutover=True,
                    note="Seeded with corrected legacy balance",
                )
                session.add(member)
                session.flush()

            existing = session.query(LegacySnapshot).filter_by(member_id=member.id).first()
            if existing:
                existing.opening_balance_rub = rub_balance
                existing.source_usd_balance = usd_balance
                existing.snapshot_date = TODAY
                print(f"Updated {name}: {usd_balance} USD → {rub_balance} RUB")
            else:
                session.add(
                    LegacySnapshot(
                        member_id=member.id,
                        snapshot_date=TODAY,
                        opening_balance_rub=rub_balance,
                        source_usd_balance=usd_balance,
                        source_note="Corrected legacy balance (spreadsheet fix)",
                    )
                )
                print(f"Added {name}: {usd_balance} USD → {rub_balance} RUB")

        session.commit()

    with SessionLocal() as session:
        from ledger.services import get_member_balances

        balances = get_member_balances(session)
        print("\n📊 Current member balances:")
        for b in balances:
            status = "owes" if b.balance_rub < 0 else ("credit" if b.balance_rub > 0 else "settled")
            print(f"  {b.display_name:<10s} {b.balance_rub:>10.2f} RUB  ({status})")


if __name__ == "__main__":
    main()
