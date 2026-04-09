import streamlit as st

from ledger.bootstrap import ensure_bootstrap
from ledger.config import settings
from ledger.database import get_db
from ledger.read_cache import load_home_data
from ledger.schemas import LedgerStatus
from ledger.ui import render_auth_sidebar, render_status_banner


def _style_balance(value: float) -> str:
    if value < 0:
        return "color: #b42318; font-weight: 600;"
    if value > 0:
        return "color: #027a48; font-weight: 600;"
    return "color: #667085;"


def _style_status(value: str) -> str:
    if "owes owner" in value:
        return (
            "color: #b42318; font-weight: 700; "
            "background-color: #fef3f2; border-radius: 999px; "
            "padding: 0.15rem 0.55rem; display: inline-block;"
        )
    if "has credit" in value:
        return (
            "color: #027a48; font-weight: 700; "
            "background-color: #ecfdf3; border-radius: 999px; "
            "padding: 0.15rem 0.55rem; display: inline-block;"
        )
    return (
        "color: #475467; font-weight: 700; "
        "background-color: #f2f4f7; border-radius: 999px; "
        "padding: 0.15rem 0.55rem; display: inline-block;"
    )


def render_home_page() -> None:
    if "mode" not in st.session_state:
        st.session_state.mode = "public"

    render_auth_sidebar()

    with get_db() as session:
        ensure_bootstrap(session)

    home = load_home_data()
    integrity_issues = home["integrity_issues"]
    if integrity_issues:
        for issue in integrity_issues:
            if issue["severity"] == "error":
                st.error(issue["message"])
            else:
                st.warning(issue["message"])
        if any(issue["severity"] == "error" for issue in integrity_issues):
            st.stop()

    status = LedgerStatus.model_validate(home["status"])

    st.title("Spotify Family Ledger")
    render_status_banner(status)

    summary1, summary2, summary3 = st.columns(3)
    with summary1:
        st.metric(
            "📉 Total Owed To Owner (RUB)",
            f"₽ {home['total_owed_rub']:.2f}",
            help="Sum of all negative member balances.",
        )
    with summary2:
        st.metric(
            "💵 Monthly Spotify Charge",
            f"$ {settings.SUBSCRIPTION_USD:.2f}",
            help="Spotify Family plan amount.",
        )
    with summary3:
        st.metric(
            "🗓️ Spotify Bills On",
            f"{settings.CUTOVER_DATE.day}th of each month",
            help="Bills on the same day every month.",
        )

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("👥 Member Balances")
        balances_df = home["balances_df"]
        styled_balances = (
            balances_df.style.format({"Balance (RUB)": "{:.2f}"})
            .map(_style_balance, subset=["Balance (RUB)"])
            .map(_style_status, subset=["Status"])
        )
        st.dataframe(styled_balances, hide_index=True, width="stretch")

    with col2:
        st.subheader("🧮 How It Works")
        st.markdown(
            """
            Each posted month uses that month's locked USD/RUB rate.

            Balances change only from monthly charges, payments, and adjustments.
            """
        )

    st.subheader("💸 Recent Payments")
    recent_payments_df = home["recent_payments_df"]
    if recent_payments_df.empty:
        st.info("💤 No payments have been recorded yet.")
    else:
        styled_payments = recent_payments_df.style.format({"RUB Paid": "₽ {:.2f}"})
        st.dataframe(styled_payments, hide_index=True, width="stretch")


st.set_page_config(
    page_title="Spotify Family Ledger",
    page_icon="🎧",
    layout="wide",
)

navigation = st.navigation(
    [
        st.Page(render_home_page, title="Home", icon="🏠", default=True),
        st.Page("pages/1_Statements.py", title="Statements", icon="📄"),
        st.Page("pages/2_Admin.py", title="Admin", icon="🔒"),
    ]
)
navigation.run()
