from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from ledger.database import get_db
from ledger.services.integrity import check_integrity
from ledger.services.queries import (
    get_ledger_status,
    get_member_statement,
    list_admin_reconciliation_history,
    list_member_balances,
    list_recent_payments,
)


def _money_label(balance_rub: Decimal) -> str:
    if balance_rub < 0:
        return "owes owner"
    if balance_rub > 0:
        return "has credit"
    return "settled"


@st.cache_data(show_spinner=False)
def load_integrity_issues() -> list[dict]:
    with get_db() as session:
        return [issue.model_dump() for issue in check_integrity(session)]


@st.cache_data(show_spinner=False)
def load_home_data() -> dict:
    with get_db() as session:
        status = get_ledger_status(session)
        balances = list_member_balances(session)
        recent_payments = list_recent_payments(session, limit=8)

    balances_df = pd.DataFrame(
        [
            {
                "Member": balance.display_name,
                "Balance (RUB)": float(balance.balance_rub),
                "Status": _money_label(balance.balance_rub),
                "Last Payment": balance.last_payment_date,
                "Last Charged Month": balance.last_charge_date,
            }
            for balance in balances
        ]
    )

    recent_payments_df = pd.DataFrame(
        [
            {
                "Date": payment.payment_date,
                "Member": payment.display_name,
                "RUB Paid": float(payment.rub_paid),
                "Note": payment.note,
            }
            for payment in recent_payments
        ]
    )

    total_owed = float(sum((-balance.balance_rub for balance in balances if balance.balance_rub < 0), Decimal("0")))
    return {
        "status": status.model_dump(mode="json"),
        "balances_df": balances_df,
        "recent_payments_df": recent_payments_df,
        "total_owed_rub": total_owed,
    }


@st.cache_data(show_spinner=False)
def load_statement_data(member_id: int) -> dict:
    with get_db() as session:
        statement = get_member_statement(session, member_id)

    entries_df = pd.DataFrame(
        [
            {
                "Date": entry.entry_date,
                "Type": entry.entry_type.replace("_", " ").title(),
                "Description": entry.description,
                "Amount (RUB)": float(entry.amount_rub),
                "Running Balance (RUB)": float(entry.balance_rub),
                "FX Locked": float(entry.fx_locked) if entry.fx_locked is not None else None,
                "Subscription USD": float(entry.subscription_usd) if entry.subscription_usd is not None else None,
                "Note": entry.note,
            }
            for entry in statement.entries
        ]
    )
    return {
        "statement": statement.model_dump(mode="json"),
        "entries_df": entries_df,
    }


@st.cache_data(show_spinner=False)
def load_member_options() -> list[tuple[int, str]]:
    with get_db() as session:
        balances = list_member_balances(session)
    return [(balance.member_id, balance.display_name) for balance in balances]


@st.cache_data(show_spinner=False)
def load_admin_reconciliation_history() -> pd.DataFrame:
    with get_db() as session:
        history = list_admin_reconciliation_history(session, limit=30)

    return pd.DataFrame(
        [
            {
                "Started At": item.started_at,
                "Trigger": item.trigger,
                "Status": item.status,
                "From": item.from_cycle_date,
                "To": item.to_cycle_date,
                "Exact Through": item.last_successful_cycle_date,
                "Failure Cycle": item.error_cycle_date,
                "Failure Message": item.error_message,
                "Cycles Posted": item.cycles_posted_count,
                "Alert Sent": item.alert_sent,
                "Alert Error": item.alert_error,
            }
            for item in history
        ]
    )
