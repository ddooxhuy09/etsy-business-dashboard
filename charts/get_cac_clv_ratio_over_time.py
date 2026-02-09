"""
CAC/LTV Ratio Over Time Chart
LTV = AOV × Avg Purchase Frequency
CAC = Marketing fees / New customers (per month)
Shows 3 ratio lines: LTV(30d)/CAC, LTV(60d)/CAC, LTV(90d)/CAC
"""
from charts._streamlit_shim import st  # noqa: F401
import pandas as pd
import textwrap
from utils.db_query import execute_query


def get_cac_clv_ratio_over_time(start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Return CAC, LTV(30d/60d/90d) and LTV/CAC ratios by month.

    For each month:
    - CAC = |Marketing fees| / New customers in that month
    - LTV(Xd) = AOV × Freq using data from the last X days ending at month_end
    """
    sql = """
    WITH bounds AS (
        SELECT
            COALESCE(CAST(%s AS date), MIN(dt.full_date)) AS start_date,
            COALESCE(CAST(%s AS date), MAX(dt.full_date)) AS end_date
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

        -- CAC = |Marketing fees| / New customers
        ROUND(
          ABS(
            COALESCE((
              SELECT SUM(COALESCE(fft.fees_and_taxes, 0))
              FROM fact_financial_transactions fft
              JOIN dim_time dt1 ON fft.transaction_date_key = dt1.time_key
              WHERE fft.transaction_type = 'Marketing'
                AND dt1.full_date BETWEEN m.month_start AND m.month_end
            ), 0)
          )
          / NULLIF((
            SELECT COUNT(DISTINCT fs2.customer_key)
            FROM fact_sales fs2
            JOIN dim_time dt2 ON fs2.sale_date_key = dt2.time_key
            WHERE fs2.customer_key IN (
                SELECT customer_key
                FROM fact_sales
                GROUP BY customer_key
                HAVING COUNT(DISTINCT order_key) = 1
            )
              AND dt2.full_date BETWEEN m.month_start AND m.month_end
          ), 0), 2) AS "CAC (USD)",

        -- LTV 30d: AOV × Freq using last 30 days ending at month_end
        (SELECT ROUND(
            (COALESCE(SUM(fs3.item_total), 0)::numeric / NULLIF(COUNT(DISTINCT fs3.order_key), 0))
            *
            (COUNT(DISTINCT fs3.order_key)::numeric / NULLIF(COUNT(DISTINCT fs3.customer_key), 0))
        , 2)
        FROM fact_sales fs3
        JOIN dim_time dt3 ON fs3.sale_date_key = dt3.time_key
        WHERE dt3.full_date BETWEEN (m.month_end - INTERVAL '29 days')::date AND m.month_end
        ) AS "LTV 30d (USD)",

        -- LTV 60d
        (SELECT ROUND(
            (COALESCE(SUM(fs4.item_total), 0)::numeric / NULLIF(COUNT(DISTINCT fs4.order_key), 0))
            *
            (COUNT(DISTINCT fs4.order_key)::numeric / NULLIF(COUNT(DISTINCT fs4.customer_key), 0))
        , 2)
        FROM fact_sales fs4
        JOIN dim_time dt4 ON fs4.sale_date_key = dt4.time_key
        WHERE dt4.full_date BETWEEN (m.month_end - INTERVAL '59 days')::date AND m.month_end
        ) AS "LTV 60d (USD)",

        -- LTV 90d
        (SELECT ROUND(
            (COALESCE(SUM(fs5.item_total), 0)::numeric / NULLIF(COUNT(DISTINCT fs5.order_key), 0))
            *
            (COUNT(DISTINCT fs5.order_key)::numeric / NULLIF(COUNT(DISTINCT fs5.customer_key), 0))
        , 2)
        FROM fact_sales fs5
        JOIN dim_time dt5 ON fs5.sale_date_key = dt5.time_key
        WHERE dt5.full_date BETWEEN (m.month_end - INTERVAL '89 days')::date AND m.month_end
        ) AS "LTV 90d (USD)"

    FROM months m
    GROUP BY m.year, m.month, m.month_start, m.month_end
    ORDER BY 1
    """

    df = execute_query(sql, (start_date, end_date))
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "Month", "CAC (USD)",
            "LTV 30d (USD)", "LTV 60d (USD)", "LTV 90d (USD)",
            "LTV(30d)/CAC", "LTV(60d)/CAC", "LTV(90d)/CAC",
        ])

    # Compute 3 ratios
    for period in ["30d", "60d", "90d"]:
        ltv_col = f"LTV {period} (USD)"
        ratio_col = f"LTV({period})/CAC"
        df[ratio_col] = df.apply(
            lambda r, lc=ltv_col: round(r[lc] / r["CAC (USD)"], 2)
            if pd.notna(r[lc]) and pd.notna(r["CAC (USD)"]) and r["CAC (USD)"] != 0
            else None,
            axis=1,
        )

    return df


def render_cac_clv_ratio_over_time_description(start_date_str: str, end_date_str: str):
    """Render description for CAC/LTV ratio chart."""
    if st.session_state.get('show_cac_clv_ratio_description', False):
        with st.expander("📋 CAC, LTV and LTV/CAC Ratio Description", expanded=False):
            st.markdown(textwrap.dedent("""
            - CAC (USD) = Tổng Marketing fees / Số khách hàng mới trong tháng
            - LTV (30d/60d/90d) = AOV × Avg Purchase Frequency (window tương ứng)
            - LTV/CAC = LTV ÷ CAC cho mỗi window
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
