"""
Profit & Loss API. Uses get_profit_loss_summary_table from dashboard/profit_loss_statement (local, no src).
Summary table uses utils.db_query -> api.db.run_query.
"""
import math
import pandas as pd
from fastapi import APIRouter, Query

from profit_loss_statement.profit_loss_summary_table import get_profit_loss_summary_table

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


@router.get("/summary-table")
def summary_table(
    start_date: str = StrOpt,
    end_date: str = StrOpt,
    view_mode: str = Query("month", description="month | year | month_year"),
    selected_items: str = Query(None, description="Comma-separated list of column names to subtract from Revenue for Net Profit. Example: refund_cost,cost_of_goods,total_etsy_fees"),
):
    """
    Get Profit & Loss summary table.
    
    selected_items: Comma-separated list of column names (e.g., "refund_cost,cost_of_goods,total_etsy_fees").
                    Net Profit = Revenue - sum(selected_items).
                    If not provided, Net Profit = 0.
    """
    try:
        selected_list = None
        if selected_items:
            selected_list = [item.strip() for item in selected_items.split(",") if item.strip()]
        
        df = get_profit_loss_summary_table(start_date, end_date, view_mode=view_mode, selected_items=selected_list)
        return {"data": _to_records(df)}
    except Exception:
        # If table doesn't exist or other DB error, return empty data
        # Don't log error to avoid noise when database is empty
        return {"data": []}
