#!/usr/bin/env python3
"""Seed a fresh v2 database with example members and opening balances."""

from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.getcwd())

from ledger.database import SessionLocal
from ledger.models import FxRate, Member, OpeningBalance


SEED_OPENING_USD = {
    "Андрей": Decimal("0.00"),
    "Даша": Decimal("0.00"),
    "Гала": Decimal("-6.67"),
    "Семен": Decimal("-10.06"),
    "Луиза": Decimal("-10.67"),
    "Даня": Decimal("-7.99"),
}

SNAPSHOT_DATE = date(2026, 4, 20)
FX_RATE = Decimal("79.00")


def main() -> None:
    with SessionLocal() as session:
        session.add(
            FxRate(
                rate_date=SNAPSHOT_DATE,
                usd_rub=FX_RATE,
                source="seed",
            )
        )

        for name, usd_balance in SEED_OPENING_USD.items():
            member = Member(
                display_name=name,
                active_from=date(2023, 5, 20),
                counted_in_denominator=True,
                billable_after_cutover=name != "Андрей",
                note="Seed member",
            )
            session.add(member)
            session.flush()

            session.add(
                OpeningBalance(
                    member_id=member.id,
                    snapshot_date=SNAPSHOT_DATE,
                    opening_balance_rub=(usd_balance * FX_RATE).quantize(Decimal("0.01")),
                    source_usd_balance=usd_balance,
                    source_note="Seed opening balance",
                )
            )

        session.commit()
        print("Seed data created.")


if __name__ == "__main__":
    main()
