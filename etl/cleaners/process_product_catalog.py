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

# Map normalized (lowercase + strip) raw column name → dim column name
# Hỗ trợ cả format cũ (Product line, Product, Variants)
# và format mới (Product Line Name, Product Name, Variant Name)
_NORM_COLUMN_MAP = {
    "product line id":   "product_line_id",    # VARCHAR(50)
    "product line name": "product_line_name",  # VARCHAR(200) — new format
    "product line":      "product_line_name",  # VARCHAR(200) — legacy alias
    "product id":        "product_id",         # VARCHAR(50)
    "product name":      "product_name",       # VARCHAR(200) — new format
    "product":           "product_name",       # VARCHAR(200) — legacy alias
    "variant id":        "variant_id",         # VARCHAR(50)
    "variant name":      "variant_name",       # VARCHAR(200) — new format
    "variants":          "variant_name",       # VARCHAR(200) — legacy alias
}

OUTPUT_COLS = [
    "product_line_id", "product_line_name",
    "product_id", "product_name",
    "variant_id", "variant_name",
]

# Keep COLUMN_MAP alias for backward compatibility
COLUMN_MAP = {
    "Product line ID": "product_line_id",
    "Product line": "product_line_name",
    "Product ID": "product_id",
    "Product": "product_name",
    "Variant ID": "variant_id",
    "Variants": "variant_name",
}


def clean_product_catalog_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean product_catalog: đổi tên cột, chuẩn hóa text, bỏ dòng thiếu natural key, bỏ trùng.
    Hỗ trợ cả format cũ và mới (case-insensitive column matching).
    """
    logger = setup_logging()
    logger.info("🔄 Cleaning product_catalog data...")

    out = df.copy()

    # 1. Strip whitespace khỏi tên cột (vd: "Product Line ID " → "Product Line ID")
    out.columns = [c.strip() if isinstance(c, str) else c for c in out.columns]

    # 2. Đổi tên cột — case-insensitive matching, ưu tiên match dài nhất trước
    rename_map = {}
    assigned_targets = set()
    # Sort by length desc để "product line name" được match trước "product line"
    sorted_norm = sorted(_NORM_COLUMN_MAP.items(), key=lambda x: -len(x[0]))
    for col in out.columns:
        norm = col.strip().lower()
        for norm_key, target in sorted_norm:
            if norm == norm_key and target not in assigned_targets:
                rename_map[col] = target
                assigned_targets.add(target)
                break
    out = out.rename(columns=rename_map)

    # Đảm bảo tất cả output columns tồn tại
    for col in OUTPUT_COLS:
        if col not in out.columns:
            out[col] = None

    # 3. Chuẩn hóa IDs (VARCHAR 50), ép sang str
    for col in ["product_line_id", "product_id", "variant_id"]:
        out[col] = out[col].astype(str).replace(["nan", "NaN", ""], None)
        out[col] = out[col].apply(lambda x: clean_text_field(x, 50) if (pd.notna(x) and str(x).strip()) else None)

    # 4. Chuẩn hóa tên (VARCHAR 200)
    for col in ["product_line_name", "product_name", "variant_name"]:
        out[col] = out[col].apply(lambda x: clean_text_field(x, 200) if pd.notna(x) else None)

    # 5. Bỏ dòng thiếu natural key (product_line_id, product_id, variant_id NOT NULL)
    before = len(out)
    out = out.dropna(subset=["product_line_id", "product_id", "variant_id"], how="any")
    dropped = before - len(out)
    if dropped:
        logger.info(f"   Dropped {dropped} rows with null in (product_line_id, product_id, variant_id)")

    # 6. Bỏ trùng theo natural key (khớp constraint uq_product_catalog_natural_key)
    out = out.drop_duplicates(subset=["product_line_id", "product_id", "variant_id"], keep="first")
    logger.info(f"✅ product_catalog: {len(out):,} rows (product_code do DB generate)")

    return out[OUTPUT_COLS]
