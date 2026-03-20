"""
Deposits Fact Table Builder
Builds deposits fact table from deposits data
"""

import pandas as pd
from datetime import datetime
import logging
from ..base_builder import BaseBuilder

logger = logging.getLogger('deposits')

class DepositsFactBuilder(BaseBuilder):
    """Build Deposits Fact Table"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_deposits_fact(self, deposits_df: pd.DataFrame) -> pd.DataFrame:
        """Build Deposits Fact Table"""
        fact_deposits = deposits_df.copy()

        # Generate keys
        fact_deposits['deposit_key'] = range(1, len(fact_deposits) + 1)

        # Rename columns to match schema
        fact_deposits['deposit_date_key'] = pd.to_datetime(fact_deposits['date']).dt.strftime('%Y%m%d').astype(int)
        fact_deposits['deposit_amount'] = fact_deposits['amount']
        fact_deposits['deposit_status'] = fact_deposits['status']

        # No status flags needed

        # Add missing bank account digits if not present
        if 'bank_account_ending_digits' not in fact_deposits.columns:
            fact_deposits['bank_account_ending_digits'] = None

        # Add audit fields
        fact_deposits['created_timestamp'] = datetime.now()
        fact_deposits['updated_timestamp'] = datetime.now()
        fact_deposits['data_source'] = 'deposits'
        fact_deposits['batch_id'] = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Select columns theo schema design
        fact_cols = [
            'deposit_key', 'deposit_date_key', 'deposit_amount', 'deposit_status',
            'bank_account_ending_digits',
            'created_timestamp', 'updated_timestamp', 'data_source', 'batch_id'
        ]

        # Clean up None strings and convert to proper NULL values
        fact_deposits = self._clean_dataframe_for_postgres(fact_deposits)

        return fact_deposits[fact_cols]

    def build(self, deposits_df: pd.DataFrame) -> pd.DataFrame:
        """Main build method for deposits fact table"""
        return self.build_deposits_fact(deposits_df)
