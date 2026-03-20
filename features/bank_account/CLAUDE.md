# Bank Account Feature

## Purpose
View, search, filter, and import bank transaction data.
Powers the Bank Account page (`/bank-account`).

## Main Components
| File | Role |
|------|------|
| `routes.py` | Read and delete endpoints for `fact_bank_transactions` |
| `import_routes.py` | Bulk CSV/Excel upload and single-row import |

Both routers share prefix `/api/static`.

## Data Flow
```
React Bank Account page
    → GET /api/static/bank-transactions?account_number=&search=&sort_by=
    → routes.py → shared/db.run_query
    → JOIN fact_bank_transactions + dim_time + dim_bank_account + dim_product_catalog
    → JSON

    → POST /api/static/bank-transactions/upload (multipart CSV/Excel)
    → import_routes.py (column mapping, date parsing, parse_description)
    → psycopg2 batch:
        1. Upsert dim_time for all transaction dates
        2. Upsert dim_bank_account for all accounts
        3. Bulk INSERT fact_bank_transactions
```

## APIs Used
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/static/bank-transactions` | GET | Paginated + filterable transaction list |
| `/api/static/bank-transactions/count` | GET | Total row count (with optional account filter) |
| `/api/static/bank-transactions` | DELETE | Delete rows by `bank_transaction_key` list |
| `/api/static/bank-transactions/upload` | POST | Bulk CSV/Excel import |
| `/api/static/bank-transactions/import-row` | POST | Single-row import |

## Key Business Logic
- **Header detection** — For Excel/CSV, auto-detects header row by scanning for "Description"/"Diễn giải"
- **Column mapping** — Vietnamese/English dual-name column renaming (e.g., "Phát sinh có" → `credit_amount`)
- **Description parsing** — `parse_description()` from `etl/cleaners/process_bank_transactions.py` extracts:
  - `pl_account_number` — P&L account for cost categorisation
  - `parsed_product_line_id`, `parsed_product_id`, `parsed_variant_id` — product linkage
- **is_business_related** — Set to True when product IDs are successfully parsed
- **dim_time auto-creation** — Missing time_keys are batch-inserted before fact rows
- **dim_bank_account upsert** — Account records are upserted with `ON CONFLICT (account_number) DO UPDATE`
- **Unique constraint** — Duplicate `(account_number, reference_number)` raises a user-friendly 400 error

## Currency Conversion Rule
All monetary values (`credit_amount`, `debit_amount`, `balance_after_transaction`) are imported in **VND** and automatically converted to **USD** at import time using `_vnd_to_usd()` in `import_routes.py`.

```
Constant: VND_TO_USD_RATE = 24_000  (1 USD = 24,000 VND)
Formula:  usd_value = abs(vnd_value) / VND_TO_USD_RATE
```

- The conversion is applied in both the bulk CSV/Excel upload and the single-row `/import-row` endpoint.
- Values are stored in USD in `fact_bank_transactions`.
- The UI displays all monetary columns in USD format (`$1,234.56`).
- The Report page labels these columns as "Total Credit (USD)", "Total Debit (USD)", "Current Balance (USD)".

## Input Validation Rules
- **No negative amounts** — All monetary values are passed through `abs()` before conversion. Bank statement debits are sometimes exported as negative numbers; the absolute value is always used.
- **Null/NaN handling** — Missing or unparseable amounts are stored as `NULL`, not zero.
- **account_number required** — Rows missing `account_number` are skipped and reported in the `errors` list.

## Database Tables Read/Written
- **Read**: `fact_bank_transactions`, `dim_time`, `dim_bank_account`, `dim_product_catalog`
- **Written**: `fact_bank_transactions`, `dim_time`, `dim_bank_account`

## Dependencies
- `shared/db.py` — `run_query`, `execute_query`, `get_database_url`
- `etl/cleaners/process_bank_transactions.py` — `parse_description()`, `clean_bank_transactions_data()`
- `etl/expected_columns.py` — `validate_columns()`, `get_raw_columns_list()`
