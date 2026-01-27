"""
Payments Fact Table Builder
Builds payments fact table from direct checkout data
"""

import pandas as pd
from datetime import datetime
import logging
from typing import Dict
from ..base_builder import BaseBuilder

logger = logging.getLogger("fact_payments")

class PaymentsFactBuilder(BaseBuilder):
    """Build Payments Fact Table"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_payments_fact(self, direct_checkout_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build Payments Fact Table"""
        fact_payments = direct_checkout_df.copy()

        # Generate keys
        fact_payments['payment_transaction_key'] = range(1, len(fact_payments) + 1)

        # Map foreign keys using direct_checkout fields + master_keys
        try:
            logger.info(f"Fact payments - Available datasets: {list(datasets.keys())}")
            logger.info(f"Fact payments - Master keys customers: {len(self.master_keys['customers'])} entries")
            logger.info(f"Fact payments - Master keys orders: {len(self.master_keys['orders'])} entries")
            logger.info(f"Fact payments - Direct checkout columns: {list(fact_payments.columns)}")
            
            # Normalize key columns from direct checkout (exact matches)
            dc_col_map = {}
            for col in fact_payments.columns:
                if col == 'order_id':
                    dc_col_map[col] = 'order_id'
                elif col == 'buyer_username':
                    dc_col_map[col] = 'buyer_user_name'
                elif col == 'payment_id':
                    dc_col_map[col] = 'payment_id'
                elif col == 'buyer_name':
                    dc_col_map[col] = 'buyer_name'
                elif col == 'buyer':
                    dc_col_map[col] = 'buyer'
                elif col == 'currency':
                    dc_col_map[col] = 'currency'
                elif col == 'listing_amount':
                    dc_col_map[col] = 'listing_amount'
                elif col == 'listing_currency':
                    dc_col_map[col] = 'listing_currency'
                elif col == 'exchange_rate':
                    dc_col_map[col] = 'exchange_rate'
                elif col == 'vat_amount':
                    dc_col_map[col] = 'vat_amount'
                elif col == 'gift_card_applied?':
                    dc_col_map[col] = 'gift_card_applied'
                elif col == 'status':
                    dc_col_map[col] = 'status'
                elif col == 'funds_available':
                    dc_col_map[col] = 'funds_available'
                elif col == 'payment_type':
                    dc_col_map[col] = 'payment_type'
                elif col == 'refund_amount':
                    dc_col_map[col] = 'refund_amount'
            if dc_col_map:
                fact_payments = fact_payments.rename(columns=dc_col_map)
                logger.info(f"Fact payments - Renamed columns: {list(fact_payments.columns)}")

            # Map order_key via order_id -> master_keys['orders']
            if 'order_id' in fact_payments.columns:
                fact_payments['order_id'] = fact_payments['order_id'].astype(str)
                fact_payments['order_key'] = fact_payments['order_id'].map(self.master_keys['orders'])
                logger.info(f"Fact payments - Mapped order_key: {fact_payments['order_key'].notna().sum()} non-null values")
            else:
                logger.warning("Fact payments - order_id column not found")
                fact_payments['order_key'] = None

            # Map customer_key via buyer_user_name -> master_keys['customers']
            if 'buyer_user_name' in fact_payments.columns:
                fact_payments['buyer_user_name'] = fact_payments['buyer_user_name'].astype(str)
                fact_payments['customer_key'] = fact_payments['buyer_user_name'].map(self.master_keys['customers'])
                logger.info(f"Fact payments - Mapped customer_key: {fact_payments['customer_key'].notna().sum()} non-null values")
            else:
                logger.warning("Fact payments - buyer_user_name column not found")
                fact_payments['customer_key'] = None
        except Exception as e:
            logger.warning(f"Error mapping keys in payments: {e}")
            fact_payments['order_key'] = None
            fact_payments['customer_key'] = None

        try:
            
            fact_payments['payment_method_key'] = fact_payments['payment_type'].map(self.master_keys['payments'])
        except Exception as e:
            logger.warning(f"Error mapping payment method keys in payments: {e}")
            fact_payments['payment_method_key'] = None

        # Rename columns to match schema
        try:
            fact_payments['payment_date_key'] = pd.to_datetime(fact_payments['order_date'], errors='coerce').dt.strftime('%Y%m%d')
            # leave as None if cannot parse
            fact_payments['payment_date_key'] = fact_payments['payment_date_key'].where(fact_payments['payment_date_key'].notna(), None)
        except Exception as e:
            logger.warning(f"Error processing payment_date_key: {e}")
            fact_payments['payment_date_key'] = None
            
        # Ensure required columns exist (values + extra); leave None if missing in source
        required_cols = [
            # 9 value columns
            'gross_amount', 'fees', 'net_amount',
            'posted_gross', 'posted_fees', 'posted_net',
            'adjusted_gross', 'adjusted_fees', 'adjusted_net',
            # extra columns
            'currency', 'listing_amount', 'listing_currency', 'exchange_rate', 'vat_amount',
            'gift_card_applied', 'status', 'funds_available',
            'buyer_username', 'buyer_name', 'buyer', 'order_date',
            'order_type', 'payment_type', 'refund_amount'
        ]
        # derive buyer_username from buyer_user_name for final output if needed
        if 'buyer_username' not in fact_payments.columns and 'buyer_user_name' in fact_payments.columns:
            fact_payments['buyer_username'] = fact_payments['buyer_user_name']
        for col in required_cols:
            if col not in fact_payments.columns:
                fact_payments[col] = None

        # Add audit fields
        fact_payments['created_timestamp'] = datetime.now()
        fact_payments['updated_timestamp'] = datetime.now()
        fact_payments['data_source'] = 'direct_checkout'
        fact_payments['batch_id'] = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # derive buyer_username from buyer_user_name for final output if needed
        if 'buyer_username' not in fact_payments.columns and 'buyer_user_name' in fact_payments.columns:
            fact_payments['buyer_username'] = fact_payments['buyer_user_name']
        for col in required_cols:
            if col not in fact_payments.columns:
                fact_payments[col] = None

        # Standardize formats across columns
        try:
            # Numeric columns
            numeric_cols = [
                'gross_amount', 'fees', 'net_amount',
                'posted_gross', 'posted_fees', 'posted_net',
                'adjusted_gross', 'adjusted_fees', 'adjusted_net',
                'listing_amount', 'vat_amount', 'refund_amount', 'exchange_rate'
            ]
            for col in numeric_cols:
                if col in fact_payments.columns:
                    fact_payments[col] = pd.to_numeric(fact_payments[col], errors='coerce')

            # Date/time columns
            datetime_cols = ['funds_available', 'order_date']
            for col in datetime_cols:
                if col in fact_payments.columns:
                    fact_payments[col] = pd.to_datetime(fact_payments[col], errors='coerce')

            # Currency code columns -> uppercase
            for col in ['currency', 'listing_currency']:
                if col in fact_payments.columns:
                    fact_payments[col] = fact_payments[col].apply(
                        lambda x: str(x).strip().upper() if pd.notna(x) and str(x).strip() else None
                    )

            # Text columns -> stripped strings or None
            text_cols = ['payment_id', 'buyer_username', 'buyer_name', 'buyer', 'status', 'payment_type', 'order_type']
            for col in text_cols:
                if col in fact_payments.columns:
                    fact_payments[col] = fact_payments[col].apply(
                        lambda x: str(x).strip() if pd.notna(x) and str(x).strip() else None
                    )

            # Keep original values for gift_card_applied (no normalization)
        except Exception as e:
            logger.warning(f"Error standardizing payment columns: {e}")

        # Select columns theo schema design (include requested value columns)
        fact_cols = [
            'payment_transaction_key', 'customer_key', 'order_key', 'payment_date_key', 'payment_method_key',
            'payment_id', 'buyer_username', 'buyer_name', 'order_id',
            # requested value columns
            'gross_amount', 'fees', 'net_amount',
            'posted_gross', 'posted_fees', 'posted_net',
            'adjusted_gross', 'adjusted_fees', 'adjusted_net',
            'currency', 'listing_amount', 'listing_currency', 'exchange_rate', 'vat_amount',
            'gift_card_applied', 'status', 'funds_available',
            'order_date', 'buyer', 'order_type', 'payment_type', 'refund_amount',
            'created_timestamp', 'updated_timestamp', 'data_source', 'batch_id'
        ]

        # Clean up None strings and convert to proper NULL values
        fact_payments = self._clean_dataframe_for_postgres(fact_payments)

        return fact_payments[fact_cols]

    def build(self, direct_checkout_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Main build method for payments fact table"""
        return self.build_payments_fact(direct_checkout_df, datasets)
