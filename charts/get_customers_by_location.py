"""
Customers by Location Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import execute_chart_query, render_chart_description
from utils.query_builder import build_standard_filters


def get_customers_by_location(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get customers by location"""
    sql = """
    SELECT 
        dg.state_name as "State", 
        COUNT(DISTINCT fs.customer_key) as "Customers", 
        ROUND(COALESCE(SUM(COALESCE(fs.item_total, 0) - COALESCE(fs.discount_amount, 0)), 0), 2) as "Revenue (USD)" 
    FROM fact_sales fs 
    JOIN dim_geography dg ON fs.geography_key = dg.geography_key 
    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
    WHERE dg.country_name = 'United States'
    """
    
    # Use shared filter builder
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.full_date')
    sql += filter_sql
    
    sql += """
    GROUP BY 1
    ORDER BY COUNT(DISTINCT fs.customer_key) DESC 
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
