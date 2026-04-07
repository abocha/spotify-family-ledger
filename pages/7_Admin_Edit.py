import streamlit as st
from decimal import Decimal

from ledger.database import get_db
from ledger.models import Payment, PostedCharge
from ledger.schemas import EditChargeCommand, EditPaymentCommand
from ledger.services.cycles import edit_posted_charge
from ledger.services.payments import edit_payment, list_payments
from ledger.ui import require_admin

st.title("Admin: Edit History")
require_admin()
st.warning("Edits are in-place and audited. Dates stay fixed.")

with get_db() as session:
    tab1, tab2 = st.tabs(["Payments", "Charges"])

    with tab1:
        payments = list_payments(session, limit=500)
        payment_map = {f"#{p.id} {p.display_name} {p.payment_date} {p.rub_paid}": p.id for p in payments}
        if payment_map:
            selected = st.selectbox("Select payment", list(payment_map.keys()))
            payment = session.get(Payment, payment_map[selected])
            if payment:
                with st.form("edit_payment_form"):
                    rub_paid = st.number_input("RUB paid", min_value=0.01, value=float(payment.rub_paid), format="%.2f")
                    fx = st.number_input("Effective FX (USD/RUB)", min_value=0.000001, value=float(payment.fx_locked), format="%.6f")
                    note = st.text_input("Note", value=payment.note or "")
                    reason = st.text_input("Edit reason", value="")
                    if st.form_submit_button("Save payment edit"):
                        cmd = EditPaymentCommand(
                            payment_id=payment.id,
                            rub_paid=Decimal(str(rub_paid)),
                            usd_rub_effective=Decimal(str(fx)),
                            note=note or None,
                            edit_reason=reason,
                        )
                        edit_payment(session, cmd)
                        session.commit()
                        st.success("Payment updated.")
                        st.rerun()
        else:
            st.info("No payments found.")

    with tab2:
        charges = session.query(PostedCharge).order_by(PostedCharge.created_at.desc()).limit(500).all()
        charge_map = {f"#{c.id} cycle {c.cycle_id} member {c.member_id} {c.charge_date}": c.id for c in charges}
        if charge_map:
            selected = st.selectbox("Select charge", list(charge_map.keys()), key="charge_select")
            charge = session.get(PostedCharge, charge_map[selected])
            if charge:
                with st.form("edit_charge_form"):
                    charge_usd = st.number_input("Charge USD", min_value=0.000001, value=float(charge.charge_usd), format="%.6f")
                    fx = st.number_input("Cycle FX (USD/RUB)", min_value=0.000001, value=float(charge.fx_locked), format="%.6f")
                    reason = st.text_input("Edit reason", value="")
                    if st.form_submit_button("Save charge edit"):
                        cmd = EditChargeCommand(
                            charge_id=charge.id,
                            charge_usd=Decimal(str(charge_usd)),
                            fx_locked=Decimal(str(fx)),
                            edit_reason=reason,
                        )
                        edit_posted_charge(session, cmd)
                        session.commit()
                        st.success("Charge updated.")
                        st.rerun()
        else:
            st.info("No posted charges found.")
