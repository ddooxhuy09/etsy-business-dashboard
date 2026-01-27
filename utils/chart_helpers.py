"""
Shared utilities for all chart functions
Eliminates code duplication across 18+ chart files

This module provides:
- Customer type display functions
- Standardized query execution
- Chart description rendering templates
- Common formatting utilities
"""

# Streamlit is no longer used (FastAPI + React only).
st = None
import pandas as pd
import textwrap
from typing import Optional, Dict, Any
from .db_query import execute_query_with_cache

# ============================================================================
# CUSTOMER TYPE UTILITIES
# ============================================================================

CUSTOMER_TYPE_MAPPING = {
    'all': 'All Customers',
    'new': 'New Customers', 
    'return': 'Returning Customers'
}


def get_customer_type_display(customer_type: str) -> str:
    """
    Get display name for customer type

    Args:
        customer_type: 'all', 'new', or 'return'

    Returns:
        Human-readable display name
    """
    return CUSTOMER_TYPE_MAPPING.get(customer_type, 'All Customers')


def get_available_customer_types() -> Dict[str, str]:
    """Get all available customer types (for dropdowns)"""
    return CUSTOMER_TYPE_MAPPING.copy()


# ============================================================================
# QUERY EXECUTION UTILITIES
# ============================================================================

def execute_chart_query(
    sql: str, 
    params: Optional[tuple] = None,
    ttl: int = 300,
    timeout: int = 30
) -> pd.DataFrame:
    """
    Execute query for chart data. Uses api.db.run_query (PostgreSQL).
    """
    return execute_query_with_cache(sql, params, ttl=ttl, timeout=timeout, use_pool=True)


# ============================================================================
# DESCRIPTION RENDERING UTILITIES
# ============================================================================

def render_chart_description(
    chart_name: str,
    description_content: str,
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
    customer_type: str = 'all',
    additional_info: Optional[str] = None
) -> None:
    """Render standardized chart description with filters (Streamlit)."""
    if st is None:
        return
    session_key = f'show_{chart_name}_description'

    if not st.session_state.get(session_key, False):
        return

    with st.expander(f"📋 {chart_name.replace('_', ' ').title()} Description", expanded=False):
        st.markdown(textwrap.dedent(description_content))
        st.markdown("---")
        st.markdown("**Filters Applied:**")
        st.markdown(f"""
        - **From Date:** {start_date_str or 'All time'}
        - **To Date:** {end_date_str or 'Present'}
        - **Customer Type:** {get_customer_type_display(customer_type)}
        """)
        if additional_info:
            st.markdown("---")
            st.markdown(additional_info)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("❌ Close", key=f"close_{chart_name}_description_btn", use_container_width=True):
                st.session_state[session_key] = False
                st.rerun()


def create_description_toggle_button(
    chart_name: str,
    button_text: str = "📋 Show Description",
    button_key: Optional[str] = None
) -> None:
    """Create toggle button for chart description (Streamlit)."""
    session_key = f'show_{chart_name}_description'
    btn_key = button_key or f"btn_{chart_name}_description"

    if st.button(button_text, key=btn_key):
        st.session_state[session_key] = not st.session_state.get(session_key, False)
        st.rerun()


# ============================================================================
# DATE FORMATTING UTILITIES
# ============================================================================

def format_date_display(date_str: Optional[str], default: str = "Not set") -> str:
    """Format date string for display."""
    if not date_str:
        return default
    try:
        from datetime import datetime
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%B %d, %Y')
    except Exception:
        return date_str


def format_currency(value: float, currency: str = "USD", decimals: int = 2) -> str:
    """Format number as currency."""
    if currency == "USD":
        return f"${value:,.{decimals}f}"
    elif currency == "VND":
        return f"₫{value:,.0f}"
    else:
        return f"{value:,.{decimals}f}"


# ============================================================================
# CHART CONFIGURATION UTILITIES
# ============================================================================

CHART_THEMES = {
    'dark': {
        'plot_bgcolor': '#1a1a1a',
        'paper_bgcolor': '#1a1a1a',
        'font_color': 'white',
        'grid_color': 'rgba(255,255,255,0.2)',
        'title_font_color': 'white'
    },
    'light': {
        'plot_bgcolor': 'white',
        'paper_bgcolor': 'white',
        'font_color': 'black',
        'grid_color': 'rgba(0,0,0,0.1)',
        'title_font_color': 'black'
    }
}


def get_default_chart_layout(theme: str = 'dark', height: int = 500) -> Dict[str, Any]:
    """Get standard Plotly layout configuration."""
    theme_config = CHART_THEMES.get(theme, CHART_THEMES['dark'])
    return {
        'height': height,
        'plot_bgcolor': theme_config['plot_bgcolor'],
        'paper_bgcolor': theme_config['paper_bgcolor'],
        'font': {'color': theme_config['font_color']},
        'title_font_color': theme_config['title_font_color'],
        'xaxis': {'color': theme_config['font_color'], 'gridcolor': theme_config['grid_color']},
        'yaxis': {'color': theme_config['font_color'], 'gridcolor': theme_config['grid_color']}
    }


# ============================================================================
# METRIC FORMATTING UTILITIES
# ============================================================================

def format_metric_value(value: Any, metric_type: str = 'number') -> str:
    """Format metric value for display."""
    if value is None or pd.isna(value):
        return "N/A"
    try:
        if metric_type == 'currency':
            return format_currency(float(value), 'USD', decimals=2)
        elif metric_type == 'percentage':
            return f"{float(value):.2f}%"
        elif metric_type == 'number':
            return f"{float(value):,.0f}"
        else:
            return str(value)
    except (ValueError, TypeError):
        return str(value)
