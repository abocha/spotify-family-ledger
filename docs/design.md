# Spotify Family Ledger — Design Doc

## 1. Project summary

We are building a small owner-facing web app for managing a shared Spotify Family subscription.

The old system lives in the legacy spreadsheet **`spotify семья`** and remains the contractual source of truth up to the cutover date. The new system replaces spreadsheet logic with a proper app that is easier to operate, harder to break, and more honest about FX effects over time.

This is not a generic finance product. It is a narrow internal tool for one owner managing a small group with predictable monthly billing.

---

## 2. Problem

The spreadsheet approach became brittle because it was trying to act as all of these at once:

- database
- accounting engine
- workflow engine
- owner UI
- reporting layer

This caused recurring issues:

- formula brittleness
- manual "copy as values" rituals
- forecast rows mixed with posted history
- low operator confidence
- poor owner UX
- weak error prevention
- accidental breakage risk

What we actually need is a tiny accounting app with a clean ledger model and a simple owner console.

---

## 3. Goal

Build an owner-friendly app that lets the owner do only two real actions:

1. **Post the next monthly charge cycle**
2. **Record a member payment**

Everything else should be derived from stored facts.

---

## 4. Desired result

The system should:

- import and preserve real legacy state from the spreadsheet
- freeze legacy balances at cutover
- track new-system charges from cutover onward
- convert RUB payments into USD credit using payment-date FX
- keep posted history immutable
- separate forecast from ledger
- show who owes what right now
- show current RUB equivalent separately from historical RUB payments
- export owner-friendly snapshots to Excel

The app should feel like a simple admin console, not like spreadsheet maintenance.

---

## 5. Contract / accounting rules

### Legacy period
Up to **2026-04-19**, the legacy spreadsheet is the contract.

Its balances are treated as authoritative, even if the old logic was imperfect.

### New period
From **2026-04-20** onward, the new app is the contract.

Rules:

- monthly subscription cost is defined in **USD**
- member debt is tracked in **USD**
- payments are usually made in **RUB**
- each payment is converted to **USD credit** using the FX rate on the payment date
- posted charges and recorded payments must not change later if newer FX data appears

### Important distinction
The system must keep separate:

1. **Historical RUB actually paid**
2. **Current RUB equivalent of current debt**

These are different concepts and must never be merged into one ambiguous total.

---

## 6. Users

### Primary user
**Owner / operator**

Needs:
- low-friction monthly workflow
- numbers they can trust
- minimal spreadsheet-like maintenance
- exportable reporting

### Secondary users
None inside the app for now.

Family members are external stakeholders, not app users.

---

## 7. Core workflows

### A. Monthly posting
Owner flow:
1. Open Home
2. Review the next unposted cycle
3. Confirm counted members, billed members, denominator, and monthly amounts
4. Ensure exact FX exists for the cycle date
5. Click **Post cycle**
6. App writes immutable posted charge rows

### B. Payment recording
Owner flow:
1. Open Record Payment
2. Select member
3. Enter payment date and RUB amount
4. App finds applicable FX
5. App computes USD credit
6. Owner confirms and saves
7. App writes immutable payment row

### C. Review / reporting
Owner flow:
1. Open Home or Members
2. See balances, due now, recent payments, upcoming cycle
3. Export current snapshot to Excel if needed

---

## 8. Non-goals

This project is **not** trying to be:

- a general bookkeeping app
- a multi-tenant SaaS
- a family budgeting tool
- a real-time bank integration product
- a collaborative editor for multiple operators
- a complex forecasting platform

Keep it narrow and boring.

---

## 9. Constraints

### Product constraints
- must preserve the legacy contract boundary cleanly
- must be easy for one owner to operate
- must reduce spreadsheet-style fragility
- must support exportable reports

### Technical constraints
- hosted on **Streamlit Community Cloud**
- Python app
- remote persistent database required
- local SQLite on Community Cloud is not acceptable as production source of truth
- Turso is the chosen database backend

### Data constraints
- legacy spreadsheet contains real contractual data
- imported data may be imperfectly structured and needs normalization
- dataset is small, but correctness matters more than scale

---

## 10. High-level architecture

### UI layer
- **Streamlit**
- pages / screens for owner operations and reporting

### App logic layer
Python services for:
- posting cycles
- recording payments
- balance calculation
- import / migration
- export generation
- validations / integrity checks

### Data layer
- **Turso** (remote libSQL / SQLite)
- source of truth for all new-system records

### Export layer
- Excel export for owner-friendly snapshots
- CSV export optional

---

## 11. Stack

### Runtime / app
- Python
- Streamlit

### Database / persistence
- SQLAlchemy
- `sqlalchemy-libsql`
- Alembic
- Turso

### Validation / config
- Pydantic
- `pydantic-settings`

### Data / export
- pandas
- XlsxWriter

### Dev quality
- pytest
- ruff
- ty

### Optional later
- `tenacity` for retry behavior
- `plotly` for richer charts
- `openpyxl` if deeper legacy Excel manipulation becomes necessary

---

## 12. Data model

### `members`
Defines who is in the family system.

Fields:
- `id`
- `display_name`
- `active_from`
- `active_to`
- `counted_in_denominator`
- `billable_after_cutover`
- `note`

### `legacy_snapshot`
Frozen opening balances from the legacy contract.

Fields:
- `id`
- `member_id`
- `snapshot_date`
- `opening_balance_usd`
- `source_note`

### `fx_rates`
Exact USD/RUB rates by date.

Fields:
- `rate_date`
- `usd_rub`
- `source`
- `imported_at`

### `charge_cycles`
One row per monthly cycle.

Fields:
- `id`
- `cycle_date`
- `status` (`forecast`, `posted`)
- `subscription_usd`
- `counted_active`
- `billed_active`
- `usd_per_counted_slot`
- `total_billed_usd`
- `owner_subsidy_usd`
- `fx_locked`
- `posted_at`

### `posted_charges`
Immutable posted member-level charges.

Fields:
- `id`
- `cycle_id`
- `member_id`
- `charge_date`
- `counted`
- `billable`
- `active_count`
- `subscription_usd`
- `charge_usd`
- `fx_locked`
- `charge_rub_equivalent`
- `created_at`

### `payments`
Immutable payment records.

Fields:
- `id`
- `member_id`
- `payment_date`
- `rub_paid`
- `fx_locked`
- `usd_credit`
- `note`
- `created_at`

### Optional later: `adjustments`
Manual corrections with explicit reason.

Possible fields:
- `id`
- `member_id`
- `adjustment_date`
- `amount_usd`
- `reason`
- `created_at`

---

## 13. Key business rules

### Cycle posting
- a cycle can be posted only once
- a cycle cannot be posted without a valid FX rate for its date
- only active counted members affect the denominator
- only active billable members receive a charge
- owner subsidy = subscription USD minus total billed USD

### Payment recording
- payment FX is looked up by payment date
- once saved, payment FX and USD credit are fixed
- missing FX prevents saving the payment unless explicitly overridden

### Balance calculation
Per member:

```text
current_usd_balance = legacy_opening_usd + posted_charges_usd - payment_credits_usd
````

Separately:

```text
current_rub_equivalent = current_usd_balance * latest_fx
```

### Integrity rules

* no duplicate posted cycle
* no duplicate member charge within a cycle
* no inactive member charged
* no payment stored without locked FX
* no cycle posted without locked FX

---

## 14. UX principles

### Owner-first

The owner should not need to understand joins, ledger internals, or database details.

### Facts in, views out

The user enters facts. The app computes everything else.

### Hide plumbing

Internal tables and technical details stay out of the main UX.

### Status-driven UI

Use simple statuses such as:

* `Forecast`
* `Ready to post`
* `Posted`
* `Payment recorded`
* `Missing FX`
* `Needs attention`

### Real errors only

Never show fake alarm counts caused by empty rows or technical artifacts.

### Minimal actions

The owner’s normal routine should be:

* check Home
* post cycle if needed
* record payments if needed
* done

---

## 15. Screens

### `Home`

Main dashboard:

* current net balance
* who owes now
* next cycle status
* latest FX
* recent payments
* real warnings only

### `Members`

Member list with:

* counted / billed status
* opening balance
* current balance
* due now
* current RUB equivalent

### `Post Cycle`

Focused cycle-posting screen:

* next unposted cycle
* counted members
* billed members
* denominator
* owner subsidy
* FX check
* post action

### `Record Payment`

Payment form:

* member
* payment date
* RUB amount
* auto-found FX
* resulting USD credit
* save action

### `History`

Filters over:

* posted cycles
* posted member charges
* payments

### `Export`

Download current snapshot to:

* Excel
* CSV

---

## 16. Import / migration plan

### Phase 1 — legacy extraction

Parse the old spreadsheet and extract:

* member list
* legacy balances as of snapshot
* payment history if useful
* available FX history
* old monthly state if needed for audit

### Phase 2 — legacy freeze

Write frozen `legacy_snapshot` rows using the agreed cutover boundary.

### Phase 3 — initialize new system

Create:

* member records
* FX table
* forecast cycles from cutover onward

### Phase 4 — verification

Reconcile:

* imported opening total
* owner-visible balances
* member roster
* first-cycle math after cutover

---

## 17. Integrity checks

The app should detect and surface:

* duplicate posted cycle
* duplicate member charge within a cycle
* payment missing FX
* cycle posted without FX
* inactive member charged
* active denominator = 0
* billable member missing charge
* balance reconciliation mismatch

These should be shown as human-readable warnings, not raw technical counters.

---

## 18. Security / operational notes

* secrets stored in Streamlit secrets / environment config
* Turso connection string and auth token not hardcoded
* no public write access
* single-operator model for v1
* regular exportable backups recommended
* database is source of truth; Excel exports are reports

---

## 19. Success criteria

The project is successful if:

* legacy state is imported correctly
* owner can post a month in one clean action
* owner can record a payment in one clean action
* balances are reproducible and trustworthy
* posted history never changes retroactively
* owner no longer needs spreadsheet rituals
* app exports a clear Excel snapshot on demand

---

## 20. MVP scope

### In scope

* legacy snapshot import
* member management
* FX table
* cycle forecasting
* cycle posting
* payment recording
* balances
* dashboard
* Excel export
* integrity checks

### Out of scope for v1

* multi-user auth
* member self-service portal
* payment processor integration
* automatic FX fetching
* notifications
* mobile-native UX
* advanced analytics

---

## 21. Build philosophy

This should be a **tiny, boring, explicit internal tool**.

Not clever.
Not over-abstracted.
Not "framework architecture astronautics."

The right shape is:

* few tables
* few services
* few screens
* strong invariants
* easy exports
* easy trust

---

## 22. Suggested repo structure

```text
spotify-family-ledger/
├─ app.py
├─ pages/
│  ├─ 1_Home.py
│  ├─ 2_Members.py
│  ├─ 3_Post_Cycle.py
│  ├─ 4_Record_Payment.py
│  ├─ 5_History.py
│  └─ 6_Export.py
├─ src/
│  ├─ db/
│  │  ├─ models.py
│  │  ├─ session.py
│  │  └─ migrations/
│  ├─ services/
│  │  ├─ balances.py
│  │  ├─ cycles.py
│  │  ├─ payments.py
│  │  ├─ fx.py
│  │  └─ exports.py
│  ├─ schemas/
│  │  ├─ commands.py
│  │  └─ settings.py
│  ├─ repositories/
│  └─ utils/
├─ scripts/
│  ├─ import_legacy.py
│  └─ seed_fx.py
├─ tests/
├─ docs/
│  └─ design.md
├─ requirements.txt
└─ README.md
```

This is only a suggested starting layout, not a rigid requirement.