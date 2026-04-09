from datetime import date
from decimal import Decimal

import streamlit as st

from ledger.bootstrap import ensure_bootstrap
from ledger.database import get_db
from ledger.models import BillingCycle, Member
from ledger.read_cache import load_admin_reconciliation_history, load_member_options
from ledger.schemas import CreateAdjustmentCommand, RecordPaymentCommand, SaveMemberCommand
from ledger.services.members import save_member
from ledger.services.payments import create_adjustment, record_payment
from ledger.ui import (
    get_admin_permissions,
    render_auth_sidebar,
    render_status_banner,
    require_admin,
)


if "mode" not in st.session_state:
    st.session_state.mode = "public"

render_auth_sidebar()
require_admin()

flash = st.session_state.pop("flash", None)
if flash:
    st.success(flash)

with get_db() as session:
    status = ensure_bootstrap(session)

st.title("Admin")
st.caption("Admin-only actions: member management, payment entry, adjustments, and manual reconciliation retry.")
render_status_banner(status)

permissions = get_admin_permissions(status.state)

retry_col, status_col = st.columns([1, 2])
with retry_col:
    if st.button(
        "Retry Reconciliation",
        type="primary",
        use_container_width=True,
        disabled=not permissions.can_retry_reconciliation,
    ):
        with get_db() as session:
            ensure_bootstrap(session, force=True, trigger="admin")
        st.session_state.flash = "Reconciliation retry completed."
        st.rerun()

with status_col:
    if status.state == "stale":
        st.warning(
            "Ledger is stale. You can edit members and retry reconciliation, "
            "but payments and adjustments stay disabled until the ledger is healthy again."
        )

tab_members, tab_payments, tab_adjustments, tab_history = st.tabs(
    ["Members", "Payments", "Adjustments", "Reconciliation History"]
)

with tab_members:
    with get_db() as session:
        members = session.query(Member).order_by(Member.display_name).all()
        options = {"New Member": None, **{member.display_name: member for member in members}}
        selected_label = st.selectbox("Edit Member", list(options.keys()))
        selected_member = options[selected_label]

    with st.form("member_form"):
        display_name = st.text_input(
            "Display Name",
            value=selected_member.display_name if selected_member else "",
            disabled=not permissions.can_manage_members,
        )
        active_from = st.date_input(
            "Active From",
            value=selected_member.active_from if selected_member else date.today(),
            disabled=not permissions.can_manage_members,
        )
        active_to = st.date_input(
            "Active To",
            value=selected_member.active_to or date.today() if selected_member and selected_member.active_to else date.today(),
            disabled=not permissions.can_manage_members,
        )
        has_active_to = st.checkbox(
            "Has End Date",
            value=bool(selected_member and selected_member.active_to),
            disabled=not permissions.can_manage_members,
        )
        counted = st.checkbox(
            "Counted In Denominator",
            value=selected_member.counted_in_denominator if selected_member else True,
            disabled=not permissions.can_manage_members,
        )
        billable = st.checkbox(
            "Billable After Cutover",
            value=selected_member.billable_after_cutover if selected_member else True,
            disabled=not permissions.can_manage_members,
        )
        note = st.text_area(
            "Note",
            value=selected_member.note or "" if selected_member else "",
            disabled=not permissions.can_manage_members,
        )
        submit = st.form_submit_button("Save Member", disabled=not permissions.can_manage_members)
        if submit:
            command = SaveMemberCommand(
                member_id=selected_member.id if selected_member else None,
                display_name=display_name,
                active_from=active_from,
                active_to=active_to if has_active_to else None,
                counted_in_denominator=counted,
                billable_after_cutover=billable,
                note=note,
            )
            with get_db() as session:
                save_member(session, command)
                session.commit()
            st.cache_data.clear()
            st.session_state.flash = "Member saved."
            st.rerun()

with tab_payments:
    options = load_member_options()
    if not options:
        st.info("No members available.")
    else:
        label_to_id = {label: member_id for member_id, label in options}
        with st.form("payment_form"):
            selected_label = st.selectbox("Member", list(label_to_id.keys()), disabled=not permissions.can_record_payments)
            payment_date = st.date_input("Payment Date", date.today(), disabled=not permissions.can_record_payments)
            rub_paid = st.number_input(
                "Amount (RUB)",
                min_value=0.01,
                step=100.0,
                format="%.2f",
                disabled=not permissions.can_record_payments,
            )
            note = st.text_input("Note", disabled=not permissions.can_record_payments)
            submit = st.form_submit_button("Record Payment", disabled=not permissions.can_record_payments)
            if submit:
                command = RecordPaymentCommand(
                    member_id=label_to_id[selected_label],
                    payment_date=payment_date,
                    rub_paid=Decimal(str(rub_paid)),
                    note=note,
                )
                with get_db() as session:
                    record_payment(session, command)
                    session.commit()
                st.cache_data.clear()
                st.session_state.flash = "Payment recorded."
                st.rerun()

with tab_adjustments:
    options = load_member_options()
    if not options:
        st.info("No members available.")
    else:
        label_to_id = {label: member_id for member_id, label in options}
        with get_db() as session:
            cycles = session.query(BillingCycle).order_by(BillingCycle.cycle_date.desc()).limit(24).all()
            cycle_options = {"None": None, **{cycle.cycle_date.isoformat(): cycle.id for cycle in cycles}}

        with st.form("adjustment_form"):
            selected_label = st.selectbox("Member", list(label_to_id.keys()), key="adj_member", disabled=not permissions.can_add_adjustments)
            effective_date = st.date_input("Effective Date", date.today(), key="adj_date", disabled=not permissions.can_add_adjustments)
            amount_rub = st.number_input(
                "Adjustment (RUB)",
                step=100.0,
                format="%.2f",
                help="Positive adds credit. Negative increases what the member owes.",
                disabled=not permissions.can_add_adjustments,
            )
            related_cycle = st.selectbox("Related Cycle", list(cycle_options.keys()), disabled=not permissions.can_add_adjustments)
            reason = st.text_area("Reason", disabled=not permissions.can_add_adjustments)
            submit = st.form_submit_button("Add Adjustment", disabled=not permissions.can_add_adjustments)
            if submit:
                command = CreateAdjustmentCommand(
                    member_id=label_to_id[selected_label],
                    effective_date=effective_date,
                    amount_rub=Decimal(str(amount_rub)),
                    reason=reason,
                    related_cycle_id=cycle_options[related_cycle],
                )
                with get_db() as session:
                    create_adjustment(session, command)
                    session.commit()
                st.cache_data.clear()
                st.session_state.flash = "Adjustment added."
                st.rerun()

with tab_history:
    history_df = load_admin_reconciliation_history()
    if history_df.empty:
        st.info("No reconciliation runs recorded yet.")
    else:
        st.dataframe(history_df, hide_index=True, width="stretch")
