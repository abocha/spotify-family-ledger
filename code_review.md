# Code Review — Spotify Family Ledger

Reviewed: all source files under `ledger/`, `pages/`, `tests/`, `scripts/`, `app.py`, `migrations/env.py`, `pyproject.toml`.

---

## 🔴 Critical Bugs

### 1. Double-commit in pages conflicts with `get_db()` context manager

**Files:** [2_Members.py](file:///home/abocha/code/spotify-family-ledger/pages/2_Members.py#L115), [3_Post_Cycle.py](file:///home/abocha/code/spotify-family-ledger/pages/3_Post_Cycle.py#L76), [5_History.py](file:///home/abocha/code/spotify-family-ledger/pages/5_History.py#L97)

The `get_db()` context manager **auto-commits on exit**:

```python
# database.py
@contextmanager
def get_db():
    session = SessionLocal()
    try:
        yield session
        session.commit()       # <-- auto-commits on clean exit
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

But three pages call `session.commit()` manually *inside* the `with get_db()` block before calling `st.rerun()`. This means:

- The explicit `session.commit()` commits the work.
- `st.rerun()` throws a `RerunException`.
- The `except` block catches it and calls `session.rollback()` — **rolling back nothing** (already committed, so harmless).
- But conceptually the exception propagation from `st.rerun()` is caught by the generic `except Exception`, which is wrong.

**Worse:** if `st.rerun()` is ever removed or the flow changes so that the `with` block exits normally, there will be a **second commit** on already-committed data.

> [!IMPORTANT]
> The `get_db()` context manager should either NOT auto-commit (let callers be explicit), or pages should NOT call `session.commit()` manually. Pick one pattern.

---

### 2. `st.rerun()` inside `get_db()` causes `except` to catch `RerunException`

**Files:** [2_Members.py](file:///home/abocha/code/spotify-family-ledger/pages/2_Members.py#L116), [3_Post_Cycle.py](file:///home/abocha/code/spotify-family-ledger/pages/3_Post_Cycle.py#L78)

Streamlit's `st.rerun()` raises a special `RerunException`. Because it's called *inside* the `with get_db()` block, `get_db()`'s `except Exception` catches it and calls `session.rollback()`. The rerun still happens (Streamlit catches it higher up), but the rollback is executing against an already-committed session. This is fragile — if the commit hadn't happened yet, **the rerun would silently roll back the user's action**.

---

### 3. `Post Cycle` page crashes when `market_rate` is `None`

**File:** [3_Post_Cycle.py](file:///home/abocha/code/spotify-family-ledger/pages/3_Post_Cycle.py#L39)

```python
delta=f"{(float(preview.fx_rate) - market_rate):.4f} vs market" if market_rate else None,
```

If `preview.fx_rate` is a `Decimal` and `market_rate` is a `float`, Python can subtract them. But if the ExchangeRate-API is down, `market_rate` is `None`, the ternary handles that. **However**, the `except Exception` block on line 80-81 silently swallows this — you would never know the page crashed. More critically, line 57:

```python
"RUB Equivalent": float(m.charge_rub_equivalent) if m.charge_rub_equivalent else None,
```

This treats `Decimal("0")` as falsy. If `charge_rub_equivalent` is `Decimal("0.00")` (non-billable member with an FX rate), this will show `None` instead of `0.00`. This is a **silent data display bug**.

---

### 4. Export service uses wrong attribute access pattern

**File:** [exports.py](file:///home/abocha/code/spotify-family-ledger/ledger/services/exports.py#L52-L78)

The query returns `(Payment, Member)` tuples, but the DataFrame comprehension accesses them as if they are named-tuple objects with `.Payment` and `.Member` attributes:

```python
payments = session.query(Payment, Member).join(Member)...
# Then:
"Date": p.Payment.payment_date,   # ❌ p is a tuple (Payment, Member)
"Member": p.Member.display_name,   # ❌
```

SQLAlchemy `session.query(A, B)` returns `Row` objects. In some SQLAlchemy versions, `row.Payment` works as a *named attribute*. In others (especially with newer SA 2.x), this works, but it's fragile. The safer pattern would be tuple unpacking (`for payment, member in payments`), which is exactly what `list_payments` in [payments.py](file:///home/abocha/code/spotify-family-ledger/ledger/services/payments.py#L88) does correctly:

```python
for p, m in rows  # ✅ correct in payments.py
```

Same issue for the `posted_charges` comprehension (accessing `.ChargeCycle`, `.PostedCharge`, `.Member`).

> [!WARNING]
> This will likely **crash at runtime** if anyone actually clicks "Download Excel Snapshot". Test this path.

---

### 5. `Record Payment` page has two submit buttons in one form — second never fires

**File:** [4_Record_Payment.py](file:///home/abocha/code/spotify-family-ledger/pages/4_Record_Payment.py#L27-L28)

```python
preview_submit = st.form_submit_button("Preview payment")
save_submit = st.form_submit_button("Save Payment", type="primary")
```

Streamlit forms can have multiple submit buttons, but only **one** fires per form submission. The form's `if preview_submit or save_submit:` block runs the same code for both. However, the user flow is broken:

1. User clicks "Preview payment" → preview shows, but it's inside the form, so on the next rerun the form resets and the preview disappears.
2. User then clicks "Save Payment" → the preview is re-computed and saved in one shot.

The real problem: **there is no two-step confirm flow**. The preview and save happen in the same form submission. The user can never "preview first, then confirm save" because the form resets between submissions. This violates the AGENTS.md requirement for a review → confirm → save flow.

---

### 6. `Record Payment` doesn't call `session.commit()`

**File:** [4_Record_Payment.py](file:///home/abocha/code/spotify-family-ledger/pages/4_Record_Payment.py#L48)

```python
if save_submit:
    payment = record_payment(session, cmd)
    st.success(...)
    # ❌ no session.commit() — relies entirely on get_db()'s auto-commit
```

Given bug #1 (`get_db` auto-commits), this actually works **accidentally** — the `with get_db()` block exits cleanly and commits. But it means the success message shows *before* the commit actually happens. If the commit fails (e.g. unique constraint violation), the user sees "Payment recorded!" but it wasn't.

---

### 7. Tests cannot run — `ModuleNotFoundError: No module named 'ledger'`

As demonstrated by the test run:

```
ModuleNotFoundError: No module named 'ledger'
```

The `pyproject.toml` doesn't define `[tool.setuptools]` or `[build-system]` package discovery, so `ledger` is not on the path when running `uv run pytest`. Tests are **completely broken**.

---

## 🟡 Medium Severity Issues

### 8. `st.set_page_config()` called in every page AND in `app.py`

**Files:** `app.py` + all 6 pages

Streamlit requires exactly one `set_page_config` call. When navigating, Streamlit executes the page script, not `app.py`. The fact that `app.py` also calls it creates potential conflicts (multiple `set_page_config` calls in a session). Some pages set `layout="wide"`, others don't, creating inconsistent layouts.

---

### 9. `market_fx.py` imports `streamlit` in a service module

**File:** [market_fx.py](file:///home/abocha/code/spotify-family-ledger/ledger/services/market_fx.py#L4)

```python
import streamlit as st

@st.cache_data(ttl=3600)
def fetch_market_rate():
```

This violates AGENTS.md rule: *"Keep business logic out of Streamlit pages."* Using `@st.cache_data` in a service module means:
- The service can't be imported in non-Streamlit contexts (tests, scripts, Alembic).
- The module import in `services/__init__.py` will crash any non-Streamlit caller.

This is why the tests fail to even import `ledger.services` — importing the package triggers `import streamlit as st` via `market_fx.py`.

---

### 10. `python-dateutil` is a transitive dependency, not declared

**File:** [pyproject.toml](file:///home/abocha/code/spotify-family-ledger/pyproject.toml)

`cycles.py` uses `from dateutil.relativedelta import relativedelta`. The `python-dateutil` package is present in `uv.lock` as a transitive dependency (via pandas), but is not listed in `pyproject.toml`. If pandas ever drops this dependency, the import will break.

---

### 11. Integrity check queries a non-nullable column for `NULL`

**File:** [integrity.py](file:///home/abocha/code/spotify-family-ledger/ledger/services/integrity.py#L14)

```python
payments_no_fx = session.query(Payment).filter(Payment.fx_locked.is_(None)).count()
```

But `Payment.fx_locked` is `Mapped[Decimal]` (non-nullable, `nullable=False`). This query will always return 0. It's not *wrong*, but it's dead code that will never find anything useful.

---

### 12. `width="stretch"` is not a valid `st.dataframe` parameter

**Files:** [2_Members.py](file:///home/abocha/code/spotify-family-ledger/pages/2_Members.py#L36), [5_History.py](file:///home/abocha/code/spotify-family-ledger/pages/5_History.py#L40) (×3)

The `st.dataframe()` parameter for width control is `use_container_width=True`, not `width="stretch"`. This is silently ignored by Streamlit (it accepts `**kwargs`), so the tables render at default width instead of stretching.

---

### 13. `ledger/services.py` stub file shadows `ledger/services/` package

**File:** [services.py](file:///home/abocha/code/spotify-family-ledger/ledger/services.py)

Both `ledger/services.py` (a file with stub `pass` functions) and `ledger/services/` (a package directory with real implementations) exist. Python's module resolution prioritizes the package directory, so `from ledger.services import ...` uses the package. But the stub file is dead code that will confuse developers and could cause import issues in edge cases.

---

### 14. `active_to` set via `st.date_input` with `value=None` can cause issues

**File:** [2_Members.py](file:///home/abocha/code/spotify-family-ledger/pages/2_Members.py#L62-L69)

```python
active_to = st.date_input(
    "Active To (optional)",
    value=(
        selected_member.active_to
        if selected_member and getattr(selected_member, "active_to", None)
        else None
    ),
)
```

When `value=None`, `st.date_input` defaults to `date.today()`. So the "optional" Active To always shows today's date, and if the user saves without clearing it, they accidentally deactivate the member effective today. There's no way to clear it back to `None` through this form.

---

## 🟢 Style / Minor Issues

### 15. `get_db()` used as both read and write context

All pages use the same `get_db()` for reads and writes. There's no read-only mode, so every page view triggers a commit (even if nothing changed). This is technically harmless with SQLite but adds unnecessary overhead.

### 16. Lazy import inside `_compute_balance`

**File:** [balances.py](file:///home/abocha/code/spotify-family-ledger/ledger/services/balances.py#L72)

```python
from datetime import date  # lazy import inside function body
today = date.today()
```

`date` is already imported at module level (line 3 imports `Decimal`; `date` is used in the type hints). Actually, looking more closely, `date` is *not* imported at the top of `balances.py`. This works but is unconventional — just add it to the top-level imports.

### 17. Missing `__all__` update if new services are added

The `services/__init__.py` manually mirrors all public functions. Any new function added to a service module must also be added here or it won't be accessible via `from ledger.services import ...`.

### 18. No test for `record_payment` rejecting missing FX

There's a test for `preview_payment_no_fx` but no test for `record_payment` raising `ValueError` when FX is missing.

### 19. No test for double-posting prevention

AGENTS.md explicitly lists "preventing double-posting" as required test coverage. There's no test for `post_cycle` raising `ValueError` when status is already "posted".

---

## Summary Table

| # | Severity | Area | Issue |
|---|----------|------|-------|
| 1 | 🔴 Critical | `database.py` + pages | Double-commit / conflicting commit patterns |
| 2 | 🔴 Critical | pages | `st.rerun()` inside `get_db()` triggers rollback |
| 3 | 🔴 Critical | `3_Post_Cycle.py` | `Decimal("0")` treated as falsy hides real values |
| 4 | 🔴 Critical | `exports.py` | Wrong tuple attribute access — likely runtime crash |
| 5 | 🔴 Critical | `4_Record_Payment.py` | Two submit buttons in one form — no real preview step |
| 6 | 🔴 Critical | `4_Record_Payment.py` | Success shown before commit; crash = silent data loss |
| 7 | 🔴 Critical | `tests/` | Tests can't run at all (`ModuleNotFoundError`) |
| 8 | 🟡 Medium | all pages | `set_page_config` conflict with `app.py` |
| 9 | 🟡 Medium | `market_fx.py` | `import streamlit` in service module breaks testability |
| 10 | 🟡 Medium | `pyproject.toml` | `python-dateutil` not declared as direct dependency |
| 11 | 🟡 Medium | `integrity.py` | Checks non-nullable column for `NULL` (dead check) |
| 12 | 🟡 Medium | pages | `width="stretch"` is invalid; tables don't stretch |
| 13 | 🟡 Medium | `ledger/` | Stub `services.py` file shadows `services/` package |
| 14 | 🟡 Medium | `2_Members.py` | `active_to` can't be set to `None` via UI form |
| 15 | 🟢 Minor | `database.py` | Read-only pages trigger unnecessary commit |
| 16 | 🟢 Minor | `balances.py` | Lazy import of `date` inside function body |
| 17 | 🟢 Minor | `services/__init__.py` | Manual `__all__` sync required for new functions |
| 18 | 🟢 Minor | tests | Missing test: `record_payment` rejecting missing FX |
| 19 | 🟢 Minor | tests | Missing test: double-posting prevention |

---

## Recommended Fix Priority

1. **Fix test infrastructure** (#7, #9) — you can't validate anything without working tests
2. **Fix transaction management** (#1, #2, #6) — pick a single commit pattern
3. **Fix export crash** (#4) — use tuple unpacking
4. **Fix Record Payment UX** (#5) — separate preview from save
5. **Delete stub `services.py`** (#13) — remove dead code
6. **Fix `width="stretch"`** (#12) — use `use_container_width=True`
7. **Fix falsy Decimal** (#3) — use `is not None` checks
8. Address remaining medium/minor issues
