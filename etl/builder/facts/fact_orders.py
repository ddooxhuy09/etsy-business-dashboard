import pandas as pd
from datetime import datetime
import logging
from ..base_builder import BaseBuilder

logger = logging.getLogger('order')

class OrderDimensionBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_order_dimension(self, orders_df: pd.DataFrame, direct_checkout_df: pd.DataFrame = None) -> pd.DataFrame:
        if orders_df is None or orders_df.empty:
            logger.warning("orders_df is None or empty, returning empty order dimension")
            return pd.DataFrame(columns=['order_key', 'order_id'])
        
        orders = orders_df.copy()
        
        if direct_checkout_df is None or direct_checkout_df.empty:
            if 'order_id' not in orders.columns:
                logger.error("No order_id column found in orders DataFrame")
                return pd.DataFrame(columns=['order_key', 'order_id'])
        else:
            if 'order_id' in direct_checkout_df.columns and 'order_id' in orders_df.columns:
                checkout_cols = ['order_id']
                if 'buyer_username' in direct_checkout_df.columns:
                    checkout_cols.append('buyer_username')
                orders = orders.merge(direct_checkout_df[checkout_cols], on='order_id', how='outer')
            else:
                if 'order_id' not in orders.columns:
                    logger.error("No order_id column found")
                    return pd.DataFrame(columns=['order_key', 'order_id'])

        orders['order_key'] = range(self.key_counters['order_key'],
                                   self.key_counters['order_key'] + len(orders))
        self.key_counters['order_key'] += len(orders)

        orders['order_type'] = orders.get('order_type', None)
        orders['payment_method'] = orders.get('payment_method', None)
        orders['payment_type'] = orders.get('payment_type', None)
        orders['number_of_items'] = orders.get('number_of_items', None)

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

        orders['order_status'] = orders.get('order_status', None)
        orders['coupon_code'] = orders.get('coupon_code', None)
        orders['coupon_details'] = orders.get('coupon_details', None)

        orders['street_1'] = orders.get('street_1', None)
        orders['street_2'] = orders.get('street_2', None)
        orders['shipping_country'] = orders.get('ship_country', None)
        orders['shipping_state'] = orders.get('ship_state', None)
        orders['shipping_city'] = orders.get('ship_city', None)
        orders['shipping_zipcode'] = orders.get('ship_zipcode', None)

        if 'sale_date' in orders.columns:
            orders['sale_date_key'] = pd.to_datetime(orders['sale_date'], errors='coerce').dt.date
        else:
            orders['sale_date_key'] = None

        if 'date_shipped' in orders.columns:
            orders['date_shipped'] = pd.to_datetime(orders['date_shipped'], errors='coerce').dt.date
        else:
            orders['date_shipped'] = None

        if 'buyer_user_id' not in orders.columns:
            orders['buyer_user_id'] = None

        if 'buyer_username' in orders.columns:
            orders['buyer_user_id'] = orders['buyer_user_id'].fillna(orders['buyer_username'])

        if self.master_keys.get('customers'):
            if 'buyer_username' in orders.columns:
                customer_lookup_key = orders['buyer_username'].fillna(orders['buyer_user_id'])
            else:
                customer_lookup_key = orders['buyer_user_id']
            orders['customer_key'] = customer_lookup_key.astype(str).map(self.master_keys['customers'])
            logger.info(f"Mapped customer_key: {orders['customer_key'].notna().sum()} non-null values")
        else:
            logger.warning("No customer master keys available; customer_key will be null")
            orders['customer_key'] = None

        for _, row in orders.iterrows():
            self.master_keys['orders'][str(row['order_id'])] = row['order_key']

        order_cols = [
            'order_key', 'order_id', 'sale_date_key', 'date_shipped',
            'customer_key', 'buyer_user_id',
            'order_type', 'payment_method', 'payment_type',
            'number_of_items', 'order_value', 'discount_amount', 'shipping_discount', 'shipping',
            'sales_tax', 'order_total', 'card_processing_fees', 'order_net', 'adjusted_order_total',
            'adjusted_card_processing_fees', 'adjusted_net_order_amount',
            'order_status', 'coupon_code', 'coupon_details', 
            'street_1', 'street_2', 'shipping_country', 'shipping_state', 
            'shipping_city', 'shipping_zipcode'
        ]

        for col in order_cols:
            if col not in orders.columns:
                orders[col] = None

        return orders[order_cols]

    def build(self, orders_df: pd.DataFrame, direct_checkout_df: pd.DataFrame) -> pd.DataFrame:
        return self.build_order_dimension(orders_df, direct_checkout_df)
