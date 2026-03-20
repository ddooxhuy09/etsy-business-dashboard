"""
Financial Transactions Fact Table Builder
Builds financial transactions fact table from statement data
"""

import pandas as pd
from datetime import datetime
import logging
from typing import Dict
from ..base_builder import BaseBuilder

logger = logging.getLogger(f"fact_financial_transactions")

class FinancialTransactionsFactBuilder(BaseBuilder):
    """Build Financial Transactions Fact Table"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_financial_transactions_fact(self, statement_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build Financial Transactions Fact Table"""
        fact_financial = statement_df.copy()

        # Generate keys
        fact_financial['financial_transaction_key'] = range(1, len(fact_financial) + 1)

        # Map extracted_id to appropriate dimension
        fact_financial['order_id'] = fact_financial['extracted_id'].where(
            fact_financial['id_type'] == 'Order ID', None
        )
        fact_financial['transaction_id'] = fact_financial['extracted_id'].where(
            fact_financial['id_type'] == 'Transaction ID', None
        )

        # Map foreign keys using master_keys
        try:
            logger.info(f"Available datasets: {list(datasets.keys())}")
            logger.info(f"Master keys customers: {len(self.master_keys['customers'])} entries")
            logger.info(f"Master keys orders: {len(self.master_keys['orders'])} entries")
            logger.info(f"Master keys products: {len(self.master_keys['products'])} entries")
            
            # Prefer mapping via direct checkout: order_id -> buyer_user_name -> customer_key
            if 'direct_checkout' in datasets:
                dc_df = datasets['direct_checkout'].copy()
                logger.info(f"Direct checkout columns: {list(dc_df.columns)}")

                # Map column names case-insensitively
                dc_col_map = {}
                for col in dc_df.columns:
                    u = col.upper()
                    if u == 'ORDER_ID':
                        dc_col_map[col] = 'order_id'
                    elif u == 'BUYER_USERNAME':
                        dc_col_map[col] = 'buyer_user_name'
                if dc_col_map:
                    dc_df = dc_df.rename(columns=dc_col_map)
                    logger.info(f"Renamed direct checkout columns: {list(dc_df.columns)}")

                if 'order_id' in dc_df.columns and 'buyer_user_name' in dc_df.columns:
                    # Normalize types for mapping
                    dc_df['order_id'] = dc_df['order_id'].astype(str)
                    fact_financial['order_id'] = fact_financial['order_id'].astype(str)

                    order_to_buyer_username = dc_df.set_index('order_id')['buyer_user_name'].to_dict()
                    logger.info(f"Order to buyer mapping: {len(order_to_buyer_username)} entries")
                    
                    fact_financial['buyer_user_name'] = fact_financial['order_id'].map(order_to_buyer_username)
                    logger.info(f"Mapped buyer_user_name: {fact_financial['buyer_user_name'].notna().sum()} non-null values")

                    # Map to customer_key using master_keys (keyed by buyer_user_name)
                    fact_financial['customer_key'] = fact_financial['buyer_user_name'].astype(str).map(self.master_keys['customers'])
                    logger.info(f"Mapped customer_key: {fact_financial['customer_key'].notna().sum()} non-null values")
                else:
                    logger.warning("Missing required columns in direct_checkout data")
                    fact_financial['customer_key'] = None
            else:
                logger.warning("Direct checkout dataset not found")
                fact_financial['customer_key'] = None
        except Exception as e:
            logger.warning(f"Error mapping customer keys in financial transactions: {e}")
            fact_financial['customer_key'] = None

        try:
            # Convert data types to ensure matching
            if 'order_id' in fact_financial.columns:
                fact_financial['order_id'] = fact_financial['order_id'].astype(str)
                fact_financial['order_key'] = fact_financial['order_id'].map(self.master_keys['orders'])
                logger.info(f"Mapped order_key: {fact_financial['order_key'].notna().sum()} non-null values")
            else:
                logger.warning("order_id column not found in fact_financial")
                fact_financial['order_key'] = None
        except Exception as e:
            logger.warning(f"Error mapping order keys in financial transactions: {e}")
            fact_financial['order_key'] = None

        # Map product_key via order_id -> listing_id (from sold_order_items) -> product_key
        try:
            if 'sold_order_items' in datasets:
                items_df = datasets['sold_order_items'].copy()
                logger.info(f"Sold order items columns: {list(items_df.columns)}")

                # Map column names (exact matches)
                items_col_map = {}
                for col in items_df.columns:
                    if col == 'order_id':
                        items_col_map[col] = 'order_id'
                    elif col == 'listing_id':
                        items_col_map[col] = 'listing_id'
                if items_col_map:
                    items_df = items_df.rename(columns=items_col_map)
                    logger.info(f"Renamed sold order items columns: {list(items_df.columns)}")

                if 'order_id' in items_df.columns and 'listing_id' in items_df.columns:
                    # Normalize types to string for stable mapping
                    items_df['order_id'] = items_df['order_id'].astype(str)
                    items_df['listing_id'] = items_df['listing_id'].astype(str)
                    if 'order_id' in fact_financial.columns:
                        fact_financial['order_id'] = fact_financial['order_id'].astype(str)

                    # One listing_id per order_id (first if multiple)
                    order_to_listing = items_df.dropna(subset=['order_id', 'listing_id']) \
                        .groupby('order_id')['listing_id'].first().to_dict()
                    logger.info(f"Order to listing mapping: {len(order_to_listing)} entries")

                    fact_financial['listing_id'] = fact_financial['order_id'].map(order_to_listing)
                    logger.info(f"Mapped listing_id: {fact_financial['listing_id'].notna().sum()} non-null values")

                    # Map listing_id to product_key using master keys
                    fact_financial['product_key'] = fact_financial['listing_id'].astype(str).map(self.master_keys['products'])
                    logger.info(f"Mapped product_key: {fact_financial['product_key'].notna().sum()} non-null values")

                    # Drop temp column
                    fact_financial = fact_financial.drop(columns=['listing_id'], errors='ignore')
                else:
                    logger.warning("Missing required columns in sold_order_items data")
                    fact_financial['product_key'] = None
            else:
                logger.warning("Sold order items dataset not found")
                fact_financial['product_key'] = None
        except Exception as e:
            logger.warning(f"Error mapping product keys in financial transactions: {e}")
            fact_financial['product_key'] = None

        # Rename columns to match SQL schema
        fact_financial['transaction_date_key'] = pd.to_datetime(fact_financial['date']).dt.strftime('%Y%m%d').astype(int)
        fact_financial['transaction_type'] = fact_financial['type']
        fact_financial['transaction_title'] = fact_financial['title']
        # Keep original value column names (leave missing as NULL/None)
        fact_financial['amount'] = fact_financial.get('amount')
        # Column comes from "Fees & Taxes" -> snake_case -> "fees_taxes"
        if 'fees_taxes' in fact_financial.columns:
            fact_financial['fees_and_taxes'] = fact_financial['fees_taxes']
        elif 'fees_and_taxes' in fact_financial.columns:
            fact_financial['fees_and_taxes'] = fact_financial['fees_and_taxes']
        else:
            fact_financial['fees_and_taxes'] = None
        fact_financial['net'] = fact_financial.get('net')

        # Add missing columns with defaults
        fact_financial['revenue_type'] = fact_financial.get('revenue_type', 'Unknown')
        fact_financial['info_description'] = fact_financial.get('info_description', '')
        fact_financial['original_info'] = fact_financial.get('info', '')  # Map 'info' to 'original_info'
        fact_financial['tax_details'] = fact_financial.get('tax_details', None)
        
        # No business flags required

        # Add audit fields
        fact_financial['created_timestamp'] = datetime.now()
        fact_financial['updated_timestamp'] = datetime.now()
        fact_financial['data_source'] = 'statement'
        fact_financial['batch_id'] = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Select columns theo schema design - only include columns that exist
        available_cols = fact_financial.columns.tolist()
        desired_cols = [
            'financial_transaction_key', 'transaction_date_key', 'customer_key', 'order_key', 'product_key',
            'extracted_id', 'order_id', 'transaction_id', 'transaction_type', 'transaction_title',
            'revenue_type', 'fee_type', 'id_type', 'info_description',
            'amount', 'fees_and_taxes', 'net', 'tax_details',
            'original_info', 'created_timestamp', 'updated_timestamp', 'data_source', 'batch_id'
        ]
        
        # Only select columns that actually exist
        fact_cols = [col for col in desired_cols if col in available_cols]
        
        # Add any missing columns with defaults
        for col in desired_cols:
            if col not in fact_financial.columns:
                if col in ['tax_details']:
                    fact_financial[col] = None
                # No business flags defaults
                elif col in ['created_timestamp', 'updated_timestamp']:
                    fact_financial[col] = datetime.now()
                else:
                    fact_financial[col] = None

        # Clean up None strings and convert to proper NULL values
        fact_financial = self._clean_dataframe_for_postgres(fact_financial)

        # Return only columns that exist to avoid KeyError
        return fact_financial[fact_cols]

    def build(self, statement_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Main build method for financial transactions fact table"""
        return self.build_financial_transactions_fact(statement_df, datasets)
