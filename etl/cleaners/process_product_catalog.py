"""
Product Catalog Data Processor
Map và clean product_catalog.csv trước khi build dim_product_catalog.

CSV: Product line ID, Product line, Product ID, Product, Variant ID, Variants
→ product_line_id, product_line_name, product_id, product_name, variant_id, variant_name

product_code được tính trong DB: (product_line_id || '_' || product_id || '_' || variant_id) STORED.
"""

import pandas as pd
import logging

from etl.utils_core import setup_logging, clean_text_field

# Map cột CSV → cột dim (VARCHAR 50: id, VARCHAR 200: name)
COLUMN_MAP = {
    "Product line ID": "product_line_id",   # VARCHAR(50)
    "Product line": "product_line_name",    # VARCHAR(200)
    "Product ID": "product_id",             # VARCHAR(50)
    "Product": "product_name",              # VARCHAR(200)
    "Variant ID": "variant_id",             # VARCHAR(50)
    "Variants": "variant_name",             # VARCHAR(200)
}


def clean_product_catalog_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean product_catalog: đổi tên cột, chuẩn hóa text, bỏ dòng thiếu natural key, bỏ trùng."""
    logger = setup_logging()
    logger.info("🔄 Cleaning product_catalog data...")

    out = df.copy()

    # 1. Đổi tên cột
    for old, new in COLUMN_MAP.items():
        if old in out.columns:
            out = out.rename(columns={old: new})
        elif new not in out.columns:
            out[new] = None

    # 2. Chuẩn hóa IDs (VARCHAR 50), ép sang str
    for col in ["product_line_id", "product_id", "variant_id"]:
        if col not in out.columns:
            out[col] = None
        out[col] = out[col].astype(str).replace(["nan", "NaN", ""], None)
        out[col] = out[col].apply(lambda x: clean_text_field(x, 50) if (pd.notna(x) and str(x).strip()) else None)

    # 3. Chuẩn hóa tên (VARCHAR 200)
    for col in ["product_line_name", "product_name", "variant_name"]:
        if col not in out.columns:
            out[col] = None
        out[col] = out[col].apply(lambda x: clean_text_field(x, 200) if pd.notna(x) else None)

    # 4. Bỏ dòng thiếu natural key (product_line_id, product_id, variant_id NOT NULL)
    before = len(out)
    out = out.dropna(subset=["product_line_id", "product_id", "variant_id"], how="any")
    dropped = before - len(out)
    if dropped:
        logger.info(f"   Dropped {dropped} rows with null in (product_line_id, product_id, variant_id)")

    # 5. Bỏ trùng theo natural key (khớp constraint uq_product_catalog_natural_key)
    out = out.drop_duplicates(subset=["product_line_id", "product_id", "variant_id"], keep="first")
    logger.info(f"✅ product_catalog: {len(out):,} rows (product_code do DB generate)")

    return out[list(COLUMN_MAP.values())]
