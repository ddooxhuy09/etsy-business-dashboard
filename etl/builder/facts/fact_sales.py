"""
Sales Fact Table Builder
Builds sales fact table from sold order items data
"""

import pandas as pd
from datetime import datetime
import logging
from typing import Dict
from ..base_builder import BaseBuilder
import hashlib

logger = logging.getLogger("fact_sales")

class SalesFactBuilder(BaseBuilder):
    """Build Sales Fact Table"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_sales_fact(self, sold_order_items_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build Sales Fact Table"""
        # Handle None input
        if sold_order_items_df is None or sold_order_items_df.empty:
            logger.warning("sold_order_items_df is None or empty, returning empty fact_sales")
            return pd.DataFrame(columns=['sales_key', 'order_id', 'transaction_id', 'quantity_sold'])
        
        fact_sales = sold_order_items_df.copy()

        # Generate keys
        fact_sales['sales_key'] = range(1, len(fact_sales) + 1)

        # Map column names for sold_order_items (exact matches)
        items_col_map = {}
        for col in fact_sales.columns:
            if col == 'order_id':
                items_col_map[col] = 'order_id'
            elif col == 'listing_id':
                items_col_map[col] = 'listing_id'
            elif col == 'transaction_id':
                items_col_map[col] = 'transaction_id'
            elif col == 'price':
                items_col_map[col] = 'item_price'
            elif col == 'quantity':
                items_col_map[col] = 'quantity_sold'
            elif col == 'item_total':
                items_col_map[col] = 'item_total'
            elif col == 'discount_amount':
                items_col_map[col] = 'discount_amount'
            elif col == 'order_shipping':
                items_col_map[col] = 'shipping_amount'
            elif col == 'shipping_discount':
                items_col_map[col] = 'shipping_discount'
            elif col == 'order_sales_tax':
                items_col_map[col] = 'order_sales_tax'
            elif col == 'sale_date':
                items_col_map[col] = 'sale_date'
            elif col == 'date_paid':
                items_col_map[col] = 'date_paid'
            elif col == 'date_shipped':
                items_col_map[col] = 'date_shipped'
            elif col == 'sku':
                items_col_map[col] = 'sku'
            elif col == 'variations':
                items_col_map[col] = 'variations'
            elif col == 'size':
                items_col_map[col] = 'size'
            elif col == 'style':
                items_col_map[col] = 'style'
            elif col == 'color':
                items_col_map[col] = 'color'
            elif col == 'material':
                items_col_map[col] = 'material'
            elif col == 'personalization':
                items_col_map[col] = 'personalization'
            elif col == 'payment_type':
                items_col_map[col] = 'payment_type'
            elif col == 'order_type':
                items_col_map[col] = 'order_type'
            elif col == 'vat_paid_by_buyer':
                items_col_map[col] = 'vat_paid_by_buyer'
            elif col == 'ship_country':
                items_col_map[col] = 'ship_country'
            elif col == 'ship_state':
                items_col_map[col] = 'ship_state'
            elif col == 'ship_city':
                items_col_map[col] = 'ship_city'
            elif col == 'ship_zipcode':
                items_col_map[col] = 'ship_zipcode'
        if items_col_map:
            fact_sales = fact_sales.rename(columns=items_col_map)

        # Map foreign keys using master_keys
        try:
            logger.info(f"Fact sales - Master keys products: {len(self.master_keys['products'])} entries")
            logger.info(f"Fact sales - Master keys customers: {len(self.master_keys['customers'])} entries")
            logger.info(f"Fact sales - Master keys orders: {len(self.master_keys['orders'])} entries")
            
            # Map product_key via listing_id -> master_keys['products']
            if 'listing_id' in fact_sales.columns:
                # Convert to clean string format (remove .0 if present)
                fact_sales['listing_id'] = fact_sales['listing_id'].apply(
                    lambda x: str(int(float(x))) if pd.notna(x) else None
                )
                
                # Debug: Check sample values and master keys
                sample_listing_ids = fact_sales['listing_id'].dropna().unique()[:5]
                sample_master_keys = list(self.master_keys['products'].keys())[:5]
                logger.info(f"Fact sales - Sample listing_id values: {sample_listing_ids}")
                logger.info(f"Fact sales - Sample master_keys products: {sample_master_keys}")
                
                fact_sales['product_key'] = fact_sales['listing_id'].map(self.master_keys['products'])
                logger.info(f"Fact sales - Mapped product_key: {fact_sales['product_key'].notna().sum()} non-null values")
            else:
                logger.warning("Fact sales - listing_id column not found")
                fact_sales['product_key'] = None

            # Map order_key via order_id -> master_keys['orders']
            if 'order_id' in fact_sales.columns:
                fact_sales['order_id'] = fact_sales['order_id'].astype(str)
                fact_sales['order_key'] = fact_sales['order_id'].map(self.master_keys['orders'])
                logger.info(f"Fact sales - Mapped order_key: {fact_sales['order_key'].notna().sum()} non-null values")
            else:
                logger.warning("Fact sales - order_id column not found")
                fact_sales['order_key'] = None

            # Map customer_key via order_id -> buyer_user_name (from direct_checkout) -> master_keys['customers']
            if 'direct_checkout' in datasets and 'order_id' in fact_sales.columns:
                dc_df = datasets['direct_checkout'].copy()
                logger.info(f"Fact sales - Direct checkout columns: {list(dc_df.columns)}")

                # Map direct_checkout column names (exact matches)
                dc_col_map = {}
                for col in dc_df.columns:
                    if col == 'order_id':
                        dc_col_map[col] = 'order_id'
                    elif col == 'buyer_username':
                        dc_col_map[col] = 'buyer_user_name'
                if dc_col_map:
                    dc_df = dc_df.rename(columns=dc_col_map)
                    logger.info(f"Fact sales - Renamed direct checkout columns: {list(dc_df.columns)}")

                if 'order_id' in dc_df.columns and 'buyer_user_name' in dc_df.columns:
                    # Normalize types for mapping
                    dc_df['order_id'] = dc_df['order_id'].astype(str)
                    fact_sales['order_id'] = fact_sales['order_id'].astype(str)

                    # Create order_id -> buyer_user_name mapping
                    order_to_buyer_username = dc_df.set_index('order_id')['buyer_user_name'].to_dict()
                    logger.info(f"Fact sales - Order to buyer mapping: {len(order_to_buyer_username)} entries")
                    
                    fact_sales['buyer_user_name'] = fact_sales['order_id'].map(order_to_buyer_username)
                    logger.info(f"Fact sales - Mapped buyer_user_name: {fact_sales['buyer_user_name'].notna().sum()} non-null values")

                    # Map to customer_key using master_keys (keyed by buyer_user_name)
                    fact_sales['customer_key'] = fact_sales['buyer_user_name'].astype(str).map(self.master_keys['customers'])
                    logger.info(f"Fact sales - Mapped customer_key: {fact_sales['customer_key'].notna().sum()} non-null values")
                else:
                    logger.warning("Fact sales - Missing required columns in direct_checkout data")
                    fact_sales['customer_key'] = None
            else:
                logger.warning("Fact sales - Direct checkout dataset not found or order_id missing")
                fact_sales['customer_key'] = None

            # Map payment_key via payment_type -> master_keys['payments']
            if 'payment_type' in fact_sales.columns:
                fact_sales['payment_key'] = fact_sales['payment_type'].map(self.master_keys['payments'])
            else:
                fact_sales['payment_key'] = None

        except Exception as e:
            logger.warning(f"Error mapping keys in sales: {e}")
            fact_sales['product_key'] = None
            fact_sales['order_key'] = None
            fact_sales['customer_key'] = None
            fact_sales['payment_key'] = None

        # Map geography_key via shipping location
        try:
            # Check if geography columns exist
            geo_cols = ['ship_country', 'ship_state', 'ship_city']
            missing_cols = [col for col in geo_cols if col not in fact_sales.columns]
            
            if missing_cols:
                fact_sales['geography_key'] = None
            else:
                # Create location hash for geography mapping (match dim_geography format)
                def _geo_hash(row):
                    if pd.notna(row['ship_country']) and pd.notna(row['ship_state']) and pd.notna(row['ship_city']):
                        raw = f"{row['ship_country']}|{row['ship_state']}|{row['ship_city']}"
                        return hashlib.md5(raw.encode()).hexdigest()[:16]
                    return None

                fact_sales['location_hash'] = fact_sales.apply(_geo_hash, axis=1)

                # Map to geography_key using master_keys
                fact_sales['geography_key'] = fact_sales['location_hash'].map(self.master_keys['geographies'])
                
                # Clean up temp column
                fact_sales = fact_sales.drop(columns=['location_hash'], errors='ignore')
        except Exception as e:
            logger.warning(f"Error mapping geography keys in sales: {e}")
            fact_sales['geography_key'] = None

        # Create date keys
        try:
            if 'sale_date' in fact_sales.columns:
                fact_sales['sale_date_key'] = pd.to_datetime(fact_sales['sale_date'], errors='coerce').dt.strftime('%Y%m%d')
                fact_sales['sale_date_key'] = fact_sales['sale_date_key'].where(fact_sales['sale_date_key'].notna(), None)
            else:
                fact_sales['sale_date_key'] = None

            if 'date_paid' in fact_sales.columns:
                fact_sales['paid_date_key'] = pd.to_datetime(fact_sales['date_paid'], errors='coerce').dt.strftime('%Y%m%d')
                fact_sales['paid_date_key'] = fact_sales['paid_date_key'].where(fact_sales['paid_date_key'].notna(), None)
            else:
                fact_sales['paid_date_key'] = None

            if 'date_shipped' in fact_sales.columns:
                fact_sales['ship_date_key'] = pd.to_datetime(fact_sales['date_shipped'], errors='coerce').dt.strftime('%Y%m%d')
                fact_sales['ship_date_key'] = fact_sales['ship_date_key'].where(fact_sales['ship_date_key'].notna(), None)
            else:
                fact_sales['ship_date_key'] = None
        except Exception as e:
            logger.warning(f"Error processing date keys: {e}")
            fact_sales['sale_date_key'] = None
            fact_sales['paid_date_key'] = None
            fact_sales['ship_date_key'] = None

        # Ensure required columns exist with defaults
        required_cols = [
            # Revenue measures
            'item_price', 'item_total', 'discount_amount', 'shipping_amount', 
            'shipping_discount', 'order_sales_tax',

            'quantity_sold', 'currency', 'transaction_id', 'sku',
            'variations', 'size', 'style', 'color', 'material', 'personalization',
            'payment_type', 'order_type', 'buyer_username', 'vat_paid_by_buyer'
        ]
        
        for col in required_cols:
            if col not in fact_sales.columns:
                fact_sales[col] = None  # Set all missing fields to NULL


        # Set conversion_date (same as sale_date if available)
        if 'sale_date' in fact_sales.columns:
            fact_sales['conversion_date'] = pd.to_datetime(fact_sales['sale_date'], errors='coerce')
        else:
            fact_sales['conversion_date'] = None


        # Add audit fields
        fact_sales['created_timestamp'] = datetime.now()
        fact_sales['updated_timestamp'] = datetime.now()
        fact_sales['data_source'] = 'sold_order_items'
        fact_sales['batch_id'] = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Select columns theo schema design
        fact_cols = [
            'sales_key', 'product_key', 'customer_key', 'order_key', 'sale_date_key', 
            'ship_date_key', 'paid_date_key', 'geography_key', 'payment_key',
            'transaction_id', 'order_id', 'sku', 'quantity_sold',
            'item_price', 'item_total', 'discount_amount', 'shipping_amount', 
            'shipping_discount', 'order_sales_tax',
            'conversion_date', 'variations', 'size', 'style', 'color', 'material', 'personalization',
            'vat_paid_by_buyer',
            'created_timestamp', 'updated_timestamp', 'data_source', 'batch_id'
        ]

        # Clean up None strings and convert to proper NULL values
        fact_sales = self._clean_dataframe_for_postgres(fact_sales)

        return fact_sales[fact_cols]

    def build(self, sold_order_items_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Main build method for sales fact table"""
        return self.build_sales_fact(sold_order_items_df, datasets)
