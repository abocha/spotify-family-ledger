# Spotify Family Ledger — Design Doc

## 1. Project summary

Spotify Family Ledger is a small owner-facing Streamlit app for managing a shared Spotify Family subscription.

It replaces fragile spreadsheet workflows with a narrow, boring, auditable ledger. The app is intentionally not a generic finance product; it is a practical internal tool for one operator managing a small shared subscription.

## 2. Source-of-truth boundary

- Up to **2026-04-19**, the legacy spreadsheet is the contractual source of truth.
- From **2026-04-20** onward, this app is the contractual source of truth.

Legacy balances are imported once into `legacy_snapshot` and then treated as frozen opening balances in RUB.

## 3. Currency model

The ledger is **RUB-first**.

- The monthly subscription price is configured in **USD**.
- When a cycle is posted, the cycle’s USD amount is converted to **RUB** using a locked USD/RUB FX rate for that cycle date.
- Member payments are recorded directly in **RUB** and create RUB credit 1:1.
- Display-only USD equivalents may be shown using the latest known FX rate, but they are not accounting truth.

### Balance formula

```text
balance_rub = legacy_opening_rub + payment_credits_rub - posted_charges_rub
```

Interpretation:
- positive balance = member has credit
- negative balance = member owes the owner

## 4. Core workflows

### A. Forecast cycles
The app keeps forecast cycles generated ahead of time so the owner can always see the next cycle.

### B. Posting a cycle
When a cycle is posted:
1. the cycle date is resolved
2. the exact USD/RUB rate for that date is ensured or manually provided
3. active counted members determine the denominator
4. active billable members receive immutable `posted_charges`
5. cycle summary fields are locked in RUB

### C. Recording a payment
When a payment is recorded:
1. the owner selects a member
2. enters payment date and RUB amount
3. the ledger stores RUB paid and RUB credit directly
4. payment history becomes part of the permanent balance trail

### D. Admin corrections
Rare edits to posted charges or payments are allowed, but they must write an audit trail with timestamp and reason.

## 5. Membership rules

Each member has:
- `active_from`
- optional `active_to`
- `counted_in_denominator`
- `billable_after_cutover`

This allows cases like:
- counted but not billed
- billed but not counted
- active for only part of the project’s timeline

## 6. Data model

### `members`
Who exists in the system and how they participate in billing.

Fields:
- `id`
- `display_name`
- `active_from`
- `active_to`
- `counted_in_denominator`
- `billable_after_cutover`
- `note`

### `legacy_snapshot`
Frozen opening balance imported from the legacy system.

Fields:
- `id`
- `member_id`
- `snapshot_date`
- `opening_balance_rub`
- `source_usd_balance`
- `source_note`

### `fx_rates`
Stored exact USD/RUB rates by date.

Fields:
- `rate_date`
- `usd_rub`
- `source`
- `imported_at`

### `charge_cycles`
One row per cycle.

Fields:
- `id`
- `cycle_date`
- `status` (`forecast`, `posted`)
- `subscription_usd`
- `subscription_rub`
- `counted_active`
- `billed_active`
- `total_billed_rub`
- `owner_subsidy_rub`
- `fx_locked`
- `posted_at`

### `posted_charges`
Immutable member-level charges for posted cycles.

Fields:
- `id`
- `cycle_id`
- `member_id`
- `charge_date`
- `active_count`
- `subscription_usd`
- `charge_usd`
- `fx_locked`
- `charge_rub`
- `billable`
- `created_at`
- `edited_at`
- `edit_reason`

### `payments`
Immutable member payment records.

Fields:
- `id`
- `member_id`
- `payment_date`
- `rub_paid`
- `fx_locked`
- `usd_credit` *(legacy field name; currently stores RUB credit in the RUB-first model)*
- `note`
- `created_at`
- `edited_at`
- `edit_reason`

## 7. FX strategy

- **Provider**: CurrencyBeacon for latest and historical USD/RUB lookups.
- **Forecast / dashboard use**: latest market mid-rate for rough reference only.
- **Posted cycles**: historical daily USD/RUB for the cycle date, unless the owner manually overrides the stored FX.
- **Payments**: recorded directly in RUB; no market FX lookup is required for the accounting entry itself.

The values stored in `fx_locked` and the posted RUB amounts remain the ledger’s source of truth.

## 8. Business invariants

- A cycle can be posted only once.
- A cycle cannot be posted without a valid FX rate.
- A cycle cannot be calculated with zero active counted members.
- Only active counted members affect the denominator.
- Only active billable members receive posted charges.
- Manual edits must record an explicit reason.
- Cycle summary fields must stay consistent with posted charges after edits.

## 9. Architecture

### UI
- Streamlit pages for dashboard, members, payments, history, export, and admin edits.

### Application layer
- service modules for balances, cycles, FX, payments, export, integrity, and member validation.

### Persistence
- SQLAlchemy ORM
- Alembic migrations
- local SQLite for development or Turso/libSQL for hosted persistence

### Export
- Excel workbook built with pandas + XlsxWriter

## 10. Operational philosophy

The system should feel like a simple admin console:
- facts in
- derived views out
- no spreadsheet gymnastics
- no silent accounting magic
- clear audit trail when humans intervene
