# FX Sourcing Options & Strategy

This document outlines the considered options for sourcing USD/RUB exchange rates and the final strategy for the Spotify Family Ledger.

## 1. Comparison of Sources

| Source | Type | Effort | Accuracy | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **ExchangeRate-API** | API | Low | Mid-Market | Reliable, open `v4` endpoint supports RUB natively without authentication required. |
| **CBR (Central Bank)** | XML | Medium | Official | The official RUB source of truth; requires XML parsing. |
| **Manual / Effective** | User | Medium | **Absolute** | Based on actual funds moved through Bybit/KZT/Banks. |

## 2. The "Effective Rate" Problem

Market rates (Google, Frankfurter, etc.) are **Mid-Market Rates**. They represent a theoretical center and are not accessible to retail users.

The owner's actual exchange path:
`RUB` $\rightarrow$ `USDT (Bybit)` $\rightarrow$ `KZT (Multi-currency account)` $\rightarrow$ `USD`

This path involves multiple spreads and fees, meaning the **Effective Rate** (the actual cost to acquire 1 USD) is significantly different from the Market Rate. Using a Market API for a ledger would create a "hidden deficit" where the ledger records a credit that doesn't match the actual cost spent.

## 3. Final Strategy: "Market-Suggested, Effective-Locked"

To maintain "accounting honesty," the app will not rely solely on an automated API.

### A. For Forecasts & Home Dashboard
- **Source**: ExchangeRate-API.
- **Purpose**: Provide a "ballpark" estimate for upcoming charges and current RUB equivalents of debt.
- **Logic**: "Based on current market trends, this is roughly what is owed."

### B. For Posted Cycles (Immutable)
- **Source**: Market Rate (Suggested) $\rightarrow$ Owner Confirmed.
- **Logic**: The owner reviews the market rate for the cycle date and confirms/locks it.

### C. For Payments (Immutable)
- **Source**: **Effective Rate (Owner Input)**.
- **Logic**: Instead of trusting an API, the owner records the actual RUB received and the resulting USD credit gained.
- **Formula**: $\text{Effective FX} = \frac{\text{RUB Received}}{\text{USD Credit Gained}}$
- **Result**: The ledger tracks real money, not theoretical market values.

## 4. Summary of Implementation
- **API**: Use ExchangeRate-API (`v4/latest`) for low-friction estimates.
- **Truth**: The `fx_locked` column in `posted_charges` and `payments` tables remains the absolute source of truth, regardless of what any API says.
