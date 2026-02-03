"""
Customer Dimension Builder
Builds customer master dimension with analytics and SCD Type 2
"""

import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Optional, Tuple, Any
from ..base_builder import BaseBuilder

logger = logging.getLogger('customer')

class CustomerDimensionBuilder(BaseBuilder):
    """Build customer dimension with analytics and segmentation"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_customer_dimension(self, orders_df: pd.DataFrame, 
                               direct_checkout_df: pd.DataFrame) -> pd.DataFrame:
        """Build customer master dimension with analytics"""
        logger.info("Building customer dimension...")
        
        # Handle None inputs
        if orders_df is None or orders_df.empty:
            logger.warning("orders_df is None or empty, cannot build customer dimension")
            return pd.DataFrame(columns=['customer_key', 'buyer_user_name', 'full_name', 'is_current'])
        if direct_checkout_df is None or direct_checkout_df.empty:
            logger.warning("direct_checkout_df is None or empty, proceeding with orders only")
            direct_checkout_df = pd.DataFrame()
        
        # Debug: Log initial column names
        logger.info(f"Initial orders_df columns: {list(orders_df.columns)}")
        logger.info(f"Initial direct_checkout_df columns: {list(direct_checkout_df.columns) if not direct_checkout_df.empty else 'empty'}")

        # STEP 1: Map column names for direct_checkout_df FIRST
        checkout_needed_cols = []
        checkout_col_mapping = {}
        
        for col in direct_checkout_df.columns if not direct_checkout_df.empty else []:
            if col == 'buyer_username':
                checkout_needed_cols.append(col)
                checkout_col_mapping[col] = 'buyer_user_name'
                logger.info(f"Found buyer_username in direct_checkout: {col}")
            elif col == 'order_id':
                checkout_needed_cols.append(col)
                checkout_col_mapping[col] = 'order_id'
                logger.info(f"Found order_id in direct_checkout: {col}")
            elif col == 'buyer':
                checkout_needed_cols.append(col)
                checkout_col_mapping[col] = 'ship_name'
                logger.info(f"Found buyer_name in direct_checkout: {col}")

        # Lấy chỉ các cột cần thiết và rename
        if checkout_needed_cols:
            direct_checkout_df = direct_checkout_df[checkout_needed_cols].rename(columns=checkout_col_mapping)
            logger.info(f"After checkout mapping: {list(direct_checkout_df.columns)}")

        # STEP 2: Map column names for orders_df
        orders_needed_cols = []
        orders_col_mapping = {}
        
        for col in orders_df.columns:
            if col == 'order_id':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'order_id'
            elif col == 'full_name':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'full_name'
            elif col == 'first_name':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'first_name'
            elif col == 'last_name':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'last_name'
            elif col == 'sale_date':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'sale_date'
            elif col == 'ship_country':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'ship_country'
            elif col == 'ship_state':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'ship_state'
            elif col == 'ship_city':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'ship_city'
            elif col == 'payment_method':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'payment_method'
            elif col == 'date_shipped':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'date_shipped'
            elif col == 'street_1':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'street_1'
            elif col == 'street_2':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'street_2'
            elif col == 'ship_zipcode':
                orders_needed_cols.append(col)
                orders_col_mapping[col] = 'ship_zipcode'

        # Lấy chỉ các cột cần thiết và rename
        if orders_needed_cols:
            orders_df = orders_df[orders_needed_cols].rename(columns=orders_col_mapping)

        
        # STEP 3: Full join direct_checkout_df with orders_df using order_id
            
            # Full join direct_checkout_df with orders_df on order_id
            merged_orders = orders_df.merge(direct_checkout_df, on='order_id', how='outer', suffixes=('_orders', '_checkout'))
            
            
            # Use merged data for customer aggregation
            
            # Group by buyer_user_name to calculate customer metrics (1 record per customer)
            
            if 'buyer_user_name' not in merged_orders.columns:
                logger.error("buyer_user_name column not found in merged data")
                return pd.DataFrame(columns=['customer_key', 'buyer_user_name', 'full_name'])
            
            # Define aggregation methods for customer info (all 'first')
            agg_dict = 'first'  # All columns use 'first' aggregation
            
            # Group by buyer_user_name to get 1 record per customer with aggregated metrics
            customer_orders = merged_orders.groupby('buyer_user_name').agg(agg_dict).reset_index()
            
            # Flatten column names if needed
            if any(isinstance(col, tuple) for col in customer_orders.columns):
                customer_orders.columns = [
                    col[0] if isinstance(col, tuple) and len(col) == 2 else col 
                    for col in customer_orders.columns
                ]
            
            # Process customer data (common logic)
            customer_orders = self._process_customer_data(customer_orders, logger)
            
        else:
            logger.warning("Could not find order_id column in one or both DataFrames")
            # Fallback to orders_df only with same groupby logic
            logger.info("Using fallback logic with orders_df only...")
            
            # Group by buyer_user_name or full_name
            logger.info("Grouping customers by buyer_user_name or full_name...")
            
            if 'buyer_user_name' in orders_df.columns:
                groupby_col = 'buyer_user_name'
            elif 'full_name' in orders_df.columns:
                groupby_col = 'full_name'
            else:
                logger.error("No valid groupby columns found (buyer_user_name or full_name)")
                return pd.DataFrame(columns=['customer_key', 'buyer_user_name', 'full_name'])
            
            # Use same aggregation method as main logic
            
            # Group by the selected column
            customer_orders = orders_df.groupby(groupby_col).agg(agg_dict).reset_index()
            
            # Flatten column names if needed
            if any(isinstance(col, tuple) for col in customer_orders.columns):
                customer_orders.columns = [
                    col[0] if isinstance(col, tuple) and len(col) == 2 else col 
                    for col in customer_orders.columns
                ]
            
            # Process customer data (common logic)
            customer_orders = self._process_customer_data(customer_orders, logger)
        
        # STEP 5: Generate surrogate keys
        logger.info("Step 5: Generating surrogate keys...")
        customer_orders['customer_key'] = range(self.key_counters['customer_key'],
                                              self.key_counters['customer_key'] + len(customer_orders))
        self.key_counters['customer_key'] += len(customer_orders)
        
        # STEP 6: Skip complex analytics - just keep basic customer info
        
        # STEP 7: SCD Type 2 fields
        logger.info("Step 7: Adding SCD Type 2 fields...")
        current_time = datetime.now()
        customer_orders['effective_date'] = current_time
        # Use a future date within pandas timestamp limits
        customer_orders['expiry_date'] = pd.to_datetime('2262-04-11')
        customer_orders['is_current'] = True
        customer_orders['created_date'] = current_time
        customer_orders['updated_date'] = current_time
        
        # Update master key lookup with string keys for consistency  
        for _, row in customer_orders.iterrows():
            self.master_keys['customers'][str(row['buyer_user_name'])] = row['customer_key']
        
        # STEP 8: Clean DataFrame for PostgreSQL insertion
        logger.info("Step 8: Cleaning DataFrame for PostgreSQL insertion...")
        customer_orders_clean = self._clean_dataframe_for_postgres(customer_orders)
        
        return customer_orders_clean

    def _process_customer_data(self, customer_orders: pd.DataFrame, logger) -> pd.DataFrame:
        """Common logic to process customer data after groupby"""
        # Rename columns to meaningful names
        column_rename_map = {
            'ship_country': 'country',
            'ship_state': 'state',
            'ship_city': 'city',
            'ship_zipcode': 'zipcode',
            'payment_method': 'payment_method',
            'date_shipped': 'ship_date',
            'street_1': 'street_1',
            'street_2': 'street_2'
        }
        
        if column_rename_map:
            customer_orders = customer_orders.rename(columns=column_rename_map)
        
        # Add missing columns as null
        expected_columns = [
            'buyer_user_name', 'full_name', 'first_name', 'last_name',
            'country', 'state', 'city', 'zipcode',
            'payment_method', 'ship_date', 'street_1', 'street_2',
            'ship_name'
        ]
        
        for col in expected_columns:
            if col not in customer_orders.columns:
                customer_orders[col] = None
        
        # Reorder columns
        customer_orders = customer_orders[expected_columns]
        
        
        return customer_orders

    def build(self, orders_df: pd.DataFrame, direct_checkout_df: pd.DataFrame) -> pd.DataFrame:
        """Main build method for customer dimension"""
        return self.build_customer_dimension(orders_df, direct_checkout_df)
