import streamlit as st
import pandas as pd
from datetime import date

from ledger.database import get_db
from ledger.bootstrap import bootstrap_page
from ledger.services import add_fx_rate, delete_fx_rate, list_all_cycles, list_fx_rates, list_payments
from ledger.services.market_fx import FxLookupError, fetch_historical_fx_rate
from ledger.ui import require_admin

st.title("History")

needs_rerun = False

tab1, tab2, tab3 = st.tabs(["Cycles", "Payments", "FX Rates"])

with get_db() as session:
    bootstrap_page(session)
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
                        "Subscription RUB": float(c.subscription_rub) if c.subscription_rub is not None else None,
                        "Counted / Billed": f"{c.counted_active or '-'} / {c.billed_active or '-'}",
                        "Owner Subsidy RUB": float(c.owner_subsidy_rub) if c.owner_subsidy_rub is not None else None,
                        "Posted At": c.posted_at.strftime("%Y-%m-%d %H:%M:%S") if c.posted_at else None,
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
                        "Recorded Credit (RUB)": float(p.rub_credit),
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
        require_admin()

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
                            st.success(f"Saved USD/RUB for {chosen_date}: {rate}")
                            needs_rerun = True
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
                        st.toast(f"Added rate for {rate_date}: {usd_rub}")
                        needs_rerun = True
                    except ValueError as e:
                        st.error(str(e))

        with st.expander("Admin: Delete FX Rate"):
            with st.form("delete_fx_form"):
                delete_date = st.date_input("Date to delete", key="delete_fx_date")
                if st.form_submit_button("Delete Rate"):
                    try:
                        delete_fx_rate(session, delete_date)
                        session.commit()
                        st.toast(f"Deleted rate for {delete_date}")
                        needs_rerun = True
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

if needs_rerun:
    st.rerun()
