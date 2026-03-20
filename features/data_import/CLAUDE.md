# Data Import Feature

## Purpose
Monthly ETL pipeline: upload Etsy CSV exports to Supabase Storage and trigger the ETL pipeline
that loads data into the PostgreSQL star schema.

## Main Components
| File | Role |
|------|------|
| `routes.py` | All `/api/import/*` endpoints + helper functions |

## Data Flow
```
React Data Import UI
    → POST /api/import/upload (multipart, 6 CSV files)
    → routes.py (validate headers → upload_file_to_storage → update manifest.json)
    → Supabase Storage bucket: etsy-raw-data/{YYYY-MM}/

    → POST /api/import/run-etl?year=&month=
    → routes.py → pipelines/run_etl.py (run_etl_pipeline)
    → ETL downloads CSVs from Supabase Storage to temp dir
    → Runs full star schema build into PostgreSQL
```

## APIs Used
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/import/verify` | GET | Check Supabase Storage connectivity |
| `/api/import/periods` | GET | List all available data periods (YYYY-MM) |
| `/api/import/periods` | POST | Create a new period folder |
| `/api/import/expected-columns` | GET | Expected CSV column headers per file type |
| `/api/import/files` | GET | Files uploaded for a given period |
| `/api/import/upload` | POST | Upload 1–6 CSV files for a period |
| `/api/import/files` | DELETE | Delete a specific uploaded file |
| `/api/import/run-etl` | POST | Trigger ETL for a period |

## File Types (6 keys)
| Key | Default filename pattern |
|-----|--------------------------|
| `statement` | `etsy_statement_{year}_{month}.csv` |
| `direct_checkout` | `EtsyDirectCheckoutPayments{year}-{month}.csv` |
| `listing` | `EtsyListingsDownload.csv` |
| `sold_order_items` | `EtsySoldOrderItems{year}-{month}.csv` |
| `sold_orders` | `EtsySoldOrders{year}-{month}.csv` |
| `deposits` | `EtsyDeposits{year}-{month}.csv` |

## Key Business Logic
- **manifest.json** — Per-period JSON file in Storage tracking uploaded filenames and sizes
- **etl_status.json** — Per-period JSON tracking last ETL run time and file snapshot
- **Skip logic** — ETL is skipped if `etl_status.json` matches current file snapshot (use `force=true` to override)
- **Column validation** — CSV headers validated against `etl/expected_columns.py` before upload
- **No overwrite** — Duplicate filenames get `(1)`, `(2)` suffixes

## Storage
- Bucket: `etsy-raw-data` (Supabase)
- Requires `SUPABASE_SERVICE_ROLE_KEY` to bypass RLS policies
- Periods tracked in `periods.json` in bucket root

## Dependencies
- `shared/storage.py` — All Supabase Storage operations
- `config.py` — `get_period_for_date()`, `parse_period()`, `get_app_root()`
- `pipelines/run_etl.py` — `run_etl()` ETL entry point
- `etl/expected_columns.py` — Column validation
