"""
Deposits Data Processor - Clean and Load to PostgreSQL
Process deposit data for fact_financials table
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging

from config import DATE_FORMATS, EXCHANGE_RATE
from etl.utils_core import ( clean_date_to_yyyymmdd, 
    clean_currency_amount, setup_logging, convert_columns_to_snake_case, ensure_proper_data_types
)

def clean_deposits_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean deposits data for database loading"""
    logger = setup_logging()
    logger.info("🔄 Cleaning deposits data...")
    
    df_clean = df.copy()
    
    # Replace missing value indicators
    df_clean = df_clean.replace(["--", "N/A", "", " "], np.nan)
    
    # Clean date columns
    if 'Date' in df_clean.columns:
        df_clean['Date'] = clean_date_to_yyyymmdd(df_clean['Date'], DATE_FORMATS['deposits'])
    

        df_clean['Amount'] = df_clean['Amount'].apply(clean_currency_amount)
    
    # Convert VND to USD using exchange rate and update currency
    if 'Currency' in df_clean.columns and 'Amount' in df_clean.columns:
        try:
            vnd_mask = df_clean['Currency'].astype(str).str.upper().eq('VND')
            if vnd_mask.any():
                df_clean.loc[vnd_mask, 'Amount'] = (
                    df_clean.loc[vnd_mask, 'Amount'] / EXCHANGE_RATE
                ).round(2)
                df_clean.loc[vnd_mask, 'Currency'] = 'USD'
        except Exception as e:
            logger.warning(f"Could not convert VND to USD: {e}")
    
    # Convert column names to snake_case
    df_clean = convert_columns_to_snake_case(df_clean)
    
    # Ensure proper data types for Parquet
    df_clean = ensure_proper_data_types(df_clean, 'deposits')
    
    logger.info(f"✅ Cleaned {len(df_clean)} deposits records")
    return df_clean

# Removed standalone process() as it's handled by pipeline