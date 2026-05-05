"""
Revenue Comparison by Month Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from ._streamlit_shim import st  # noqa: F401
import pandas as pd
from datetime import datetime
import textwrap
from core.query_utils.chart_helpers import execute_chart_query
from core.query_utils.db_query import execute_query


def get_revenue_comparison_by_month(month1_year, month1_month, month2_year, month2_month):
    """
    Get revenue comparison between two specific months

    Args:
        month1_year: Year for first month (e.g., 2025)
        month1_month: Month number for first month (1-12)
        month2_year: Year for second month (e.g., 2024)
        month2_month: Month number for second month (1-12)

    Returns:
        DataFrame with revenue data for both months
    """

    month1_start = datetime(month1_year, month1_month, 1).date()
    if month1_month == 12:
        month1_end = datetime(month1_year + 1, 1, 1).date() - pd.Timedelta(days=1)
    else:
        month1_end = datetime(month1_year, month1_month + 1, 1).date() - pd.Timedelta(days=1)

    month2_start = datetime(month2_year, month2_month, 1).date()
    if month2_month == 12:
        month2_end = datetime(month2_year + 1, 1, 1).date() - pd.Timedelta(days=1)
    else:
        month2_end = datetime(month2_year, month2_month + 1, 1).date() - pd.Timedelta(days=1)

    sql = """
    WITH month1_daily AS (
        SELECT 
            dt.date_key as date,
            ROUND(COALESCE(SUM(COALESCE(fs.item_total, 0) - COALESCE(fo.discount_amount, 0)), 0), 2) as revenue,
            'Month 1' as month_label,
            dt.day_of_month as day_of_month
        FROM fact_order_items fs 
        JOIN fact_orders fo ON fs.order_key = fo.order_key
        JOIN dim_time dt ON fo.sale_date_key = dt.date_key
        WHERE dt.date_key >= %s AND dt.date_key <= %s
        GROUP BY dt.date_key, dt.day_of_month
    ),
    month2_daily AS (
        SELECT 
            dt.date_key as date,
            ROUND(COALESCE(SUM(COALESCE(fs.item_total, 0) - COALESCE(fo.discount_amount, 0)), 0), 2) as revenue,
            'Month 2' as month_label,
            dt.day_of_month as day_of_month
        FROM fact_order_items fs 
        JOIN fact_orders fo ON fs.order_key = fo.order_key
        JOIN dim_time dt ON fo.sale_date_key = dt.date_key
        WHERE dt.date_key >= %s AND dt.date_key <= %s
        GROUP BY dt.date_key, dt.day_of_month
    )
    SELECT 
        date as "Date",
        revenue as "Revenue (USD)",
        month_label as "Month",
        day_of_month as "Day"
    FROM month1_daily
    UNION ALL
    SELECT 
        date as "Date",
        revenue as "Revenue (USD)",
        month_label as "Month",
        day_of_month as "Day"
    FROM month2_daily
    ORDER BY "Month", "Day"
    """

    params = [
        month1_start, month1_end,
        month2_start, month2_end
    ]

    return execute_query(sql, tuple(params))


def get_month_aggregates(month_start, month_end):
    """Return aggregates for a month: orders_count, revenue, profit."""
    orders_sql = """
    SELECT COUNT(DISTINCT fs.order_key) AS orders_count
    FROM fact_order_items fs
    JOIN fact_orders fo ON fs.order_key = fo.order_key
    JOIN dim_time dt ON fo.sale_date_key = dt.date_key
    WHERE dt.date_key >= %s AND dt.date_key <= %s
    """
    orders_df = execute_query(orders_sql, (month_start, month_end))
    orders_count = int(orders_df.iloc[0, 0]) if not orders_df.empty else 0

    rev_profit_sql = """
    SELECT 
        COALESCE(SUM(COALESCE(fp.gross_amount, 0)), 0) AS revenue,
        COALESCE(SUM(COALESCE(fp.net_amount, 0)), 0)   AS profit
    FROM fact_payments fp
    JOIN dim_time dt ON fp.funds_available_date = dt.date_key
    WHERE dt.date_key >= %s AND dt.date_key <= %s
    """
    rp_df = execute_query(rev_profit_sql, (month_start, month_end))
    revenue = float(rp_df.iloc[0, 0]) if not rp_df.empty else 0.0
    profit = float(rp_df.iloc[0, 1]) if not rp_df.empty else 0.0

    return {
        "orders_count": orders_count,
        "revenue": revenue,
        "profit": profit,
    }


def get_comparison_percentages(month1_year, month1_month, month2_year, month2_month):
    """Compute Order Total %, Revenue %, Profit % for month1 vs month2."""
    m1_start = datetime(month1_year, month1_month, 1).date()
    if month1_month == 12:
        m1_end = (datetime(month1_year + 1, 1, 1) - pd.Timedelta(days=1)).date()
    else:
        m1_end = (datetime(month1_year, month1_month + 1, 1) - pd.Timedelta(days=1)).date()

    m2_start = datetime(month2_year, month2_month, 1).date()
    if month2_month == 12:
        m2_end = (datetime(month2_year + 1, 1, 1) - pd.Timedelta(days=1)).date()
    else:
        m2_end = (datetime(month2_year, month2_month + 1, 1) - pd.Timedelta(days=1)).date()

    m1 = get_month_aggregates(m1_start, m1_end)
    m2 = get_month_aggregates(m2_start, m2_end)

    def ratio_pct(a, b):
        if b and b != 0:
            return (a / b) * 100.0
        return None

    return {
        "orders_pct": ratio_pct(m1["orders_count"], m2["orders_count"]),
        "revenue_pct": ratio_pct(m1["revenue"], m2["revenue"]),
        "profit_pct": ratio_pct(m1["profit"], m2["profit"]),
        "m1": m1,
        "m2": m2,
    }


def render_revenue_comparison_by_month_description(month1_year, month1_month, month2_year, month2_month):
    """Render description for revenue comparison chart"""
    if st.session_state.get('show_revenue_comparison_by_month_description', False):
        with st.expander("📋 Revenue Comparison by Month Description", expanded=False):
            st.markdown(textwrap.dedent("""
            **SO SÁNH DOANH THU THEO NGÀY TRONG THÁNG**

            **Công thức:** Daily Revenue = SUM(item_total - discount_amount) GROUP BY date
            ...
            """))
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("❌ Close", key="close_revenue_comparison_by_month_description_btn", width='stretch'):
                    st.session_state.show_revenue_comparison_by_month_description = False
                    st.rerun()


def get_month_name(month_number):
    """Get month name from month number"""
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    return month_names[month_number - 1]
