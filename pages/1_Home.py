import streamlit as st

from ledger.database import get_db
from ledger.bootstrap import bootstrap_page
from ledger.read_cache import (
    load_dashboard_data,
    load_integrity_issues,
    load_market_rate_value,
)

st.title("Dashboard")

with get_db() as session:
    bootstrap_page(session)

dashboard = load_dashboard_data()
issues = load_integrity_issues()
market_rate = load_market_rate_value()

if issues:
    with st.expander(f"Integrity issues: {len(issues)}", expanded=False):
        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "error":
                st.error(issue["message"])
            elif severity == "warning":
                st.warning(issue["message"])
            else:
                st.info(issue["message"])

col1, col2 = st.columns(2)

with col1:
    st.subheader("Balances")
    st.metric("Total Owed to Owner (RUB)", f"₽ {dashboard['owed_total']:.0f}")

    balances_df = dashboard["balances_df"]
    if dashboard["balances_count"] == 0:
        st.info("No members configured yet. Please add members on the Members page.")
    elif balances_df.empty:
        st.success("Everyone is settled! 🎉")
    else:
        st.dataframe(balances_df, hide_index=True, width="stretch")

with col2:
    st.subheader("Next Action")
    next_cycle_date = dashboard["next_cycle_date"]
    if next_cycle_date:
        st.info(f"Next cycle to post: **{next_cycle_date.strftime('%d %B %Y')}**")
    else:
        st.success("All forecasted cycles are posted.")

    st.subheader("Latest Exchange Rate (USD/RUB)")

    fx_col1, fx_col2 = st.columns(2)

    latest_fx = dashboard["latest_fx"]
    with fx_col1:
        if latest_fx:
            st.metric(
                "Locked Exchange Rate",
                f"{latest_fx['usd_rub']:.2f}",
                help=f"Source: {latest_fx['source']} (Date: {latest_fx['rate_date']})",
            )
        else:
            st.warning("No FX rates recorded.")

    with fx_col2:
        if market_rate is not None:
            st.metric(
                "Market Suggested",
                f"{market_rate:.2f}",
                help=(
                    "Fetched from CurrencyBeacon. "
                    "This is a reference mid-rate; payments use RUB directly."
                ),
            )
        else:
            st.metric("Market Suggested", "Unavailable")

st.subheader("Recent Payments")
recent_payments_df = dashboard["recent_payments_df"]
if recent_payments_df.empty:
    st.write("No payments recorded yet.")
else:
    st.dataframe(recent_payments_df, hide_index=True, width="stretch")