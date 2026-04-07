# Spotify Family Ledger

Small owner-facing web app for managing a shared Spotify Family subscription.

This project replaces the legacy spreadsheet-based workflow with a proper app that is easier to operate, harder to break, and more honest about FX effects over time.

## What this app does

The owner should only need to do two real actions:

1. **Post the next monthly charge cycle**
2. **Record a member payment**

Everything else is derived from stored facts.

## Why this exists

The old spreadsheet tried to be all of these at once:

- database
- accounting engine
- workflow engine
- UI
- reporting layer

That led to predictable pain:

- brittle formulas
- manual "copy as values" rituals
- forecast rows mixed with actual history
- weak error prevention
- poor owner UX
- hard-to-trust totals

This app turns that into a small, explicit internal tool.

## Contract boundary

### Legacy period
Up to **2026-04-19**, the legacy spreadsheet (`spotify семья`) is the contractual source of truth.

### New period
From **2026-04-20** onward, this app is the contractual source of truth.

## Accounting model

- Subscription cost is defined in **USD**
- Member debt is tracked in **USD**
- Payments are usually made in **RUB**
- Each RUB payment is converted into **USD credit** using the FX rate for the payment date
- Positive balance means the member has credit; negative balance means the member owes the owner
- Posted charges and recorded payments are **immutable**
- Forecasts may change; posted history may not

### Important distinction

The system must keep these separate:

1. **Historical RUB actually paid**
2. **Current RUB equivalent of current balance**

These are different numbers and must never be merged into one ambiguous total.

## Core workflows

### 1. Post next cycle
The owner:
- opens the app
- reviews the next unposted monthly cycle
- confirms member counts and FX
- clicks **Post cycle**

The app:
- locks the cycle FX
- writes immutable posted charge rows
- updates balances

### 2. Record payment
The owner:
- selects a member
- enters payment date and RUB amount
- confirms the computed USD credit
- clicks **Save payment**

The app:
- uses the operator-entered effective FX
- locks FX and USD credit
- writes an immutable payment row
- updates balances

## Stack

### Runtime / app
- Python
- Streamlit

### Database
- Turso (remote libSQL / SQLite)
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

## Why Turso

The app is deployed on Streamlit Community Cloud.

Local SQLite on Community Cloud is not safe as a writable source of truth because local filesystem persistence is not guaranteed across restarts / redeploys. Turso gives us remote SQLite semantics with persistence.

## UX principles

- **Owner-first**: no spreadsheet rituals
- **Facts in, views out**: user enters facts, app computes results
- **Hide plumbing**: internal mechanics should not leak into normal workflow
- **Status-driven UI**: clear operational states
- **Real errors only**: no fake alarms from empty rows or formula artifacts
- **Small and boring**: tiny internal tool, not a platform

## Screens

- **Home** — dashboard, balances, next action
- **Members** — roster, balances, billable/countable status
- **Post Cycle** — next cycle review and posting
- **Record Payment** — payment form
- **History** — posted cycles and payments
- **Export** — Excel / CSV snapshot export

## High-level data model

Main tables:

- `members`
- `legacy_snapshot`
- `fx_rates`
- `charge_cycles`
- `posted_charges`
- `payments`

See [`docs/design.md`](docs/design.md) for the full design.

## MVP scope

### In scope
- import legacy snapshot
- member management
- FX table
- cycle forecasting
- cycle posting
- payment recording
- balances
- dashboard
- Excel export
- integrity checks

### Out of scope for v1
- multi-user auth
- member self-service
- payment processor integration
- automatic FX fetching
- notifications
- advanced analytics

## Build philosophy

This should be a **tiny, boring, explicit internal tool**.

Not clever.  
Not over-abstracted.  
Not a pseudo-fintech empire.

The right shape is:

- few tables
- few services
- few screens
- strong invariants
- easy exports
- easy trust

## Status

Design phase / implementation in progress.
