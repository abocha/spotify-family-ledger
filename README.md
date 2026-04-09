# Spotify Family Ledger

Spotify Family Ledger is a small, purpose-built ledger for one job:

**automatically and credibly answer, for each member, "How much do I owe Andrei right now, and why?"**

This project exists because the owner pays Spotify in **USD**, members reimburse in **RUB**, and the RUB/USD exchange rate is volatile enough that naive month-to-month accrual becomes unfair and impossible to explain. The old spreadsheet could not preserve historical accrual correctly. This app is meant to.

## The Real Mentality

This is not a generic finance app.

This is not primarily a subscription management app.

This is not a dashboard that happens to show balances.

This is a **self-healing accrual ledger** for a tiny shared-cost arrangement:

- Spotify charges the owner automatically on a schedule.
- The system must lock the historical FX for each billing month.
- Members pay the owner back later, in RUB, on irregular dates and often in lump sums.
- When the app wakes up after months of inactivity, it must catch up deterministically.
- Members must be able to inspect the ledger and conclude that the math is fair.
- Negative balances mean a member owes money and needs to pay up to settle.

## Mantra

- Posted months are the truth.
- Historical FX is locked per month.
- Wake-up reconciliation is idempotent.
- Balances are derived, never hand-maintained.
- If reconciliation fails, the app says so plainly.

## Product Truths

### 1. The purpose is trustable debt tracking

The main output is not "admin convenience". The main output is a statement each member can inspect:

- which months they were charged for
- what FX was used each month
- what they paid and when
- what they owe now

If a member cannot look at the statement and say "yes, this makes sense", the product failed.

### 2. Automation is mandatory

The owner should not need to remember routine monthly bookkeeping. If something is not recorded, it effectively does not exist. The app therefore needs to:

- notice missed billing months
- fetch historical USD/RUB rates automatically from CurrencyBeacon
- post the missing monthly accruals
- recover correctly after Streamlit Community Cloud sleep

### 3. Historical FX is not a nice-to-have

It is the core accounting requirement.

Each monthly Spotify charge starts as a USD amount and becomes a RUB debt using that month's locked FX. Recomputing old months with a later FX rate would be unfair and would break trust.

### 4. Reliability means fail-closed honesty

If the system cannot reconcile a missing month exactly, it must not silently guess and pretend the current balances are exact.

Instead it should say, clearly:

- up to which month the ledger is exact
- what month failed
- why it failed
- whether shown balances exclude unreconciled months

Smooth-looking wrong numbers are worse than an explicit degraded state.

### 5. Fast feels trustworthy

The app should feel calm and under control.

- A deliberate loading/reconciliation screen after a long sleep is acceptable.
- Slow or janky navigation between normal screens is not.
- Wake-up work should be isolated and visible.
- Regular page views should mostly read from already-reconciled data.

Performance is part of reliability here. If every screen feels sluggish, users will assume the numbers are shaky too.

## Operating Constraints

The product is intentionally built around free infrastructure:

- **UI/runtime**: Streamlit Community Cloud
- **database**: Turso / libSQL free tier
- **FX provider**: CurrencyBeacon API

This means the app will sleep most of the time. That is expected. The architecture must therefore optimize for **correct wake-up reconciliation**, not for always-on processing.

## What The App Should Do

On wake-up, the system should reconcile itself from the last known good posted month up to the present:

1. Find the last posted cycle.
2. Determine which billing months are missing.
3. For each missing month:
   - fetch historical USD/RUB from CurrencyBeacon
   - create the posted cycle
   - create locked member charges
4. Commit the month once it is fully consistent.
5. Stop immediately on the first unreconcilable month.

If all months reconcile, balances are exact.

If one month fails, the app should remain truthful about what is exact and what is pending.

## Access Model

- Members should have read access to the ledger and their statements.
- Only the admin should be able to record payments.
- Only the admin should be able to introduce adjustments or corrections.
- Other than those rare write actions, the system should run on its own.

## What The App Should Not Do

- It should not depend on someone opening the app exactly on billing day.
- It should not maintain balances as mutable stored fields.
- It should not treat "estimated FX" as accounting truth.
- It should not require regular manual nudging to stay correct.
- It should not hide uncertainty behind optimistic UI.

## Current Domain Model

The current implementation is RUB-first after the `CUTOVER_DATE`:

- Spotify subscription price is configured in USD.
- Monthly posted charges are locked in RUB using a historical FX rate.
- Member payments are recorded in RUB.
- Member balances are derived from opening balance, posted charges, and payments.

That direction is correct. The next step is to make the implementation more explicit, more reliable after sleep/wake cycles, and more transparent for members.

## V2 Direction

The target design is a small ledger centered on:

- **members**
- **posted monthly cycles**
- **locked member charges**
- **RUB payments**
- **reconciliation runs**

The system should feel like a tiny receivables ledger with Spotify-specific automation, not like a generic admin console.

See [docs/v2_blueprint.md](/home/abocha/code/spotify-family-ledger/docs/v2_blueprint.md) for the concrete v2 architecture and workflow.

## Setup

### Local Development

1. Install dependencies
   ```bash
   uv sync
   ```

2. Configure environment
   Create a `.env` file with at least:
   ```env
   TURSO_URL=sqlite:///local.db
   TURSO_KEY=
   SUBSCRIPTION_USD=8.00
   CUTOVER_DATE=2026-04-20
   CURRENCYBEACON_API_KEY=your_key_here
   ```

   Notes:
   - `TURSO_URL` can point to local SQLite or a remote libSQL/Turso database.
   - `EXCHANGERATE_API_KEY` is still accepted as a temporary fallback during migration, but new setups should use `CURRENCYBEACON_API_KEY`.

3. Initialize database
   ```bash
   uv run alembic upgrade head
   ```

4. Optional: seed a fresh local database
   ```bash
   uv run python scripts/seed_from_scratch.py
   ```

5. Run the app
   ```bash
   uv run streamlit run app.py
   ```

### Streamlit Community Cloud Deployment

1. Create a Streamlit Community Cloud app with `app.py` as the entry point.

2. Configure secrets:
   ```toml
   TURSO_URL = "your_turso_url"
   TURSO_KEY = "your_turso_key"
   SUBSCRIPTION_USD = "8.00"
   CUTOVER_DATE = "2026-04-20"
   CURRENCYBEACON_API_KEY = "your_key_here"
   ```

3. Ensure the database schema has been migrated before deployment:
   ```bash
   uv run alembic upgrade head
   ```

## Development Commands

- Sync environment: `uv sync`
- Database migrations: `uv run alembic upgrade head`
- Static analysis: `uv run ruff check . --fix && uv run ty check .`
- Tests: `uv run pytest tests/`
- Run app: `uv run streamlit run app.py`
