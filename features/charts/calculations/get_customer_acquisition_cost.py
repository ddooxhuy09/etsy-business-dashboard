"""
Customer Acquisition Cost Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from ._streamlit_shim import st  # noqa: F401
from core.query_utils.chart_helpers import (
    execute_chart_query,
    render_chart_description
)


def get_customer_acquisition_cost(start_date: str = None, end_date: str = None):
    """Get customer acquisition cost"""
    sql = """
    SELECT ROUND(
        ABS(
            COALESCE((
                SELECT SUM(COALESCE(fft.fees_and_taxes, 0))
                FROM fact_statement fft
                JOIN dim_time dt1 ON fft.entry_date = dt1.date_key
                WHERE fft.entry_type = 'Marketing'
                AND dt1.date_key >= %s::date AND dt1.date_key <= %s::date
            ), 0)
        )
        /
        NULLIF((
            SELECT COUNT(DISTINCT fo2.customer_key)
            FROM fact_order_items fs2
            JOIN fact_orders fo2 ON fs2.order_key = fo2.order_key
            JOIN dim_time dt2 ON fo2.sale_date_key = dt2.date_key
            WHERE fo2.customer_key IN (
                SELECT fo_sub.customer_key
                FROM fact_orders fo_sub
                GROUP BY fo_sub.customer_key
                HAVING COUNT(DISTINCT fo_sub.order_key) = 1
            )
            AND dt2.date_key >= %s::date AND dt2.date_key <= %s::date
        ), 0)
    , 2) AS "CAC (USD)"
    """
    
    s = start_date or '2000-01-01'
    e = end_date or '2099-12-31'
    params = [s, e, s, e]
    
    return execute_chart_query(sql, tuple(params))


def render_customer_acquisition_cost_description(start_date_str, end_date_str, customer_type):
    """Render description for customer acquisition cost chart"""
    description_content = """
    **CHI PHÍ THU HÚT KHÁCH HÀNG (CAC) - USD**

    **Công thức:** CAC = Marketing Spend / New Customers

    - **Marketing Spend**: Tổng chi phí marketing (SUM(fees_and_taxes) từ fact_statement WHERE entry_type = 'Marketing' - Fees and Taxes trong file etsy_statement_2025_1.csv)
    - **New Customers**: Số khách hàng mới (COUNT(DISTINCT customer_key) WHERE COUNT(order_key) = 1)
    - **Kết quả**: Chi phí trung bình để thu hút 1 khách hàng mới (USD)

    Chỉ số này giúp đánh giá hiệu quả của các chiến dịch marketing.
    """
    
    render_chart_description(
        chart_name="customer_acquisition_cost",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
