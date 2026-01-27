"""
New vs Returning Customer Sales Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import (
    execute_chart_query,
    render_chart_description
)
from utils.query_builder import build_standard_filters


def get_new_vs_returning_customer_sales(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get new vs returning customer sales"""
    sql = """
    SELECT 
        CASE WHEN customer_orders.order_count = 1 THEN 'New Customers' ELSE 'Returning Customers' END as "Customer Type",
        ROUND(SUM(COALESCE(fs.item_total, 0) - COALESCE(fs.discount_amount, 0)), 2) as "Revenue (USD)" 
    FROM fact_sales fs 
    JOIN dim_time dtime ON fs.sale_date_key = dtime.time_key
    JOIN (
        SELECT customer_key, COUNT(DISTINCT order_key) as order_count 
        FROM fact_sales 
        GROUP BY customer_key
    ) customer_orders ON fs.customer_key = customer_orders.customer_key
    WHERE 1=1
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dtime.full_date')
    sql += filter_sql
    
    sql += """
    GROUP BY 1
    ORDER BY SUM(COALESCE(fs.item_total, 0) - COALESCE(fs.discount_amount, 0)) DESC
    """
    
    return execute_chart_query(sql, tuple(params) if params else None)


def render_new_vs_returning_customer_sales_description(start_date_str, end_date_str, customer_type):
    """Render description for new vs returning customer sales chart"""
    description_content = """
    **DOANH THU: KHÁCH HÀNG MỚI vs. KHÁCH HÀNG QUAY LẠI (USD)**

    **Phân nhóm theo kiểu khách hàng:**
    - **New Customers**: Khách có đúng 1 đơn hàng (order_count = 1)
    - **Returning Customers**: Khách có > 1 đơn hàng

    **Chỉ số hiển thị:**
    - **Revenue (USD)** = SUM(item_total) - SUM(discount_amount)
    """
    
    render_chart_description(
        chart_name="new_vs_returning_customer_sales",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
