"""
Bank Transactions Data Processor - Clean and Load to PostgreSQL
Process bank transaction statements with product parsing
"""

import pandas as pd
import numpy as np
import re
import logging
from typing import Optional, Set

from config import DATE_FORMATS, EXCHANGE_RATE
from etl.utils_core import (
    clean_date_to_yyyymmdd, 
    setup_logging, 
    convert_columns_to_snake_case,
    ensure_proper_data_types,
    ensure_text_ids
)


def get_allowed_pl_accounts() -> Set[str]:
    """Load valid PL account numbers from dim_pl_accounts."""
    logger = setup_logging()
    try:
        from core.database import run_query

        df = run_query(
            "SELECT pl_account_number FROM dim_pl_accounts WHERE pl_account_number IS NOT NULL",
            None,
        )
    except Exception as e:
        logger.warning(f"Could not load PL accounts from dim_pl_accounts: {e}")
        return set()

    if df is None or df.empty or 'pl_account_number' not in df.columns:
        logger.warning("No PL accounts found in dim_pl_accounts")
        return set()

    return {
        str(value).strip().upper()
        for value in df['pl_account_number'].dropna()
        if str(value).strip()
    }


def parse_description(description: str, allowed_pl_accounts: Optional[Set[str]] = None) -> dict:
    """
    Parse description to extract product information and pl_account_number.

    Supported formats:
      Case A — 3 segments, 3rd is PL account (no variant):
        "GEMIMI_DH69251_6414 mua tool..."
        → product_line=GEMIMI, product=DH69251, variant=None, pl=6414

      Case B — 3 segments + 4th PL account via underscore or space:
        "DEF_MG01107417_03 6221 Ck mua yarn..."
        "TBL_BLO_TO01_6222 chart ..."
        → product_line=DEF, product=MG01107417, variant=03, pl=6221

      Case C — 3 segments only, no PL account:
        "1_1_1"
        → product_line=1, product=1, variant=1, pl=None

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

    if allowed_pl_accounts is None:
        allowed_pl_accounts = get_allowed_pl_accounts()

    pattern = r'([A-Z0-9]+)_([A-Z0-9]+)_([A-Z0-9]+)(?:[_\s]+(\d{4}))?'
    match = re.search(pattern, description, flags=re.IGNORECASE)

    if match:
        seg3 = match.group(3).upper()
        seg4 = match.group(4)  # may be None

        result['parsed_product_line_id'] = match.group(1).upper()
        result['parsed_product_id'] = match.group(2).upper()

        if seg3 in allowed_pl_accounts:
            # Case A: 3rd segment IS the PL account number — no variant
            result['pl_account_number'] = seg3
            result['parsed_variant_id'] = None
        else:
            # Case B/C: 3rd segment is the variant
            result['parsed_variant_id'] = seg3
            if seg4 and seg4 in allowed_pl_accounts:
                result['pl_account_number'] = seg4

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
    allowed_pl_accounts = get_allowed_pl_accounts()
    logger.info(f"Loaded {len(allowed_pl_accounts)} PL accounts from dim_pl_accounts")
    parsed_data = df_clean[desc_col].apply(lambda value: parse_description(value, allowed_pl_accounts))
    parsed_df = pd.DataFrame(parsed_data.tolist())
    
    # Add parsed columns to dataframe
    df_clean['pl_account_number'] = parsed_df['pl_account_number']
    df_clean['parsed_product_line_id'] = parsed_df['parsed_product_line_id']
    df_clean['parsed_product_id'] = parsed_df['parsed_product_id']
    df_clean['parsed_variant_id'] = parsed_df['parsed_variant_id']
    
    # Convert column names to snake_case
    logger.info("📝 Converting column names to snake_case...")
    df_clean = convert_columns_to_snake_case(df_clean)
    
    # Translate columns from Vietnamese to standard English
    col_mapping = {
        'phat_sinh_co': 'credit_amount',
        'phat_sinh_no': 'debit_amount',
        'so_du': 'balance',
        'phat_sinh_co_credit_amount': 'credit_amount',
        'phat_sinh_no_debit_amount': 'debit_amount',
        'so_du_balance': 'balance'
    }
    df_clean = df_clean.rename(columns=col_mapping)
    
    # Clean date columns - convert to yyyyMMdd format
    # Bank transactions use format: dd/mm/yyyy (e.g., 01/01/2024)
    date_format = "%d/%m/%Y"
    date_columns = ['ngay_gd_transaction_date', 'ngay_mo_tai_khoan_opening_date', 'ngay_gd', 'ngay_mo_tai_khoan']
    for col in date_columns:
        if col in df_clean.columns:
            logger.info(f"📅 Cleaning date column: {col}")
            df_clean[col] = clean_date_to_yyyymmdd(df_clean[col], date_format)
    
    # Clean numeric columns (amounts and balance)
    numeric_columns = [
        'credit_amount',
        'debit_amount',
        'balance'
    ]
    
    for col in numeric_columns:
        if col in df_clean.columns:
            logger.info(f"💰 Cleaning numeric column: {col}")
            df_clean[col] = df_clean[col].astype(str).str.replace(',', '', regex=False)
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            df_clean[col] = df_clean[col] / EXCHANGE_RATE
    
    # Ensure proper data types
    logger.info("✅ Ensuring proper data types...")
    df_clean = ensure_proper_data_types(df_clean, 'bank_transactions')
    df_clean = ensure_text_ids(df_clean)
    
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
