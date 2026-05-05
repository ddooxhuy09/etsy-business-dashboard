"""
Total Revenue Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from ._streamlit_shim import st  # noqa: F401
from core.query_utils.chart_helpers import (
    execute_chart_query,
    render_chart_description,
    get_customer_type_display
)
from core.query_utils.query_builder import build_standard_filters


def get_total_revenue(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get total revenue"""
    sql = """
    SELECT ROUND(COALESCE(SUM(COALESCE(fs.item_total, 0) - COALESCE(fo.discount_amount, 0)), 0), 2) as "Total Revenue (USD)" 
    FROM fact_order_items fs 
    JOIN fact_orders fo ON fs.order_key = fo.order_key
    JOIN dim_time dt ON fo.sale_date_key = dt.date_key
    WHERE 1=1
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.date_key')
    sql += filter_sql
    
    return execute_chart_query(sql, tuple(params) if params else None)


def render_get_total_revenue_description(start_date_str, end_date_str, customer_type):
    """Render description for total revenue KPI"""
    description_content = """
    **TỔNG DOANH THU (USD)**

    **Công thức:** Total Revenue = SUM(item_total) - SUM(discount_amount)

    - **item_total**: Tổng giá trị sản phẩm bán (từ bảng fact_order_items - Item Total trong file EtsySoldOrderItems2025-1.csv)
    - **discount_amount**: Số tiền giảm giá (từ bảng fact_order_items - Discount Amount trong file EtsySoldOrderItems2025-1.csv)
    - **Kết quả**: Doanh thu thực tế sau khi trừ giảm giá (USD)
    """
    
    render_chart_description(
        chart_name="total_revenue",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
