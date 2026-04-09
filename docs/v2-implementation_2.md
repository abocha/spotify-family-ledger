# Remediation Plan: Align V2 With Spec and Ledger Semantics

## Summary

Patch the current v2 rewrite in three areas so it matches the original implementation plan and the broader product contract:

- make stale mode recoverable by allowing **repair actions only**
- make opening balances a **single frozen cutover import** per member
- close the current verification gaps with targeted tests for failure handling and access behavior

Chosen defaults:
- opening balances are imported once and then treated as frozen
- any later correction to cutover debt is expressed as an **adjustment**, not a second snapshot
- when stale, admin may **edit members and retry reconciliation**, but may **not** record payments or add adjustments

## Key Changes

### 1. Lock opening-balance semantics to the product model

Update the data model and read layer so opening balances cannot silently double-count.

- Change `opening_balances` to enforce **one row per member**, not one row per `(member, snapshot_date)`.
- Treat opening balance as a special frozen cutover fact, not a timeline of snapshots.
- Update balance queries and statement queries to read that single opening row directly instead of summing all opening rows.
- Update seed/reset assumptions so reseeding or manual repair cannot create multiple opening-balance rows for one member.
- If opening-balance repair is ever needed, require it to happen through `adjustments`, not through extra opening imports.

Public/data contract impact:
- `OpeningBalance` becomes logically one-per-member.
- `source_note` remains metadata for the cutover import only.
- member statement continues to show one opening-balance entry at the start.

### 2. Make stale mode repairable without allowing normal writes

Refine stale-mode gating in the admin UI.

- Split admin capabilities into:
  - **repair actions**: member edits, manual reconciliation retry
  - **normal writes**: payments, adjustments
- In stale mode:
  - keep member management enabled
  - keep retry enabled
  - keep payment entry disabled
  - keep adjustment entry disabled
- Update copy so the stale banner explicitly says which actions are still allowed.
- Preserve public read-only views exactly as they are now.

Behavior impact:
- a reconciliation failure caused by bad member config can be fixed in-app
- stale mode still prevents normal financial writes against an incomplete ledger

### 3. Close the missing spec coverage with targeted tests

Add the missing tests that prove the current code actually satisfies the implementation plan.

Required additions:
- opening-balance uniqueness and non-accumulation
- stale mode allows member edits + retry but blocks payments/adjustments
- Telegram delivery failure is recorded on `reconciliation_runs` and does not crash reconciliation
- admin/public access split for the rewritten page set
- stale banner/exact-through behavior remains visible on Home and Statements

Also add one regression test for:
- an attempted second opening-balance import for the same member is rejected or otherwise cannot affect balances twice

## Test Plan

Add or update tests to cover these scenarios:

- `opening_balances` has one row per member and cannot be double-counted
- balances/statements use the frozen opening import exactly once
- stale reconciliation due to member configuration can be repaired by editing members and retrying
- stale reconciliation blocks payment writes and adjustment writes
- Telegram send failure records `alert_error` and returns a stale outcome without raising
- public users can still open Home and Statements without login
- admin gating still protects the Admin page and write actions

## Assumptions

- No schema compatibility with the abandoned v1 model is needed.
- Existing v2 in-progress schema can be adjusted freely before a production reset.
- Opening-balance corrections after cutover should be visible as adjustments, not hidden as replacement imports.
- “Repair actions only” in stale mode means **member edits + retry**, and does not include payments or adjustments.
