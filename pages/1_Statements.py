import streamlit as st

from ledger.bootstrap import ensure_bootstrap
from ledger.database import get_db
from ledger.read_cache import load_integrity_issues, load_member_options, load_statement_data
from ledger.schemas import MemberStatement
from ledger.services.queries import get_ledger_status
from ledger.ui import format_balance_caption, render_auth_sidebar, render_status_banner


if "mode" not in st.session_state:
    st.session_state.mode = "public"

render_auth_sidebar()

with get_db() as session:
    ensure_bootstrap(session)
    status = get_ledger_status(session)

integrity_issues = load_integrity_issues()
if integrity_issues:
    for issue in integrity_issues:
        if issue["severity"] == "error":
            st.error(issue["message"])
        else:
            st.warning(issue["message"])
    if any(issue["severity"] == "error" for issue in integrity_issues):
        st.stop()

st.title("Member Statements")
st.caption("Inspect each member's month-by-month charges, payments, adjustments, and running balance.")
render_status_banner(status)

options = load_member_options()
if not options:
    st.info("No members are configured yet.")
    st.stop()

label_to_id = {label: member_id for member_id, label in options}
selected_label = st.selectbox("Member", list(label_to_id.keys()))
statement_data = load_statement_data(label_to_id[selected_label])
statement = MemberStatement.model_validate(statement_data["statement"])

col1, col2 = st.columns(2)
with col1:
    st.metric("Current Balance (RUB)", f"₽ {statement.current_balance_rub:.2f}")
    st.caption(format_balance_caption(float(statement.current_balance_rub)))
with col2:
    st.metric(
        "Last Payment Date",
        statement.last_payment_date.isoformat() if statement.last_payment_date else "Never",
    )
    exact_through = statement.exact_through_date.isoformat() if statement.exact_through_date else "n/a"
    st.caption(f"Ledger exact through {exact_through}.")

entries_df = statement_data["entries_df"]
if entries_df.empty:
    st.info("No statement entries yet.")
else:
    st.dataframe(entries_df, hide_index=True, width="stretch")
