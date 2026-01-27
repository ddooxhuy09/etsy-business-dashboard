"""
Total Customers Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import (
    execute_chart_query,
    render_chart_description
)
from utils.query_builder import build_standard_filters


def get_total_customers(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get total customers"""
    sql = """
    SELECT COUNT(DISTINCT fs.customer_key) as "Total Customers" 
    FROM fact_sales fs 
    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
    WHERE 1=1
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.full_date')
    sql += filter_sql
    
    return execute_chart_query(sql, tuple(params) if params else None)


def render_get_total_customers_description(start_date_str, end_date_str, customer_type):
    """Render description for total customers KPI"""
    description_content = """
    **TỔNG SỐ KHÁCH HÀNG**

    **Công thức:** Total Customers = COUNT(DISTINCT customer_key)

    - **customer_key**: Khóa duy nhất của khách hàng (từ bảng fact_sales)
    - **COUNT(DISTINCT)**: Đếm số khách hàng không trùng lặp
    - **Kết quả**: Tổng số khách hàng đã mua hàng
    """
    
    render_chart_description(
        chart_name="total_customers",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
