from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from ledger.database import get_db
from ledger.services import (
    check_integrity,
    fetch_market_rate,
    get_latest_fx_rate,
    get_member_balances,
    get_next_unposted_cycle,
    list_all_cycles,
    list_fx_rates,
    list_payments,
)

ZERO = Decimal("0")


@st.cache_data(ttl=60, show_spinner=False, max_entries=64)
def load_dashboard_data() -> dict:
    with get_db() as session:
        balances = get_member_balances(session)
        next_cycle = get_next_unposted_cycle(session)
        latest_fx = get_latest_fx_rate(session)
        recent_payments = list_payments(session, limit=5)

    owed_total = float(sum(-b.balance_rub for b in balances if b.balance_rub < 0))

    balances_df = pd.DataFrame(
        [
            {
                "Member": b.display_name,
                "Balance (RUB)": float(b.balance_rub),
                "Status": (
                    "✅has credit"
                    if b.balance_rub > 0
                    else ("❌owes owner" if b.balance_rub < 0 else "✅settled")
                ),
            }
            for b in balances
            if b.balance_rub != 0
        ]
    )

    recent_payments_df = pd.DataFrame(
        [
            {
                "Date": p.payment_date,
                "Member": p.display_name,
                "RUB": float(p.rub_paid),
                "Recorded Credit (RUB)": float(p.rub_credit),
            }
            for p in recent_payments
        ]
    )

    return {
        "balances_df": balances_df,
        "balances_count": len(balances),
        "owed_total": owed_total,
        "next_cycle_date": next_cycle.cycle_date if next_cycle else None,
        "latest_fx": (
            {
                "usd_rub": float(latest_fx.usd_rub),
                "source": latest_fx.source,
                "rate_date": latest_fx.rate_date,
            }
            if latest_fx
            else None
        ),
        "recent_payments_df": recent_payments_df,
    }


@st.cache_data(ttl="15m", show_spinner=False, max_entries=16)
def load_integrity_issues() -> list[dict]:
    with get_db() as session:
        return [issue.model_dump() for issue in check_integrity(session)]


@st.cache_data(ttl="15m", show_spinner=False, max_entries=8)
def load_market_rate_value() -> float | None:
    return fetch_market_rate()


@st.cache_data(ttl=120, show_spinner=False, max_entries=64)
def load_cycles_history_df() -> pd.DataFrame:
    with get_db() as session:
        cycles = list_all_cycles(session)

    return pd.DataFrame(
        [
            {
                "Date": c.cycle_date,
                "Status": c.status,
                "Subscription USD": float(c.subscription_usd),
                "Subscription RUB": float(c.subscription_rub) if c.subscription_rub is not None else None,
                "Counted / Billed": f"{c.counted_active or '-'} / {c.billed_active or '-'}",
                "Owner Subsidy RUB": float(c.owner_subsidy_rub) if c.owner_subsidy_rub is not None else None,
                "Posted At": c.posted_at.strftime("%Y-%m-%d %H:%M:%S") if c.posted_at else None,
            }
            for c in cycles
        ]
    )


@st.cache_data(ttl=120, show_spinner=False, max_entries=64)
def load_payments_history_df() -> pd.DataFrame:
    with get_db() as session:
        payments = list_payments(session)

    return pd.DataFrame(
        [
            {
                "Date": p.payment_date,
                "Member": p.display_name,
                "RUB Paid": float(p.rub_paid),
                "Recorded Credit (RUB)": float(p.rub_credit),
                "Note": p.note,
                "Logged At": p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for p in payments
        ]
    )


@st.cache_data(ttl=120, show_spinner=False, max_entries=64)
def load_fx_rates_history_df() -> pd.DataFrame:
    with get_db() as session:
        fx_rates = list_fx_rates(session)

    return pd.DataFrame(
        [
            {
                "Date": fx.rate_date,
                "USD/RUB": float(fx.usd_rub),
                "Source": fx.source,
                "Imported At": fx.imported_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for fx in fx_rates
        ]
    )