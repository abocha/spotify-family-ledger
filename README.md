# Spotify Family Ledger

A small owner-facing Streamlit app for managing a shared Spotify Family subscription with **RUB-first** accounting while keeping the subscription price defined in USD.

## Features

- **RUB-first accounting** for balances, payments, and posted charges.
- **Monthly cycle forecasting and posting** with locked USD/RUB FX per cycle.
- **CurrencyBeacon integration** for market and historical USD/RUB lookups.
- **Admin tools** for member management and audited edits to history.
- **Excel export** for owner-friendly reporting.

## Setup

1. **Install dependencies**
   ```bash
   uv sync
   ```

2. **Configure environment**
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

3. **Initialize database**
   ```bash
   uv run alembic upgrade head
   ```

4. **Optional: seed a fresh local database**
   ```bash
   uv run python scripts/seed_from_scratch.py
   ```

5. **Run the app**
   ```bash
   uv run streamlit run app.py
   ```

## Design principles

- **Immutability**: once a cycle is posted, its member charges and FX are locked.
- **Traceability**: manual edits are audit-trailed with timestamp and reason.
- **Practicality**: members pay in RUB, receive RUB credit, and are charged in RUB.
