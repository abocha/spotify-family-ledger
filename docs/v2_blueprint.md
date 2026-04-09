# Spotify Family Ledger V2 Blueprint

## Goal

Build a small, elegant ledger that can wake up after months of inactivity and still answer one question exactly:

**How much does each member owe the owner right now, and why?**

The v2 design should optimize for:

- reliability after Streamlit sleep
- exact historical FX-based accrual
- explainability to members
- minimal manual maintenance
- free-tier-friendly infrastructure
- fast, non-janky everyday navigation

## Product Model

The system models two independent timelines:

1. **Owner cost accrual**
   Spotify charges the owner's card on a monthly schedule in USD.

2. **Member reimbursement**
   Members pay the owner back later, in RUB, on irregular dates and often in lump sums.

The ledger's job is to convert the first timeline into a sequence of locked monthly RUB debts, then subtract the second timeline from it.

## Core Principles

### Posted months are the truth

The truth is a posted monthly cycle with:

- billing date
- locked subscription USD
- locked historical USD/RUB rate
- locked set of member charges

### Reconciliation must be deterministic

When the app wakes up, it must be able to derive the same result every time from the same inputs.

### Balances are derived

Balances should never be hand-maintained fields. They are computed from:

- opening balances
- posted member charges
- member payments
- explicit adjustments if any

### Corrections must remain legible

If history must be corrected, the correction should be visible and explainable. Prefer explicit adjustment records over silent mutation wherever possible.

### The app must fail closed

If a missing month cannot be posted exactly, the app should expose a degraded-but-honest state rather than invent a number.

### Negative means "owes"

The existing sign convention should stay:

- positive balance = member has credit
- zero balance = settled
- negative balance = member owes the owner

This is intuitive in the "bank account / in the red" sense and should remain consistent throughout the product.

## Proposed Data Model

V2 does not need a fully generic accounting engine. A focused model is enough.

### `members`

Stores who participates in the shared plan.

Suggested fields:

- `id`
- `display_name`
- `active_from`
- `active_to`
- `counted_in_denominator`
- `billable_after_cutover`
- `note`
- `statement_token` or equivalent, if member self-view is added

### `opening_balances`

Frozen cutover import from the old spreadsheet.

Suggested fields:

- `id`
- `member_id`
- `snapshot_date`
- `opening_balance_rub`
- `source_note`
- `source_usd_balance`

### `billing_cycles`

Exactly one row per billing month after cutover.

Suggested fields:

- `id`
- `cycle_date`
- `status` with values like `posted` or `reconciliation_failed`
- `subscription_usd`
- `fx_locked`
- `subscription_rub`
- `counted_active`
- `billed_active`
- `total_billed_rub`
- `owner_subsidy_rub`
- `posted_at`
- `reconciliation_run_id`

Important note:
v2 probably does not need forecast rows as first-class objects.

### `member_charges`

One immutable posted charge per billed member per cycle.

Suggested fields:

- `id`
- `cycle_id`
- `member_id`
- `charge_date`
- `active_count`
- `subscription_usd`
- `charge_usd`
- `fx_locked`
- `charge_rub`
- `created_at`

Optional if corrections remain in-place:

- `edited_at`
- `edit_reason`

Preferred alternative:
keep posted charges immutable and store corrections separately.

### `payments`

Member payments recorded in RUB.

Suggested fields:

- `id`
- `member_id`
- `payment_date`
- `rub_paid`
- `note`
- `created_at`

Optional:

- `recorded_by`
- `external_reference`

### `adjustments`

Use only for rare exceptions and historical repair.

Suggested fields:

- `id`
- `member_id`
- `effective_date`
- `amount_rub`
- `reason`
- `created_at`
- `related_cycle_id` nullable

Positive or negative sign should be chosen to read naturally in statements.

### `reconciliation_runs`

This is the table that makes the app operationally trustworthy.

Suggested fields:

- `id`
- `started_at`
- `completed_at`
- `status` such as `running`, `success`, `failed`
- `from_cycle_date`
- `to_cycle_date`
- `last_successful_cycle_date`
- `error_cycle_date`
- `error_message`
- `app_version`

This table powers top-level health messaging.

## Balance Formula

For each member:

```text
amount_owed_rub =
  posted_charges_rub
  - payments_rub
  - opening_credit_rub
  +/- adjustments_rub
```

Presentation convention for v2:

- positive = member has credit
- zero = settled
- negative = member owes the owner

Statements and dashboards should speak this plainly in labels and helper text so there is no ambiguity.

## Reconciliation Flow

This is the heart of the system.

### Trigger

Run reconciliation on app wake-up and optionally from an explicit admin retry action.

This should be the expensive path. Normal screen-to-screen navigation should not repeatedly perform heavy reconciliation work.

### Algorithm

1. Load the last successfully posted cycle after cutover.
2. Determine all missing billing dates up to the current date.
3. Create a new `reconciliation_runs` row with status `running`.
4. For each missing billing month, in order:
   - fetch historical FX from CurrencyBeacon
   - load active members for that cycle date
   - compute denominator and billable members
   - compute `subscription_rub`, `charge_rub`, and subsidy
   - insert the `billing_cycles` row
   - insert all `member_charges`
   - validate cycle totals
   - commit the month
5. If all months succeed:
   - mark the run `success`
   - record `last_successful_cycle_date`
6. If a month fails:
   - stop immediately
   - mark the run `failed`
   - record `error_cycle_date` and a human-readable error message

### Idempotency

The reconciliation routine must be safe to rerun.

Enforce:

- unique `cycle_date` in `billing_cycles`
- unique `(cycle_id, member_id)` in `member_charges`
- "already posted" treated as success, not as corruption

### Commit Strategy

Prefer committing one month at a time after full validation. That way:

- successfully reconciled months remain safely posted
- a later failure does not erase good work
- the app can truthfully report "exact through X"

## Performance Model

Performance matters because slow UI feels unreliable even when the math is correct.

### Acceptable slow path

After a long Streamlit sleep, the app may show a deliberate loading or reconciliation screen while it:

- reconnects to the database
- determines missing months
- fetches CurrencyBeacon FX for those months
- posts catch-up cycles

This is acceptable because it communicates that the system is actively bringing itself back to a known-good state.

### Unacceptable slow path

Once reconciliation is complete, normal page transitions should feel fast. The app should not spend 10-15 seconds redoing the same heavy work on every screen.

### Practical guidance

- isolate wake-up reconciliation into a dedicated startup path
- record reconciliation results so later screens can trust and reuse them
- avoid repeated FX fetches during normal browsing
- avoid recomputing large derived views independently on every page
- prefer cached read models for member tables, statements, and summaries
- invalidate caches only when a real write occurs

In short:

slow wake-up is acceptable, jank is not.

## Failure Modes

### FX fetch failure

If CurrencyBeacon is unavailable for one of the missing months:

- stop reconciliation
- keep all earlier months posted
- show a global warning such as:
  - exact through `2026-01-20`
  - failed to reconcile `2026-02-20`
  - reason: FX fetch unavailable

### No counted members

If a month has zero counted members:

- stop reconciliation
- mark it as a configuration problem
- surface exactly which month and why

### Partial database corruption

If cycle totals do not match charge rows, or member charges are missing:

- mark ledger health as degraded
- do not present the ledger as fully healthy
- expose a repair path

## Integrity Rules

V2 integrity checks should be stronger than today.

At minimum verify:

- every posted cycle has a locked FX rate
- every posted cycle has at least one counted member
- `subscription_rub = subscription_usd * fx_locked`, rounded by policy
- `total_billed_rub = sum(member_charges.charge_rub)`
- `billed_active = count(member_charges)`
- `owner_subsidy_rub = subscription_rub - total_billed_rub`
- all edited or adjusted history rows carry a reason
- no duplicate posted cycle exists for a billing date

## UX Blueprint

### 1. Home

The home page should answer:

- is the ledger healthy?
- through what month is it exact?
- who owes the most right now?
- when did each person last pay?

Suggested widgets:

- reconciliation status banner
- exact-through date
- failed-month warning if any
- explicit loading/progress UI while wake-up reconciliation is running
- table of members with:
  - amount owed
  - months since last payment
  - last charged month
  - last payment date

### 2. Member Statements

This is the trust page and possibly the public-facing page.

Each member should be able to see:

- current amount owed
- last payment date
- list of monthly charges with:
  - billing month
  - USD subscription reference
  - locked FX
  - RUB charge
- list of payments
- running balance

This page should be simple enough that a member can audit it visually in under a minute.

This is also the main read-only experience for non-admin users.

### 3. Record Payment

The payment flow should be extremely lightweight:

- choose member
- enter RUB amount
- enter date
- optional note
- save

No extra ceremony unless you are editing history.

This action should be admin-only.

### 4. Corrections

Keep this rare and clearly labeled.

Preferred flow:

- add an adjustment
- require a reason
- show it on statements

Avoid normalizing in-place edits as a routine admin action.

This action should be admin-only.

### 5. Reconciliation Status

Make status visible on every important page:

- `Healthy`
- `Exact through 2026-07-20`
- `Last wake-up sync at ...`
- `Reconciliation failed for 2026-08-20: CurrencyBeacon timeout`

## Access Model

### Members

Members should have read-only access.

They should be able to inspect:

- current balance
- posted monthly charges
- locked FX used for each month
- payment history
- running balance explanation

### Admin

The admin is the only actor allowed to mutate financial history intentionally.

Admin-only actions:

- record payments
- introduce adjustments
- retry reconciliation manually if needed
- manage rare configuration or repair actions

Everything else should happen automatically through reconciliation.

## What To Remove From The Current Mental Model

### Forecast cycles as a core concept

Forecasts are not important to the real job. Members care about posted history, not placeholders.

### Market FX as a first-class display

Current market FX is not accounting truth. Historical locked FX is.

### Routine in-place editing

Corrections should be explicit and legible, not casual mutation.

### Hidden background magic

Wake-up reconciliation should be a visible system behavior with a recorded run status.

## Migration Path From The Current App

### Phase 1: operational hardening

Keep the current tables, but:

- add `reconciliation_runs`
- move bootstrap logic into a dedicated reconciliation service
- surface exact-through and failed-month status
- remove estimated FX from "truth" screens
- strengthen integrity checks

This yields immediate reliability gains without a full schema rewrite.

### Phase 2: UX reset

- replace admin-centric copy with statement-centric copy
- build the member statement view
- simplify home around status and who owes what
- make payment entry faster

### Phase 3: data model cleanup

- rename misleading legacy fields such as `usd_credit`
- introduce `adjustments`
- consider replacing in-place edits with append-only corrections

### Phase 4: optional member self-service

If desired later:

- add tokenized member statement links
- keep them read-only
- make them explainable without admin context

## Recommended Implementation Sequence

1. Introduce a dedicated `reconcile_ledger()` service.
2. Add `reconciliation_runs` and status reporting.
3. Make wake-up reconciliation fail closed and report exact-through date.
4. Remove estimated FX from any screen that implies truth.
5. Build member statements.
6. Replace edit-heavy admin flows with adjustment-based corrections.
7. Clean up naming and schema debt.

## Definition Of Done For V2

V2 is successful when the app can sleep for months, wake up, reconcile itself, and present a member statement that is:

- exact
- understandable
- audit-friendly
- low-maintenance for the owner

In plain language:

the owner should not have to remember routine bookkeeping, and members should not have to take the owner's word for the math.
