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
import psycopg2

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


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Please configure it in your environment or `.env` file."
        )
    return url


def run_query(sql: str, params: Optional[Union[Tuple, List, dict]] = None) -> pd.DataFrame:
    """
    Run a SQL query and return a DataFrame.
    Uses PostgreSQL with psycopg2 and %s placeholders.
    """
    url = get_database_url()
    dsn = url.replace("postgresql+psycopg2://", "postgresql://") if "postgresql" in url else url
    with psycopg2.connect(dsn) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def execute_query(sql: str, params: Optional[Union[Tuple, List, dict]] = None) -> None:
    """
    Execute a SQL statement (INSERT, UPDATE, DELETE) that doesn't return data.
    Uses PostgreSQL with psycopg2 and %s placeholders.
    """
    url = get_database_url()
    dsn = url.replace("postgresql+psycopg2://", "postgresql://") if "postgresql" in url else url
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
