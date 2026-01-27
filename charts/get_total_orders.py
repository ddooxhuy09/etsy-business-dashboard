"""
Total Orders Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import (
    execute_chart_query,
    render_chart_description
)
from utils.query_builder import build_standard_filters


def get_total_orders(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get total orders"""
    sql = """
    SELECT COUNT(DISTINCT fs.order_key) as "Total Orders" 
    FROM fact_sales fs 
    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
    WHERE 1=1
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.full_date')
    sql += filter_sql
    
    return execute_chart_query(sql, tuple(params) if params else None)


def render_get_total_orders_description(start_date_str, end_date_str, customer_type):
    """Render description for total orders KPI"""
    description_content = """
    **TỔNG SỐ ĐƠN HÀNG**

    **Công thức:** Total Orders = COUNT(DISTINCT order_key)

    - **order_key**: Khóa duy nhất của đơn hàng (từ bảng fact_sales)
    - **COUNT(DISTINCT)**: Đếm số đơn hàng không trùng lặp
    - **Kết quả**: Tổng số đơn hàng đã bán
    """
    
    render_chart_description(
        chart_name="total_orders",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
