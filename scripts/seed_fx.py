import sys
import os
from datetime import date

sys.path.insert(0, os.getcwd())
from ledger.database import SessionLocal
from ledger.services import add_fx_rate

def main():
    print("Seeding FX rates...")
    with SessionLocal() as session:
        # A few fixed rates just for demonstration/setup
        rates = [
            (date(2026, 4, 14), 93.5000),
            (date(2026, 4, 20), 94.1200),
            (date(2026, 5, 20), 92.8500),
            (date(2026, 6, 20), 91.0000),
        ]
        
        for d, rate in rates:
            try:
                add_fx_rate(session, d, rate, "seed script")
                print(f"Added: {d} -> {rate}")
            except ValueError:
                print(f"Rate for {d} already exists - skipping")
        
        session.commit()
    print("Done!")

if __name__ == "__main__":
    main()
