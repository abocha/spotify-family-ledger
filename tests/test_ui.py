import pytest
import streamlit as st

from ledger.schemas import LedgerStatus
from ledger.ui import get_admin_permissions, render_status_banner, require_admin


@pytest.fixture(autouse=True)
def clear_session_state():
    st.session_state.clear()
    yield
    st.session_state.clear()


def test_get_admin_permissions_for_stale_mode():
    permissions = get_admin_permissions("stale")
    assert permissions.can_retry_reconciliation is True
    assert permissions.can_manage_members is True
    assert permissions.can_record_payments is False
    assert permissions.can_add_adjustments is False


def test_require_admin_stops_public_mode(monkeypatch):
    st.session_state["mode"] = "public"
    stopped = {"called": False}

    def fake_stop():
        stopped["called"] = True
        raise RuntimeError("stopped")

    monkeypatch.setattr(st, "stop", fake_stop)

    with pytest.raises(RuntimeError, match="stopped"):
        require_admin()

    assert stopped["called"] is True


def test_require_admin_allows_admin_mode():
    st.session_state["mode"] = "admin"
    require_admin()


def test_render_status_banner_shows_stale_details(monkeypatch):
    captured = {"message": None}

    def fake_error(message: str):
        captured["message"] = message

    monkeypatch.setattr(st, "error", fake_error)

    render_status_banner(
        LedgerStatus(
            state="stale",
            exact_through_date=None,
            last_attempted_cycle_date=None,
            failure_cycle_date=None,
            failure_message="FX fetch failed",
            cycles_posted_count=0,
            alert_sent=False,
            last_completed_at=None,
            last_run_trigger="startup",
        )
    )

    assert captured["message"] is not None
    assert "Ledger stale" in captured["message"]
    assert "FX fetch failed" in captured["message"]
