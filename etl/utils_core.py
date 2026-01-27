"""
Core utility functions used by ETL cleaners/builders (moved from src.core.utils).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def setup_logging(name: str = "etl") -> logging.Logger:
    """Return a logger with a simple console handler (idempotent)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    return logger


def clean_text_field(value: Any, max_len: Optional[int] = None) -> Optional[str]:
    if value is None or (isinstance(value, float) and (np.isnan(value) or not np.isfinite(value))):
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    s = re.sub(r"\s+", " ", s)
    if max_len is not None:
        s = s[:max_len]
    return s


def clean_currency_amount(value: Any) -> float:
    """Parse a currency-ish string to float; returns 0.0 on empty."""
    if value is None or (isinstance(value, float) and (np.isnan(value) or not np.isfinite(value))):
        return 0.0
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "--"}:
        return 0.0
    s = s.replace(",", "")
    s = re.sub(r"[₫đ$€£]", "", s)
    s = s.replace("(", "-").replace(")", "")
    try:
        return float(s)
    except Exception:
        m = re.search(r"-?\d+(\.\d+)?", s)
        return float(m.group(0)) if m else 0.0


def clean_date_to_yyyymmdd(series: pd.Series, date_format: str) -> pd.Series:
    """Convert a date column to YYYY-MM-DD (string)."""
    dt = pd.to_datetime(series, format=date_format, errors="coerce")
    return dt.dt.strftime("%Y-%m-%d")


def convert_columns_to_snake_case(df: pd.DataFrame) -> pd.DataFrame:
    def _snake(s: str) -> str:
        s2 = re.sub(r"[^\w\s]", " ", s)
        s2 = re.sub(r"\s+", " ", s2).strip().lower()
        s2 = s2.replace(" ", "_")
        s2 = re.sub(r"_+", "_", s2)
        return s2

    out = df.copy()
    out.columns = [_snake(c) for c in out.columns]
    return out


def ensure_proper_data_types(df: pd.DataFrame, data_type: str = "") -> pd.DataFrame:
    """Lightweight dtype cleanup; keep as-is for PostgreSQL loading."""
    return df


def extract_id_from_info(info: Any) -> Optional[tuple]:
    """
    Best-effort extraction for statement Info column.
    Returns tuple(extracted_id, id_type, description) or None.
    """
    if info is None or (isinstance(info, float) and np.isnan(info)):
        return None
    s = str(info)
    m = re.search(r"(order|order id|#)\s*[:#]?\s*(\d+)", s, re.IGNORECASE)
    if m:
        return (m.group(2), "order_id", s)
    m = re.search(r"(listing|listing id)\s*[:#]?\s*(\d+)", s, re.IGNORECASE)
    if m:
        return (m.group(2), "listing_id", s)
    m = re.search(r"(transaction|transaction id)\s*[:#]?\s*(\d+)", s, re.IGNORECASE)
    if m:
        return (m.group(2), "transaction_id", s)
    return None


def extract_product_variations(variations: Any) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {"size": None, "style": None, "color": None, "material": None}
    if variations is None or (isinstance(variations, float) and np.isnan(variations)):
        return out
    s = str(variations)
    parts = re.split(r"[;,]\s*", s)
    for p in parts:
        if ":" in p:
            k, v = p.split(":", 1)
            k = k.strip().lower()
            v = v.strip()
            if "size" in k:
                out["size"] = v
            elif "style" in k:
                out["style"] = v
            elif "color" in k or "colour" in k:
                out["color"] = v
            elif "material" in k:
                out["material"] = v
    return out


def get_schema_for_dataframe(data_type: str, df: pd.DataFrame):
    """Optional helper for Parquet writing in original project; not required for PostgreSQL."""
    return None

