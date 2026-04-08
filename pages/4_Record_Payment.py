import streamlit as st
from datetime import date
from decimal import Decimal

from ledger.database import get_db
from ledger.bootstrap import bootstrap_page
from ledger.models import Member
from ledger.schemas import RecordPaymentCommand
from ledger.services import preview_payment, record_payment
from ledger.ui import require_admin

st.title("Record Payment")
require_admin()

flash = st.session_state.pop("flash", None)
if flash:
    st.success(flash)

if "payment_preview" not in st.session_state:
    st.session_state.payment_preview = None
    st.session_state.payment_cmd = None

with get_db() as session:
    bootstrap_page(session)
    
    members = session.query(Member).order_by(Member.display_name).all()
    if not members:
        st.warning("No members available.")
        st.stop()

    member_map = {m.display_name: m.id for m in members}

    if st.session_state.payment_preview is None:
        with st.form("payment_form", clear_on_submit=False):
            selected_name = st.selectbox("Member", list(member_map.keys()))
            payment_date = st.date_input("Payment Date", date.today())
            rub_paid = st.number_input("Amount (RUB)", min_value=0.01, step=100.0, format="%.2f")
            note = st.text_input("Note (optional)")

            preview_submit = st.form_submit_button("Preview payment")

            if preview_submit:
                cmd = RecordPaymentCommand(
                    member_id=member_map[selected_name],
                    payment_date=payment_date,
                    rub_paid=Decimal(str(rub_paid)),
                    note=" ".join(note.split()) if note else None,
                )

                try:
                    preview = preview_payment(session, cmd)
                    st.session_state.payment_preview = preview
                    st.session_state.payment_cmd = cmd
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Unexpected error: {str(e)}")
    else:
        preview = st.session_state.payment_preview
        cmd = st.session_state.payment_cmd
        assert cmd is not None

        st.subheader("Review Payment Details")
        st.info(f"**Member:** {preview.display_name}")
        st.info(f"**Payment Date:** {preview.payment_date}")
        st.info(f"**RUB Paid:** {preview.rub_paid}")
        st.success(f"**RUB Credit to be applied:** {preview.rub_credit:.2f}")

        note_text = cmd.note or ""
        if note_text:
            st.info(f"**Note:** {note_text}")

        with st.form("confirm_payment_form"):
            st.warning("This action is immutable. Confirm logging this payment.")
            confirm = st.checkbox("I confirm the above details.")
            save_submit = st.form_submit_button("Confirm & Save", type="primary")
            cancel_submit = st.form_submit_button("Cancel")

            if cancel_submit:
                st.session_state.payment_preview = None
                st.session_state.payment_cmd = None
                st.rerun()

            if save_submit:
                if not confirm:
                    st.error("Please explicitly confirm before saving.")
                else:
                    try:
                        payment = record_payment(session, cmd)
                        session.commit()
                        st.cache_data.clear()
                        st.session_state.flash = f"Payment recorded. Member credited with {payment.usd_credit:.2f} RUB"
                        st.session_state.payment_preview = None
                        st.session_state.payment_cmd = None
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Unexpected error: {str(e)}")