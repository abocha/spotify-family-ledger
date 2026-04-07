import streamlit as st
import pandas as pd

from ledger.database import get_db
from ledger.services import get_next_unposted_cycle, preview_cycle, post_cycle

st.set_page_config(page_title="Post Cycle - Spotify Family Ledger")
st.title("Post Cycle")

with get_db() as session:
    next_cycle = get_next_unposted_cycle(session)
    
    if not next_cycle:
        st.success("All forecasted cycles have been posted. Check back next month.")
        st.stop()
        
    st.subheader(f"Next cycle: {next_cycle.cycle_date.strftime('%B %Y')}")
    st.write(f"**Date:** {next_cycle.cycle_date}")
    
    try:
        preview = preview_cycle(session, next_cycle.id)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Subscription Cost", f"${preview.subscription_usd:.2f}")
        col2.metric("Denominator (Counted)", preview.counted_active)
        col3.metric("Billed Members", preview.billed_active)
        
        col4, col5, col6 = st.columns(3)
        col4.metric("Per Slot USD", f"${preview.usd_per_counted_slot:.4f}")
        col5.metric("Owner Subsidy USD", f"${preview.owner_subsidy_usd:.4f}")
        
        from ledger.services import fetch_market_rate
        market_rate = fetch_market_rate()
        
        if preview.fx_available:
            col6.metric(
                "FX Rate (Locked USD/RUB)", 
                f"{preview.fx_rate:.4f}",
                delta=f"{(float(preview.fx_rate) - market_rate):.4f} vs market" if market_rate else None,
                delta_color="off"
            )
        else:
            col6.metric(
                "FX Rate", 
                "Missing", 
                delta=f"Market suggests {market_rate:.4f}" if market_rate else None, 
                delta_color="off"
            )
            
        st.write("### Member Charges")
        members_df = pd.DataFrame([
            {
                "Member": m.display_name,
                "Counted": "✅" if m.counted else "❌",
                "Billable": "✅" if m.billable else "❌",
                "Charge (USD)": float(m.charge_usd),
                "RUB Equivalent": float(m.charge_rub_equivalent) if m.charge_rub_equivalent else None,
            }
            for m in preview.member_charges
        ])
        st.dataframe(members_df, hide_index=True)
        
        if not preview.fx_available:
            st.error(f"Cannot post cycle: No FX rate exists for {next_cycle.cycle_date}. Please add it first.")
        else:
            with st.form("post_cycle_form"):
                st.warning("Posting is immutable. This will lock the FX rate and generate charges.")
                confirm = st.checkbox("I have reviewed the charges and FX rate and want to post this cycle.")
                submit = st.form_submit_button("Post Cycle", type="primary")
                
                if submit:
                    if not confirm:
                        st.error("Please explicitly confirm before posting.")
                    else:
                        post_cycle(session, next_cycle.id)
                        session.commit()
                        st.toast(f"Cycle {next_cycle.cycle_date} posted successfully!")
                        st.rerun()
                        
    except Exception as e:
        st.error(f"Error preparing cycle: {e}")
