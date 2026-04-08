import pandas as pd
import streamlit as st

from ledger.bootstrap import bootstrap_page
from ledger.database import get_db
from ledger.services import get_next_unposted_cycle, preview_cycle
from ledger.ui import require_admin

st.title("Next Cycle Preview")
require_admin()

with get_db() as session:
    bootstrap_page(session)
    next_cycle = get_next_unposted_cycle(session)

    if not next_cycle:
        st.success("All forecasted cycles are up to date.")
        st.stop()

    st.subheader(f"Next cycle: {next_cycle.cycle_date.strftime('%B %Y')}")
    st.write(f"**Date:** {next_cycle.cycle_date}")

    try:
        preview = preview_cycle(session, next_cycle.id)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("Subscription Cost (USD)", f"${preview.subscription_usd:.2f}")
    col2.metric("Denominator (Counted)", preview.counted_active)
    col3.metric("Billed Members", preview.billed_active)

    col4, col5, col6 = st.columns(3)
    col4.metric("Per Slot RUB", f"{preview.rub_per_slot:.2f}" if preview.rub_per_slot is not None else "n/a")
    col5.metric("Owner Subsidy RUB", f"{preview.owner_subsidy_rub:.2f}" if preview.owner_subsidy_rub is not None else "n/a")
    col6.metric(
        "FX Rate (Locked USD/RUB)",
        f"{preview.fx_rate:.4f}" if preview.fx_rate is not None else "Missing",
        delta_color="off",
    )

    st.write("### Member Charges")
    members_df = pd.DataFrame(
        [
            {
                "Member": m.display_name,
                "Counted": "✅" if m.counted else "❌",
                "Billable": "✅" if m.billable else "❌",
                "Charge (USD)": float(m.charge_usd),
                "Charge (RUB)": float(m.charge_rub) if m.charge_rub is not None else None,
            }
            for m in preview.member_charges
        ]
    )
    st.dataframe(members_df, hide_index=True)

    st.info(
        "Cycle processing is automatic on the 20th and on startup catch-up. This page is read-only."
    )
