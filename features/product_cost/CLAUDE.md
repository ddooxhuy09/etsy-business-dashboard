# Product Cost Feature

## Purpose
Per-product profitability analysis: COGS breakdown, Etsy fee breakdown, and margin analysis.
Powers the Product Cost page (`/product-cost`).

## Main Components
| File | Role |
|------|------|
| `routes.py` | Route registration via `register_routes(app)` pattern |
| `models.py` | Pydantic response models (`ProductSummary`, `VariantDetail`, etc.) |
| `queries.py` | All SQL queries using SQLAlchemy engine |
| `cache.py` | In-memory TTL cache instances (5-minute TTL) |
| `config.py` | SQLAlchemy engine creation (reads `shared.db.get_database_url`) |

## Data Flow
```
React Product Cost page
    → GET /api/products
    → routes.py (check cache → query_products_optimized)
    → queries.py (SQLAlchemy, engine from config.py)
    → shared/db.py (DATABASE_URL)
    → PostgreSQL → Pydantic models → JSON
```

## APIs Used
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/products` | GET | List all products with cost metrics |
| `/api/products/{id}/variants` | GET | Variants and pricing for a product |
| `/api/products/{id}/cogs_breakdown` | GET | COGS by cost category |
| `/api/products/{id}/etsy_fee_breakdown` | GET | Etsy fee breakdown by fee type |
| `/api/products/{id}/margin_breakdown` | GET | Margin analysis by order |
| `/api/cache/clear` | POST | Clear all in-memory caches |
| `/api/health` | GET | Health check |

## Key Business Logic
- **COGS categories** — configured in `config.py` (`COGS_LABELS` mapping PL account → label)
- **Margin formula** — `margin = (sales - refund - cogs - etsy_fee) / sales * 100`
- **Caching** — All query results cached for 5 minutes to reduce DB load; invalidated via `/api/cache/clear`
- **Router pattern** — Uses `register_routes(app)` instead of `APIRouter` because `app.get()` is called directly

## Database Tables Read
`fact_sales`, `fact_bank_transactions`, `dim_product_catalog`, `dim_time`

## Dependencies
- `shared/db.py` — `get_database_url()` for SQLAlchemy engine
