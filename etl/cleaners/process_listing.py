"""
Listing Data Processor - Clean and Load to PostgreSQL
Process listing data for dim_listing table
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging

from etl.utils_core import setup_logging, convert_columns_to_snake_case, ensure_proper_data_types, ensure_text_ids


def clean_listing_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean listing data for database loading"""
    logger = setup_logging()
    logger.info("Cleaning listing data...")

    df_clean = df.copy()

    # Handle missing values in text columns
    text_cols = ['TITLE', 'DESCRIPTION', 'TAGS', 'MATERIALS', 'SKU']
    for col in text_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna('')

    # Trim leading/trailing spaces from the title
    if 'TITLE' in df_clean.columns:
        df_clean['TITLE'] = df_clean['TITLE'].str.strip()

    # Remove extra spaces and unwanted special characters from description
    if 'DESCRIPTION' in df_clean.columns:
        df_clean['DESCRIPTION'] = df_clean['DESCRIPTION'].str.replace(r'[ \t]+', ' ', regex=True)
        df_clean['DESCRIPTION'] = df_clean['DESCRIPTION'].str.replace(r'[^\w\s\.\,\!\?\&\'\"\(\)\-\n]', '', regex=True)

    # Split list-like columns and remove extra spaces
    if 'TAGS' in df_clean.columns:
        df_clean['tags_list'] = df_clean['TAGS'].astype(str).str.split(',').apply(
            lambda x: [i.strip() for i in x] if isinstance(x, list) else x
        )
    if 'MATERIALS' in df_clean.columns:
        df_clean['materials_list'] = df_clean['MATERIALS'].astype(str).str.split(',').apply(
            lambda x: [i.strip() for i in x] if isinstance(x, list) else x
        )
    if 'SKU' in df_clean.columns:
        df_clean['SKU'] = df_clean['SKU'].astype(str).str.split(',').apply(
            lambda x: [i.strip() for i in x] if isinstance(x, list) else x
        )

    # Convert column names to snake_case
    df_clean = convert_columns_to_snake_case(df_clean)

    # Ensure price and quantity are numeric
    if 'price' in df_clean.columns:
        df_clean['price'] = pd.to_numeric(df_clean['price'].replace('', np.nan), errors='coerce')
    if 'quantity' in df_clean.columns:
        df_clean['quantity'] = pd.to_numeric(df_clean['quantity'].replace('', np.nan), errors='coerce')
        df_clean['quantity'] = df_clean['quantity'].fillna(0).astype(int)

    # Ensure proper data types for Parquet
    df_clean = ensure_proper_data_types(df_clean, 'listing')
    df_clean = ensure_text_ids(df_clean)

    return df_clean
