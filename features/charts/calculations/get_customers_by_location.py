"""
Customers by Location Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from ._streamlit_shim import st  # noqa: F401
from core.query_utils.chart_helpers import execute_chart_query, render_chart_description
from core.query_utils.query_builder import build_standard_filters


def get_customers_by_location(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get customers by location"""
    sql = """
    SELECT 
        fo.shipping_state as "State", 
        COUNT(DISTINCT fo.customer_key) as "Customers", 
        ROUND(COALESCE(SUM(COALESCE(fs.item_total, 0) - COALESCE(fo.discount_amount, 0)), 0), 2) as "Revenue (USD)" 
    FROM fact_order_items fs 
    JOIN fact_orders fo ON fs.order_key = fo.order_key 
    JOIN dim_time dt ON fo.sale_date_key = dt.date_key
    WHERE fo.shipping_country = 'United States'
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.date_key')
    sql += filter_sql
    
    sql += """
    GROUP BY 1
    ORDER BY COUNT(DISTINCT fo.customer_key) DESC 
    LIMIT 12
    """
    
    return execute_chart_query(sql, tuple(params) if params else None)

def render_customers_by_location_description(start_date_str, end_date_str, customer_type):
    """Render description for customers by location chart"""
    description_content = """
    **KHÁCH HÀNG THEO TIỂU BANG (US) - USD**

    - **State**: Tên tiểu bang
    - **Customers**: Số khách hàng duy nhất
    - **Revenue (USD)**: Doanh thu ròng (USD)
    - **Lưu ý**: GROUP BY cột hiển thị để tăng tương thích
    """
    
    render_chart_description(
        chart_name="customers_by_location",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
