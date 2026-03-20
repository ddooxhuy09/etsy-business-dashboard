"""
Bank Account Dimension Builder
Builds bank account dimension from dim_bank_account.csv
"""

import pandas as pd
from datetime import datetime
import logging
from ..base_builder import BaseBuilder
from etl.utils_core import clean_text_field

logger = logging.getLogger('bank_account')

class BankAccountDimensionBuilder(BaseBuilder):
    """Build bank account dimension from bank account data"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_bank_account_dimension(self, bank_account_df: pd.DataFrame) -> pd.DataFrame:
        """Build bank account dimension"""
        logger.info("Building bank account dimension...")
        
        dim_bank_account = bank_account_df.copy()
        
        # STEP 1: Ensure columns exist and clean data
        logger.info("Step 1: Cleaning and validating data...")
        
        # Clean text fields
        text_fields = ['account_number', 'account_name', 'cif_number', 
                       'customer_address', 'currency_code']
        
        for field in text_fields:
            if field in dim_bank_account.columns:
                dim_bank_account[field] = dim_bank_account[field].apply(
                    lambda x: clean_text_field(x, 200) if pd.notna(x) else None
                )
        
        # STEP 2: Handle existing keys or generate new ones
        logger.info("Step 2: Handling surrogate keys...")
        
        if 'bank_account_key' not in dim_bank_account.columns:
            # Generate new keys if they don't exist
            dim_bank_account['bank_account_key'] = range(
                self.key_counters.get('bank_account_key', 1),
                self.key_counters.get('bank_account_key', 1) + len(dim_bank_account)
            )
            self.key_counters['bank_account_key'] = (
                self.key_counters.get('bank_account_key', 1) + len(dim_bank_account)
            )
        
        # STEP 3: Handle date fields
        logger.info("Step 3: Processing date fields...")
        
        if 'opening_date' in dim_bank_account.columns:
            # opening_date có thể là:
            # 1. INTEGER format yyyyMMdd (từ process_bank_transactions)
            # 2. Date string (dd/mm/yyyy hoặc yyyy-mm-dd)
            # 3. Datetime object
            def parse_opening_date(val):
                if pd.isna(val):
                    return None
                # Nếu là integer (yyyyMMdd format), convert sang datetime
                if isinstance(val, (int, float)) and not pd.isna(val):
                    val_str = str(int(val))
                    if len(val_str) == 8:  # yyyyMMdd format
                        try:
                            return pd.to_datetime(val_str, format='%Y%m%d', errors='coerce')
                        except:
                            return None
                # Nếu là string hoặc datetime, parse bình thường
                return pd.to_datetime(val, errors='coerce')
            
            dim_bank_account['opening_date'] = dim_bank_account['opening_date'].apply(parse_opening_date)
        
        # STEP 4: Add or update audit fields
        logger.info("Step 4: Adding audit fields...")
        current_time = datetime.now()
        
        if 'created_date' not in dim_bank_account.columns:
            dim_bank_account['created_date'] = current_time
        
        if 'updated_date' not in dim_bank_account.columns:
            dim_bank_account['updated_date'] = current_time
        else:
            # Update timestamp for all records being loaded
            dim_bank_account['updated_date'] = current_time
        
        # Ensure is_active field exists
        if 'is_active' not in dim_bank_account.columns:
            dim_bank_account['is_active'] = True
        
        # Ensure currency_code exists
        if 'currency_code' not in dim_bank_account.columns:
            dim_bank_account['currency_code'] = 'VND'
        
        # STEP 5: Build lookup dictionary for foreign key resolution
        logger.info("Step 5: Building lookup dictionary...")
        if not hasattr(self.master_keys, 'bank_accounts'):
            self.master_keys['bank_accounts'] = {}
        
        for _, row in dim_bank_account.iterrows():
            account_number = str(row['account_number']).strip()
            self.master_keys['bank_accounts'][account_number] = row['bank_account_key']
        
        # STEP 6: Select and order columns
        logger.info("Step 6: Selecting and ordering columns...")
        output_columns = [
            'bank_account_key',
            'account_number',
            'account_name',
            'opening_date',
            'cif_number',
            'customer_address',
            'is_active',
            'currency_code',
            'created_date',
            'updated_date'
        ]
        
        # Ensure all columns exist
        for col in output_columns:
            if col not in dim_bank_account.columns:
                dim_bank_account[col] = None
        
        # STEP 7: Clean DataFrame for PostgreSQL
        logger.info("Step 7: Cleaning DataFrame for PostgreSQL insertion...")
        dim_bank_account_clean = self._clean_dataframe_for_postgres(dim_bank_account)
        
        logger.info(f"✅ Built bank account dimension with {len(dim_bank_account_clean):,} records")
        
        return dim_bank_account_clean[output_columns]

    def build(self, bank_account_df: pd.DataFrame) -> pd.DataFrame:
        """Main build method for bank account dimension"""
        return self.build_bank_account_dimension(bank_account_df)

