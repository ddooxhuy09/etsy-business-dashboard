"""
Total Orders by Month Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import (
    execute_chart_query,
    render_chart_description
)
from utils.query_builder import build_standard_filters


def get_total_orders_by_month(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get total orders by month"""
    sql = """
    SELECT 
        dt.year || '-' || LPAD(dt.month::text, 2, '0') as "Month",
        COUNT(DISTINCT fs.order_key) as "Orders" 
    FROM fact_sales fs 
    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
    WHERE 1=1
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.full_date')
    sql += filter_sql
    
    sql += """
    GROUP BY dt.year, dt.month 
    ORDER BY dt.year, dt.month
    """
    
    return execute_chart_query(sql, tuple(params) if params else None)


def render_total_orders_by_month_description(start_date_str, end_date_str, customer_type):
    """Render description for total orders by month chart"""
    description_content = """
    **TỔNG SỐ ĐƠN HÀNG THEO THÁNG (BIỂU ĐỒ CỘT)**

    **Công thức:** Orders = COUNT(DISTINCT order_key) GROUP BY month

    - **Month**: Tháng (định dạng YYYY-MM)
    - **Orders**: Tổng số đơn hàng theo tháng
    - **order_key**: Khóa duy nhất của đơn hàng (từ bảng fact_sales)
    - **COUNT(DISTINCT)**: Đếm số đơn hàng không trùng lặp
    - **Kết quả**: Biểu đồ cột hiển thị số đơn hàng từng tháng

    Chart này giúp so sánh số lượng đơn hàng giữa các tháng và xác định tháng có nhiều đơn hàng nhất.
    """
    
    render_chart_description(
        chart_name="total_orders_by_month",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
