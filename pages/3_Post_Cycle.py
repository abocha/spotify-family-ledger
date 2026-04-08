import pandas as pd
import streamlit as st

from ledger.bootstrap import bootstrap_page
from ledger.database import get_db
from ledger.read_cache import load_next_cycle_preview_data

st.title("Next Cycle Preview")

with get_db() as session:
    bootstrap_page(session)

# Use cached loader for preview data
preview = load_next_cycle_preview_data()

if preview["state"] == "empty":
    st.success("All forecasted cycles are up to date.")
    st.stop()

if preview["state"] == "error":
    st.error(preview["message"])
    st.stop()

st.subheader(f"Next cycle: {pd.Timestamp(preview['cycle_date']).strftime('%B %Y')}")
st.write(f"**Date:** {preview['cycle_date']}")

# Show info if using estimated FX
if preview.get("uses_estimated_fx"):
    st.info(
        f"Exact cycle-date FX is not recorded yet. Estimated RUB values below use the latest stored FX rate "
        f"({preview.get('estimated_fx_rate', 'N/A')} USD/RUB)."
    )

# Metrics row 1: always available
col1, col2, col3 = st.columns(3)
col1.metric("Subscription Cost (USD)", f"${preview['subscription_usd']:.2f}")
col2.metric("Denominator (Counted)", preview['counted_active'])
col3.metric("Billed Members", preview['billed_active'])

# Metrics row 2: depends on FX availability
col4, col5, col6 = st.columns(3)

if preview.get("uses_estimated_fx"):
    # Show estimated values
    col4.metric(
        "Estimated Per Slot RUB",
        f"{preview['estimated_rub_per_slot']:.2f}" if preview['estimated_rub_per_slot'] is not None else "n/a",
    )
    col5.metric(
        "Estimated Owner Subsidy RUB",
        f"{preview['estimated_owner_subsidy_rub']:.2f}" if preview['estimated_owner_subsidy_rub'] is not None else "n/a",
    )
    col6.metric(
        "Estimated FX (USD/RUB)",
        f"{preview['estimated_fx_rate']:.4f}" if preview['estimated_fx_rate'] is not None else "n/a",
        delta_color="off",
    )
else:
    # Show actual locked values
    col4.metric("Per Slot RUB", f"{preview['rub_per_slot']:.2f}" if preview['rub_per_slot'] is not None else "n/a")
    col5.metric("Owner Subsidy RUB", f"{preview['owner_subsidy_rub']:.2f}" if preview['owner_subsidy_rub'] is not None else "n/a")
    col6.metric(
        "FX Rate (Locked USD/RUB)",
        f"{preview['fx_rate']:.4f}" if preview['fx_rate'] is not None else "Missing",
        delta_color="off",
    )

st.write("### Member Charges")

# Build member charges dataframe
if preview.get("uses_estimated_fx"):
    members_data = [
        {
            "Member": m["display_name"],
            "Counted": "✅" if m["counted"] else "❌",
            "Billable": "✅" if m["billable"] else "❌",
            "Charge (USD)": f"{m['charge_usd']:.2f}",
            "Estimated Charge (RUB)": f"{m['estimated_charge_rub']:.2f}" if m["estimated_charge_rub"] is not None else None,
        }
        for m in preview["member_charges"]
    ]
else:
    members_data = [
        {
            "Member": m["display_name"],
            "Counted": "✅" if m["counted"] else "❌",
            "Billable": "✅" if m["billable"] else "❌",
            "Charge (USD)": f"{m['charge_usd']:.2f}",
            "Charge (RUB)": f"{m['charge_rub']:.2f}" if m["charge_rub"] is not None else None,
        }
        for m in preview["member_charges"]
    ]

members_df = pd.DataFrame(members_data)
st.dataframe(members_df, hide_index=True)

st.info(
    "Cycle processing is automatic on the 20th and on startup catch-up. This page is read-only."
)
