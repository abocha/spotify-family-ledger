import streamlit as st
import pandas as pd
from datetime import date

from ledger.database import get_db
from ledger.models import Member
from ledger.services import get_member_balances
from ledger.ui import require_admin

st.title("Members")

needs_rerun = False

with get_db() as session:
    balances = get_member_balances(session)

    if balances:
        df = pd.DataFrame(
            [
                {
                    "Name": b.display_name,
                    "Current USD Balance": round(float(b.balance_usd), 2),
                    "RUB Equivalent": (
                        round(float(b.balance_rub_equivalent), 2)
                        if b.balance_rub_equivalent is not None
                        else "No FX"
                    ),
                    "Is Active": "✅" if b.is_active else "❌",
                    "Counted (Denominator)": "✅" if b.counted_in_denominator else "❌",
                    "Billable (Receives Charge)": (
                        "✅" if b.billable_after_cutover else "❌"
                    ),
                }
                for b in balances
            ]
        )
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("No members configured yet.")

    st.divider()
    require_admin()

    with st.expander("Admin: Add/Edit Member"):
        members = session.query(Member).order_by(Member.display_name).all()
        member_options = {"New Member": None}
        for m in members:
            member_options[m.display_name] = m

        selected_key = st.selectbox("Select Member", list(member_options.keys()))
        selected_member = member_options[selected_key]

        with st.form("member_form", clear_on_submit=True):
            display_name = st.text_input(
                "Display Name",
                value=selected_member.display_name if selected_member else "",
            )
            active_from = st.date_input(
                "Active From",
                value=selected_member.active_from if selected_member else date.today(),
            )
            has_active_to = st.checkbox(
                "Has End Date?",
                value=bool(
                    selected_member and getattr(selected_member, "active_to", None)
                ),
            )
            active_to = None
            if has_active_to:
                active_to = st.date_input(
                    "Active To",
                    value=(
                        selected_member.active_to
                        if selected_member
                        and getattr(selected_member, "active_to", None)
                        else date.today()
                    ),
                )
            counted = st.checkbox(
                "Counted in Denominator",
                value=(
                    selected_member.counted_in_denominator if selected_member else True
                ),
            )
            billable = st.checkbox(
                "Billable after Cutover",
                value=(
                    selected_member.billable_after_cutover if selected_member else True
                ),
            )
            note = st.text_area(
                "Note",
                value=(
                    selected_member.note
                    if selected_member and getattr(selected_member, "note", None)
                    else ""
                ),
            )

            submit = st.form_submit_button("Save Member")
            if submit:
                if not display_name:
                    st.error("Display Name is required.")
                else:
                    if selected_member:
                        selected_member.display_name = display_name
                        selected_member.active_from = active_from
                        selected_member.active_to = active_to
                        selected_member.counted_in_denominator = counted
                        selected_member.billable_after_cutover = billable
                        selected_member.note = note
                        st.success(f"Updated member: {display_name}")
                    else:
                        new_member = Member(
                            display_name=display_name,
                            active_from=active_from,
                            active_to=active_to,
                            counted_in_denominator=counted,
                            billable_after_cutover=billable,
                            note=note,
                        )
                        session.add(new_member)
                        st.success(f"Added member: {display_name}")
                    session.commit()
                    needs_rerun = True

if needs_rerun:
    st.rerun()
