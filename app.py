import streamlit as st

st.set_page_config(
    page_title="Spotify Family Ledger",
    page_icon="🛰️",
    layout="wide",
)

st.title("🛰️ Spotify Family Ledger")

st.markdown(
    """
    **Welcome to the Spotify Family Ledger.**

    Use the sidebar to navigate:
    - **Home**: Dashboard and next actions.
    - **Members**: Current roster and balances.
    - **Post Cycle**: Post the next monthly cycle.
    - **Record Payment**: Record a received payment.
    - **History**: View past cycles and payments.
    - **Export**: Download Excel or CSV data.
    """
)
