"""
API routes for importing Product Catalog data.
Supports CSV/Excel file upload and single-row import.
"""
import io
import math
import logging
import pandas as pd
from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from typing import Optional
from pydantic import BaseModel

from core.database import run_query, execute_query, get_database_url
from etl.cleaners.process_product_catalog import clean_product_catalog_data
from etl.expected_columns import validate_columns, get_raw_columns_list

router = APIRouter(prefix="/api/static", tags=["product-catalog"])
logger = logging.getLogger(__name__)


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


@router.post("/product-catalog/upload")
async def upload_product_catalog(file: UploadFile = File(...)):
    """Upload and import product_catalog (.csv, .xlsx, .xls) file."""
    fname = file.filename.lower() if file.filename else ""
    allowed_exts = (".csv", ".xlsx", ".xls")
    if not any(fname.endswith(ext) for ext in allowed_exts):
        raise HTTPException(status_code=400, detail="File phải là CSV hoặc Excel (.csv, .xlsx, .xls)")

    try:
        content = await file.read()

        if fname.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(content), encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(content), encoding='utf-8-sig')
        else:
            df = pd.read_excel(io.BytesIO(content))

        header_errors = validate_columns("product_catalog", df.columns.tolist())
        if header_errors:
            expected = get_raw_columns_list("product_catalog")
            return {
                "ok": False,
                "message": "Sai định dạng cột file product catalog",
                "imported": 0,
                "errors": header_errors,
                "expected_columns": expected,
                "received_columns": list(df.columns),
            }

        # Detect duplicates in file before cleaning
        KEY_COLS = ["product_line_id", "product_id", "variant_id"]
        _key_norm_map = {"product line id": "product_line_id", "product id": "product_id", "variant id": "variant_id"}
        _raw_rename = {c: _key_norm_map[c.strip().lower()] for c in df.columns if c.strip().lower() in _key_norm_map}
        df_raw_keys = df.rename(columns=_raw_rename)
        dup_rows = []
        if all(c in df_raw_keys.columns for c in KEY_COLS):
            _keys = df_raw_keys[KEY_COLS].astype(str).apply(lambda s: s.str.strip())
            _dup_mask = _keys.duplicated(keep=False)
            if _dup_mask.any():
                _df_dup = df_raw_keys[_dup_mask].copy()
                for _, grp in _df_dup.groupby(KEY_COLS):
                    k = grp.iloc[0]
                    dup_rows.append(
                        f"{k['product_line_id']} / {k['product_id']} / {k['variant_id']} ({len(grp)} lần)"
                    )

        df_clean = clean_product_catalog_data(df)

        if df_clean.empty:
            return {"ok": False, "message": "No valid data after cleaning", "imported": 0}

        import psycopg2
        from psycopg2.extras import execute_values

        cols = ["product_line_id", "product_id", "variant_id", "product_line", "product", "variants"]
        for c in cols:
            if c not in df_clean.columns:
                df_clean[c] = None

        df_upsert = df_clean[cols].copy()
        dsn = get_database_url().replace("postgresql+psycopg2://", "postgresql://")

        try:
            with psycopg2.connect(dsn) as conn:
                with conn.cursor() as cur:
                    rows = list(zip(
                        df_upsert["product_line_id"].tolist(),
                        df_upsert["product_id"].tolist(),
                        df_upsert["variant_id"].tolist(),
                        df_upsert["product_line"].tolist(),
                        df_upsert["product"].tolist(),
                        df_upsert["variants"].tolist(),
                    ))
                    execute_values(
                        cur,
                        """
                        INSERT INTO dim_product_line (
                            product_line_id, product_id, variant_id,
                            product_line, product, variants
                        )
                        VALUES %s
                        ON CONFLICT (product_line_id, product_id, variant_id)
                        DO NOTHING
                        """,
                        rows,
                        page_size=2000,
                    )
                    inserted = cur.rowcount if cur.rowcount >= 0 else len(rows)
                    skipped = len(rows) - inserted
                conn.commit()
        except Exception:
            raise

        return {
            "ok": True,
            "message": f"Inserted {inserted} rows mới, {skipped} rows đã tồn tại (skipped)",
            "imported": inserted,
            "skipped": skipped,
            "total_in_file": len(rows),
            "duplicates_in_file": dup_rows,
            "errors": [],
        }
    except Exception as e:
        logger.exception("Error in product-catalog upload")
        import traceback
        print("Error in product-catalog upload:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


class ProductCatalogRow(BaseModel):
    product_line_id: str
    product_id: str
    variant_id: str
    product_line: Optional[str] = None
    product: Optional[str] = None
    variants: Optional[str] = None


@router.post("/product-catalog/import-row")
def import_product_catalog_row(row: ProductCatalogRow):
    """Import a single product catalog row."""
    try:
        existing = run_query("""
            SELECT dim_product_line_key FROM dim_product_line
            WHERE product_line_id = %s AND product_id = %s AND variant_id = %s
        """, (row.product_line_id, row.product_id, row.variant_id))

        if not existing.empty:
            execute_query("""
                UPDATE dim_product_line
                SET product_line = %s, product = %s, variants = %s
                WHERE product_line_id = %s AND product_id = %s AND variant_id = %s
            """, (
                row.product_line, row.product, row.variants,
                row.product_line_id, row.product_id, row.variant_id
            ))
            return {"ok": True, "message": "Updated existing row", "action": "update"}
        else:
            execute_query("""
                INSERT INTO dim_product_line (
                    product_line_id, product_id, variant_id,
                    product_line, product, variants
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                row.product_line_id, row.product_id, row.variant_id,
                row.product_line, row.product, row.variants
            ))
            return {"ok": True, "message": "Inserted new row", "action": "insert"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error importing row: {str(e)}")
