# Report Feature

## Purpose
Bank account statement viewer with PDF export.
Powers the Report page (`/report`).

## Main Components
| File | Role |
|------|------|
| `routes.py` | FastAPI router with all `/api/reports/*` endpoints |
| `pdf.py` | ReportLab PDF generation (no FastAPI dependency — pure function) |

## Data Flow
```
React Report page
    → GET /api/reports/bank-accounts
    → routes.py (_run helper → shared/db.run_query)
    → PostgreSQL → JSON

    → GET /api/reports/account-statement/pdf
    → routes.py → pdf.py (create_pdf_report)
    → Response(bytes, media_type="application/pdf")
```

## APIs Used
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reports/bank-accounts` | GET | Paginated list of bank accounts with stats |
| `/api/reports/bank-accounts/count` | GET | Total count of bank accounts |
| `/api/reports/bank-account-info` | GET | Details for a single account |
| `/api/reports/account-statement` | GET | Transaction rows for an account (with date filter) |
| `/api/reports/account-statement/pdf` | GET | Download statement as PDF |

## Query Parameters
- `account_number` — required filter for statement/info endpoints
- `from_date` / `to_date` — YYYY-MM-DD date range
- `offset` / `limit` — pagination for bank-accounts list

## Key Business Logic
- `_run()` — wraps `run_query` to return empty DataFrame on any DB error (prevents 500s when tables are empty)
- PDF generation uses ReportLab with Vietnamese font support (Times-Roman fallback to Helvetica)
- Date strings are validated (length + dash-count) before interpolation into SQL to prevent injection

## Database Tables Read
`fact_bank_transactions`, `dim_time`, `dim_bank_account`

## Dependencies
- `shared/db.py` — `run_query()`
- ReportLab (`reportlab` package) for PDF output
