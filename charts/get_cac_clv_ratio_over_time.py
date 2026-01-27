"""
CAC/CLV Ratio Over Time Chart - REFACTORED
Uses shared utilities to eliminate code duplication
"""
from charts._streamlit_shim import st  # noqa: F401
import pandas as pd
import textwrap
from utils.db_query import execute_query


def get_cac_clv_ratio_over_time(start_date: str = None, end_date: str = None, lifespan_months: int = 12) -> pd.DataFrame:
    """
    Return CAC, CLV and CLV/CAC by month between start_date and end_date.

    Args:
        start_date: 'YYYY-MM-DD' or None
        end_date: 'YYYY-MM-DD' or None
        lifespan_months: Lifespan used in CLV computation
    """
    sql = """
    WITH bounds AS (
        SELECT 
            COALESCE(%s::date, MIN(dt.full_date)) AS start_date,
            COALESCE(%s::date, MAX(dt.full_date)) AS end_date
        FROM dim_time dt
    ), months AS (
        SELECT ym.year, ym.month,
               MIN(dt.full_date) AS month_start,
               MAX(dt.full_date) AS month_end
        FROM (
            SELECT DISTINCT dt.year, dt.month
            FROM fact_sales fs
            JOIN dim_time dt ON fs.sale_date_key = dt.time_key
            JOIN bounds b ON dt.full_date BETWEEN b.start_date AND b.end_date
            UNION
            SELECT DISTINCT dt.year, dt.month
            FROM fact_payments fp
            JOIN dim_time dt ON fp.payment_date_key = dt.time_key
            JOIN bounds b ON dt.full_date BETWEEN b.start_date AND b.end_date
            UNION
            SELECT DISTINCT dt.year, dt.month
            FROM fact_financial_transactions fft
            JOIN dim_time dt ON fft.transaction_date_key = dt.time_key
            JOIN bounds b ON dt.full_date BETWEEN b.start_date AND b.end_date
        ) ym
        JOIN dim_time dt ON dt.year = ym.year AND dt.month = ym.month
        GROUP BY ym.year, ym.month
        ORDER BY ym.year, ym.month
    )
    SELECT 
        m.year || '-' || LPAD(m.month::text, 2, '0') AS "Month",
        ROUND(
          COALESCE((
            SELECT SUM(COALESCE(fft.fees_and_taxes, 0))
            FROM fact_financial_transactions fft
            JOIN dim_time dt1 ON fft.transaction_date_key = dt1.time_key
            WHERE fft.transaction_type = 'Marketing'
              AND dt1.full_date BETWEEN m.month_start AND m.month_end
          ), 0) 
          / NULLIF((
            SELECT COUNT(DISTINCT fs.customer_key)
            FROM fact_sales fs
            JOIN dim_time dt2 ON fs.sale_date_key = dt2.time_key
            WHERE fs.customer_key IN (
                SELECT customer_key
                FROM fact_sales
                GROUP BY customer_key
                HAVING COUNT(DISTINCT order_key) = 1
            )
              AND dt2.full_date BETWEEN m.month_start AND m.month_end
          ), 0), 2) AS "CAC (USD)",
        ROUND((
          (
            (SELECT SUM(COALESCE(fs.item_total, 0))
             FROM fact_sales fs 
             JOIN dim_time dt ON fs.sale_date_key = dt.time_key
             WHERE dt.full_date BETWEEN m.month_start AND m.month_end) * 1.0 /
            NULLIF((SELECT COUNT(DISTINCT fs.customer_key) 
                    FROM fact_sales fs 
                    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
                    WHERE dt.full_date BETWEEN m.month_start AND m.month_end), 0)
          ) * %s
          -
          (
            (SELECT 
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
             WHERE dt.full_date BETWEEN m.month_start AND m.month_end
            ) * 1.0 /
            NULLIF((SELECT COUNT(DISTINCT fs.customer_key) 
                    FROM fact_sales fs 
                    JOIN dim_time dt ON fs.sale_date_key = dt.time_key
                    WHERE dt.full_date BETWEEN m.month_start AND m.month_end), 0)
          )
        ), 2) AS "CLV (USD)"
    FROM months m
    ORDER BY 1
    """

    df = execute_query(sql, (start_date, end_date, lifespan_months))
    if df is None or df.empty:
        return pd.DataFrame(columns=["Month", "CAC (USD)", "CLV (USD)", "CLV/CAC (x)"])

    # Compute ratio (x)
    df["CLV/CAC (x)"] = df.apply(lambda r: (r["CLV (USD)"] / r["CAC (USD)"]) if r["CAC (USD)"] and r["CAC (USD)"] != 0 else None, axis=1)
    return df


def render_cac_clv_ratio_over_time_description(start_date_str: str, end_date_str: str):
    """Render description for CAC/CLV ratio chart."""
    if st.session_state.get('show_cac_clv_ratio_description', False):
        with st.expander("📋 CAC, CLV and CLV/CAC Ratio Description", expanded=False):
            st.markdown(textwrap.dedent("""
            - CAC (USD) = Tổng Marketing fees / Số khách hàng mới (1 đơn duy nhất) trong tháng
            - CLV (USD) ≈ ARPU tháng × Lifespan − Chi phí trung bình/khách hàng trong tháng
            - CLV/CAC (%) = (CLV / CAC) × 100
            """))
            st.markdown(textwrap.dedent(f"""
            **Filters Applied:**

            - From Date: {start_date_str or 'All time'}
            - To Date: {end_date_str or 'Present'}
            """))
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("❌ Close", key="close_cac_clv_ratio_description_btn", width='stretch'):
                    st.session_state.show_cac_clv_ratio_description = False
                    st.rerun()
