# Product Catalog Feature

## Purpose
View, search, sort, and import the product master list (`dim_product_catalog`).
Powers the Product Catalog page (`/product-catalog`).

## Main Components
| File | Role |
|------|------|
| `routes.py` | Read and delete endpoints |
| `import_routes.py` | Bulk CSV/Excel upload and single-row upsert |

Both routers share the prefix `/api/static` to match the existing frontend API calls.

## Data Flow
```
React Product Catalog page
    → GET /api/static/product-catalog?search=&sort_by=&limit=&offset=
    → routes.py → shared/db.run_query → dim_product_catalog → JSON

    → POST /api/static/product-catalog/upload (multipart CSV/Excel)
    → import_routes.py → etl/cleaners/process_product_catalog.py
    → psycopg2 batch upsert ON CONFLICT DO NOTHING → dim_product_catalog
```

## APIs Used
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/static/product-catalog` | GET | Paginated + searchable product list |
| `/api/static/product-catalog/count` | GET | Total row count |
| `/api/static/product-catalog` | DELETE | Delete rows by primary key list |
| `/api/static/product-catalog/upload` | POST | Bulk CSV/Excel import |
| `/api/static/product-catalog/import-row` | POST | Single-row upsert |

## Key Business Logic
- **Composite key** — `(product_line_id, product_id, variant_id)` is the natural key; has a UNIQUE constraint
- **Batch upsert** — `ON CONFLICT (product_line_id, product_id, variant_id) DO NOTHING` for bulk upload
- **Column validation** — `etl/expected_columns.validate_columns("product_catalog", ...)` before any insert
- **Duplicate detection** — Duplicates within the uploaded file are reported back to the user before cleaning

## Database Tables Read/Written
`dim_product_catalog`

## Dependencies
- `shared/db.py` — `run_query`, `execute_query`, `get_database_url`
- `etl/cleaners/process_product_catalog.py` — `clean_product_catalog_data()`
- `etl/expected_columns.py` — `validate_columns()`, `get_raw_columns_list()`
