"""
Average Order Value Over Time Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from ._streamlit_shim import st  # noqa: F401
from core.query_utils.chart_helpers import execute_chart_query, render_chart_description
from core.query_utils.query_builder import build_standard_filters


def get_average_order_value_over_time(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get average order value over time"""
    sql = """
    SELECT 
        dt.date_key as "Date", 
        ROUND(
            SUM(COALESCE(fs.item_total, 0) - COALESCE(fo.discount_amount, 0)) 
            / NULLIF(COUNT(DISTINCT fs.order_key), 0),
        2) as "AOV (USD)" 
    FROM fact_order_items fs 
    JOIN fact_orders fo ON fs.order_key = fo.order_key
    JOIN dim_time dt ON fo.sale_date_key = dt.date_key
    WHERE 1=1
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.date_key')
    sql += filter_sql
    
    sql += """
    GROUP BY dt.date_key 
    ORDER BY dt.date_key
    """
    
    return execute_chart_query(sql, tuple(params) if params else None)

def render_average_order_value_over_time_description(start_date_str, end_date_str, customer_type):
    """Render description for average order value over time chart"""
    description_content = """
    **GIÁ TRỊ ĐƠN HÀNG TRUNG BÌNH THEO THỜI GIAN (AOV) - USD**

    **Công thức mỗi ngày:** AOV = (SUM(item_total) - SUM(discount_amount)) / COUNT(DISTINCT order_key)

    - **item_total**: Tổng giá trị sản phẩm bán (từ bảng fact_order_items - Item Total trong file EtsySoldOrderItems2025-1.csv)
    - **discount_amount**: Số tiền giảm giá (từ bảng fact_order_items - Discount Amount trong file EtsySoldOrderItems2025-1.csv)
    - **COUNT(DISTINCT order_key)**: Số đơn hàng trong ngày
    - **Bảo vệ lỗi**: dùng NULLIF(..., 0) để tránh chia cho 0 khi không có đơn hàng
    - **Kết quả**: Giá trị đơn hàng trung bình theo ngày (USD)
    """
    
    render_chart_description(
        chart_name="average_order_value_over_time",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
