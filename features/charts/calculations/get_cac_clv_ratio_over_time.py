"""
CAC/LTV Ratio Over Time Chart
LTV = AOV × Avg Purchase Frequency
CAC = Marketing fees / New customers (per month)
Shows 3 ratio lines: LTV(30d)/CAC, LTV(60d)/CAC, LTV(90d)/CAC
"""
from ._streamlit_shim import st  # noqa: F401
import pandas as pd
import textwrap
from core.query_utils.db_query import execute_query


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
            COALESCE(CAST(%s AS date), MIN(dt.date_key)) AS start_date,
            COALESCE(CAST(%s AS date), MAX(dt.date_key)) AS end_date
        FROM dim_time dt
    ), months AS (
        SELECT ym.year, ym.month_num,
               MIN(dt.date_key) AS month_start,
               MAX(dt.date_key) AS month_end
        FROM (
            SELECT DISTINCT dt.year, dt.month_num
            FROM fact_order_items fs
            JOIN fact_orders fo ON fs.order_key = fo.order_key
            JOIN dim_time dt ON fo.sale_date_key = dt.date_key
            JOIN bounds b ON dt.date_key BETWEEN b.start_date AND b.end_date
            UNION
            SELECT DISTINCT dt.year, dt.month_num
            FROM fact_statement fft
            JOIN dim_time dt ON fft.entry_date = dt.date_key
            JOIN bounds b ON dt.date_key BETWEEN b.start_date AND b.end_date
        ) ym
        JOIN dim_time dt ON dt.year = ym.year AND dt.month_num = ym.month_num
        GROUP BY ym.year, ym.month_num
        ORDER BY ym.year, ym.month_num
    )
    SELECT
        m.year || '-' || LPAD(m.month_num::text, 2, '0') AS "Month",

        ROUND(
          ABS(
            COALESCE((
              SELECT SUM(COALESCE(fft.fees_and_taxes, 0))
              FROM fact_statement fft
              JOIN dim_time dt1 ON fft.entry_date = dt1.date_key
              WHERE fft.entry_type = 'Marketing'
                AND dt1.date_key BETWEEN m.month_start AND m.month_end
            ), 0)
          )
          / NULLIF((
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
              AND dt2.date_key BETWEEN m.month_start AND m.month_end
          ), 0), 2) AS "CAC (USD)",

        (SELECT ROUND(
            (COALESCE(SUM(fs3.item_total), 0)::numeric / NULLIF(COUNT(DISTINCT fs3.order_key), 0))
            *
            (COUNT(DISTINCT fs3.order_key)::numeric / NULLIF(COUNT(DISTINCT fo3.customer_key), 0))
        , 2)
        FROM fact_order_items fs3
        JOIN fact_orders fo3 ON fs3.order_key = fo3.order_key
        JOIN dim_time dt3 ON fo3.sale_date_key = dt3.date_key
        WHERE dt3.date_key BETWEEN (m.month_end - INTERVAL '29 days')::date AND m.month_end
        ) AS "LTV 30d (USD)",

        (SELECT ROUND(
            (COALESCE(SUM(fs4.item_total), 0)::numeric / NULLIF(COUNT(DISTINCT fs4.order_key), 0))
            *
            (COUNT(DISTINCT fs4.order_key)::numeric / NULLIF(COUNT(DISTINCT fo4.customer_key), 0))
        , 2)
        FROM fact_order_items fs4
        JOIN fact_orders fo4 ON fs4.order_key = fo4.order_key
        JOIN dim_time dt4 ON fo4.sale_date_key = dt4.date_key
        WHERE dt4.date_key BETWEEN (m.month_end - INTERVAL '59 days')::date AND m.month_end
        ) AS "LTV 60d (USD)",

        (SELECT ROUND(
            (COALESCE(SUM(fs5.item_total), 0)::numeric / NULLIF(COUNT(DISTINCT fs5.order_key), 0))
            *
            (COUNT(DISTINCT fs5.order_key)::numeric / NULLIF(COUNT(DISTINCT fo5.customer_key), 0))
        , 2)
        FROM fact_order_items fs5
        JOIN fact_orders fo5 ON fs5.order_key = fo5.order_key
        JOIN dim_time dt5 ON fo5.sale_date_key = dt5.date_key
        WHERE dt5.date_key BETWEEN (m.month_end - INTERVAL '89 days')::date AND m.month_end
        ) AS "LTV 90d (USD)"

    FROM months m
    GROUP BY m.year, m.month_num, m.month_start, m.month_end
    ORDER BY 1
    """

    df = execute_query(sql, (start_date, end_date))
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "Month", "CAC (USD)",
            "LTV 30d (USD)", "LTV 60d (USD)", "LTV 90d (USD)",
            "LTV(30d)/CAC", "LTV(60d)/CAC", "LTV(90d)/CAC",
        ])

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
