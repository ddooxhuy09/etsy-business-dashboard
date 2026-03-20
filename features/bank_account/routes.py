"""
API routes for Bank Transactions static data.
"""
import math
import pandas as pd
from fastapi import APIRouter, Query, Body, HTTPException

from shared.db import run_query, execute_query

router = APIRouter(prefix="/api/static", tags=["bank-account"])


def _to_records(df):
    """Convert DataFrame to JSON-safe records."""
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    out = pd.DataFrame(df).replace({pd.NA: None}).to_dict(orient="records")

    def _js(v):
        if v is None or (isinstance(v, float) and (math.isnan(v) or not math.isfinite(v))):
            return None
        if hasattr(v, "item"):
            return v.item()
        return v

    return [{k: _js(v) for k, v in row.items()} for row in out]


@router.get("/bank-transactions")
def get_bank_transactions(
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    search: str = Query(None, description="Search in description, reference_number, account_number"),
    sort_by: str = Query(None, description="Column to sort by"),
    sort_order: str = Query("desc", description="asc or desc"),
    account_number: str = Query(None, description="Filter by account number"),
):
    """Get bank transactions data from fact_bank_transactions table."""
    where_conditions = []
    params = []

    if account_number:
        where_conditions.append("fbt.account_number = %s")
        params.append(account_number)

    if search:
        search_conditions = []
        for col in ["fbt.transaction_description", "fbt.reference_number", "fbt.account_number"]:
            search_conditions.append(f'CAST({col} AS TEXT) ILIKE %s')
            params.append(f"%{search}%")
        if search_conditions:
            where_conditions.append("(" + " OR ".join(search_conditions) + ")")

    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

    order_clause = ""
    if sort_by:
        valid_cols = ["transaction_date", "reference_number", "account_number",
                     "credit_amount", "debit_amount", "balance_after_transaction",
                     "transaction_description", "pl_account_number"]
        if sort_by in valid_cols:
            if sort_by == "transaction_date":
                order_clause = "ORDER BY dt.full_date"
            else:
                order_clause = f'ORDER BY fbt.{sort_by}'
            order_clause += " DESC" if sort_order and sort_order.lower() == "desc" else " ASC"
    else:
        order_clause = "ORDER BY dt.full_date DESC, fbt.bank_transaction_key DESC"

    query = f"""
        SELECT
            fbt.bank_transaction_key,
            dt.full_date AS transaction_date,
            fbt.reference_number,
            fbt.account_number,
            dba.account_name,
            fbt.transaction_description,
            fbt.pl_account_number,
            fbt.parsed_product_line_id,
            fbt.parsed_product_id,
            fbt.parsed_variant_id,
            COALESCE(dpc.product_line_name, dpc2.product_line_name) AS product_line_name,
            COALESCE(dpc.product_name, dpc2.product_name) AS product_name,
            COALESCE(dpc.variant_name, dpc2.variant_name) AS variant_name,
            COALESCE(fbt.credit_amount, 0) AS credit_amount,
            COALESCE(fbt.debit_amount, 0) AS debit_amount,
            fbt.balance_after_transaction,
            fbt.is_business_related,
            fbt.data_source,
            fbt.batch_id
        FROM fact_bank_transactions fbt
        LEFT JOIN dim_time dt ON fbt.transaction_date_key = dt.time_key
        LEFT JOIN dim_bank_account dba ON fbt.bank_account_key = dba.bank_account_key
        LEFT JOIN dim_product_catalog dpc ON fbt.product_catalog_key = dpc.product_catalog_key
        LEFT JOIN dim_product_catalog dpc2 ON
            fbt.parsed_product_line_id IS NOT NULL
            AND fbt.parsed_product_id IS NOT NULL
            AND fbt.parsed_variant_id IS NOT NULL
            AND fbt.parsed_product_line_id = dpc2.product_line_id
            AND fbt.parsed_product_id = dpc2.product_id
            AND fbt.parsed_variant_id = dpc2.variant_id
        {where_clause}
        {order_clause}
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    df = run_query(query, tuple(params) if params else None)

    count_query = f"""
        SELECT COUNT(*) as c
        FROM fact_bank_transactions fbt
        {where_clause}
    """
    count_params = params[:-2] if len(params) > 2 else []
    total = run_query(count_query, tuple(count_params) if count_params else None)
    total_count = int(total["c"].iloc[0]) if not total.empty else 0

    return {
        "data": _to_records(df),
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/bank-transactions/count")
def get_bank_transactions_count(account_number: str = Query(None)):
    """Get total count of bank transactions."""
    if account_number:
        df = run_query("SELECT COUNT(*) as total FROM fact_bank_transactions WHERE account_number = %s", (account_number,))
    else:
        df = run_query("SELECT COUNT(*) as total FROM fact_bank_transactions")
    total = int(df["total"].iloc[0]) if not df.empty else 0
    return {"total": total}


@router.delete("/bank-transactions")
def delete_bank_transactions(ids: list[int] = Body(..., embed=True)):
    """Delete bank transactions by primary keys (bank_transaction_key)."""
    if not ids:
        raise HTTPException(status_code=400, detail="No ids provided")
    ids = [int(i) for i in ids]
    execute_query(
        "DELETE FROM fact_bank_transactions WHERE bank_transaction_key = ANY(%s)",
        (ids,),
    )
    return {"ok": True, "deleted": len(ids)}
