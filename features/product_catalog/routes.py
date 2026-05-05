"""
API routes for Product Catalog static data.
"""
import math
import pandas as pd
from fastapi import APIRouter, Query, Body, HTTPException

from core.database import run_query, execute_query

router = APIRouter(prefix="/api/static", tags=["product-catalog"])


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


@router.get("/product-catalog")
def get_product_catalog(
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    search: str = Query(None, description="Search in all columns"),
    sort_by: str = Query(None, description="Column to sort by"),
    sort_order: str = Query("asc", description="asc or desc"),
):
    """Get product catalog data from dim_product_line table."""
    where_clause = ""
    params = []

    if search:
        search_conditions = []
        for col in ["product_line_id", "product_id", "variant_id", "product_line", "product", "variants", "product_code"]:
            search_conditions.append(f'CAST("{col}" AS TEXT) ILIKE %s')
            params.append(f"%{search}%")
        if search_conditions:
            where_clause = "WHERE " + " OR ".join(search_conditions)

    order_clause = ""
    if sort_by:
        valid_cols = ["dim_product_line_key", "product_line_id", "product_id", "variant_id",
                      "product_line", "product", "variants", "product_code"]
        if sort_by in valid_cols:
            order_clause = f'ORDER BY "{sort_by}"'
            order_clause += " DESC" if sort_order and sort_order.lower() == "desc" else " ASC"

    query = f"""
        SELECT
            dim_product_line_key AS product_catalog_key,
            product_line_id,
            product_id,
            variant_id,
            product_line AS product_line_name,
            product AS product_name,
            variants AS variant_name,
            product_code
        FROM dim_product_line
        {where_clause}
        {order_clause}
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    df = run_query(query, tuple(params) if params else None)

    count_query = f'SELECT COUNT(*) as c FROM dim_product_line {where_clause}'
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
    df = run_query("SELECT COUNT(*) as total FROM dim_product_line")
    total = int(df["total"].iloc[0]) if not df.empty else 0
    return {"total": total}


@router.delete("/product-catalog")
def delete_product_catalog(ids: list[int] = Body(..., embed=True)):
    """Delete product catalog rows by primary keys (dim_product_line_key)."""
    if not ids:
        raise HTTPException(status_code=400, detail="No ids provided")
    ids = [int(i) for i in ids]
    execute_query(
        "DELETE FROM dim_product_line WHERE dim_product_line_key = ANY(%s)",
        (ids,),
    )
    return {"ok": True, "deleted": len(ids)}
