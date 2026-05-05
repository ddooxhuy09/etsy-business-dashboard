from ._streamlit_shim import st  # noqa: F401
import pandas as pd
import textwrap
from core.query_utils.db_query import execute_query
from core.query_utils.chart_helpers import get_customer_type_display


def get_new_customers_over_time(start_date: str = None, end_date: str = None, customer_type: str = 'all'):
    """Get new/returning customers over time based on customer_type filter"""
    having_clause = "HAVING COUNT(DISTINCT order_key) > 1" if customer_type == 'return' else "HAVING COUNT(DISTINCT order_key) = 1"
    sql = f"""SELECT dt.date_key as "Date", COUNT(DISTINCT fo.customer_key) as "New Customers"
           FROM fact_order_items fs
           JOIN fact_orders fo ON fs.order_key = fo.order_key
           JOIN dim_time dt ON fo.sale_date_key = dt.date_key
           WHERE fo.customer_key IN (
               SELECT fo_sub.customer_key
               FROM fact_orders fo_sub
               GROUP BY fo_sub.customer_key
               {having_clause}
           )"""
    
    params = []
    if start_date:
        sql += " AND dt.date_key >= %s::date"
        params.append(start_date)
    if end_date:
        sql += " AND dt.date_key <= %s::date"
        params.append(end_date)
    
    sql += """ GROUP BY 1 
               ORDER BY 1"""
    
    return execute_query(sql, tuple(params) if params else None)

def render_new_customers_over_time_description(start_date_str, end_date_str, customer_type):
    """Render description for new customers over time chart"""
    if st.session_state.get('show_new_customers_over_time_description', False):
        with st.expander("📋 New Customers Over Time Description", expanded=False):
            st.markdown(textwrap.dedent("""
            **KHÁCH HÀNG MỚI THEO THỜI GIAN**

            - **New Customers**: Khách hàng chỉ có 1 đơn hàng duy nhất (COUNT(order_key) = 1)
            - **Đếm theo ngày**: GROUP BY cột hiển thị (Date) để tránh lỗi group-by
            - **Ý nghĩa**: Theo dõi xu hướng thu hút khách hàng mới theo ngày
            """))

            st.markdown(textwrap.dedent(f"""
            **Filters Applied:**

            - From Date: {start_date_str or 'All time'}
            - To Date: {end_date_str or 'Present'}
            - Customer Type: {get_customer_type_display(customer_type)}
            """))
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("❌ Close", key="close_new_customers_over_time_description_btn", width='stretch'):
                    st.session_state.show_new_customers_over_time_description = False
                    st.rerun()
