"""
Customer Acquisition Cost Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import (
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
                FROM fact_financial_transactions fft
                JOIN dim_time dt1 ON fft.transaction_date_key = dt1.time_key
                WHERE fft.transaction_type = 'Marketing'
                AND dt1.full_date >= %s::date AND dt1.full_date <= %s::date
            ), 0)
        )
        /
        NULLIF((
            SELECT COUNT(DISTINCT fs.customer_key)
            FROM fact_sales fs
            JOIN dim_time dt2 ON fs.sale_date_key = dt2.time_key
            WHERE fs.customer_key IN (
                SELECT customer_key
                FROM fact_sales
                GROUP BY customer_key
                HAVING COUNT(DISTINCT order_key) = 1
            )
            AND dt2.full_date >= %s::date AND dt2.full_date <= %s::date
        ), 0)
    , 2) AS "CAC (USD)"
    """
    
    # Use provided dates or wide default (all data) when null
    s = start_date or '2000-01-01'
    e = end_date or '2099-12-31'
    params = [s, e, s, e]
    
    return execute_chart_query(sql, tuple(params))


def render_customer_acquisition_cost_description(start_date_str, end_date_str, customer_type):
    """Render description for customer acquisition cost chart"""
    description_content = """
    **CHI PHÍ THU HÚT KHÁCH HÀNG (CAC) - USD**

    **Công thức:** CAC = Marketing Spend / New Customers

    - **Marketing Spend**: Tổng chi phí marketing (SUM(fees_and_taxes) từ fact_financial_transactions WHERE transaction_type = 'Marketing' - Fees and Taxes trong file etsy_statement_2025_1.csv)
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
