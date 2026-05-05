"""
Revenue by Month Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from ._streamlit_shim import st  # noqa: F401
from core.query_utils.chart_helpers import execute_chart_query, render_chart_description
from core.query_utils.query_builder import build_standard_filters


def get_revenue_by_month(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get revenue by month"""
    sql = """
    SELECT 
        dt.year || '-' || LPAD(dt.month_num::text, 2, '0') as "Month",
        ROUND(COALESCE(SUM(COALESCE(fs.item_total, 0) - COALESCE(fo.discount_amount, 0)), 0), 2) as "Revenue (USD)"
    FROM fact_order_items fs
    JOIN fact_orders fo ON fs.order_key = fo.order_key
    JOIN dim_time dt ON fo.sale_date_key = dt.date_key
    WHERE 1=1
    """
    
    filter_sql, params = build_standard_filters(start_date, end_date, customer_type, 'fs', 'dt.date_key')
    sql += filter_sql
    
    sql += """
    GROUP BY dt.year, dt.month_num
    ORDER BY dt.year, dt.month_num
    """
    
    return execute_chart_query(sql, tuple(params) if params else None)

def render_revenue_by_month_description(start_date_str, end_date_str, customer_type):
    """Render description for revenue by month chart"""
    description_content = """
    **DOANH THU THEO THÁNG (BIỂU ĐỒ CỘT) - USD**

    **SQL Query:**
    ```sql
    SELECT 
        dt.year || '-' || LPAD(dt.month_num::text, 2, '0') as "Month",
        ROUND(COALESCE(SUM(COALESCE(fs.item_total, 0) - COALESCE(fo.discount_amount, 0)), 0), 2) as "Revenue (USD)"
    FROM fact_order_items fs
    JOIN fact_orders fo ON fs.order_key = fo.order_key
    JOIN dim_time dt ON fo.sale_date_key = dt.date_key
    WHERE 1=1
    [[ AND dt.date_key >= start_date ]]
    [[ AND dt.date_key <= end_date ]]
    [[ AND customer_type filter ]]
    GROUP BY dt.year, dt.month_num
    ORDER BY dt.year, dt.month_num
    ```

    **Giải thích:**
    - **Month**: Tháng (định dạng YYYY-MM)
    - **Revenue (USD)**: Doanh thu ròng theo tháng (USD)
    - **item_total**: Tổng giá trị sản phẩm bán (từ bảng fact_order_items - Item Total trong file EtsySoldOrderItems2025-1.csv)
    - **discount_amount**: Số tiền giảm giá (từ bảng fact_order_items - Discount Amount trong file EtsySoldOrderItems2025-1.csv)

    **Kết quả**: Biểu đồ cột hiển thị doanh thu từng tháng (USD)
    """
    
    render_chart_description(
        chart_name="revenue_by_month",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
