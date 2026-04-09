from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from ledger.auth import get_admin_password_hash, is_admin_password
from ledger.schemas import LedgerStatus, ReconciliationOutcome


@dataclass(frozen=True)
class AdminPermissions:
    can_retry_reconciliation: bool
    can_manage_members: bool
    can_record_payments: bool
    can_add_adjustments: bool


def get_admin_permissions(state: str) -> AdminPermissions:
    if state == "healthy":
        return AdminPermissions(
            can_retry_reconciliation=True,
            can_manage_members=True,
            can_record_payments=True,
            can_add_adjustments=True,
        )
    if state == "stale":
        return AdminPermissions(
            can_retry_reconciliation=True,
            can_manage_members=True,
            can_record_payments=False,
            can_add_adjustments=False,
        )
    return AdminPermissions(
        can_retry_reconciliation=False,
        can_manage_members=False,
        can_record_payments=False,
        can_add_adjustments=False,
    )


def is_admin_mode() -> bool:
    return st.session_state.get("mode") == "admin"


def require_admin() -> None:
    if not is_admin_mode():
        st.warning("🔒 Admin mode required.")
        st.stop()


def render_auth_sidebar() -> None:
    with st.sidebar:
        st.header("🔐 Access")
        if is_admin_mode():
            st.success("✅ Admin mode enabled")
            if st.button("Log out", use_container_width=True):
                st.session_state.mode = "public"
                st.rerun()
            return

        st.info("👀 Public read-only mode")
        password = st.text_input("Admin password", type="password")
        if st.button("Log in as admin", use_container_width=True):
            if is_admin_password(password):
                st.session_state.mode = "admin"
                st.rerun()
            else:
                st.error("❌ Wrong password.")

        if not get_admin_password_hash():
            st.warning("⚠️ ADMIN_PASSWORD_HASH is not configured.")


def render_status_banner(status: LedgerStatus | ReconciliationOutcome) -> None:
    if status.state == "healthy":
        if status.exact_through_date is None:
            st.success("✅ Ledger healthy. No posted billing cycles yet.")
            return

        exact_through = status.exact_through_date.isoformat()
        st.success(f"✅ Ledger healthy. Exact through {exact_through}.")
        return

    if status.state == "running":
        st.warning(f"⏳ {status.failure_message or 'Reconciliation is currently running.'}")
        return

    exact_through = status.exact_through_date.isoformat() if status.exact_through_date else "nothing yet"
    failure_cycle = status.failure_cycle_date.isoformat() if status.failure_cycle_date else "unknown month"
    message = status.failure_message or "Unknown reconciliation error."
    st.error(
        f"⚠️ Ledger stale. Exact through {exact_through}. "
        f"Failed while reconciling {failure_cycle}. {message}"
    )


def format_balance_caption(balance_rub: float) -> str:
    if balance_rub < 0:
        return "Negative means this member owes money."
    if balance_rub > 0:
        return "Positive means this member has credit."
    return "Zero means settled."
