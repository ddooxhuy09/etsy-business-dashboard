"""
Profit & Loss API. Uses get_profit_loss_summary_table from dashboard/profit_loss_statement (local, no src).
Summary table uses utils.db_query -> api.db.run_query.
"""
import math
import logging
import pandas as pd
from fastapi import APIRouter, Query, HTTPException

from profit_loss_statement.profit_loss_summary_table import get_profit_loss_summary_table
from profit_loss_statement.profit_formula_config import (
    get_default_profit_expense_items,
    get_profit_formula_display,
    EXPENSE_ITEM_LABELS,
    PL_ACCOUNT_MAPPING,
)
from utils.db_query import execute_query

router = APIRouter(prefix="/api/profit-loss", tags=["profit-loss"])
logger = logging.getLogger(__name__)


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
    start_date: str = Query(None, description="YYYY-MM-DD"),
    end_date: str = Query(None, description="YYYY-MM-DD"),
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
        logger.info(
            "[P&L] summary-table params start=%s end=%s view_mode=%s selected_items=%s use_default=%s",
            start_date,
            end_date,
            view_mode,
            selected_items,
            use_default_formula,
        )
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
        try:
            logger.info("[P&L] summary-table result shape=%s cols=%s", getattr(df, "shape", None), list(df.columns) if hasattr(df, "columns") else None)
        except Exception:
            pass
        return {"data": _to_records(df)}
    except Exception as e:
        # Trước đây swallow error → UI chỉ thấy [] và không biết vì sao.
        logger.exception("[P&L] summary-table failed: %s", repr(e))
        return {"data": []}


@router.delete("/clean-bank-by-pl")
def clean_bank_by_pl(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    pl_accounts: str = Query(..., description="Comma-separated PL account numbers, e.g. 6222,6211"),
    account_number: str = Query(None, description="Optional bank account_number to restrict delete"),
):
    """
    Hard delete các dòng fact_bank_transactions theo PL account + khoảng ngày.
    Dùng cẩn thận, không thể undo.
    """
    accounts = [a.strip() for a in pl_accounts.split(",") if a.strip()]
    if not accounts:
        raise HTTPException(status_code=400, detail="No PL accounts provided")

    logger.warning(
        "[P&L] clean-bank-by-pl start=%s end=%s pl_accounts=%s account_number=%s",
        start_date,
        end_date,
        accounts,
        account_number,
    )

    sql = """
    DELETE FROM fact_bank_transactions AS fbt
    USING dim_time dt
    WHERE fbt.transaction_date_key = dt.time_key
      AND dt.full_date BETWEEN %s AND %s
      AND fbt.pl_account_number = ANY(%s)
    """
    params = [start_date, end_date, accounts]
    if account_number:
        sql += " AND fbt.account_number = %s"
        params.append(account_number)

    try:
        execute_query(sql, tuple(params))
        return {"ok": True, "deleted_pl_accounts": accounts}
    except Exception as e:
        logger.exception("[P&L] clean-bank-by-pl failed: %s", repr(e))
        raise HTTPException(status_code=500, detail="Failed to delete bank transactions")
