"""
Query Builder Utilities
Simple helpers for building SQL queries with filters

Eliminates duplicated filter logic across 18 chart files
"""

from typing import Tuple, List, Optional


def build_customer_filter(
    customer_type: str, 
    table_alias: str = 'fs'
) -> Tuple[str, List]:
    """
    Build customer type filter SQL clause
    """
    if customer_type == 'all':
        return ("", [])
    
    if customer_type == 'new':
        condition = '= 1'
    elif customer_type == 'return':
        condition = '> 1'
    else:
        return ("", [])
    
    sql_condition = f"""
    AND {table_alias}.customer_key IN (
        SELECT customer_key 
        FROM fact_sales 
        GROUP BY customer_key 
        HAVING COUNT(DISTINCT order_key) {condition}
    )"""
    
    return (sql_condition, [])


def build_date_filter(
    start_date: Optional[str],
    end_date: Optional[str],
    date_column: str = 'dt.full_date'
) -> Tuple[str, List]:
    """
    Build date range filter SQL clause
    """
    sql = ""
    params = []
    
    if start_date:
        sql += f" AND {date_column} >= %s"
        params.append(start_date)
    
    if end_date:
        sql += f" AND {date_column} <= %s"
        params.append(end_date)
    
    return (sql, params)


def build_standard_filters(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    customer_type: str = 'all',
    table_alias: str = 'fs',
    date_column: str = 'dt.full_date'
) -> Tuple[str, List]:
    """
    Build standard date + customer type filters
    """
    all_sql = ""
    all_params = []
    
    date_sql, date_params = build_date_filter(start_date, end_date, date_column)
    all_sql += date_sql
    all_params.extend(date_params)
    
    customer_sql, customer_params = build_customer_filter(customer_type, table_alias)
    all_sql += customer_sql
    all_params.extend(customer_params)
    
    return (all_sql, all_params)
