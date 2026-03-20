# Charts Feature

## Purpose
KPI cards and time-series charts for the Charts page (`/charts`). Serves 17+ analytical metrics
calculated from the PostgreSQL star schema.

## Main Components
| File | Role |
|------|------|
| `routes.py` | FastAPI router with all `/api/charts/*` endpoints |
| `calculations/` | One file per metric — pure SQL-returning functions |
| `calculations/_streamlit_shim.py` | No-op shim for legacy `st` import |

## Data Flow
```
React Charts page
    → GET /api/charts/<metric>?start_date=&end_date=&customer_type=
    → routes.py (_safe_chart_call)
    → calculations/get_<metric>.py (SQL query)
    → shared/query_utils/chart_helpers.py (execute_chart_query)
    → shared/query_utils/db_query.py
    → shared/db.py (run_query → PostgreSQL)
    → DataFrame → JSON → Frontend
```

## APIs Used (all GET)
| Endpoint | Description |
|----------|-------------|
| `/api/charts/total-revenue` | Sum of sales revenue |
| `/api/charts/total-orders` | Total order count |
| `/api/charts/total-customers` | Unique customer count |
| `/api/charts/average-order-value` | AOV KPI |
| `/api/charts/revenue-by-month` | Monthly revenue trend |
| `/api/charts/profit-by-month` | Monthly profit trend |
| `/api/charts/new-vs-returning` | New vs returning customer split |
| `/api/charts/new-customers-over-time` | New customer acquisition trend |
| `/api/charts/customers-by-location` | Geographic customer distribution |
| `/api/charts/customer-retention-rate` | Retention rate over time |
| `/api/charts/total-sales-by-product` | Product-level revenue ranking |
| `/api/charts/customer-acquisition-cost` | CAC metric |
| `/api/charts/customer-lifetime-value` | CLV metric |
| `/api/charts/cac-clv-ratio-over-time` | CAC/CLV ratio trend |
| `/api/charts/total-orders-by-month` | Monthly order count |
| `/api/charts/average-order-value-over-time` | AOV trend |
| `/api/charts/revenue-comparison` | Month-over-month comparison |
| `/api/charts/month-names` | Month name lookup |

## Query Parameters (most endpoints)
- `start_date` / `end_date` — YYYY-MM-DD date range filter
- `customer_type` — `all` | `new` | `return`

## Key Business Logic
- `_sanitize_dates`: Expands same-start-and-end-date to full month range
- `_safe_chart_call`: Returns empty DataFrame instead of 500 on any DB error
- Shared filter builders in `shared/query_utils/query_builder.py` generate standard WHERE clauses

## Database Tables Read
`fact_sales`, `fact_payments`, `dim_time`, `dim_customer`, `dim_product`, `dim_geography`

## Adding a New Chart
1. Create `calculations/get_<metric>.py` with `get_<metric>(start_date, end_date, customer_type)` returning a DataFrame
2. Add one `@router.get("/<endpoint>")` in `routes.py` following the existing pattern
3. No other files need modification
