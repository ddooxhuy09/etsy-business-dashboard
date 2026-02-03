"""
Bank Transactions Data Processor - Clean and Load to PostgreSQL
Process bank transaction statements with product parsing
"""

import pandas as pd
import numpy as np
import re
import logging

from config import DATE_FORMATS
from etl.utils_core import (
    clean_date_to_yyyymmdd, 
    setup_logging, 
    convert_columns_to_snake_case,
    ensure_proper_data_types
)


def parse_description(description: str) -> dict:
    """
    Parse description to extract product information and pl_account_number
    
    Pattern (expanded): {Product line ID}_{Product ID}_{Variant ID} [pl_account_number]
    - Product line / Product ID / Variant ID: chuỗi chữ hoặc số (ví dụ: DEF_MG01107417_03 hoặc 1_1_1)
    - PL account (tùy chọn): 4 digits (e.g., 6221)
    Ví dụ:
      "DEF_MG01107417_03 6221 Ck mua yarn..."
      "1_1_1"
    
    Returns dict with: pl_account_number, parsed_product_line_id, parsed_product_id, parsed_variant_id
    """
    result = {
        'pl_account_number': None,
        'parsed_product_line_id': None,
        'parsed_product_id': None,
        'parsed_variant_id': None
    }
    
    if description is None or (isinstance(description, float) and pd.isna(description)) or not isinstance(description, str):
        return result
    
    # Chỉ chấp nhận một số PL account nhất định (các TK chi phí/cogs hợp lệ)
    ALLOWED_PL_ACCOUNTS = {
        "6211", "6221", "6222", "6223", "6224", "6225",
        "6273",
        "6411", "6412", "6413", "6414",
        "6421", "6428",
    }

    pattern = r'([A-Z0-9]+)_([A-Z0-9]+)_([A-Z0-9]+)(?:\s+(\d{4}))?'
    match = re.search(pattern, description, flags=re.IGNORECASE)
    
    if match:
        result['parsed_product_line_id'] = match.group(1).upper()
        result['parsed_product_id'] = match.group(2).upper()
        result['parsed_variant_id'] = match.group(3)
        if match.group(4):
            pl_acc = match.group(4)
            # Chỉ nhận các PL account thuộc whitelist, còn lại bỏ qua (None)
            if pl_acc in ALLOWED_PL_ACCOUNTS:
                result['pl_account_number'] = pl_acc
    
    return result


def clean_bank_transactions_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean bank transactions data for database loading"""
    logger = setup_logging()
    logger.info("🔄 Cleaning bank transactions data...")
    
    df_clean = df.copy()
    
    # Replace missing value indicators
    df_clean = df_clean.replace(["--", "N/A", "", " "], np.nan)
    df_clean = df_clean.infer_objects(copy=False)
    
    # Parse Description column BEFORE converting to snake_case
    logger.info("🔍 Parsing Description column for product information...")
    # Find the Description column (it has Vietnamese characters)
    desc_col = [col for col in df_clean.columns if 'Description' in col][0]
    parsed_data = df_clean[desc_col].apply(parse_description)
    parsed_df = pd.DataFrame(parsed_data.tolist())
    
    # Add parsed columns to dataframe
    df_clean['pl_account_number'] = parsed_df['pl_account_number']
    df_clean['parsed_product_line_id'] = parsed_df['parsed_product_line_id']
    df_clean['parsed_product_id'] = parsed_df['parsed_product_id']
    df_clean['parsed_variant_id'] = parsed_df['parsed_variant_id']
    
    # Convert column names to snake_case
    logger.info("📝 Converting column names to snake_case...")
    df_clean = convert_columns_to_snake_case(df_clean)
    
    # Clean date columns - convert to yyyyMMdd format
    # Bank transactions use format: dd/mm/yyyy (e.g., 01/01/2024)
    date_format = "%d/%m/%Y"
    date_columns = ['ngay_gd_transaction_date', 'ngay_mo_tai_khoan_opening_date']
    for col in date_columns:
        if col in df_clean.columns:
            logger.info(f"📅 Cleaning date column: {col}")
            df_clean[col] = clean_date_to_yyyymmdd(df_clean[col], date_format)
    
    # Clean numeric columns (amounts and balance)
    numeric_columns = [
        'phat_sinh_co_credit_amount',
        'phat_sinh_no_debit_amount',
        'so_du_balance'
    ]
    
    for col in numeric_columns:
        if col in df_clean.columns:
            logger.info(f"💰 Cleaning numeric column: {col}")
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    
    # Ensure proper data types
    logger.info("✅ Ensuring proper data types...")
    df_clean = ensure_proper_data_types(df_clean, 'bank_transactions')
    
    # Log summary
    logger.info(f"✅ Cleaned {len(df_clean):,} bank transaction records")
    logger.info(f"📊 Columns: {list(df_clean.columns)}")
    
    # Log parsing statistics
    parsed_count = df_clean['parsed_product_line_id'].notna().sum()
    total_count = len(df_clean)
    logger.info(f"🔍 Successfully parsed {parsed_count:,} out of {total_count:,} descriptions ({parsed_count/total_count*100:.1f}%)")
    
    return df_clean


def process_bank_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main processing function for bank transactions
    
    Args:
        df: Raw bank transactions DataFrame
        
    Returns:
        Cleaned and processed DataFrame
    """
    logger = setup_logging()
    logger.info("=" * 70)
    logger.info("🏦 PROCESSING BANK TRANSACTIONS DATA")
    logger.info("=" * 70)
    
    # Clean the data
    df_processed = clean_bank_transactions_data(df)
    
    logger.info("=" * 70)
    logger.info("✅ BANK TRANSACTIONS PROCESSING COMPLETE")
    logger.info("=" * 70)
    
    return df_processed

