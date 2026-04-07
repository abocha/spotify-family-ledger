"""Initialization and background sync logic for Streamlit pages."""

from datetime import date

import streamlit as st
from sqlalchemy.orm import Session

from ledger.services.cycles import ensure_forecast_cycles, process_backlog


_BOOTSTRAP_STATE_KEY = "ledger_bootstrapped_for"


def bootstrap_page(session: Session) -> None:
    """Run required background tasks once per calendar day per browser session."""
    today_key = date.today().isoformat()
    if st.session_state.get(_BOOTSTRAP_STATE_KEY) == today_key:
        return

    try:
        process_backlog(session)
        ensure_forecast_cycles(session)
        st.session_state[_BOOTSTRAP_STATE_KEY] = today_key
    except Exception as e:
        st.warning(f"Automatic background sync partially failed: {e}")
        # Intentionally do not set the flag so the app can retry on refresh.
