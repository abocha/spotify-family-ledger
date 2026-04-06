# AGENTS.md

## Purpose

This repository contains a **small owner-facing internal tool** for managing a shared Spotify Family subscription.

The app replaces a spreadsheet-based workflow with a proper web app that is:

- easier to operate
- harder to break
- more honest about FX effects over time
- explicit about ledger history vs forecast

This is **not** a generic finance product or a platform. Keep it narrow, boring, and trustworthy.

---

## Project shape

### What we are building
A Streamlit app backed by Turso (remote SQLite / libSQL) for one primary operator.

The owner should only need to do two real actions:

1. **Post the next monthly charge cycle**
2. **Record a member payment**

Everything else should be derived from stored facts.

### Contract boundary
- Up to **2026-04-19**, the legacy spreadsheet (`spotify семья`) is the contractual source of truth.
- From **2026-04-20** onward, this app is the contractual source of truth.

Do not blur this boundary.

---

## Core domain rules

### Accounting model
- Subscription cost is defined in **USD**
- Member debt is tracked in **USD**
- Payments are usually made in **RUB**
- Each payment is converted to **USD credit** using the FX rate for the **payment date**
- Posted charges and recorded payments are **immutable**
- Forecasts may change; posted history may not

### Important distinction
Keep these separate at all times:

1. **Historical RUB actually paid**
2. **Current RUB equivalent of current debt**

They are different concepts and must never be merged into one ambiguous total.

### Balance formula
For each member:

`current_usd_balance = legacy_opening_usd + posted_charges_usd - payment_credits_usd`

Current RUB equivalent is display-only:

`current_rub_equivalent = current_usd_balance * latest_fx`

---

## Product principles

### Owner-first
The primary user is the owner/operator, not an engineer.

The UI should:
- reduce cognitive load
- avoid spreadsheet rituals
- expose only the next meaningful action
- show human-readable statuses and errors

### Facts in, views out
Users enter facts. The app computes results.

Do not make the user manually maintain accounting state.

### Hide plumbing
Do not expose raw database mechanics, helper tables, or internal workflow artifacts in the normal UI unless needed for debugging/admin.

### Real errors only
Never show fake alarms caused by empty data, optional fields, or technical artifacts.

### Small and boring wins
Prefer:
- few tables
- few services
- few screens
- explicit rules
- straightforward code

Avoid framework theatrics, clever abstractions, and “future-proofing” for imaginary scale.

---

## Tech stack

### Runtime / app
- Python
- Streamlit

### Database
- Turso
- SQLAlchemy
- `sqlalchemy-libsql`
- Alembic

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

Do not introduce major new dependencies without a concrete need.

---

## Architecture rules

## 1. Source of truth
The database is the source of truth.

Excel / CSV exports are reports and snapshots, not live operational state.

## 2. Keep business logic out of Streamlit pages
Pages should mostly:
- gather inputs
- call services
- render results

Do not bury core accounting logic in page files.

## 3. Prefer explicit service functions
Put domain operations in service-layer functions such as:
- `post_next_cycle(...)`
- `record_payment(...)`
- `get_member_balances(...)`
- `build_export_workbook(...)`

## 4. Use immutable ledger rows
Never “update history” when a new FX rate appears.

Instead:
- forecasts may be recalculated
- posted charges stay fixed
- recorded payments stay fixed

## 5. Separate forecast from ledger
Do not mix:
- future schedule / forecast
- posted cycles
- immutable member-level charges
- recorded payments

These are different layers.

## 6. Make invariants enforceable
Prefer DB constraints + service checks over UI conventions.

Examples:
- cycle can only be posted once
- payment cannot be saved without locked FX
- duplicate member charge in one cycle must be impossible
- inactive member must not be charged

---

## Expected data model

Main tables:

- `members`
- `legacy_snapshot`
- `fx_rates`
- `charge_cycles`
- `posted_charges`
- `payments`

Optional later:
- `adjustments`

Keep schema names explicit and unsurprising.

---

## Screen expectations

The app should stay roughly within this owner-facing shape:

- `Home`
- `Members`
- `Post Cycle`
- `Record Payment`
- `History`
- `Export`

Do not expand the UI surface casually.

If a new screen is proposed, justify why it is better than improving an existing one.

---

## UX rules

### Home
Must answer:
- who owes now
- what is the next action
- whether the next cycle is ready to post
- whether there are any real issues

### Posting flow
Must feel like:
- review
- confirm
- post

Not:
- manual ledger editing
- copy/paste
- state juggling

### Payment flow
Must feel like:
- choose member
- enter date and amount
- see FX and USD credit
- save

Not:
- manual FX locking rituals
- hidden derived columns
- spreadsheet-style staging steps

### Error messaging
Errors must be written in owner language.

Good:
- “No FX rate exists for 2026-05-20”
- “April 2026 cycle is already posted”

Bad:
- “Integrity count = 17”
- raw stack traces shown in normal workflow

---

## Coding standards

### General
- Write clear, boring, maintainable Python
- Prefer explicit names over short clever names
- Prefer small functions with single responsibilities
- Avoid hidden side effects

### Types
- Add type hints on public functions and service boundaries
- Use Pydantic schemas for command/input validation where helpful

### Database
- Keep DB access centralized
- Avoid SQL scattered across UI pages
- Use transactions for posting cycles and saving payments

### Streamlit
- Keep page code thin
- Use forms for destructive / important actions
- Avoid overcomplicated session-state machinery

### Comments
Comment only where intent is non-obvious or business rules are easy to misread.

Do not narrate trivial code.

---

## Testing expectations

Changes touching money, posting, balances, FX, or imports should have tests.

Minimum useful test coverage should include:
- posting a cycle
- preventing double-posting
- payment recording with locked FX
- balance calculations
- inactive member exclusion
- denominator / billed-member logic
- legacy snapshot reconciliation

Prefer focused unit/integration tests over giant end-to-end test pyramids.

---

## Migrations and data safety

### Alembic
Use Alembic for schema changes.

### Migration rules
- Migrations must be additive and readable whenever possible
- Destructive migrations require explicit justification
- Never silently rewrite posted historical data

### Imports
Legacy import scripts should be:
- idempotent where practical
- transparent about assumptions
- easy to re-run in a staging DB

---

## Exports

Exports should be owner-friendly and boring.

They should prioritize:
- clarity
- traceability
- reproducibility

Do not try to recreate a spreadsheet app inside the export.

Exports are outputs, not the system.

---

## Approval stops

Stop and ask for approval before doing any of the following:

1. Changing core business rules
   - cutover date semantics
   - balance formula
   - counted vs billable logic
   - FX-locking behavior

2. Destructive schema/data operations
   - dropping tables/columns
   - rewriting posted charges
   - bulk-changing payment history

3. Expanding scope materially
   - auth
   - multi-user roles
   - member portal
   - automatic FX fetching
   - notifications
   - external payment integrations

4. Major dependency additions
   - anything that meaningfully increases complexity or hosting risk

5. Deployment/infrastructure changes
   - changes beyond the current Streamlit + Turso target

---

## Preferred agent workflow

When working on a task:

1. Understand the exact user-visible goal
2. Respect the current design doc and contract boundary
3. Make the smallest clean change that solves the real problem
4. Preserve invariants
5. Provide evidence

### Evidence means
For non-trivial changes, report:
- what changed
- what assumptions were made
- what was tested
- what remains intentionally untouched

Keep reports compact.

---

## Prompting preference for coding agents

Prefer minimal, modern prompting style:

- goal
- constraints
- what counts as evidence
- where to stop for approval

Do not over-narrate steps.
Do not invent busywork.
Do not “future-proof” beyond the actual project needs.

---

## Things to avoid

Do not:
- turn this into a generic bookkeeping platform
- reintroduce spreadsheet-style manual state transitions
- store operational truth in exports
- mix forecast rows with immutable history
- expose raw internal tables as normal UX
- add abstraction layers “just in case”
- optimize for scale that does not exist
- silently change accounting semantics

---

## Decision rule

If there is a choice between:

- clever and concise
- explicit and boring

choose **explicit and boring**.

If there is a choice between:

- more flexibility
- stronger trust and invariants

choose **stronger trust and invariants**.

If there is a choice between:

- a prettier implementation
- a workflow that is easier for the owner

choose **the easier owner workflow**.

---

## Canonical docs

The following should stay aligned:
- `README.md`
- `docs/design.md`
- this `AGENTS.md`

If code behavior changes in a way that affects product rules or operator workflow, update the docs too.