"""Startup reconciliation gate for Streamlit pages."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from ledger.schemas import ReconciliationOutcome
from ledger.services.reconciliation import reconcile_ledger


_BOOTSTRAP_FLAG = "ledger_v2_bootstrapped"
_BOOTSTRAP_RESULT = "ledger_v2_bootstrap_result"


def ensure_bootstrap(
    session: Session,
    *,
    force: bool = False,
    trigger: str = "startup",
) -> ReconciliationOutcome:
    if force:
        st.session_state.pop(_BOOTSTRAP_FLAG, None)
        st.session_state.pop(_BOOTSTRAP_RESULT, None)

    cached = st.session_state.get(_BOOTSTRAP_RESULT)
    if st.session_state.get(_BOOTSTRAP_FLAG) and cached:
        return ReconciliationOutcome.model_validate(cached)

    with st.spinner("Reconciling the ledger and checking for missed billing months..."):
        outcome = reconcile_ledger(session, trigger=trigger)

    if outcome.cycles_posted_count > 0 or outcome.state == "stale":
        st.cache_data.clear()
    if outcome.state != "running":
        st.session_state[_BOOTSTRAP_FLAG] = True
        st.session_state[_BOOTSTRAP_RESULT] = outcome.model_dump(mode="json")
    return outcome
