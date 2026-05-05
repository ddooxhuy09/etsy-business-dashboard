"""
Sold Order Items Data Processor - Clean and Load to PostgreSQL
Process order items for fact_sales and dim_product tables
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging


from config import DATE_FORMATS
from etl.utils_core import (
    clean_date_to_yyyymmdd, 
    clean_currency_amount, 
    setup_logging, convert_columns_to_snake_case,
    ensure_proper_data_types, ensure_text_ids
)

def clean_sold_order_items_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean sold order items data for database loading"""
    logger = setup_logging()
    logger.info("🔄 Cleaning sold order items data...")
    
    df_clean = df.copy()
    
    # Replace missing value indicators
    df_clean = df_clean.replace(["--", "N/A", "", " "], np.nan)
    
    # Clean date columns with mixed formats
    # - 'Sale Date': mm/dd/yy
    # - 'Date Paid' and 'Date Shipped': mm/dd/YYYY
    if 'Sale Date' in df_clean.columns:
        df_clean['Sale Date'] = pd.to_datetime(df_clean['Sale Date'], format=DATE_FORMATS['sold_items'], errors='coerce')
    if 'Date Paid' in df_clean.columns:
        df_clean['Date Paid'] = pd.to_datetime(df_clean['Date Paid'], format=DATE_FORMATS['sold_items_paid_shipped'], errors='coerce')
    if 'Date Shipped' in df_clean.columns:
        df_clean['Date Shipped'] = pd.to_datetime(df_clean['Date Shipped'], format=DATE_FORMATS['sold_items_paid_shipped'], errors='coerce')
    
    # Clean numeric columns
    numeric_columns = ['Price', 'Quantity', 'Total', 'Item Total']
    for col in numeric_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(clean_currency_amount)
    
    # Clean text columns
    text_columns = ['Title', 'Category', 'Materials', 'Tags', 'Item Name', 'Description']
    for col in text_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].str.strip().str.replace(r'\s+', ' ', regex=True)  # Vectorized
            # Remove invalid characters
            if col in ['Title', 'Item Name', 'Description']:
                df_clean[col] = df_clean[col].str.replace(r'[^\w\s\.\,\!\?\&\'\"\(\)\-]', '', regex=True)
    
    # Convert column names to snake_case
    df_clean = convert_columns_to_snake_case(df_clean)
    
    # Ensure proper data types for Parquet
    df_clean = ensure_proper_data_types(df_clean, 'sold_order_items')
    df_clean = ensure_text_ids(df_clean)
    
    logger.info(f"✅ Cleaned {len(df_clean)} sold order items records")
    return df_clean

# Removed standalone process() as it's handled by pipeline
