"""
Customer Lifetime Value Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
from utils.chart_helpers import execute_chart_query, render_chart_description
from utils.query_builder import build_customer_filter


def get_customer_lifetime_value(start_date: str = None, end_date: str = None, customer_type: str = 'all', customer_lifespan_months: int = 12):
    """Get customer lifetime value"""
    s = start_date or '2000-01-01'
    e = end_date or '2099-12-31'
    cust_sql, _ = build_customer_filter(customer_type, 'fs')
    date_cond = " AND dt.full_date >= %s::date AND dt.full_date <= %s::date"
    sql = """
    SELECT ROUND(
        (
            -- Average Revenue per Customer
            (SELECT SUM(COALESCE(fs.item_total, 0))
             FROM fact_sales fs
             JOIN dim_time dt ON fs.sale_date_key = dt.time_key
             WHERE 1=1""" + date_cond + cust_sql + """) * 1.0 /
            NULLIF((SELECT COUNT(DISTINCT fs.customer_key)
                    FROM fact_sales fs
                    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
                    WHERE 1=1""" + date_cond + cust_sql + """), 0)
            *
            -- Customer Lifespan
            %s
            -
            -- Total Costs of Serving the Customer
            (
                SELECT
                    SUM(COALESCE(fp.fees, 0)) +
                    SUM(COALESCE(fp.posted_fees, 0)) +
                    SUM(COALESCE(fp.adjusted_fees, 0)) +
                    SUM(COALESCE(dim_order.card_processing_fees, 0)) +
                    SUM(COALESCE(dim_order.adjusted_card_processing_fees, 0)) +
                    SUM(COALESCE(fs.discount_amount, 0)) +
                    SUM(COALESCE(fs.shipping_discount, 0))
                FROM fact_sales fs
                JOIN fact_payments fp ON fs.order_key = fp.order_key
                JOIN dim_order ON fs.order_key = dim_order.order_key
                JOIN dim_time dt ON fs.sale_date_key = dt.time_key
                WHERE 1=1""" + date_cond + cust_sql + """
            ) * 1.0 /
            NULLIF((SELECT COUNT(DISTINCT fs.customer_key)
                    FROM fact_sales fs
                    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
                    WHERE 1=1""" + date_cond + cust_sql + """), 0)
        )
    , 2) AS "CLV (USD)"
    """
    params = [s, e, s, e, customer_lifespan_months, s, e, s, e]
    
    return execute_chart_query(sql, tuple(params))


def render_customer_lifetime_value_description(start_date_str, end_date_str, customer_type):
    """Render description for customer lifetime value chart"""
    description_content = """
    **GIÁ TRỊ KHÁCH HÀNG TRỌN ĐỜI (CLV) - USD**

    **Công thức:** CLV = (Average Revenue per Customer × Customer Lifespan) − Total Costs of Serving the Customer

    - **Average Revenue per Customer**: Doanh thu trung bình mỗi khách hàng
    - **Customer Lifespan**: Tuổi thọ khách hàng (có thể điều chỉnh qua filter customer_lifespan_months, mặc định 12 tháng)
    - **Total Costs of Serving**: Tổng chi phí phục vụ khách hàng bao gồm:
      - fees, posted_fees, adjusted_fees (từ fact_payments) (Fees, Posted Fees, Adjusted Fees trong file EtsyDirectCheckoutPayments2025-1.csv)
      - card_processing_fees, adjusted_card_processing_fees (từ dim_order) (Card Processing Fees, Adjusted Card Processing Fees trong file EtsySoldOrders2025-1.csv)
      - discount_amount, shipping_discount (từ fact_sales) (Discount Amount, Shipping Discount trong file EtsySoldOrderItems2025-1.csv)

    Chỉ số này cho thấy lợi nhuận thực tế từ mỗi khách hàng trong suốt vòng đời (USD).
    Có thể điều chỉnh Customer Lifespan theo nhu cầu phân tích (theo ngày, tháng, năm).
    """
    
    render_chart_description(
        chart_name="customer_lifetime_value",
        description_content=description_content,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        customer_type=customer_type
    )
