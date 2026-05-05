"""
Customer Lifetime Value (LTV) Chart
Formula: LTV = AOV × Average Purchase Frequency Rate
- AOV = Total Revenue / Total Orders
- Avg Purchase Frequency = Total Orders / Total Unique Customers
- All calculated within the same time period (30, 60, or 90 days)
"""
from core.query_utils.chart_helpers import execute_chart_query


def get_customer_lifetime_value(start_date: str = None, end_date: str = None,
                                customer_type: str = 'all', period_days: int = 30):
    """
    Calculate LTV = AOV × Avg Purchase Frequency for a given lookback window.

    Args:
        start_date / end_date: ignored when period_days is used;
            the window is [end_ref - period_days, end_ref] where
            end_ref = end_date or the latest sale date.
        customer_type: 'all' | 'new' | 'return'
        period_days: lookback window in days (30, 60, or 90)
    """
    if customer_type == 'new':
        cust_filter = """
            AND fo.customer_key IN (
                SELECT fo_sub.customer_key FROM fact_orders fo_sub
                GROUP BY fo_sub.customer_key HAVING COUNT(DISTINCT fo_sub.order_key) = 1
            )"""
    elif customer_type == 'return':
        cust_filter = """
            AND fo.customer_key IN (
                SELECT fo_sub.customer_key FROM fact_orders fo_sub
                GROUP BY fo_sub.customer_key HAVING COUNT(DISTINCT fo_sub.order_key) > 1
            )"""
    else:
        cust_filter = ""

    sql = f"""
    WITH date_range AS (
        SELECT
            COALESCE(%s::date, (SELECT MAX(dt.date_key) FROM fact_order_items fs2 JOIN fact_orders fo2 ON fs2.order_key = fo2.order_key JOIN dim_time dt ON fo2.sale_date_key = dt.date_key))
                AS end_ref
    ),
    period AS (
        SELECT
            (end_ref - INTERVAL '1 day' * %s)::date AS period_start,
            end_ref AS period_end
        FROM date_range
    )
    SELECT
        ROUND(
            COALESCE(SUM(fs.item_total), 0)::numeric
            / NULLIF(COUNT(DISTINCT fs.order_key), 0)
        , 2) AS "AOV (USD)",

        ROUND(
            COUNT(DISTINCT fs.order_key)::numeric
            / NULLIF(COUNT(DISTINCT fo.customer_key), 0)
        , 2) AS "Avg Purchase Frequency",

        ROUND(
            (COALESCE(SUM(fs.item_total), 0)::numeric / NULLIF(COUNT(DISTINCT fs.order_key), 0))
            *
            (COUNT(DISTINCT fs.order_key)::numeric / NULLIF(COUNT(DISTINCT fo.customer_key), 0))
        , 2) AS "LTV (USD)"

    FROM fact_order_items fs
    JOIN fact_orders fo ON fs.order_key = fo.order_key
    JOIN dim_time dt ON fo.sale_date_key = dt.date_key
    CROSS JOIN period p
    WHERE dt.date_key BETWEEN p.period_start AND p.period_end
    {cust_filter}
    """

    params = (end_date, period_days)
    return execute_chart_query(sql, params)
