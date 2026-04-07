import streamlit as st


def is_admin_mode() -> bool:
    return st.session_state.get("mode") == "admin"


def require_admin() -> None:
    if not is_admin_mode():
        st.warning("Admin mode required. Log in on the main page.")
        st.stop()
