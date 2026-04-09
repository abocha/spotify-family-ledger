from datetime import date
from unittest.mock import patch

import pytest
import streamlit as st

from ledger.bootstrap import ensure_bootstrap
from ledger.schemas import ReconciliationOutcome


@pytest.fixture(autouse=True)
def clear_session_state():
    st.session_state.clear()
    yield
    st.session_state.clear()


def test_ensure_bootstrap_runs_once_per_session(session):
    outcome = ReconciliationOutcome(
        state="healthy",
        exact_through_date=None,
        last_attempted_cycle_date=None,
        failure_cycle_date=None,
        failure_message=None,
        cycles_posted_count=0,
        alert_sent=False,
    )

    with patch("ledger.bootstrap.reconcile_ledger", return_value=outcome) as mock_reconcile:
        first = ensure_bootstrap(session)
        second = ensure_bootstrap(session)

    assert first.state == "healthy"
    assert second.state == "healthy"
    mock_reconcile.assert_called_once()


def test_ensure_bootstrap_force_reruns(session):
    outcome = ReconciliationOutcome(
        state="healthy",
        exact_through_date=None,
        last_attempted_cycle_date=None,
        failure_cycle_date=None,
        failure_message=None,
        cycles_posted_count=0,
        alert_sent=False,
    )

    with patch("ledger.bootstrap.reconcile_ledger", return_value=outcome) as mock_reconcile:
        ensure_bootstrap(session)
        ensure_bootstrap(session, force=True, trigger="admin")

    assert mock_reconcile.call_count == 2


def test_ensure_bootstrap_does_not_clear_cache_on_healthy_noop(session):
    outcome = ReconciliationOutcome(
        state="healthy",
        exact_through_date=None,
        last_attempted_cycle_date=None,
        failure_cycle_date=None,
        failure_message=None,
        cycles_posted_count=0,
        alert_sent=False,
    )

    with patch("ledger.bootstrap.reconcile_ledger", return_value=outcome):
        with patch("ledger.bootstrap.st.cache_data") as mock_cache:
            ensure_bootstrap(session)

    mock_cache.clear.assert_not_called()


def test_ensure_bootstrap_clears_cache_on_stale_or_mutation(session):
    stale = ReconciliationOutcome(
        state="stale",
        exact_through_date=None,
        last_attempted_cycle_date=None,
        failure_cycle_date=date(2026, 5, 20),
        failure_message="FX failed",
        cycles_posted_count=0,
        alert_sent=False,
    )

    with patch("ledger.bootstrap.reconcile_ledger", return_value=stale):
        with patch("ledger.bootstrap.st.cache_data") as mock_cache:
            ensure_bootstrap(session)

    mock_cache.clear.assert_called_once()
