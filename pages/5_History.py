import streamlit as st
from datetime import date

from ledger.database import get_db
from ledger.bootstrap import bootstrap_page
from ledger.read_cache import (
    load_cycles_history_df,
    load_fx_rates_history_df,
    load_payments_history_df,
)
from ledger.services import add_fx_rate, delete_fx_rate
from ledger.services.market_fx import FxLookupError, fetch_historical_fx_rate
from ledger.ui import require_admin

st.title("History")

with get_db() as session:
    bootstrap_page(session)

section = st.radio(
    "Section",
    ["Cycles", "Payments", "FX Rates"],
    horizontal=True,
)

if section == "Cycles":
    st.subheader("All Cycles")
    df_cycles = load_cycles_history_df()
    if df_cycles.empty:
        st.info("No cycles found.")
    else:
        st.dataframe(df_cycles, hide_index=True, width="stretch")

elif section == "Payments":
    st.subheader("All Payments")
    df_payments = load_payments_history_df()
    if df_payments.empty:
        st.info("No payments recorded yet.")
    else:
        st.dataframe(df_payments, hide_index=True, width="stretch")

else:
    st.subheader("FX Rates Log")
    require_admin()

    with get_db() as session:
        with st.expander("Historical FX lookup"):
            with st.form("fx_lookup_form"):
                chosen_date = st.date_input("Date", key="lookup_date_picker")

                if st.form_submit_button("Fetch & Save historical FX"):
                    try:
                        rate = fetch_historical_fx_rate(chosen_date)
                        if rate is None:
                            st.error(f"CurrencyBeacon returned no USD/RUB rate for {chosen_date}.")
                        else:
                            add_fx_rate(
                                session,
                                chosen_date,
                                float(rate),
                                source="CurrencyBeacon (manual lookup)",
                            )
                            session.commit()
                            st.cache_data.clear()
                            st.rerun()
                    except FxLookupError as e:
                        st.error(str(e))
                    except ValueError:
                        st.info(f"Rate for {chosen_date} already exists in DB.")

        with st.expander("Manual FX override"):
            with st.form("add_fx_form"):
                rate_date = st.date_input("Rate Date", date.today(), key="manual_fx_rate_date")
                usd_rub = st.number_input("USD/RUB Rate", value=79.0, min_value=1.0, format="%.4f")
                source = st.text_input("Source (optional)")

                if st.form_submit_button("Add Rate"):
                    try:
                        add_fx_rate(session, rate_date, usd_rub, " ".join(source.split()) if source else None)
                        session.commit()
                        st.cache_data.clear()
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

        with st.expander("Admin: Delete FX Rate"):
            with st.form("delete_fx_form"):
                delete_date = st.date_input("Date to delete", key="delete_fx_date")
                if st.form_submit_button("Delete Rate"):
                    try:
                        delete_fx_rate(session, delete_date)
                        session.commit()
                        st.cache_data.clear()
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    df_fx = load_fx_rates_history_df()
    if df_fx.empty:
        st.info("No FX rates recorded yet.")
    else:
        st.dataframe(df_fx, hide_index=True, width="stretch")