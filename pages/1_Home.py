import streamlit as st
import pandas as pd

from ledger.database import get_db
from ledger.bootstrap import bootstrap_page
from ledger.services import (
    check_integrity,
    fetch_market_rate,
    get_latest_fx_rate,
    get_member_balances,
    get_next_unposted_cycle,
    list_payments,
)

st.title("Dashboard")

with get_db() as session:
    bootstrap_page(session)
    issues = check_integrity(session)
    if issues:
        st.error(f"Found {len(issues)} integrity issue(s). Data needs attention.")
        for issue in issues:
            st.warning(issue.message)

    balances = get_member_balances(session)
    next_cycle = get_next_unposted_cycle(session)
    latest_fx = get_latest_fx_rate(session)
    recent_payments = list_payments(session, limit=5)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Balances")
    # balance_rub is the field name now
    owed_to_owner = sum((-b.balance_rub for b in balances if b.balance_rub < 0))
    st.metric("Total Owed to Owner (RUB)", f"{owed_to_owner:.2f}")

    if balances:
        owed_df = pd.DataFrame(
            [
                {
                    "Member": b.display_name,
                    "Balance (RUB)": f"{b.balance_rub:.2f}",
                    "Status": "has credit" if b.balance_rub > 0 else ("owes owner" if b.balance_rub < 0 else "settled"),
                }
                for b in balances
                if b.balance_rub != 0
            ]
        )
        if not owed_df.empty:
            st.dataframe(owed_df, hide_index=True)
        else:
            st.success("Everyone is settled!")
    else:
        st.info("No members configured yet.")

with col2:
    st.subheader("Next Action")
    if next_cycle:
        st.info(f"Next cycle to post: **{next_cycle.cycle_date.strftime('%B %Y')}**")
    else:
        st.success("All forecasted cycles are posted.")

    st.subheader("Latest FX Rate")
    market_rate = fetch_market_rate()

    col2a, col2b = st.columns(2)
    with col2a:
        if latest_fx:
            st.metric(
                "Locked cycle FX (USD/RUB)",
                f"{latest_fx.usd_rub:.4f}",
                help=f"Source: {latest_fx.source} (Date: {latest_fx.rate_date})",
            )
        else:
            st.warning("No FX rates recorded.")

    with col2b:
        if market_rate:
            st.metric(
                "Market Suggested (mid-rate)",
                f"{market_rate:.4f}",
                help=(
                    "Fetched from CurrencyBeacon. "
                    "This is a reference mid-rate; payments use RUB directly."
                ),
            )
        else:
            st.metric("Market Suggested (mid-rate)", "Unavailable")

st.subheader("Recent Payments")
if recent_payments:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Date": p.payment_date,
                    "Member": p.display_name,
                    "RUB": float(p.rub_paid),
                    "Recorded Credit (RUB)": float(p.rub_credit),
                }
                for p in recent_payments
            ]
        ),
        hide_index=True,
    )
else:
    st.write("No payments recorded yet.")
