"""
Database layer for the dashboard.

Database connection is configured via environment variables (typically loaded from `.env`).
Required:
- DATABASE_URL (PostgreSQL connection string)
"""
import os
from typing import Optional, Union, Tuple, List
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

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

# Global SQLAlchemy engine (lazy initialization)
_engine = None


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Please configure it in your environment or `.env` file."
        )
    return url


def _get_engine():
    """Get or create SQLAlchemy engine (singleton pattern)."""
    global _engine
    if _engine is None:
        url = get_database_url()
        # Ensure we use postgresql:// format for SQLAlchemy
        if "postgresql+psycopg2://" in url:
            url = url.replace("postgresql+psycopg2://", "postgresql://")
        _engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)
    return _engine


def _escape_percent(sql: str) -> str:
    """
    Escape literal % to %% for psycopg2, while keeping %s placeholders.
    e.g. "Retention Rate (%)" → "Retention Rate (%%)" but "%s" stays "%s".
    """
    return sql.replace('%', '%%').replace('%%s', '%s')


def run_query(sql: str, params: Optional[Union[Tuple, List, dict]] = None) -> pd.DataFrame:
    """
    Run a SQL query and return a DataFrame.
    Uses psycopg2 cursor directly for %s-style params (most reliable).
    Falls back to SQLAlchemy text() only for dict/named params.
    """
    engine = _get_engine()

    # Normalize params
    if params is not None:
        if isinstance(params, (list, tuple)) and len(params) == 0:
            params = None
        elif isinstance(params, dict) and len(params) == 0:
            params = None

    # Dict params → SQLAlchemy text() with :name style
    if params and isinstance(params, dict):
        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            if result.returns_rows:
                return pd.DataFrame(result.fetchall(), columns=list(result.keys()))
            return pd.DataFrame()

    # Positional params → psycopg2 cursor.execute(sql, params) directly
    if isinstance(params, list):
        params = tuple(params)

    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        if params:
            cursor.execute(_escape_percent(sql), params)
        else:
            cursor.execute(sql)
        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return pd.DataFrame(rows, columns=columns)
        return pd.DataFrame()
    finally:
        raw_conn.close()


def execute_query(sql: str, params: Optional[Union[Tuple, List, dict]] = None) -> None:
    """
    Execute a SQL statement (INSERT, UPDATE, DELETE) that doesn't return data.
    """
    engine = _get_engine()

    if params and isinstance(params, dict):
        with engine.connect() as conn:
            conn.execute(text(sql), params)
            conn.commit()
        return

    if isinstance(params, list):
        params = tuple(params)

    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        if params:
            cursor.execute(_escape_percent(sql), params)
        else:
            cursor.execute(sql)
        raw_conn.commit()
        cursor.close()
    finally:
        raw_conn.close()
