"""
Thin adapter for chart SQL execution. Uses api.db.run_query (PostgreSQL).
Replace for src.analytics.utils.postgres_connection in dashboard charts.
"""
from api.db import run_query


def execute_query(sql: str, params: tuple = None):
    return run_query(sql, params)


def execute_query_with_cache(sql: str, params: tuple = None, ttl: int = 300, timeout: int = 30, use_pool: bool = True):
    return run_query(sql, params)
