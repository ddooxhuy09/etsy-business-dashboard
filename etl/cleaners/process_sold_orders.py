import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging


from config import DATE_FORMATS, DATA_FILES, EXCHANGE_RATE
from etl.utils_core import (
    clean_date_to_yyyymmdd, 
    clean_currency_amount, 
    setup_logging, convert_columns_to_snake_case, ensure_proper_data_types
)

def clean_sold_orders_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean sold orders data for database loading"""
    logger = setup_logging()
    logger.info("🔄 Cleaning sold orders data...")
    
    df_clean = df.copy()
    
    # Replace missing value indicators
    df_clean = df_clean.replace(["--", "N/A", "", " "], np.nan)

    # Split SKU list-like field
    if 'SKU' in df_clean.columns:
        df_clean['SKU'] = df_clean['SKU'].astype(str).where(~df_clean['SKU'].isna(), '').str.split(',')
    
    # Clean date columns
    date_columns = ['Sale Date', 'Order Date', 'Ship Date', 'Date Shipped']
    for col in date_columns:
        if col in df_clean.columns:
            df_clean[col] = pd.to_datetime(df_clean[col], format=DATE_FORMATS['sold_orders'], errors='coerce')
    
    # Clean numeric columns
    numeric_columns = ['Order Value', 'Discount Amount', 'Order Total', 'Number of Items', 'Card Processing Fees', 'Order Net']
    for col in numeric_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(clean_currency_amount)
    
    # Convert amounts to USD using exchange rate (multiply by 100 then divide by exchange rate)
    try:
        columns_to_convert = ['Card Processing Fees', 'Order Net']
        for col in columns_to_convert:
            if col in df_clean.columns:
                df_clean[col] = (df_clean[col] * 100 / EXCHANGE_RATE).round(2)
    except Exception as e:
        logger.warning(f"Could not convert to USD: {e}")
    
    # Clean text columns
    text_columns = ['Full Name', 'First Name', 'Last Name', 'Buyer', 'Order Status']
    for col in text_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].str.strip().str.replace(r'\s+', ' ', regex=True)  # Vectorized
    
    # Standardize order status
    if 'Order Status' in df_clean.columns:
        status_mapping = {
            'completed': 'Completed',
            'processing': 'Processing', 
            'shipped': 'Shipped',
            'delivered': 'Delivered',
            'cancelled': 'Cancelled',
            'refunded': 'Refunded'
        }
        df_clean['Order Status'] = df_clean['Order Status'].str.lower().map(status_mapping).fillna(df_clean['Order Status'])
    
    # Clean address fields
    address_columns = ['Address1', 'Address2', 'City', 'State', 'Country', 'Zip']
    for col in address_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].str.strip().str.replace(r'\s+', ' ', regex=True)  # Vectorized
    
    # Convert column names to snake_case
    df_clean = convert_columns_to_snake_case(df_clean)
    
    # Ensure proper data types for Parquet
    df_clean = ensure_proper_data_types(df_clean, 'sold_orders')
    
    logger.info(f"✅ Cleaned {len(df_clean)} sold orders records")
    return df_clean

# Removed standalone process() as it's handled by pipeline