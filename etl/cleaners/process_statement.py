"""
Statement Data Processor - Clean and Load to PostgreSQL
Process financial statements for fact_financials table
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging


from config import DATE_FORMATS, DATA_FILES, EXCHANGE_RATE
from etl.utils_core import (
     clean_date_to_yyyymmdd, 
    extract_id_from_info, clean_currency_amount,
     setup_logging, convert_columns_to_snake_case,
    ensure_proper_data_types
)

def clean_statement_currency_columns(series: pd.Series) -> pd.Series:
    """Clean currency columns specifically for statement data"""
    # Replace "--" with None/NaN first
    cleaned = series.replace("--", np.nan)
    
    # Convert to string and remove currency symbols and commas
    cleaned = cleaned.astype(str).str.replace(",", "", regex=False)
    
    # Handle negative values: preserve minus sign before currency symbol
    # Replace patterns like -₫123 with -123, ₫123 with 123
    cleaned = cleaned.str.replace(r"-₫", "-", regex=True)
    cleaned = cleaned.str.replace(r"₫", "", regex=True)
    cleaned = cleaned.str.replace(r"-đ", "-", regex=True)
    cleaned = cleaned.str.replace(r"đ", "", regex=True)
    
    return cleaned

def clean_statement_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean statement data for database loading"""
    logger = setup_logging()
    logger.info("🔄 Cleaning statement data...")
    
    df_clean = df.copy()
    
    # Replace missing value indicators
    df_clean = df_clean.replace(["--", "N/A", "", " "], np.nan)
    df_clean = df_clean.infer_objects(copy=False)
    
    # Clean date column and convert to yyyyMMdd format
    if 'Date' in df_clean.columns:
        df_clean['Date'] = clean_date_to_yyyymmdd(df_clean['Date'], DATE_FORMATS['statement'])
    
    # Clean numeric columns with specific processing for statement data
    numeric_columns = ['Amount', 'Fees & Taxes', 'Net', 'Tax Details']
    for col in numeric_columns:
        if col in df_clean.columns:
            df_clean[col] = clean_statement_currency_columns(df_clean[col])
    
    # After cleaning, convert VND amounts to USD by dividing by exchange rate
    if 'Currency' in df_clean.columns:
        try:
            vnd_mask = df_clean['Currency'].astype(str).str.upper().eq('VND')
            if vnd_mask.any():
                for col in numeric_columns:
                    if col in df_clean.columns:
                        df_clean.loc[vnd_mask, col] = pd.to_numeric(
                            df_clean.loc[vnd_mask, col], errors='coerce'
                        ) / EXCHANGE_RATE
                # Round to 2 decimals
                for col in numeric_columns:
                    if col in df_clean.columns:
                        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').round(2)
                # Update currency to USD
                df_clean.loc[vnd_mask, 'Currency'] = 'USD'
        except Exception as e:
            logger.warning(f"Could not convert statement VND to USD: {e}")
    
    # Clean text columns (skip Type, Title, Info to keep original content)
    # Note: Type, Title, Info columns are kept as-is without cleaning
    
    # Extract transaction information
    if 'Info' in df_clean.columns:
        logger.info("Extracting transaction IDs from Info column...")
        
        extracted_info = df_clean['Info'].apply(extract_id_from_info)
        df_clean['extracted_id'] = extracted_info.apply(lambda x: x[0] if x else None)
        df_clean['id_type'] = extracted_info.apply(lambda x: x[1] if x else None)
        df_clean['info_description'] = extracted_info.apply(lambda x: x[2] if x else None)
    
    # Add financial categorization
    df_clean['revenue_type'] = df_clean['Type'].apply(categorize_revenue_type)
    df_clean['fee_type'] = df_clean['Type'].apply(categorize_fee_type)
    
    # Convert column names to snake_case
    df_clean = convert_columns_to_snake_case(df_clean)
    
    # Ensure proper data types for Parquet
    df_clean = ensure_proper_data_types(df_clean, 'statement')
    
    logger.info(f"✅ Cleaned {len(df_clean)} statement records")
    return df_clean

def categorize_revenue_type(transaction_type: str) -> str:
    """Categorize revenue type from transaction type"""
    if pd.isna(transaction_type):
        return 'Unknown'
    
    transaction_type = str(transaction_type).lower()
    
    if any(word in transaction_type for word in ['sale', 'order', 'item']):
        return 'Sale'
    elif any(word in transaction_type for word in ['deposit', 'payout']):
        return 'Deposit'
    elif any(word in transaction_type for word in ['refund', 'return']):
        return 'Refund'
    elif any(word in transaction_type for word in ['fee', 'charge']):
        return 'Fee'
    elif any(word in transaction_type for word in ['tax']):
        return 'Tax'
    else:
        return 'Other'

def categorize_fee_type(transaction_type: str) -> str:
    """Categorize fee type from transaction type"""
    if pd.isna(transaction_type):
        return None
    
    transaction_type = str(transaction_type).lower()
    
    if 'transaction' in transaction_type:
        return 'Transaction Fee'
    elif 'listing' in transaction_type:
        return 'Listing Fee'
    elif 'payment' in transaction_type:
        return 'Payment Processing'
    elif 'advertising' in transaction_type:
        return 'Advertising'
    elif 'regulatory' in transaction_type:
        return 'Regulatory Fee'
    else:
        return None

# Removed standalone process() as it's handled by pipeline