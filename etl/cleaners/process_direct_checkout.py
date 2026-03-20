"""
Direct Checkout Data Processor - Clean and Load to PostgreSQL
Process direct checkout payment data for fact_financials table
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging


from config import DATE_FORMATS, EXCHANGE_RATE
from etl.utils_core import (
    clean_date_to_yyyymmdd, clean_currency_amount, setup_logging, convert_columns_to_snake_case, ensure_proper_data_types
)

def clean_direct_checkout_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean direct checkout data for database loading"""
    logger = setup_logging()
    logger.info("🔄 Cleaning direct checkout data...")
    
    df_clean = df.copy()
    
    # Replace missing value indicators
    df_clean = df_clean.replace(["--", "N/A", "", " "], np.nan)
    
    # Clean date columns
    if 'Order Date' in df_clean.columns:
        df_clean['Order Date'] = pd.to_datetime(df_clean['Order Date'], format=DATE_FORMATS['direct_checkout'], errors='coerce')
    
    # Clean numeric columns
    numeric_columns = ['Gross Amount', 'Fees', 'Net Amount', 'Posted Gross', 'Posted Fees', 'Posted Net']
    for col in numeric_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(clean_currency_amount)
    
    # Convert VND to USD using exchange rate (multiply by 100 then divide by exchange rate)
    if 'Currency' in df_clean.columns:
        try:
            vnd_mask = df_clean['Currency'].astype(str).str.upper().eq('VND')
            if vnd_mask.any():
                # Convert specified columns from VND to USD
                vnd_columns = ['Gross Amount', 'Fees', 'Net Amount', 'Posted Gross', 'Posted Fees', 'Posted Net']
                for col in vnd_columns:
                    if col in df_clean.columns:
                        df_clean.loc[vnd_mask, col] = (
                            df_clean.loc[vnd_mask, col] * 100 / EXCHANGE_RATE
                        ).round(2)
                
                # Update currency to USD
                df_clean.loc[vnd_mask, 'Currency'] = 'USD'
        except Exception as e:
            logger.warning(f"Could not convert VND to USD: {e}")
    
    # Convert column names to snake_case
    df_clean = convert_columns_to_snake_case(df_clean)
    
    # Ensure proper data types for Parquet
    df_clean = ensure_proper_data_types(df_clean, 'direct_checkout')
    
    logger.info(f"✅ Cleaned {len(df_clean)} direct checkout records")
    return df_clean

# Removed standalone process() as it's handled by pipeline