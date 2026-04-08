"""Initialization and background sync logic for Streamlit pages."""

from datetime import date

import streamlit as st
from sqlalchemy.orm import Session

from ledger.services.cycles import ensure_forecast_cycles, process_backlog


_BOOTSTRAP_STATE_KEY = "ledger_bootstrapped_for"


def bootstrap_page(session: Session) -> bool:
    """Run required background tasks once per calendar day per browser session.
    
    Returns True if DB mutations occurred (and cache was cleared), False otherwise.
    """
    today_key = date.today().isoformat()
    if st.session_state.get(_BOOTSTRAP_STATE_KEY) == today_key:
        return False

    try:
        backlog_results = process_backlog(session)
        forecast_results = ensure_forecast_cycles(session)
        
        # Clear cache only if either service made DB changes
        if backlog_results or forecast_results:
            st.cache_data.clear()
            mutations_occurred = True
        else:
            mutations_occurred = False
        
        st.session_state[_BOOTSTRAP_STATE_KEY] = today_key
        return mutations_occurred
    except Exception as e:
        st.warning(f"Automatic background sync partially failed: {e}")
        # Intentionally do not set the flag so the app can retry on refresh.
        return False
