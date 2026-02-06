"""
Dashboard FastAPI – mounts API routes and serves built frontend (frontend/dist).
Run: uvicorn api.main:app --reload --port 8001
"""
import os
import sys
import logging
from pathlib import Path

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Load .env file if exists
try:
    from dotenv import load_dotenv
    # Load .env from project root
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try loading from current directory
        load_dotenv()
except ImportError:
    # python-dotenv not installed, skip loading .env
    pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from api.auth_middleware import AuthMiddleware

from api.product_cost.routes import register_routes as register_product_cost_routes
from api.charts_routes import router as charts_router
from api.profit_loss_routes import router as profit_loss_router
from api.reports_routes import router as reports_router
from api.import_routes import router as import_router
from api.static_data_routes import router as static_data_router
from api.static_data_import_routes import router as static_data_import_router
from api.auth_routes import router as auth_router

app = FastAPI(title="Dashboard API", version="0.1.0")

# CORS middleware (must be first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware (protects all /api/* routes except /api/auth/*)
app.add_middleware(AuthMiddleware)

# Product Cost: /api/products, /api/products/{id}/variants, cogs_breakdown, etsy_fee_breakdown, margin_breakdown, /api/cache/clear, /api/health
register_product_cost_routes(app)

# Charts: /api/charts/total-revenue, /api/charts/revenue-by-month, ...
app.include_router(charts_router)

# Profit & Loss: /api/profit-loss/summary-table
app.include_router(profit_loss_router)

# Reports: /api/reports/bank-accounts, account-statement, account-statement/pdf
app.include_router(reports_router)

# Import: /api/import/files, upload, run-etl
app.include_router(import_router)

# Static Data: /api/static/product-catalog, /api/static/bank-transactions
app.include_router(static_data_router)
# Static Data Import: /api/static/product-catalog/upload, /api/static/bank-transactions/upload
app.include_router(static_data_import_router)
# Auth: /api/auth/me, /api/auth/verify (public, no auth required)
app.include_router(auth_router)


def _get_frontend_dist() -> Path | None:
    """
    Resolve path to frontend/dist in both dev (source tree) and PyInstaller.
    Priority:
    1) Env FRONTEND_DIST
    2) PyInstaller _MEIPASS/frontend/dist
    3) Repo-relative ../frontend/dist
    """
    env_path = os.getenv("FRONTEND_DIST")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    # PyInstaller bundle
    if getattr(sys, "_MEIPASS", None):
        p = Path(sys._MEIPASS) / "frontend" / "dist"  # type: ignore[attr-defined]
        if p.exists():
            return p

    # Source tree
    p = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if p.exists():
        return p
    return None


_FRONTEND_DIST = _get_frontend_dist()

if _FRONTEND_DIST:
    # Serve static assets (JS, CSS, images) from /assets/*
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="assets",
    )


@app.get("/")
def home():
    if _FRONTEND_DIST and (_FRONTEND_DIST / "index.html").exists():
        return FileResponse(_FRONTEND_DIST / "index.html")
    return {"message": "Dashboard API", "docs": "/docs"}


# Catch-all route for SPA: return index.html for all non-API routes
@app.get("/{full_path:path}")
def serve_spa(full_path: str, request: Request):
    """
    Serve index.html for all routes that are not API routes.
    This allows React Router to handle client-side routing.
    """
    # Don't interfere with API routes
    if full_path.startswith("api/"):
        return Response(status_code=404, content='{"detail":"Not Found"}', media_type="application/json")
    
    # Don't interfere with static assets
    if full_path.startswith("assets/"):
        return Response(status_code=404, content='{"detail":"Not Found"}', media_type="application/json")
    
    # Return index.html for all other routes (SPA routing)
    if _FRONTEND_DIST and (_FRONTEND_DIST / "index.html").exists():
        return FileResponse(_FRONTEND_DIST / "index.html")
    
    return {"message": "Dashboard API", "docs": "/docs"}


@app.get("/api/home")
def api_home():
    return {"message": "Home"}


@app.get("/api/charts")
def api_charts():
    return {"message": "Charts (data: /api/charts/total-revenue, /api/charts/revenue-by-month, ...)"}


@app.get("/api/product-cost")
def api_product_cost():
    return {"message": "Product Cost (data: /api/products)"}


@app.get("/api/profit-loss")
def api_profit_loss():
    return {"message": "Profit & Loss Statement"}


@app.get("/api/report")
def api_report():
    return {"message": "Report"}
