"""
API routes for static data: Product Catalog and Bank Transactions.
These are not monthly data, but shared across all periods.
"""
import math
import pandas as pd
from fastapi import APIRouter, Query

from api.db import run_query

router = APIRouter(prefix="/api/static", tags=["static"])


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


# ========== Product Catalog ==========
@router.get("/product-catalog")
def get_product_catalog(
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    search: str = Query(None, description="Search in all columns"),
    sort_by: str = Query(None, description="Column to sort by"),
    sort_order: str = Query("asc", description="asc or desc"),
):
    """
    Get product catalog data from dim_product_catalog table.
    """
    where_clause = ""
    params = []
    
    if search:
        # Search in text columns
        search_conditions = []
        for col in ["product_line_id", "product_id", "variant_id", "product_line_name", "product_name", "variant_name", "product_code"]:
            search_conditions.append(f'CAST("{col}" AS TEXT) ILIKE %s')
            params.append(f"%{search}%")
        if search_conditions:
            where_clause = "WHERE " + " OR ".join(search_conditions)
    
    order_clause = ""
    if sort_by:
        # Validate column name
        valid_cols = ["product_catalog_key", "product_line_id", "product_id", "variant_id", 
                      "product_line_name", "product_name", "variant_name", "product_code",
                      "created_date", "updated_date"]
        if sort_by in valid_cols:
            order_clause = f'ORDER BY "{sort_by}"'
            if sort_order and sort_order.lower() == "desc":
                order_clause += " DESC"
            else:
                order_clause += " ASC"
    
    # Get data
    query = f"""
        SELECT 
            product_catalog_key,
            product_line_id,
            product_id,
            variant_id,
            product_line_name,
            product_name,
            variant_name,
            product_code,
            created_date,
            updated_date
        FROM dim_product_catalog
        {where_clause}
        {order_clause}
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    
    df = run_query(query, tuple(params) if params else None)
    
    # Get total count
    count_query = f'SELECT COUNT(*) as c FROM dim_product_catalog {where_clause}'
    count_params = params[:-2] if len(params) > 2 else []
    total = run_query(count_query, tuple(count_params) if count_params else None)
    total_count = int(total["c"].iloc[0]) if not total.empty else 0
    
    return {
        "data": _to_records(df),
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/product-catalog/count")
def get_product_catalog_count():
    """Get total count of product catalog items."""
    df = run_query("SELECT COUNT(*) as total FROM dim_product_catalog")
    total = int(df["total"].iloc[0]) if not df.empty else 0
    return {"total": total}


# ========== Bank Transactions ==========
@router.get("/bank-transactions")
def get_bank_transactions(
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    search: str = Query(None, description="Search in description, reference_number, account_number"),
    sort_by: str = Query(None, description="Column to sort by"),
    sort_order: str = Query("desc", description="asc or desc"),
    account_number: str = Query(None, description="Filter by account number"),
):
    """
    Get bank transactions data from fact_bank_transactions table.
    Joins with dim_time for date and dim_bank_account for account info.
    """
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
            if sort_order and sort_order.lower() == "desc":
                order_clause += " DESC"
            else:
                order_clause += " ASC"
    else:
        # Default: sort by date descending (newest first)
        order_clause = "ORDER BY dt.full_date DESC, fbt.bank_transaction_key DESC"
    
    # Get data with joins
    # Join với dim_product_catalog bằng product_catalog_key HOẶC bằng parsed IDs
    # Chỉ join bằng parsed IDs nếu cả 3 IDs đều không NULL
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
    
    # Get total count
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
