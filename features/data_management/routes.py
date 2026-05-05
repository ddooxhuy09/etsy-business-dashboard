"""
Data Management API — view and edit imported data, organised by the 6 original CSV file types.

Endpoints:
  GET  /api/data/{source}          — paginated list (period, search, page, page_size)
  PUT  /api/data/{source}/{pk}     — update a row
  DELETE /api/data/{source}/{pk}   — delete a row
  GET  /api/data/sources           — list available sources with labels

Sources: statement | payments | listings | sold-order-items | sold-orders | deposits
"""
import math
from typing import Any, Dict, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from core.database import run_query, execute_query

router = APIRouter(prefix="/api/data", tags=["data-management"])

# ---------------------------------------------------------------------------
# Source configuration
# ---------------------------------------------------------------------------

SOURCES = {
    "statement": {
        "label": "Statement",
        "table": "fact_statement",
        "pk": "statement_key",
        "select": """
            SELECT
                fft.statement_key         AS id,
                dt.date_key::text         AS "Date",
                fft.entry_type            AS "Type",
                fft.title                 AS "Title",
                fft.info                  AS "Info",
                fft.ref_order_id          AS "Order ID",
                fft.amount                AS "Amount",
                fft.fees_and_taxes        AS "Fees & Taxes",
                fft.net                   AS "Net"
            FROM fact_statement fft
            LEFT JOIN dim_time dt ON fft.entry_date = dt.date_key
        """,
        "date_col": "dt.date_key",
        "search_cols": ["fft.title", "fft.entry_type", "fft.info"],
        "order_by": "dt.date_key DESC",
        "amount_cols": ["Amount", "Fees & Taxes", "Net"],
        "editable_cols": ["entry_type", "title", "info", "amount", "fees_and_taxes", "net"],
    },
    "payments": {
        "label": "Payments",
        "table": "fact_payments",
        "pk": "payment_key",
        "select": """
            SELECT
                fp.payment_key       AS id,
                dt.date_key::text    AS "Date",
                fp.payment_id        AS "Payment ID",
                fp.order_id          AS "Order ID",
                fp.gross_amount      AS "Gross",
                fp.fees              AS "Fees",
                fp.net_amount        AS "Net",
                fp.payment_status    AS "Status"
            FROM fact_payments fp
            LEFT JOIN dim_time dt ON fp.funds_available_date = dt.date_key
        """,
        "date_col": "dt.date_key",
        "search_cols": ["fp.payment_status"],
        "order_by": "dt.date_key DESC",
        "amount_cols": ["Gross", "Fees", "Net"],
        "editable_cols": ["gross_amount", "fees", "net_amount", "payment_status"],
    },
    "listings": {
        "label": "Listings",
        "table": "dim_product",
        "pk": "product_key",
        "select": """
            SELECT
                dp.product_key      AS id,
                dp.listing_id       AS "Listing ID",
                dp.title            AS "Title",
                dp.price            AS "Price",
                dp.quantity         AS "Quantity"
            FROM dim_product dp
        """,
        "date_col": None,
        "search_cols": ["dp.title"],
        "order_by": "dp.listing_id DESC",
        "amount_cols": ["Price"],
        "editable_cols": ["title", "price", "quantity"],
    },
    "sold-order-items": {
        "label": "Sold Order Items",
        "table": "fact_order_items",
        "pk": "order_item_key",
        "select": """
            SELECT
                fs.order_item_key       AS id,
                dt.date_key::text       AS "Sale Date",
                fo.order_id             AS "Order ID",
                fs.transaction_id       AS "Transaction ID",
                fs.sku                  AS "SKU",
                dp.title                AS "Item Name",
                fs.quantity_sold        AS "Quantity",
                fs.price                AS "Price",
                fo.discount_amount      AS "Discount",
                fs.item_total           AS "Item Total"
            FROM fact_order_items fs
            LEFT JOIN fact_orders fo ON fs.order_key = fo.order_key
            LEFT JOIN dim_time dt ON fo.sale_date_key = dt.date_key
            LEFT JOIN dim_product dp ON fs.product_key = dp.product_key
        """,
        "date_col": "dt.date_key",
        "search_cols": ["fs.sku", "dp.title"],
        "order_by": "dt.date_key DESC",
        "amount_cols": ["Price", "Discount", "Item Total"],
        "editable_cols": ["quantity_sold", "price", "item_total"],
    },
    "sold-orders": {
        "label": "Sold Orders",
        "table": "fact_orders",
        "pk": "order_key",
        "select": """
            SELECT
                fo.order_key            AS id,
                fo.order_id             AS "Order ID",
                fo.order_type           AS "Order Type",
                fo.number_of_items      AS "Items",
                fo.order_total          AS "Order Total",
                fo.discount_amount      AS "Discount",
                fo.shipping             AS "Shipping",
                fo.sales_tax            AS "Sales Tax",
                fo.coupon_code          AS "Coupon",
                fo.payment_method       AS "Payment Method",
                fo.shipping_country     AS "Ship To Country"
            FROM fact_orders fo
        """,
        "date_col": None,
        "search_cols": ["fo.order_type", "fo.coupon_code", "fo.shipping_country"],
        "order_by": "fo.order_id DESC",
        "amount_cols": ["Order Total", "Discount", "Shipping", "Sales Tax"],
        "editable_cols": ["order_type", "number_of_items", "order_total", "discount_amount", "shipping", "coupon_code"],
    },
    "deposits": {
        "label": "Deposits",
        "table": "bridge_deposits",
        "pk": "deposit_key",
        "select": """
            SELECT
                fd.deposit_key                  AS id,
                dt.date_key::text               AS "Date",
                fd.amount                       AS "Amount",
                fd.deposit_status               AS "Status",
                fd.bank_account_ending_digits   AS "Bank Account Ending"
            FROM bridge_deposits fd
            LEFT JOIN dim_time dt ON fd.deposit_date = dt.date_key
        """,
        "date_col": "dt.date_key",
        "search_cols": ["fd.deposit_status"],
        "order_by": "dt.date_key DESC",
        "amount_cols": ["Amount"],
        "editable_cols": ["amount", "deposit_status"],
    },
}

ALLOWED_SOURCES = set(SOURCES.keys())


def _source_or_404(source: str) -> dict:
    if source not in ALLOWED_SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown source '{source}'. Valid: {sorted(ALLOWED_SOURCES)}")
    return SOURCES[source]


# ---------------------------------------------------------------------------
# GET /api/data/sources
# ---------------------------------------------------------------------------

@router.get("/sources")
def list_sources():
    """Return all available data sources with labels and amount column names."""
    return [
        {"key": k, "label": v["label"], "amount_cols": v["amount_cols"]}
        for k, v in SOURCES.items()
    ]


# ---------------------------------------------------------------------------
# GET /api/data/{source}
# ---------------------------------------------------------------------------

@router.get("/{source}")
def list_rows(
    source: str,
    period: Optional[str] = Query(None, description="YYYY-MM period filter"),
    search: Optional[str] = Query(None, description="Search keyword"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    cfg = _source_or_404(source)

    where_clauses = []
    params: list = []

    DATE_SOURCES = {"statement", "payments", "sold-order-items", "deposits"}
    if period:
        try:
            p_year, p_month = period.split("-")
            p_year, p_month = int(p_year), int(p_month)
            if source in DATE_SOURCES:
                where_clauses.append("dt.year = %s AND dt.month_num = %s")
                params += [p_year, p_month]
            elif source == "sold-orders":
                where_clauses.append(
                    "fo.order_id IN (SELECT fo2.order_id FROM fact_orders fo2 "
                    "JOIN dim_time dt2 ON fo2.sale_date_key = dt2.date_key "
                    "WHERE dt2.year = %s AND dt2.month_num = %s)"
                )
                params += [p_year, p_month]
        except Exception:
            pass

    # Search filter
    if search and cfg["search_cols"]:
        search_parts = [f"LOWER({col}::text) LIKE %s" for col in cfg["search_cols"]]
        where_clauses.append(f"({' OR '.join(search_parts)})")
        params += [f"%{search.lower()}%"] * len(cfg["search_cols"])

    # Build WHERE clause
    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    order_sql = f" ORDER BY {cfg['order_by']}"
    offset = (page - 1) * page_size

    count_sql = f"SELECT COUNT(*) as cnt FROM ({cfg['select']}{where_sql}) sub"
    data_sql = f"{cfg['select']}{where_sql}{order_sql} LIMIT %s OFFSET %s"

    try:
        count_df = run_query(count_sql, tuple(params) if params else None)
        total = int(count_df.iloc[0]["cnt"]) if not count_df.empty else 0

        data_params = params + [page_size, offset]
        df = run_query(data_sql, tuple(data_params))
        import numpy as np
        df = df.replace([np.inf, -np.inf], np.nan)
        rows = df.astype(object).where(df.notna(), None).to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "source": source,
        "label": cfg["label"],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
        "amount_cols": cfg["amount_cols"],
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# PUT /api/data/{source}/{pk}
# ---------------------------------------------------------------------------

class UpdatePayload(BaseModel):
    data: Dict[str, Any]


@router.put("/{source}/{pk}")
def update_row(source: str, pk: int, body: UpdatePayload):
    cfg = _source_or_404(source)
    allowed = set(cfg["editable_cols"])
    fields = {k: v for k, v in body.data.items() if k in allowed}

    if not fields:
        raise HTTPException(status_code=400, detail="No editable fields provided.")

    set_clause = ", ".join(f"{col} = %s" for col in fields)
    values = list(fields.values()) + [pk]
    sql = f"UPDATE {cfg['table']} SET {set_clause} WHERE {cfg['pk']} = %s"

    try:
        execute_query(sql, tuple(values))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "updated": pk}


# ---------------------------------------------------------------------------
# DELETE /api/data/{source}/{pk}
# ---------------------------------------------------------------------------

@router.delete("/{source}/{pk}")
def delete_row(source: str, pk: int):
    cfg = _source_or_404(source)
    sql = f"DELETE FROM {cfg['table']} WHERE {cfg['pk']} = %s"

    try:
        execute_query(sql, (pk,))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "deleted": pk}
