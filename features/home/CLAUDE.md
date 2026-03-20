# Home Feature

## Purpose
Landing page / dashboard overview. Currently a stub that returns a welcome message.

## Main Components
- No backend logic — served by the catch-all SPA handler in `api/main.py`
- Frontend page: `frontend/src/pages/Home.jsx`

## Data Flow
```
GET /api/home → { message: "Home" }
```

## APIs Used
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/home` | GET | Health check / welcome stub |

## Key Business Logic
None. The Home page is a placeholder for a future summary dashboard.

## Adding Home Logic
1. Add query functions here (e.g., `get_kpi_summary.py`)
2. Add a `routes.py` with an APIRouter
3. Register the router in `api/main.py`
