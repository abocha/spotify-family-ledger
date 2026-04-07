# Editing past entries (in place) — notes

Status: Proposed implementation.

Decision: Allow operator to edit past payments **values** in place, while keeping **payment_date fixed** (Option A).

Rationale:
- Allows practical operator corrections.
- Keeps ledger semantics stable enough for exports/balances.
- Still not fully ledger-true; we therefore must capture `edit_reason` and `edited_at`.
