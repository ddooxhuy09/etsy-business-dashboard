import pandas as pd
from datetime import datetime
import logging
from ..base_builder import BaseBuilder

logger = logging.getLogger('bank_transactions')

class BankTransactionsFactBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_bank_transactions_fact(
        self, 
        bank_transactions_df: pd.DataFrame,
        dim_bank_account_df: pd.DataFrame = None,
        dim_product_catalog_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        logger.info("Building bank transactions fact table...")
        
        fact = bank_transactions_df.copy()
        
        column_mapping = {}
        
        for col in fact.columns:
            col_lower = col.lower()
            if col in ['pl_account_number', 'parsed_product_line_id', 'parsed_product_id', 'parsed_variant_id']:
                continue
            elif 'reference' in col_lower:
                column_mapping[col] = 'reference_number'
            elif 'account_number' in col_lower and 'khoan' in col_lower:
                column_mapping[col] = 'account_number'
            elif 'account_name' in col_lower:
                column_mapping[col] = 'account_name'
            elif 'credit' in col_lower:
                column_mapping[col] = 'credit_amount'
            elif 'debit' in col_lower:
                column_mapping[col] = 'debit_amount'
            elif 'balance' in col_lower or 'du' in col_lower:
                column_mapping[col] = 'balance'
            elif 'description' in col_lower or 'giai' in col_lower:
                column_mapping[col] = 'transaction_description'
            elif 'opening' in col_lower and 'date' in col_lower:
                column_mapping[col] = 'opening_date'
        
        fact = fact.rename(columns=column_mapping)
        logger.info(f"   Columns after rename: {list(fact.columns)}")

        fact['bank_transaction_key'] = range(1, len(fact) + 1)

        date_cols = [col for col in fact.columns if 'gd' in col.lower() or ('date' in col.lower() and col != 'opening_date')]
        if date_cols:
            date_col = date_cols[0]
            fact['transaction_date'] = pd.to_datetime(
                fact[date_col], 
                format='%d/%m/%Y',
                errors='coerce'
            )
        else:
            fact['transaction_date'] = None

        account_col = None
        for col in fact.columns:
            if col == 'account_number':
                account_col = col
                break
        if account_col is None:
            for col in fact.columns:
                cl = col.lower()
                if ('account' in cl and 'number' in cl) or ('tai_khoan' in cl):
                    if 'ngay' not in cl and 'date' not in cl and 'opening' not in cl:
                        account_col = col
                        break

        if account_col and account_col != 'account_number':
            fact['account_number'] = fact[account_col]
        elif account_col is None:
            fact['account_number'] = None

        output_columns = [
            'bank_transaction_key',
            'transaction_date',
            'reference_number',
            'account_number',
            'account_name',
            'opening_date',
            'transaction_description',
            'pl_account_number',
            'parsed_product_line_id',
            'parsed_product_id',
            'parsed_variant_id',
            'credit_amount',
            'debit_amount',
            'balance'
        ]
        
        for col in output_columns:
            if col not in fact.columns:
                fact[col] = None

        fact_clean = self._clean_dataframe_for_postgres(fact)
        
        total_records = len(fact_clean)
        matched_accounts = fact_clean['account_number'].notna().sum()
        
        logger.info(f"Built bank transactions fact table:")
        logger.info(f"   Total records: {total_records:,}")
        logger.info(f"   Matched accounts: {matched_accounts:,}")
        
        return fact_clean[output_columns]

    def build(
        self, 
        bank_transactions_df: pd.DataFrame,
        dim_bank_account_df: pd.DataFrame = None,
        dim_product_catalog_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        return self.build_bank_transactions_fact(
            bank_transactions_df, 
            dim_bank_account_df,
            dim_product_catalog_df
        )
