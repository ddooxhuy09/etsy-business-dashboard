"""
API routes for Bank Transactions static data.
"""
import math
import pandas as pd
from fastapi import APIRouter, Query, Body, HTTPException

from core.database import run_query, execute_query

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
    date_from: str = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: str = Query(None, description="Filter to date (YYYY-MM-DD)"),
):
    """Get bank transactions data from fact_bank_transactions table."""
    where_conditions = []
    params = []

    if account_number:
        where_conditions.append("fbt.account_number = %s")
        params.append(account_number)

    if date_from:
        where_conditions.append("fbt.transaction_date >= %s")
        params.append(date_from)

    if date_to:
        where_conditions.append("fbt.transaction_date <= %s")
        params.append(date_to)

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
                     "credit_amount", "debit_amount", "balance",
                     "transaction_description", "pl_account_number"]
        if sort_by in valid_cols:
            if sort_by == "transaction_date":
                order_clause = "ORDER BY fbt.transaction_date"
            else:
                order_clause = f'ORDER BY fbt.{sort_by}'
            order_clause += " DESC" if sort_order and sort_order.lower() == "desc" else " ASC"
    else:
        order_clause = "ORDER BY fbt.transaction_date DESC, fbt.bank_transaction_key DESC"

    query = f"""
        SELECT
            fbt.bank_transaction_key,
            fbt.transaction_date,
            fbt.reference_number,
            fbt.account_number,
            fbt.account_name,
            fbt.transaction_description,
            fbt.pl_account_number,
            fbt.parsed_product_line_id,
            fbt.parsed_product_id,
            fbt.parsed_variant_id,
            COALESCE(dpl.product_line, dpl2.product_line, fbt.parsed_product_line_id) AS product_line_name,
            COALESCE(dpl.product, dpl2.product, fbt.parsed_product_id) AS product_name,
            COALESCE(dpl.variants, dpl2.variants, fbt.parsed_variant_id) AS variant_name,
            COALESCE(fbt.credit_amount, 0) AS credit_amount,
            COALESCE(fbt.debit_amount, 0) AS debit_amount,
            fbt.balance,
            (fbt.parsed_product_line_id IS NOT NULL) AS is_business_related
        FROM fact_bank_transactions fbt
        LEFT JOIN dim_product_line dpl ON FALSE
        LEFT JOIN dim_product_line dpl2 ON
            fbt.parsed_product_line_id IS NOT NULL
            AND fbt.parsed_product_id IS NOT NULL
            AND fbt.parsed_variant_id IS NOT NULL
            AND fbt.parsed_product_line_id = dpl2.product_line_id
            AND fbt.parsed_product_id = dpl2.product_id
            AND fbt.parsed_variant_id = dpl2.variant_id
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
def get_bank_transactions_count(
    account_number: str = Query(None),
    date_from: str = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: str = Query(None, description="Filter to date (YYYY-MM-DD)"),
):
    """Get total count of bank transactions."""
    where_conditions = []
    params = []
    if account_number:
        where_conditions.append("account_number = %s")
        params.append(account_number)
    if date_from:
        where_conditions.append("transaction_date >= %s")
        params.append(date_from)
    if date_to:
        where_conditions.append("transaction_date <= %s")
        params.append(date_to)
    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    df = run_query(f"SELECT COUNT(*) as total FROM fact_bank_transactions {where_clause}", tuple(params) if params else None)
    total = int(df["total"].iloc[0]) if not df.empty else 0
    return {"total": total}


@router.put("/bank-transactions/{bank_transaction_key}")
def update_bank_transaction(bank_transaction_key: int, updates: dict = Body(...)):
    """Update a single bank transaction row by primary key."""
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided")

    allowed_columns = {
        "transaction_date": "transaction_date",
        "reference_number": "reference_number",
        "account_number": "account_number",
        "account_name": "account_name",
        "transaction_description": "transaction_description",
        "pl_account_number": "pl_account_number",
        "credit_amount": "credit_amount",
        "debit_amount": "debit_amount",
        "balance": "balance",
        "parsed_product_line_id": "parsed_product_line_id",
        "parsed_product_id": "parsed_product_id",
        "parsed_variant_id": "parsed_variant_id",
    }

    set_clauses = []
    params = []
    for key, value in updates.items():
        col = allowed_columns.get(key)
        if not col:
            raise HTTPException(status_code=400, detail=f"Invalid column: {key}")
        if key in ("credit_amount", "debit_amount", "balance") and value is not None:
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Invalid number for {key}: {value}")
        set_clauses.append(f"{col} = %s")
        params.append(value)

    params.append(bank_transaction_key)
    execute_query(
        f"UPDATE fact_bank_transactions SET {', '.join(set_clauses)} WHERE bank_transaction_key = %s",
        tuple(params),
    )
    return {"ok": True, "updated": bank_transaction_key}


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
