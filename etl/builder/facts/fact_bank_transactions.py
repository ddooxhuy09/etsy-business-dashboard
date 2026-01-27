"""
Bank Transactions Fact Table Builder
Builds bank transactions fact table from cleaned bank transactions data
"""

import pandas as pd
from datetime import datetime
import logging
from ..base_builder import BaseBuilder

logger = logging.getLogger('bank_transactions')

class BankTransactionsFactBuilder(BaseBuilder):
    """Build Bank Transactions Fact Table"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)
        # Initialize lookup dictionaries if they don't exist
        if not hasattr(self.master_keys, 'bank_accounts'):
            self.master_keys['bank_accounts'] = {}
        if not hasattr(self.master_keys, 'product_catalog'):
            self.master_keys['product_catalog'] = {}

    def build_bank_transactions_fact(
        self, 
        bank_transactions_df: pd.DataFrame,
        dim_bank_account_df: pd.DataFrame = None,
        dim_product_catalog_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        """Build Bank Transactions Fact Table with foreign keys"""
        logger.info("Building bank transactions fact table...")
        
        fact_transactions = bank_transactions_df.copy()
        
        # STEP 1: Map column names and prepare data
        logger.info("Step 1: Mapping column names...")
        
        # Build dynamic column mapping based on actual column names
        # (handles encoding issues in column names)
        column_mapping = {}
        
        for col in fact_transactions.columns:
            col_lower = col.lower()
            # Keep parsed columns and pl_account_number as-is
            if col in ['pl_account_number', 'parsed_product_line_id', 'parsed_product_id', 'parsed_variant_id']:
                continue  # No mapping needed, keep original name
            # Map other columns
            elif 'reference' in col_lower:
                column_mapping[col] = 'reference_number'
            elif 'account_number' in col_lower and 'khoan' in col_lower:  # Vietnamese 'tài khoản'
                column_mapping[col] = 'account_number'
            elif 'account_name' in col_lower:
                column_mapping[col] = 'account_name'
            elif 'credit' in col_lower:
                column_mapping[col] = 'credit_amount'
            elif 'debit' in col_lower:
                column_mapping[col] = 'debit_amount'
            elif 'balance' in col_lower or 'du' in col_lower:  # 'số dư'
                column_mapping[col] = 'balance_after_transaction'
            elif 'description' in col_lower or 'giai' in col_lower:  # 'diễn giải'
                column_mapping[col] = 'transaction_description'
        
        # Rename columns
        fact_transactions = fact_transactions.rename(columns=column_mapping)
        logger.info(f"   Columns after rename: {list(fact_transactions.columns)}")
        
        # STEP 2: Build lookup dictionaries for foreign keys
        logger.info("Step 2: Building lookup dictionaries...")
        
        # Build bank account lookup
        if dim_bank_account_df is not None:
            for _, row in dim_bank_account_df.iterrows():
                account_number = str(row['account_number']).strip()
                self.master_keys['bank_accounts'][account_number] = row['bank_account_key']
            logger.info(f"   Loaded {len(self.master_keys['bank_accounts'])} bank accounts")
        
        # Build product catalog lookup
        if dim_product_catalog_df is not None:
            for _, row in dim_product_catalog_df.iterrows():
                # Normalize values: strip whitespace, convert to string, handle NaN
                pl_id = str(row.get('product_line_id', '')).strip() if pd.notna(row.get('product_line_id')) else ''
                p_id = str(row.get('product_id', '')).strip() if pd.notna(row.get('product_id')) else ''
                v_id = str(row.get('variant_id', '')).strip() if pd.notna(row.get('variant_id')) else ''
                composite_key = f"{pl_id}_{p_id}_{v_id}"
                self.master_keys['product_catalog'][composite_key] = row['product_catalog_key']
            logger.info(f"   Loaded {len(self.master_keys['product_catalog'])} product catalog items")
            # Log first few keys for debugging
            if len(self.master_keys['product_catalog']) > 0:
                sample_keys = list(self.master_keys['product_catalog'].keys())[:3]
                logger.info(f"   Sample product catalog keys: {sample_keys}")
        
        # STEP 3: Generate surrogate keys
        logger.info("Step 3: Generating surrogate keys...")
        fact_transactions['bank_transaction_key'] = range(
            self.key_counters.get('bank_transaction_key', 1),
            self.key_counters.get('bank_transaction_key', 1) + len(fact_transactions)
        )
        self.key_counters['bank_transaction_key'] = (
            self.key_counters.get('bank_transaction_key', 1) + len(fact_transactions)
        )
        
        # STEP 4: Generate foreign keys
        logger.info("Step 4: Generating foreign keys...")
        
        # Transaction Date Key (YYYYMMDD format as integer)
        # Find the date column - it should be one that hasn't been renamed yet
        date_cols = [col for col in fact_transactions.columns if 'gd' in col.lower() or 'date' in col.lower()]
        if date_cols:
            date_col = date_cols[0]
            fact_transactions['transaction_date_key'] = pd.to_datetime(
                fact_transactions[date_col], 
                format='%d/%m/%Y',
                errors='coerce'
            ).dt.strftime('%Y%m%d').astype('Int64')
        else:
            fact_transactions['transaction_date_key'] = None
        
        # Bank Account Key - lookup from dim_bank_account
        # Prefer explicit account number columns, avoid date columns that contain "khoan"
        account_col = None
        preferred_exact = ['account_number', 'so_tai_khoan', 'so_tk']
        for col in fact_transactions.columns:
            if col.lower() in preferred_exact:
                account_col = col
                break
        if account_col is None:
            candidates = [
                col for col in fact_transactions.columns
                if ('account' in col.lower() and 'number' in col.lower())
                or ('tai_khoan' in col.lower())
                or ('khoan' in col.lower() and 'ngay' not in col.lower() and 'date' not in col.lower())
            ]
            if candidates:
                account_col = candidates[0]

        if account_col:
            fact_transactions['bank_account_key'] = fact_transactions[account_col].apply(
                lambda x: self.master_keys['bank_accounts'].get(str(x).strip()) if pd.notna(x) else None
            )
            # Also keep standardized account_number for NOT NULL constraint
            fact_transactions['account_number'] = fact_transactions[account_col]
        else:
            fact_transactions['bank_account_key'] = None
            fact_transactions['account_number'] = None
        
        # Product Catalog Key - lookup from dim_product_catalog using parsed IDs
        # Ensure master_keys['product_catalog'] exists
        if 'product_catalog' not in self.master_keys:
            self.master_keys['product_catalog'] = {}
        
        def get_product_catalog_key(row):
            # Check if parsed columns exist
            if 'parsed_product_line_id' not in row.index or \
               'parsed_product_id' not in row.index or \
               'parsed_variant_id' not in row.index:
                return None
            
            # Normalize values: strip whitespace, convert to string, handle NaN
            pl_id = str(row.get('parsed_product_line_id', '')).strip() if pd.notna(row.get('parsed_product_line_id')) else ''
            p_id = str(row.get('parsed_product_id', '')).strip() if pd.notna(row.get('parsed_product_id')) else ''
            v_id = str(row.get('parsed_variant_id', '')).strip() if pd.notna(row.get('parsed_variant_id')) else ''
            
            # Skip if any part is empty
            if not pl_id or not p_id or not v_id:
                return None
            
            composite_key = f"{pl_id}_{p_id}_{v_id}"
            return self.master_keys['product_catalog'].get(composite_key)
        
        fact_transactions['product_catalog_key'] = fact_transactions.apply(
            get_product_catalog_key, 
            axis=1
        )
        
        # Log matching statistics
        matched_products = fact_transactions['product_catalog_key'].notna().sum()
        logger.info(f"   Product catalog key matching: {matched_products}/{len(fact_transactions)} ({matched_products/len(fact_transactions)*100:.1f}%)")
        
        # STEP 5: Add business classification
        logger.info("Step 5: Adding business classification...")
        
        # Determine if transaction is business-related based on parsed product info
        fact_transactions['is_business_related'] = fact_transactions['parsed_product_line_id'].notna()
        
        # STEP 6: Add audit fields
        logger.info("Step 6: Adding audit fields...")
        fact_transactions['data_source'] = 'bank_statement'
        fact_transactions['batch_id'] = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # STEP 7: Select and order columns according to schema
        logger.info("Step 7: Selecting and ordering columns...")
        output_columns = [
            'bank_transaction_key',
            'bank_account_key',
            'transaction_date_key',
            'product_catalog_key',
            'reference_number',
            'account_number',
            'transaction_description',
            'pl_account_number',
            'parsed_product_line_id',
            'parsed_product_id',
            'parsed_variant_id',
            'credit_amount',
            'debit_amount',
            'balance_after_transaction',
            'is_business_related',
            'data_source',
            'batch_id'
        ]
        
        # Ensure all columns exist
        for col in output_columns:
            if col not in fact_transactions.columns:
                fact_transactions[col] = None
        
        # STEP 8: Clean DataFrame for PostgreSQL
        logger.info("Step 8: Cleaning DataFrame for PostgreSQL insertion...")
        fact_transactions_clean = self._clean_dataframe_for_postgres(fact_transactions)
        
        # Log statistics
        total_records = len(fact_transactions_clean)
        business_records = fact_transactions_clean['is_business_related'].sum()
        matched_accounts = fact_transactions_clean['bank_account_key'].notna().sum()
        matched_products = fact_transactions_clean['product_catalog_key'].notna().sum()
        
        logger.info(f"✅ Built bank transactions fact table:")
        logger.info(f"   Total records: {total_records:,}")
        logger.info(f"   Business-related: {business_records:,} ({business_records/total_records*100:.1f}%)")
        logger.info(f"   Matched bank accounts: {matched_accounts:,} ({matched_accounts/total_records*100:.1f}%)")
        logger.info(f"   Matched products: {matched_products:,} ({matched_products/total_records*100:.1f}%)")
        
        return fact_transactions_clean[output_columns]

    def build(
        self, 
        bank_transactions_df: pd.DataFrame,
        dim_bank_account_df: pd.DataFrame = None,
        dim_product_catalog_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        """Main build method for bank transactions fact table"""
        return self.build_bank_transactions_fact(
            bank_transactions_df, 
            dim_bank_account_df,
            dim_product_catalog_df
        )

