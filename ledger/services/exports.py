"""Export service — owner-friendly Excel snapshot."""

import io
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from ledger.models import ChargeCycle, FxRate, Member, Payment, PostedCharge
from ledger.services.balances import get_member_balances


def build_export_workbook(session: Session) -> io.BytesIO:
    """Generate Excel workbook with snapshot data."""
    output = io.BytesIO()

    # Get data
    balances = get_member_balances(session)
    payments = (
        session.query(Payment, Member)
        .join(Member)
        .order_by(Payment.payment_date.desc())
        .all()
    )
    posted_charges = (
        session.query(PostedCharge, Member, ChargeCycle)
        .join(Member)
        .join(ChargeCycle)
        .order_by(ChargeCycle.cycle_date.desc(), Member.display_name)
        .all()
    )
    fx_rates = session.query(FxRate).order_by(FxRate.rate_date.desc()).all()

    # Pre-process into dataframes
    df_members = pd.DataFrame(
        [
            {
                "Name": b.display_name,
                "Active": "Yes" if b.is_active else "No",
                "Counted": "Yes" if b.counted_in_denominator else "No",
                "Billable": "Yes" if b.billable_after_cutover else "No",
                "Legacy USD": float(b.legacy_opening_usd),
                "Charges USD": float(b.posted_charges_usd),
                "Credits USD": float(b.payment_credits_usd),
                "Current USD Balance": float(b.balance_usd),
                "Current RUB Equivalent": float(b.balance_rub_equivalent) if b.balance_rub_equivalent is not None else None,
            }
            for b in balances
        ]
    )

    df_payments = pd.DataFrame(
        [
            {
                "Date": p.Payment.payment_date,
                "Member": p.Member.display_name,
                "RUB Paid": float(p.Payment.rub_paid),
                "FX Locked": float(p.Payment.fx_locked),
                "USD Credit": float(p.Payment.usd_credit),
                "Note": p.Payment.note,
            }
            for p in payments
        ]
    )

    df_charges = pd.DataFrame(
        [
            {
                "Cycle": p.ChargeCycle.cycle_date,
                "Member": p.Member.display_name,
                "Denominator": p.PostedCharge.active_count,
                "Subscription USD": float(p.PostedCharge.subscription_usd),
                "Charge USD": float(p.PostedCharge.charge_usd),
                "FX Locked": float(p.PostedCharge.fx_locked),
                "RUB Equivalent": float(p.PostedCharge.charge_rub_equivalent),
                "Billable": "Yes" if p.PostedCharge.billable else "No",
            }
            for p in posted_charges
        ]
    )

    df_fx = pd.DataFrame(
        [
            {
                "Date": fx.rate_date,
                "USD/RUB": float(fx.usd_rub),
                "Source": fx.source,
            }
            for fx in fx_rates
        ]
    )

    df_summary = pd.DataFrame(
        [
            {"Metric": "Generated Date", "Value": str(date.today())},
            {"Metric": "Total Members", "Value": len(balances)},
            {
                "Metric": "Total Owed to Owner (USD)",
                "Value": float(sum(b.balance_usd for b in balances if b.balance_usd > 0)),
            },
        ]
    )

    # Write to Excel
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_summary.to_excel(writer, sheet_name="Summary", index=False)
        df_members.to_excel(writer, sheet_name="Members", index=False)
        df_charges.to_excel(writer, sheet_name="Charges", index=False)
        df_payments.to_excel(writer, sheet_name="Payments", index=False)
        df_fx.to_excel(writer, sheet_name="FX Rates", index=False)

        # Basic formatting
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            worksheet.set_column(0, 10, 15)

    output.seek(0)
    return output
