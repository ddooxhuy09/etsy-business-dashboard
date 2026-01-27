"""
Total Sales by Product Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import (
    execute_chart_query,
    render_chart_description
)
from utils.query_builder import build_standard_filters


def get_total_sales_by_product(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get total sales by product"""
    sql = """
    SELECT 
        CASE WHEN LENGTH(dp.title) > 30 THEN LEFT(dp.title, 27) || '...' ELSE dp.title END as "Product", 
        ROUND(COALESCE(SUM(COALESCE(fs.item_total, 0) - COALESCE(fs.discount_amount, 0)), 0), 2) as "Revenue (USD)" 
    FROM fact_sales fs 
    JOIN dim_product dp ON fs.product_key = dp.product_key 
    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
    WHERE dp.is_current = true
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.full_date')
    sql += filter_sql
    
    sql += """
    GROUP BY 1 
    ORDER BY SUM(COALESCE(fs.item_total, 0) - COALESCE(fs.discount_amount, 0)) DESC 
    LIMIT 10
    """
    
    return execute_chart_query(sql, tuple(params) if params else None)


def render_total_sales_by_product_description(start_date_str, end_date_str, customer_type):
    """Render description for total sales by product chart"""
    description_content = """
    **DOANH THU THEO SẢN PHẨM (TOP 10) - USD**

    **Công thức:** Revenue = SUM(item_total) - SUM(discount_amount) theo từng sản phẩm

    - **Product**: Tên sản phẩm (rút gọn tối đa 30 ký tự để dễ đọc)
    - **Revenue (USD)**: Doanh thu ròng của sản phẩm (USD)
    - **Lấy TOP 10 sản phẩm có doanh thu cao nhất**
    """
    
    render_chart_description(
        chart_name="total_sales_by_product",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
