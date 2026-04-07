import os
import sys
from datetime import date
from decimal import Decimal


sys.path.insert(0, os.getcwd())
from ledger.config import settings
from ledger.database import SessionLocal
from ledger.models import LegacySnapshot, Member

# Based on inspection of legacy.xlsx 'Общее' sheet:
# Row 3: Gala (+1.33)
# Row 4: Semen (-2.06)
# Row 5: Dasha (None, effectively inactive)
# Row 6: Luiza (-2.67)
# Row 7: Danya (+0.005)

RAW_BALANCES = {
    "Гала": Decimal("1.333333"),
    "Семен": Decimal("-2.062535"),
    "Даша": Decimal("0.000000"),
    "Луиза": Decimal("-2.666667"),
    "Даня": Decimal("0.005000"),
}


def main():
    print("Seeding legacy snapshot and members...")
    
    with SessionLocal() as session:
        for name, balance in RAW_BALANCES.items():
            # Create member if missing
            member = session.query(Member).filter_by(display_name=name).first()
            if not member:
                is_active = (name != "Даша") # Dasha is completely empty in the spreadsheet
                member = Member(
                    display_name=name,
                    active_from=date(2023, 5, 20),
                    active_to=None if is_active else date(2023, 7, 20),
                    counted_in_denominator=is_active,
                    billable_after_cutover=is_active,
                    note="Imported from legacy.xlsx"
                )
                session.add(member)
                session.flush() # get member.id
                print(f"Created member {name} (id={member.id})")
            
            # Create snapshot if missing
            snapshot = session.query(LegacySnapshot).filter_by(member_id=member.id).first()
            if not snapshot:
                snapshot = LegacySnapshot(
                    member_id=member.id,
                    snapshot_date=settings.CUTOVER_DATE,
                    opening_balance_usd=balance,
                    source_note="Hardcoded extracted from legacy.xlsx Column B"
                )
                session.add(snapshot)
                print(f"Created snapshot for {name}: {balance} USD")
            else:
                print(f"Snapshot for {name} already exists.")
                
        session.commit()
    print("Done!")

if __name__ == "__main__":
    main()
