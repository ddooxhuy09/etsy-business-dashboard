"""
Order Dimension Builder
Builds order dimension with order characteristics
"""

import pandas as pd
from datetime import datetime
import logging
from ..base_builder import BaseBuilder

logger = logging.getLogger('order')

class OrderDimensionBuilder(BaseBuilder):
    """Build order dimension with order characteristics"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_order_dimension(self, orders_df: pd.DataFrame, direct_checkout_df: pd.DataFrame = None) -> pd.DataFrame:
        """Build Order Dimension theo chuẩn Etsy MDM"""
        # Handle None orders_df
        if orders_df is None or orders_df.empty:
            logger.warning("orders_df is None or empty, returning empty order dimension")
            return pd.DataFrame(columns=['order_key', 'order_id'])
        
        orders = orders_df.copy()
        
        # Handle direct_checkout_df if it's None or empty
        if direct_checkout_df is None or direct_checkout_df.empty:
            logger.warning("direct_checkout_df is None or empty, proceeding without it")
            # Check if order_id exists in orders_df
            if 'order_id' not in orders.columns:
                logger.error("No order_id column found in orders DataFrame and no direct_checkout data")
                return pd.DataFrame(columns=['order_key', 'order_id'])
        else:
            # Map column names for direct_checkout_df to get order_id
            checkout_column_mapping = {}
            for col in direct_checkout_df.columns:
                if col == 'order_id':
                    checkout_column_mapping[col] = 'order_id'
            
            if checkout_column_mapping:
                direct_checkout_df = direct_checkout_df.rename(columns=checkout_column_mapping)
            
            # Merge orders with direct_checkout to get order_id
            if 'order_id' in direct_checkout_df.columns and 'order_id' in orders_df.columns:
                orders = orders.merge(direct_checkout_df[['order_id']], on='order_id', how='outer')
            else:
                logger.warning("Could not find order_id column in one or both DataFrames")
                # Fallback: try to get order_id from orders_df if available
                if 'order_id' not in orders.columns:
                    logger.error("No order_id column found in either DataFrame")
                    return pd.DataFrame(columns=['order_key', 'order_id'])

        # Generate surrogate keys
        orders['order_key'] = range(self.key_counters['order_key'],
                                   self.key_counters['order_key'] + len(orders))
        self.key_counters['order_key'] += len(orders)

        # Order Characteristics
        orders['order_type'] = orders.get('order_type', None)
        orders['payment_method'] = orders.get('payment_method', None)
        orders['payment_type'] = orders.get('payment_type', None)
        orders['number_of_items'] = orders.get('number_of_items', None)

        # Financial Information
        orders['order_value'] = orders.get('order_value', None)
        orders['discount_amount'] = orders.get('discount_amount', None)
        orders['shipping_discount'] = orders.get('shipping_discount', None)
        orders['shipping'] = orders.get('shipping', None)
        orders['sales_tax'] = orders.get('sales_tax', None)
        orders['order_total'] = orders.get('order_total', None)
        orders['card_processing_fees'] = orders.get('card_processing_fees', None)
        orders['order_net'] = orders.get('order_net', None)
        orders['adjusted_order_total'] = orders.get('adjusted_order_total', None)
        orders['adjusted_card_processing_fees'] = orders.get('adjusted_card_processing_fees', None)
        orders['adjusted_net_order_amount'] = orders.get('adjusted_net_order_amount', None)

        # Discounts & Promotions
        orders['coupon_code'] = orders.get('coupon_code', None)
        orders['coupon_details'] = orders.get('coupon_details', None)

        # Safely check discount amount with error handling
        if 'discount_amount' in orders.columns:
            orders['has_discount'] = orders['discount_amount'].apply(
                lambda x: pd.notna(x) and float(x) > 0 if pd.notna(x) else False
            )
        else:
            orders['has_discount'] = False

        orders['discount_type'] = orders['coupon_code'].apply(
            lambda x: 'Percentage' if x and '%' in str(x) else 'Fixed' if x else None
        )

        # Shipping Info
        orders['shipping_method'] = None  # No default value
        orders['shipping_country'] = orders.get('ship_country', None)
        orders['shipping_state'] = orders.get('ship_state', None)
        orders['shipping_city'] = orders.get('ship_city', None)
        orders['is_international'] = orders['ship_country'].apply(
            lambda x: False if x == 'United States' else True if pd.notna(x) else None
        )


        # Special Attributes
        orders['is_gift'] = False  # Default to False
        orders['has_personalization'] = False  # Default to False
        orders['in_person_location'] = orders.get('inperson_location', None)

        # Update master key lookup with string keys for consistency
        for _, row in orders.iterrows():
            self.master_keys['orders'][str(row['order_id'])] = row['order_key']

        # Audit Fieldsơ-p0o9i8k
        orders['created_date'] = datetime.now()
        orders['updated_date'] = datetime.now()

        # Select columns theo schema design
        order_cols = [
            'order_key', 'order_id', 'order_type', 'payment_method', 'payment_type',
            'number_of_items', 'order_value', 'discount_amount', 'shipping_discount', 'shipping',
            'sales_tax', 'order_total', 'card_processing_fees', 'order_net', 'adjusted_order_total',
            'adjusted_card_processing_fees', 'adjusted_net_order_amount', 'coupon_code', 'coupon_details', 
            'has_discount', 'discount_type', 'shipping_method', 'shipping_country', 'shipping_state', 
            'shipping_city', 'is_international', 'is_gift', 
            'has_personalization', 'in_person_location', 'created_date', 'updated_date'
        ]

        return orders[order_cols]

    def build(self, orders_df: pd.DataFrame, direct_checkout_df: pd.DataFrame) -> pd.DataFrame:
        """Main build method for order dimension"""
        return self.build_order_dimension(orders_df, direct_checkout_df)
