# FX Sourcing Options & Strategy

This document outlines the considered options for sourcing USD/RUB exchange rates and the strategy used by the Spotify Family Ledger.

## 1. Comparison of sources

| Source | Type | Effort | Accuracy | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **CurrencyBeacon** | API | Low | Mid-market | Simple JSON API, historical and latest endpoints, API key required. |
| **CBR (Central Bank)** | XML / official data | Medium | Official | Official RUB source of truth; requires custom parsing and different series handling. |
| **Manual / Effective** | User | Medium | **Absolute** | Best for mirroring real funds moved through banks/exchanges instead of market reference data. |

## 2. The “effective rate” problem

Market APIs provide a **mid-market reference rate**. That is useful for estimates and consistent historical posting, but it may still differ from the owner’s real conversion path once spreads and fees are involved.

Example real path:
`RUB -> USDT -> KZT account -> USD`

That path can produce an **effective rate** different from the market mid-rate.

## 3. Final strategy: market-suggested, ledger-locked

### A. Forecasts and dashboard
- **Source**: CurrencyBeacon latest market rate.
- **Purpose**: show a ballpark RUB equivalent and current reference FX.
- **Meaning**: informative only.

### B. Posted cycles
- **Source**: CurrencyBeacon historical daily USD/RUB rate for the cycle date, unless the owner manually overrides it in the FX log.
- **Meaning**: once a cycle is posted, the chosen FX is locked in the ledger.

### C. Payments
- **Source**: owner-entered RUB payment amount.
- **Meaning**: in the current RUB-first model, payment credit is recorded directly in RUB rather than converted through a market FX lookup.

## 4. Implementation summary

- **Provider**: CurrencyBeacon for `latest` and `historical` USD/RUB lookups.
- **Truth**: the `fx_locked` values stored in posted cycles and posted charges remain the ledger’s source of truth, regardless of later market changes.
