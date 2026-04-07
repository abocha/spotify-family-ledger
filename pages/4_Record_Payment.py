import streamlit as st
from datetime import date
from decimal import Decimal

from ledger.database import get_db
from ledger.models import Member
from ledger.schemas import RecordPaymentCommand
from ledger.services import preview_payment, record_payment

st.set_page_config(page_title="Record Payment - Spotify Family Ledger")
st.title("Record Payment")

with get_db() as session:
    members = session.query(Member).order_by(Member.display_name).all()
    if not members:
        st.warning("No members available.")
        st.stop()
        
    member_map = {m.display_name: m.id for m in members}
    
    with st.form("payment_form", clear_on_submit=True):
        selected_name = st.selectbox("Member", list(member_map.keys()))
        payment_date = st.date_input("Payment Date", date.today())
        rub_paid = st.number_input("Amount (RUB)", min_value=0.01, step=100.0, format="%.2f")
        note = st.text_input("Note (optional)")
        
        preview_submit = st.form_submit_button("Preview payment")
        save_submit = st.form_submit_button("Save Payment", type="primary")
        
        if preview_submit or save_submit:
            cmd = RecordPaymentCommand(
                member_id=member_map[selected_name],
                payment_date=payment_date,
                rub_paid=Decimal(str(rub_paid)),
                note=" ".join(note.split()) if note else None
            )
            
            try:
                preview = preview_payment(session, cmd)
                
                if not preview.fx_available:
                    st.error(f"No FX rate available for {payment_date}. Cannot record payment.")
                else:
                    st.info(f"**FX Rate lookup:** {preview.fx_rate} USD/RUB")
                    st.success(f"**USD Credit to be applied:** ${preview.usd_credit:.4f}")
                    
                    if save_submit:
                        payment = record_payment(session, cmd)
                        st.success(f"Payment recorded! Member credited with ${payment.usd_credit:.4f}")
            except Exception as e:
                st.error(f"Error: {str(e)}")
