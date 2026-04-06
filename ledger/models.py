from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# TODO: Implement based on AGENTS.md
# - members
# - legacy_snapshot
# - fx_rates
# - charge_cycles
# - posted_charges
# - payments
