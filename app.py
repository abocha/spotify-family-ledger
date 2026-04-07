import streamlit as st

from ledger.auth import get_admin_password_hash, is_admin_password
from ledger.database import get_db
from ledger.bootstrap import bootstrap_page

st.set_page_config(
    page_title="Spotify Family Ledger",
    page_icon="🛰️",
    layout="wide",
)

if "mode" not in st.session_state:
    st.session_state.mode = "user"

with get_db() as session:
    bootstrap_page(session)

st.title("🛰️ Spotify Family Ledger")

if st.session_state.mode == "user":
    st.success("User mode: read-only")
    st.markdown(
        """
        **Welcome.**

        This is the read-only view.

        The ledger is now self-running: monthly cycle processing happens automatically.
        """
    )
    if not get_admin_password_hash():
        st.warning("Admin auth is not configured yet. Set ADMIN_PASSWORD_HASH in Streamlit secrets.")
    password = st.text_input("Admin password", type="password")
    if st.button("Log in as admin"):
        if is_admin_password(password):
            st.session_state.mode = "admin"
            st.rerun()
        else:
            st.error("Wrong password.")
else:
    st.success("Admin mode: write access enabled")
    st.markdown(
        """
        **Admin mode unlocked.**

        The ledger processes cycles automatically; admin mode is now mostly for inspection and emergency maintenance.
        """
    )
    if st.button("Log out"):
        st.session_state.mode = "user"
        st.rerun()
