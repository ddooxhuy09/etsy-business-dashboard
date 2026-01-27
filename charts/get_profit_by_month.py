"""
Profit by Month Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import (
    execute_chart_query,
    render_chart_description
)
from utils.query_builder import build_date_filter


def get_profit_by_month(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get profit by month based on fact_payments.net_amount"""
    sql = """
    SELECT 
        dt.year || '-' || LPAD(dt.month::text, 2, '0') as "Month",
        ROUND(COALESCE(SUM(COALESCE(fp.net_amount, 0)), 0), 2) as "Profit (USD)"
    FROM fact_payments fp
    JOIN dim_time dt ON fp.payment_date_key = dt.time_key
    WHERE 1=1
    """

    filter_sql, params = build_date_filter(start_date, end_date, 'dt.full_date')
    sql += filter_sql

    sql += """
    GROUP BY dt.year, dt.month
    ORDER BY dt.year, dt.month
    """

    return execute_chart_query(sql, tuple(params) if params else None)


def render_profit_by_month_description(start_date_str, end_date_str, customer_type):
    """Render description for profit by month chart"""
    description_content = """
    **LỢI NHUẬN THEO THÁNG (USD)**

    - **Công thức:** Profit (USD) = SUM(fact_payments.net_amount là cột Net Amount trong file EtsyDirectCheckoutPayments2025-1.csv)
    - Sử dụng ngày theo `payment_date_key` trong bảng `fact_payments`
    - Nhóm theo tháng để tổng hợp lợi nhuận theo từng tháng
    """
    
    render_chart_description(
        chart_name="profit_by_month",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
