# Profit & Loss Feature

## Purpose
Monthly/yearly P&L summary table with configurable expense formula.
Powers the Profit & Loss page (`/profit-loss`).

## Main Components
| File | Role |
|------|------|
| `routes.py` | FastAPI router with `/api/profit-loss/*` endpoints |
| `summary_table.py` | Core P&L query logic; builds the transposed period × line-item DataFrame |
| `formula_config.py` | Constants: `PROFIT_EXPENSE_ITEMS`, `EXPENSE_ITEM_LABELS`, `PL_ACCOUNT_MAPPING` |

## Data Flow
```
React P&L page
    → GET /api/profit-loss/summary-table?view_mode=month&selected_items=...
    → routes.py
    → summary_table.py (multiple SQL queries, joins, pivots)
    → shared/query_utils/db_query.py → shared/db.py
    → Transposed DataFrame → JSON
```

## APIs Used
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/profit-loss/formula-config` | GET | Return expense item config and formula display string |
| `/api/profit-loss/summary-table` | GET | Full P&L transposed table |
| `/api/profit-loss/clean-bank-by-pl` | DELETE | Hard-delete bank transactions by PL account + date range |

## Query Parameters (`/summary-table`)
- `start_date` / `end_date` — YYYY-MM-DD filter
- `view_mode` — `month` (aggregate by month) | `year` | `month_year` (month + year columns)
- `selected_items` — comma-separated expense column names for Net Profit calculation
- `use_default_formula` — if true and `selected_items` is null, uses `PROFIT_EXPENSE_ITEMS` from config

## Key Business Logic
- **P&L Formula** — `Net Profit = Revenue − (refund_cost + cost_of_goods + total_etsy_fees + operating_expenses)`
- **COGS source** — `fact_bank_transactions` filtered by PL account numbers 6211–6225
- **Operating expenses** — `fact_bank_transactions` filtered by PL accounts 6273, 6411–6428
- **Etsy fees** — `fact_financial_transactions` by transaction_type (Fee, VAT, Marketing)
- **Period scaffold** — Union of periods from both `fact_financial_transactions` and `fact_bank_transactions`
  ensures months with only bank costs still appear in the table

## Database Tables Read/Written
- **Read**: `fact_financial_transactions`, `fact_bank_transactions`, `dim_time`
- **Written**: `fact_bank_transactions` (DELETE via `clean-bank-by-pl`)

## Configuring the Formula
Edit `formula_config.py`:
- `PROFIT_EXPENSE_ITEMS` — list of column names subtracted from Revenue
- `EXPENSE_ITEM_LABELS` — display names for the UI
- `PL_ACCOUNT_MAPPING` — maps bank PL account numbers to column names
