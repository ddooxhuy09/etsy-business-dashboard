"""
Statement Data Processor - Clean and Load to PostgreSQL
Process financial statements for fact_statement.
"""

import re

import numpy as np
import pandas as pd

from config import DATE_FORMATS, EXCHANGE_RATE
from etl.utils_core import (
    clean_date_to_yyyymmdd,
    convert_columns_to_snake_case,
    ensure_proper_data_types,
    setup_logging,
)


def clean_statement_currency_columns(series: pd.Series) -> pd.Series:
    """Clean Etsy statement currency columns."""
    cleaned = series.replace("--", "0")
    cleaned = cleaned.astype(str).str.replace(",", "", regex=False)
    cleaned = cleaned.str.replace(r"-₫", "-", regex=True)
    cleaned = cleaned.str.replace(r"₫", "", regex=True)
    cleaned = cleaned.str.replace(r"-đ", "-", regex=True)
    cleaned = cleaned.str.replace(r"đ", "", regex=True)
    cleaned = pd.to_numeric(cleaned, errors="coerce").fillna(0.0)
    return cleaned


def extract_ref_order_id_from_statement(info, title):
    """Extract order ID from Etsy statement Info or Title text."""
    patterns = [
        r"\border\s*#\s*(\d+)",
        r"\border\s*:\s*(\d+)",
        r"\bpayment\s+for\s+order\s*#\s*(\d+)",
        r"\bcharge\s+for\s+refund\s+(\d+)",
        r"\brefund\s+for\s+order\s*#\s*(\d+)",
    ]

    for value in [info, title]:
        if pd.isna(value):
            continue
        text = str(value)
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def clean_statement_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean statement data for fact_statement loading."""
    logger = setup_logging()
    logger.info("Cleaning statement data...")

    df_clean = df.copy()
    df_clean = df_clean.replace(["--", "N/A", "", " "], np.nan)
    df_clean = df_clean.infer_objects(copy=False)

    if "Date" in df_clean.columns:
        df_clean["Date"] = clean_date_to_yyyymmdd(df_clean["Date"], DATE_FORMATS["statement"])

    for col in ["Amount", "Fees & Taxes", "Net"]:
        if col in df_clean.columns:
            df_clean[col] = clean_statement_currency_columns(df_clean[col]) / EXCHANGE_RATE

    if "Tax Details" in df_clean.columns:
        df_clean["Tax Details"] = df_clean["Tax Details"].where(df_clean["Tax Details"].notna(), None)

    df_clean["ref_order_id"] = df_clean.apply(
        lambda row: extract_ref_order_id_from_statement(row.get("Info"), row.get("Title")),
        axis=1,
    )

    df_clean = convert_columns_to_snake_case(df_clean)

    if "ref_order_id" in df_clean.columns:
        df_clean["ref_order_id"] = pd.to_numeric(df_clean["ref_order_id"], errors="coerce").astype("Int64")

    output_columns = [
        "date",
        "type",
        "title",
        "info",
        "amount",
        "fees_taxes",
        "net",
        "tax_details",
        "ref_order_id",
    ]
    for col in output_columns:
        if col not in df_clean.columns:
            df_clean[col] = None

    df_clean = ensure_proper_data_types(df_clean, "statement")

    logger.info(f"Cleaned {len(df_clean)} statement records")
    return df_clean[output_columns]


# Removed standalone process() as it's handled by pipeline
