"""
Customer Retention Rate Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from ._streamlit_shim import st  # noqa: F401
from core.query_utils.chart_helpers import (
    execute_chart_query,
    render_chart_description
)
from core.query_utils.query_builder import build_standard_filters


def get_customer_retention_rate(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get customer retention rate"""
    sql = """
    SELECT ROUND(
        COUNT(DISTINCT CASE WHEN order_count > 1 THEN fo.customer_key END) * 100.0 / NULLIF(COUNT(DISTINCT fo.customer_key), 0),
    2) AS "Retention Rate (%)"
    FROM fact_order_items fs
    JOIN fact_orders fo ON fs.order_key = fo.order_key
    JOIN (SELECT fo2.customer_key, COUNT(DISTINCT fo2.order_key) AS order_count FROM fact_orders fo2 GROUP BY 1) co ON fo.customer_key = co.customer_key
    JOIN dim_time dt ON fo.sale_date_key = dt.date_key
    WHERE 1=1
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.date_key')
    sql += filter_sql
    
    return execute_chart_query(sql, tuple(params) if params else None)


def render_customer_retention_rate_description(start_date_str, end_date_str, customer_type):
    """Render description for customer retention rate chart"""
    description_content = """
    **TỶ LỆ GIỮ CHÂN KHÁCH HÀNG**

    - **Công thức**: Retention Rate = (Khách hàng quay lại / Tổng khách hàng) × 100
    - **Khách hàng quay lại**: Customer có > 1 đơn hàng (order_count > 1)
    - **Tổng khách hàng**: Tất cả khách hàng trong kỳ (có thể lọc theo loại khách hàng)
    - **Theo dõi khả năng giữ chân khách hàng**
    - **Chỉ số quan trọng cho CLV và chiến lược marketing**
    """
    
    render_chart_description(
        chart_name="retention_rate",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
