from datetime import date

import streamlit as st

from ledger.bootstrap import bootstrap_page
from ledger.database import get_db
from ledger.models import Member
from ledger.read_cache import load_members_table_df
from ledger.services import save_member
from ledger.ui import require_admin

st.title("Members")

flash = st.session_state.pop("flash", None)
if flash:
    st.success(flash)

with get_db() as session:
    bootstrap_page(session)

# Use cached loader for display table
df = load_members_table_df()
if not df.empty:
    st.dataframe(df, hide_index=True, width="stretch")
else:
    st.info("No members configured yet.")

st.divider()

with get_db() as session:
    require_admin()

    with st.expander("Admin: Add/Edit Member"):
        members = session.query(Member).order_by(Member.display_name).all()
        member_options = {"New Member": None}
        for m in members:
            member_options[m.display_name] = m

        selected_key = st.selectbox("Select Member", list(member_options.keys()))
        selected_member = member_options[selected_key]

        with st.form("member_form", clear_on_submit=True):
            display_name = st.text_input("Display Name", value=selected_member.display_name if selected_member else "")
            active_from = st.date_input("Active From", value=selected_member.active_from if selected_member else date.today())
            has_active_to = st.checkbox("Has End Date?", value=bool(selected_member and getattr(selected_member, "active_to", None)))
            active_to = None
            if has_active_to:
                active_to = st.date_input(
                    "Active To",
                    value=(selected_member.active_to if selected_member and getattr(selected_member, "active_to", None) else date.today()),
                )
            counted = st.checkbox("Counted in Denominator", value=(selected_member.counted_in_denominator if selected_member else True))
            billable = st.checkbox(
                "Receives monthly charge",
                value=(selected_member.billable_after_cutover if selected_member else True),
                help="If enabled, this member gets a charge row when monthly billing is posted."
            )
            note = st.text_area("Note", value=(selected_member.note if selected_member and getattr(selected_member, "note", None) else ""))

            submit = st.form_submit_button("Save Member")
            if submit:
                try:
                    member = save_member(
                        session,
                        member_id=(selected_member.id if selected_member else None),
                        display_name=display_name,
                        active_from=active_from,
                        active_to=active_to,
                        counted_in_denominator=counted,
                        billable_after_cutover=billable,
                        note=note,
                    )
                    session.commit()
                    st.cache_data.clear()
                    st.session_state.flash = f"Saved member: {member.display_name}"
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
