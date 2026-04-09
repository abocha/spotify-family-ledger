# V2 Implementation Plan: Self-Healing Public Ledger

## Summary

Rewrite the app as a small public read-only ledger with admin-only write actions, using a new schema and a dedicated wake-up reconciliation engine.

Chosen defaults:
- **Hard reset schema**: no v1 data-model compatibility layer, no automatic migration of old history.
- **Public read-only**: anyone with the app link can view balances and statements.
- **Admin-only writes**: only admin can record payments, add adjustments, manage members, or trigger manual retry.
- **Negative balance means owes money**: preserve the current sign convention everywhere.
- **Failure mode**: if reconciliation fails, the app enters **stale read-only mode**, shows “exact through” status, and sends a **Telegram alert** best-effort.
- **Performance rule**: one visible slow wake-up path is acceptable; normal screen-to-screen navigation must be fast and must not redo heavy work.

Initial v2 scope should **drop** forecast/post-cycle UX, market-rate widgets, in-place edit history, and Excel export. Those are not part of the first rewrite.

## Key Changes

### 1. Reset the domain and schema

Replace the current v1 cycle/payment schema with a clean v2 schema in [ledger/models.py](/home/abocha/code/spotify-family-ledger/ledger/models.py) and a new Alembic baseline:

- `members`
- `opening_balances`
- `fx_rates`
- `billing_cycles`
- `member_charges`
- `payments`
- `adjustments`
- `reconciliation_runs`
- `job_locks`

Schema rules:
- `billing_cycles.cycle_date` unique.
- `member_charges (cycle_id, member_id)` unique.
- `payments` and `adjustments` are append-only in normal flow.
- `reconciliation_runs` stores exact-through, failure month, error message, and Telegram alert status.
- `job_locks` is a DB-backed lease table for a single reconciliation lock so concurrent wake-ups do not double-post cycles.

Naming rules:
- remove `usd_credit` entirely
- remove forecast/status concepts except `posted` and `failed` reconciliation states
- preserve the negative-balance-means-owes convention in both storage and UI labels

Reset strategy:
- replace the current migration history with a new baseline revision
- add one explicit reset script/command for local and remote reset during rollout
- do **not** build any automatic v1-to-v2 history migration

### 2. Build the reconciliation engine first

Replace the current bootstrap/cycle flow in [ledger/bootstrap.py](/home/abocha/code/spotify-family-ledger/ledger/bootstrap.py) and [ledger/services/cycles.py](/home/abocha/code/spotify-family-ledger/ledger/services/cycles.py) with a dedicated reconciliation service.

New core interface:
- `reconcile_ledger(session, today=None, trigger="startup" | "admin") -> ReconciliationOutcome`

`ReconciliationOutcome` must include:
- `state`: `healthy`, `stale`, or `running`
- `exact_through_date`
- `last_attempted_cycle_date`
- `failure_cycle_date`
- `failure_message`
- `cycles_posted_count`
- `alert_sent`

Behavior:
- derive billing day from `CUTOVER_DATE.day`
- find all missing billing months from the last posted month through `today`
- acquire `job_locks` lease before any expensive work
- fetch historical FX from CurrencyBeacon and persist to `fx_rates`
- post one month at a time, validating totals before commit
- stop at first failure
- mark `reconciliation_runs` success/failure explicitly
- on failure, send a best-effort Telegram message once for that failed run
- if Telegram fails, record the alert failure but do not fail the app harder

Startup behavior:
- run reconciliation once on app wake-up / first session entry
- show a dedicated loading/status screen while reconciliation is running
- after completion, all normal pages must read only from persisted data and cached read models
- do not re-fetch FX or rerun reconciliation on ordinary page navigation in the same session unless admin explicitly retries

### 3. Rebuild the read/query layer for speed

Replace the current ad hoc cache layer with a thin read-model/query layer that serves the new UI quickly.

New query/read-model interfaces:
- `get_ledger_status()`
- `list_member_balances()`
- `get_member_statement(member_id)`
- `list_recent_payments(limit)`
- `list_admin_reconciliation_history(limit)`

Performance decisions:
- no heavy writes during normal page rendering
- no repeated external FX calls after reconciliation completes
- use `st.cache_data` only for read models, cleared only after actual writes or completed reconciliation
- read models should be keyed off persisted data, not TTL-dependent “maybe stale” estimates
- remove “estimated FX” paths entirely from truth screens

Reuse allowed:
- keep and adapt the existing CurrencyBeacon fetcher, auth helper, and DB engine setup if still clean
- do not preserve v1 bootstrap, forecast, post-cycle preview, or edit-in-place logic

### 4. Rewrite the Streamlit app surface

Replace the current page set with a minimal v2 UI in [pages/3_Post_Cycle.py](/home/abocha/code/spotify-family-ledger/pages/3_Post_Cycle.py) and the rest of `pages/*`.

New page set:
- **Home**: public ledger health + member balances + last payment info
- **Statements**: public per-member statement page with a member selector
- **Admin**: admin-only page containing payment entry, adjustment entry, member management, and manual retry
- optional **Reconciliation History** as part of Admin, not a separate public page

UI rules:
- public users never need to log in for read-only views
- admin login remains password-hash based from secrets
- writes only exist on the Admin page
- statements must show:
  - monthly charge rows
  - locked FX for each month
  - payments
  - adjustments
  - running balance
  - clear labels that negative means “owes”
- remove market FX widgets, forecast messaging, and editable history tabs
- if ledger is stale, all public pages show the same prominent status banner:
  - exact through date
  - failed month
  - short failure reason
- stale mode remains readable, but admin write forms are disabled except:
  - manual retry reconciliation
  - configuration/repair actions if explicitly needed

### 5. Add the new config and alerting contracts

Extend settings with:
- `CURRENCYBEACON_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Behavior:
- Telegram alerting is best-effort and production-facing
- local dev can run without Telegram secrets
- no email integration in v2
- billing day is derived from `CUTOVER_DATE`, not added as a separate setting

## Test Plan

Add or replace tests so the suite proves the new operating model, not just arithmetic helpers.

Core reconciliation:
- empty DB after cutover posts all missing months through today
- several months of inactivity reconcile in order and stop at the first failed month
- rerunning reconciliation after a successful run is idempotent
- concurrent startup attempts cannot double-post cycles because of `job_locks`
- partial success keeps earlier months committed and marks the ledger stale

Accounting correctness:
- each cycle locks the historical FX used that month
- per-member charges and cycle totals match exactly
- negative balances mean the member owes money
- payments reduce debt correctly
- adjustments affect statements and balances correctly

Failure behavior:
- CurrencyBeacon failure produces stale read-only mode with exact-through status
- Telegram alert is sent once per failed reconciliation run
- Telegram delivery failure is recorded but does not crash the app
- stale mode disables normal admin write flows except retry/repair entry points

Access and UX:
- public users can open Home and Statements without login
- public users cannot access Admin write actions
- admin login enables payments, adjustments, member edits, and retry
- ordinary page navigation after startup does not trigger FX fetches or reconciliation again in-session

Performance acceptance:
- wake-up path may show a loading/reconciliation view
- after successful reconciliation, subsequent page loads should use only DB reads and cached read models
- no page should depend on live FX fetches for normal rendering

## Assumptions

- Existing v1 production data is disposable or will be re-entered manually after reset.
- Public read-only means the full ledger is visible to anyone with the app URL, including all member balances and statements.
- v2 MVP does not include Excel export or generic history editing; adjustments replace routine in-place edits.
- The existing CurrencyBeacon integration is reusable; the existing forecast/bootstrap/edit-history flows are not.
- The first implementation target is a clean, reliable MVP, not backwards-compatible evolution.
