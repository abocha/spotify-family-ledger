# AGENTS.md - Development Guide

## Product Identity

Spotify Family Ledger is a small public ledger for one job:

**automatically and credibly answer, for each member, "How much do I owe Andrei right now, and why?"**

The app is not a generic finance tool and not a Spotify operations console. It is a self-healing accrual ledger built around:

- automatic monthly Spotify charges in USD
- member reimbursements in RUB
- locked historical USD/RUB rates per posted month
- transparent member statements
- low-maintenance operation on Streamlit Community Cloud + Turso free tier

## Business Logic & Invariants

### 1. Currency Model: RUB-First With Locked Historical FX

As of `CUTOVER_DATE` (`2026-04-20`), the system is RUB-first.

- Spotify subscription price is configured in USD via `SUBSCRIPTION_USD`.
- When a billing month is posted, the app fetches and locks that month's historical USD/RUB rate.
- Member charges are stored in RUB and remain derived from the locked monthly FX.
- Member payments are recorded in RUB.
- Balances are derived, never stored as mutable fields.

Balance formula:

```text
balance_rub =
  opening_balance_rub
  + payments_rub
  + adjustments_rub
  - posted_charges_rub
```

Sign convention:

- positive = member has credit
- zero = settled
- negative = member owes money

This sign convention is intentional and must remain consistent in storage, UI labels, and statements.

### 2. Cutover Boundary

`CUTOVER_DATE` is the boundary between the old spreadsheet and this app.

- No cycles should be generated before cutover.
- Opening balances are imported once at cutover.
- Opening balances are a **single frozen import per member**, not a timeline of snapshots.
- If cutover debt needs correction later, use an explicit adjustment instead of a second opening balance row.

### 3. Monthly Truth Model

The truth is a posted monthly billing cycle plus its posted member charges.

Current v2 model:

- `billing_cycles`: one row per posted billing month
- `member_charges`: one row per billed member per cycle
- `payments`: append-only RUB payments
- `adjustments`: explicit corrective events
- `reconciliation_runs`: operational history for wake-up sync
- `job_locks`: DB-backed reconciliation lock

There are **no forecast cycles** in the current design.

### 4. Wake-Up Reconciliation

The app is expected to sleep for long stretches on Streamlit Community Cloud. Reliability comes from deterministic catch-up on wake-up.

On startup:

1. Find missing billing months from the last posted cycle through today.
2. Fetch historical FX for each missing month from CurrencyBeacon.
3. Post each month in order.
4. Stop immediately on the first unreconcilable month.
5. Record success/failure in `reconciliation_runs`.

Rules:

- reconciliation must be idempotent
- reconciliation must be guarded by a DB lock
- if reconciliation fails, the app must fail closed and say so plainly
- ordinary navigation must not keep redoing heavy reconciliation work

### 5. Membership Rules

Each member has two independent flags:

- `counted_in_denominator`
- `billable_after_cutover`

This allows:

- members who affect the shared split but are not charged
- members who are charged but do not count toward the split

### 6. Access Model

- Home and Statements are public read-only views.
- Admin authentication uses `ADMIN_PASSWORD_HASH`.
- Only admin may:
  - manage members
  - record payments
  - add adjustments
  - retry reconciliation

When the ledger is stale:

- public pages remain readable
- admin may still repair member configuration and retry reconciliation
- normal financial writes remain disabled until the ledger is healthy

## Technical Standards

- **Model consistency**: prefer explicit field names like `charge_rub`, `rub_paid`, `opening_balance_rub`.
- **Integrity gate**: always run integrity checks before surfacing balances/statements.
- **Auditability**: corrections must be legible. Prefer adjustments over silent mutation.
- **Fail-closed honesty**: if exact reconciliation is not possible, do not show misleading current numbers.
- **Performance**: Streamlit reruns are expensive over long-distance latency. Prefer fewer DB round trips, aggregate queries, and cached read models.

## Current Implementation Notes

- Navigation uses Streamlit `st.navigation` / `st.Page`.
- Startup bootstrap runs once per session and caches its outcome in `st.session_state`.
- Read-model loaders in `ledger/read_cache.py` use `st.cache_data`.
- Cache should be cleared only after real writes or reconciliation that changes public truth.
- The Statements path has already been optimized to reduce remote DB round trips.
- Read-path DB indexes exist for:
  - `member_charges.member_id`
  - `member_charges.charge_date`
  - `payments.member_id`
  - `payments.payment_date`
  - `adjustments.member_id`
  - `adjustments.effective_date`
  - `reconciliation_runs.started_at`

## Working With The Repo

- Sync environment: `uv sync`
- Apply DB migrations: `uv run alembic upgrade head`
- Static analysis: `uv run ruff check . --fix && uv run ty check .`
- Tests: `uv run pytest tests/`
- Run app locally: `uv run streamlit run app.py`

Useful scripts:

- Reset DB: `uv run python scripts/reset_db.py`
- Seed a fresh local DB: `uv run python scripts/seed_from_scratch.py`
- Generate admin password hash: `uv run python scripts/hash_password.py`
