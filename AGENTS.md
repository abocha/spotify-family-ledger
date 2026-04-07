# AGENTS.md - Development Guide

## Business Logic & Invariants

### 1. Currency Model: RUB-First
As of **2026-04-20**, the system transitioned from USD-first (legacy) to **RUB-first** accounting.
- **Legacy Balances**: Imported once and converted to RUB at the cutover FX rate.
- **Monthly Charges**: The monthly Spotify Family subscription cost is defined in USD (e.g., $8.00). When a cycle is posted, it is converted to RUB using that day's locked FX rate.
- **Member Payments**: Recorded in RUB. Credit is applied 1:1 in RUB.
- **Member Balances**: Calculated as `sum(payments_rub) + legacy_opening_rub - sum(posted_charges_rub)`.

### 2. The Cutover Date
The `CUTOVER_DATE` (2026-04-20) is the boundary between the legacy spreadsheet and this app.
- No cycles should be generated before this date.
- The first cycle is typically the month including or immediately following the cutover date.

### 3. Cycle Lifecycle
- **Forecast**: Cycles are generated 6 months in advance as placeholders. No charges are applied.
- **Posted**: A user explicitly posts a cycle. This action:
  - Locks the FX rate for that cycle.
  - Generates immutable `PostedCharge` rows for each billable member.
  - Transition from `forecast` to `posted` is **one-way** and **irreversible**.

### 4. Membership Rules
- **Counted in Denominator**: If true, the member is part of the "slots" that share the subscription cost.
- **Billable after Cutover**: If true, the member receives a personal charge row when a cycle is posted.
- These flags allow for members who share the cost but aren't charged (subsidized) or members who are charged but don't count toward the slot count.

## Technical Standards

- **Model Consistency**: Use explicit field names (e.g., `charge_rub`) instead of generic or misleading ones.
- **Integrity**: Always run the integrity check service before surfacing balances to users.
- **Auditability**: Rare manual edits to history MUST include an `edit_reason`.

## Working with the Repo

- **Sync Environment**: `uv sync`
- **Database Migrations**: `uv run alembic upgrade head`
- **Static Analysis**: `uv run ruff check . --fix && uv run ty check .`
- **Tests**: `uv run pytest tests/`
- **Run App**: `uv run streamlit run app.py`
