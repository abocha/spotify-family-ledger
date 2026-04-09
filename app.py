import streamlit as st

from ledger.bootstrap import ensure_bootstrap
from ledger.database import get_db
from ledger.read_cache import load_home_data, load_integrity_issues
from ledger.schemas import LedgerStatus
from ledger.ui import format_balance_caption, render_auth_sidebar, render_status_banner


st.set_page_config(
    page_title="Spotify Family Ledger",
    page_icon="🎧",
    layout="wide",
)

if "mode" not in st.session_state:
    st.session_state.mode = "public"

render_auth_sidebar()

with get_db() as session:
    ensure_bootstrap(session)

integrity_issues = load_integrity_issues()
if integrity_issues:
    for issue in integrity_issues:
        if issue["severity"] == "error":
            st.error(issue["message"])
        else:
            st.warning(issue["message"])
    if any(issue["severity"] == "error" for issue in integrity_issues):
        st.stop()

home = load_home_data()
status = LedgerStatus.model_validate(home["status"])

st.title("Spotify Family Ledger")
st.caption("Public ledger view. Negative balances mean the member owes money.")
render_status_banner(status)

col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("Member Balances")
    st.dataframe(home["balances_df"], hide_index=True, width="stretch")

with col2:
    st.subheader("Owner Summary")
    st.metric("Total Owed To Owner (RUB)", f"₽ {home['total_owed_rub']:.2f}")
    st.caption(format_balance_caption(-1.0))

st.subheader("Recent Payments")
recent_payments_df = home["recent_payments_df"]
if recent_payments_df.empty:
    st.info("No payments have been recorded yet.")
else:
    st.dataframe(recent_payments_df, hide_index=True, width="stretch")
