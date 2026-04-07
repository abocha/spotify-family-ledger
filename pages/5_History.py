import streamlit as st
import pandas as pd
from datetime import date

from ledger.database import get_db
from ledger.services import add_fx_rate, list_all_cycles, list_payments, list_fx_rates
from ledger.models import FxRate

st.set_page_config(page_title="History - Spotify Family Ledger", layout="wide")
st.title("History")

tab1, tab2, tab3 = st.tabs(["Posted Cycles", "Payments", "FX Rates"])

with get_db() as session:
    with tab1:
        st.subheader("All Cycles")
        cycles = list_all_cycles(session)
        if cycles:
            df_cycles = pd.DataFrame(
                [
                    {
                        "Date": c.cycle_date,
                        "Status": c.status,
                        "Subscription USD": float(c.subscription_usd),
                        "Counted / Billed": f"{c.counted_active or '-'} / {c.billed_active or '-'}",
                        "Owner Subsidy USD": (
                            float(c.owner_subsidy_usd)
                            if c.owner_subsidy_usd is not None
                            else None
                        ),
                        "Posted At": (
                            c.posted_at.strftime("%Y-%m-%d %H:%M:%S")
                            if c.posted_at
                            else None
                        ),
                    }
                    for c in cycles
                ]
            )
            st.dataframe(df_cycles, hide_index=True, width="stretch")
        else:
            st.info("No cycles found.")

    with tab2:
        st.subheader("All Payments")
        payments = list_payments(session)
        if payments:
            df_payments = pd.DataFrame(
                [
                    {
                        "Date": p.payment_date,
                        "Member": p.display_name,
                        "RUB Paid": float(p.rub_paid),
                        "FX Locked": float(p.fx_locked),
                        "USD Credit": float(p.usd_credit),
                        "Note": p.note,
                        "Logged At": p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for p in payments
                ]
            )
            st.dataframe(df_payments, hide_index=True, width="stretch")
        else:
            st.info("No payments recorded yet.")

    with tab3:
        st.subheader("FX Rates Log")

        with st.expander("Add New FX Rate"):
            with st.form("add_fx_form", clear_on_submit=True):
                from ledger.services import fetch_market_rate

                default_rate = fetch_market_rate() or 1.0

                rate_date = st.date_input("Rate Date", date.today())
                usd_rub = st.number_input(
                    "USD/RUB Rate",
                    value=float(default_rate),
                    min_value=1.0,
                    format="%.4f",
                    help=(
                        "Defaults to current ExchangeRate-API market estimate."
                        if getattr(fetch_market_rate, "__name__", "")
                        else ""
                    ),
                )
                source = st.text_input("Source (optional)")

                if st.form_submit_button("Add Rate"):
                    try:
                        add_fx_rate(
                            session,
                            rate_date,
                            usd_rub,
                            " ".join(source.split()) if source else None,
                        )
                        session.commit()
                        st.toast(f"Added rate for {rate_date}: {usd_rub}")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

        fx_rates = list_fx_rates(session)
        if fx_rates:
            df_fx = pd.DataFrame(
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
            st.dataframe(df_fx, hide_index=True, width="stretch")
        else:
            st.info("No FX rates recorded yet.")
