"""Tests for bootstrap_page background sync and cache invalidation logic."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import streamlit as st
from sqlalchemy.orm import Session

from ledger.bootstrap import bootstrap_page


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def clear_session_state():
    """Clear Streamlit session state before each test."""
    st.session_state.clear()
    yield
    st.session_state.clear()


def test_bootstrap_no_cache_clear_on_no_mutations(mock_session, clear_session_state):
    """Regression test: cache should NOT be cleared when bootstrap makes no DB changes.
    
    Scenario:
    - No backlog cycles to process (backlog returns empty list)
    - No new forecast cycles needed (forecast returns empty list)
    - Expected: cache is NOT cleared, daily flag IS set, function returns False
    """
    with patch("ledger.bootstrap.process_backlog", return_value=[]):
        with patch("ledger.bootstrap.ensure_forecast_cycles", return_value=[]):
            with patch("ledger.bootstrap.st.cache_data") as mock_cache:
                result = bootstrap_page(mock_session)
    
    # Cache should NOT be cleared on no-op
    mock_cache.clear.assert_not_called()
    
    # Function should return False (no mutations)
    assert result is False
    
    # Daily flag should still be set (prevents retry on same day)
    today_key = date.today().isoformat()
    assert st.session_state.get("ledger_bootstrapped_for") == today_key


def test_bootstrap_clears_cache_on_backlog_mutations(mock_session, clear_session_state):
    """Cache SHOULD be cleared when backlog processes cycles."""
    mock_cycle = MagicMock()
    mock_cycle.cycle_date = date(2026, 4, 20)
    
    with patch("ledger.bootstrap.process_backlog", return_value=[mock_cycle]):
        with patch("ledger.bootstrap.ensure_forecast_cycles", return_value=[]):
            with patch("ledger.bootstrap.st.cache_data") as mock_cache:
                result = bootstrap_page(mock_session)
    
    # Cache SHOULD be cleared
    mock_cache.clear.assert_called_once()
    
    # Function should return True (mutations occurred)
    assert result is True
    
    # Daily flag should be set
    today_key = date.today().isoformat()
    assert st.session_state.get("ledger_bootstrapped_for") == today_key


def test_bootstrap_clears_cache_on_forecast_mutations(mock_session, clear_session_state):
    """Cache SHOULD be cleared when forecast generates new cycles."""
    mock_cycle = MagicMock()
    mock_cycle.cycle_date = date(2026, 5, 20)
    
    with patch("ledger.bootstrap.process_backlog", return_value=[]):
        with patch("ledger.bootstrap.ensure_forecast_cycles", return_value=[mock_cycle]):
            with patch("ledger.bootstrap.st.cache_data") as mock_cache:
                result = bootstrap_page(mock_session)
    
    # Cache SHOULD be cleared
    mock_cache.clear.assert_called_once()
    
    # Function should return True (mutations occurred)
    assert result is True


def test_bootstrap_skips_on_repeated_call(mock_session, clear_session_state):
    """Bootstrap should skip execution if already run today in this session."""
    today_key = date.today().isoformat()
    st.session_state["ledger_bootstrapped_for"] = today_key
    
    with patch("ledger.bootstrap.process_backlog") as mock_backlog:
        with patch("ledger.bootstrap.ensure_forecast_cycles") as mock_forecast:
            result = bootstrap_page(mock_session)
    
    # Should have returned immediately without calling services
    mock_backlog.assert_not_called()
    mock_forecast.assert_not_called()
    
    # Return value should be False (nothing was done)
    assert result is False


def test_bootstrap_does_not_set_flag_on_error(mock_session, clear_session_state):
    """If bootstrap fails, flag should NOT be set (allows retry on refresh)."""
    with patch("ledger.bootstrap.process_backlog", side_effect=RuntimeError("DB error")):
        with patch("ledger.bootstrap.st.warning"):
            result = bootstrap_page(mock_session)
    
    # Function should return False (error occurred)
    assert result is False
    
    # Daily flag should NOT be set (allows retry)
    assert st.session_state.get("ledger_bootstrapped_for") is None
