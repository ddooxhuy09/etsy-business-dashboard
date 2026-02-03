"""
Profit & Loss API. Uses get_profit_loss_summary_table from dashboard/profit_loss_statement (local, no src).
Summary table uses utils.db_query -> api.db.run_query.
"""
import math
import pandas as pd
from fastapi import APIRouter, Query

from profit_loss_statement.profit_loss_summary_table import get_profit_loss_summary_table
from profit_loss_statement.profit_formula_config import (
    get_default_profit_expense_items,
    get_profit_formula_display,
    EXPENSE_ITEM_LABELS,
    PL_ACCOUNT_MAPPING,
)

router = APIRouter(prefix="/api/profit-loss", tags=["profit-loss"])

StrOpt = Query(None, description="YYYY-MM-DD")


def _json_safe(v):
    """Replace NaN, inf, -inf and convert numpy scalars; ensure JSON-serializable."""
    if v is None or (isinstance(v, float) and (math.isnan(v) or not math.isfinite(v))):
        return None
    if pd.isna(v):
        return None
    if hasattr(v, "item"):
        x = v.item()
        if isinstance(x, float) and (math.isnan(x) or not math.isfinite(x)):
            return None
        return x
    return v


def _to_records(df):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    out = pd.DataFrame(df).to_dict(orient="records")
    return [{k: _json_safe(v) for k, v in row.items()} for row in out]


@router.get("/formula-config")
def get_formula_config():
    """
    Get the profit formula configuration.
    
    Returns:
        - default_expense_items: List of expense item column names used in default formula
        - expense_item_labels: Mapping from column name to display label
        - formula_display: Human-readable formula string
        - pl_account_mapping: Mapping from PL account numbers to column names
    """
    return {
        "default_expense_items": get_default_profit_expense_items(),
        "expense_item_labels": EXPENSE_ITEM_LABELS,
        "formula_display": get_profit_formula_display(),
        "pl_account_mapping": PL_ACCOUNT_MAPPING,
    }


@router.get("/summary-table")
def summary_table(
    start_date: str = StrOpt,
    end_date: str = StrOpt,
    view_mode: str = Query("month", description="month | year | month_year"),
    selected_items: str = Query(None, description="Comma-separated list of column names to subtract from Revenue for Net Profit. Example: refund_cost,cost_of_goods,total_etsy_fees"),
    use_default_formula: bool = Query(True, description="If True and selected_items is None, use default formula from config"),
):
    """
    Get Profit & Loss summary table.
    
    selected_items: Comma-separated list of column names (e.g., "refund_cost,cost_of_goods,total_etsy_fees").
                    Net Profit = Revenue - sum(selected_items).
                    If not provided and use_default_formula=True, uses default formula from config.
    
    use_default_formula: If True (default) and selected_items is not provided,
                        Net Profit will be calculated using the default formula from profit_formula_config.py.
                        If False and selected_items is not provided, Net Profit = 0.
    """
    try:
        selected_list = None
        if selected_items:
            selected_list = [item.strip() for item in selected_items.split(",") if item.strip()]
        
        df = get_profit_loss_summary_table(
            start_date, 
            end_date, 
            view_mode=view_mode, 
            selected_items=selected_list,
            use_default_formula=use_default_formula
        )
        return {"data": _to_records(df)}
    except Exception:
        # If table doesn't exist or other DB error, return empty data
        # Don't log error to avoid noise when database is empty
        return {"data": []}
