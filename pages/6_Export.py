import datetime

import streamlit as st

from ledger.database import get_db
from ledger.services import build_export_workbook

st.title("Export")

st.markdown(
    """
Download a complete snapshot of the ledger.

This includes:
- **Summary**: Key metrics and generated date.
- **Members**: Current active status, counters, and up-to-date balances in USD and RUB.
- **Charges**: Full history of immutable posted charges per member.
- **Payments**: Full log of recorded member payments with operator-locked effective FX.
- **FX Rates**: All recorded exchange rates.
"""
)

try:
    with get_db() as session:
        workbook_bytes = build_export_workbook(session)

        date_str = datetime.date.today().strftime("%Y-%m-%d")
        filename = f"spotify_ledger_export_{date_str}.xlsx"

        st.download_button(
            label="📄 Download Excel Snapshot",
            data=workbook_bytes.getvalue(),
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
except Exception as e:
    st.error(f"Error generating export: {str(e)}")
