import streamlit as st

from ledger.auth import get_admin_password_hash, is_admin_password

st.set_page_config(
    page_title="Spotify Family Ledger",
    page_icon="🛰️",
    layout="wide",
)

if "mode" not in st.session_state:
    st.session_state.mode = "user"

st.title("🛰️ Spotify Family Ledger")

if st.session_state.mode == "user":
    st.success("User mode: read-only")
    st.markdown(
        """
        **Welcome.**

        This is the read-only view.

        Use the sidebar to browse the ledger.
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

        You can now post cycles, add payments, edit members, and change history.
        """
    )
    if st.button("Log out"):
        st.session_state.mode = "user"
        st.rerun()
