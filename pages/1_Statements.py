import streamlit as st

from ledger.bootstrap import ensure_bootstrap
from ledger.database import get_db
from ledger.read_cache import load_statement_data, load_statement_page_data
from ledger.schemas import LedgerStatus, MemberStatement
from ledger.ui import format_balance_caption, render_auth_sidebar, render_status_banner


if "mode" not in st.session_state:
    st.session_state.mode = "public"

render_auth_sidebar()

with get_db() as session:
    ensure_bootstrap(session)

page_data = load_statement_page_data()
status = LedgerStatus.model_validate(page_data["status"])
integrity_issues = page_data["integrity_issues"]
if integrity_issues:
    for issue in integrity_issues:
        if issue["severity"] == "error":
            st.error(issue["message"])
        else:
            st.warning(issue["message"])
    if any(issue["severity"] == "error" for issue in integrity_issues):
        st.stop()

st.title("📄 Member Statements")
st.caption("Inspect month-by-month charges, payments, adjustments, and the running balance.")
render_status_banner(status)

options = page_data["options"]
if not options:
    st.info("👥 No members are configured yet.")
    st.stop()

selected_member = st.selectbox(
    "👤 Member",
    options,
    index=None,
    placeholder="Choose a member",
    format_func=lambda option: option[1],
)
if selected_member is None:
    left, center, right = st.columns([1, 2, 1])
    with center:
        st.markdown("## 👤")
        st.markdown("### Pick a member")
        st.caption("The statement appears here after selection.")
    st.stop()

statement_data = load_statement_data(
    selected_member[0],
    status.exact_through_date.isoformat() if status.exact_through_date else None,
)
statement = MemberStatement.model_validate(statement_data["statement"])

col1, col2 = st.columns(2)
with col1:
    st.metric("📉 Current Balance (RUB)", f"₽ {statement.current_balance_rub:.2f}")
    st.caption(format_balance_caption(float(statement.current_balance_rub)))
with col2:
    st.metric(
        "💸 Last Payment Date",
        statement.last_payment_date.isoformat() if statement.last_payment_date else "Never",
    )
    exact_through = statement.exact_through_date.isoformat() if statement.exact_through_date else "n/a"
    st.caption(f"✅ Ledger exact through {exact_through}.")

entries_df = statement_data["entries_df"]
if entries_df.empty:
    st.info("🧾 No statement entries yet.")
else:
    styled_entries = entries_df.style.format(
        {
            "Amount (RUB)": "₽ {:.2f}",
            "Running Balance (RUB)": "₽ {:.2f}",
            "FX Locked": "{:.4f}",
            "Subscription USD": "$ {:.2f}",
        },
        na_rep="",
    )
    st.dataframe(styled_entries, hide_index=True, width="stretch")
