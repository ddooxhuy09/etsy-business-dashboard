"""
Average Order Value Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import (
    execute_chart_query,
    render_chart_description
)
from utils.query_builder import build_standard_filters


def get_average_order_value(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get average order value"""
    sql = """
    SELECT ROUND(SUM(COALESCE(fs.item_total, 0) - COALESCE(fs.discount_amount, 0)) / NULLIF(COUNT(DISTINCT fs.order_key), 0), 2) as "AOV (USD)" 
    FROM fact_sales fs 
    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
    WHERE 1=1
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.full_date')
    sql += filter_sql
    
    return execute_chart_query(sql, tuple(params) if params else None)


def render_get_average_order_value_description(start_date_str, end_date_str, customer_type):
    """Render description for average order value KPI"""
    description_content = """
    **GIÁ TRỊ ĐƠN HÀNG TRUNG BÌNH (AOV) - USD**

    **Công thức:** AOV = Total Revenue / Total Orders

    - **Total Revenue**: Tổng doanh thu (SUM(item_total) - SUM(discount_amount))
    - **Total Orders**: Tổng số đơn hàng (COUNT(DISTINCT order_key))
    - **Kết quả**: Giá trị trung bình mỗi đơn hàng (USD)
    """
    
    render_chart_description(
        chart_name="average_order_value",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
