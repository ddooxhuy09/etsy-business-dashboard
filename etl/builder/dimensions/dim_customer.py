import logging

import pandas as pd

from ..base_builder import BaseBuilder

logger = logging.getLogger('customer')


class CustomerDimensionBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_customer_dimension(
        self,
        orders_df: pd.DataFrame,
        direct_checkout_df: pd.DataFrame,
    ) -> pd.DataFrame:
        logger.info("Building customer dimension...")

        output_cols = ['customer_key', 'buyer_user_name', 'full_name']
        if orders_df is None or orders_df.empty:
            logger.warning("orders_df is None or empty, cannot build customer dimension")
            return pd.DataFrame(columns=output_cols)

        orders = orders_df.copy()
        checkout = direct_checkout_df.copy() if direct_checkout_df is not None else pd.DataFrame()

        if 'order_id' not in orders.columns:
            logger.error("order_id column not found in orders data")
            return pd.DataFrame(columns=output_cols)

        # Keep order_id, full_name, and buyer_user_id from sold_orders
        orders_cols = ['order_id']
        if 'full_name' in orders.columns:
            orders_cols.append('full_name')
        if 'buyer_user_id' in orders.columns:
            orders_cols.append('buyer_user_id')
        orders = orders[orders_cols]

        has_checkout = (
            not checkout.empty
            and {'order_id', 'buyer_username'}.issubset(checkout.columns)
        )

        if has_checkout:
            checkout = checkout[['order_id', 'buyer_username']].rename(
                columns={'buyer_username': 'buyer_user_name'}
            )
            # Outer merge brings in buyer_user_name from checkout and
            # buyer_user_id from sold_orders on the same order_id row.
            customers = orders.merge(checkout, on='order_id', how='outer')
            group_col = 'buyer_user_name'
        elif 'buyer_user_id' in orders.columns:
            # No checkout: identify customers by their Etsy user ID
            customers = orders.rename(columns={'buyer_user_id': 'buyer_user_name'})
            logger.warning("direct_checkout not available; using buyer_user_id as customer identifier")
            group_col = 'buyer_user_name'
        else:
            logger.error("No valid customer identifier found in orders or checkout data")
            return pd.DataFrame(columns=output_cols)

        customers = customers.dropna(subset=[group_col])

        agg = {}
        if 'full_name' in customers.columns:
            agg['full_name'] = 'first'
        if 'buyer_user_id' in customers.columns:
            agg['buyer_user_id'] = 'first'

        customers = customers.groupby(group_col, as_index=False).agg(agg if agg else 'first')
        if 'full_name' not in customers.columns:
            customers['full_name'] = None

        customers['customer_key'] = range(
            self.key_counters['customer_key'],
            self.key_counters['customer_key'] + len(customers),
        )
        self.key_counters['customer_key'] += len(customers)

        # Register buyer_user_name AND buyer_user_id as lookup keys for the same customer.
        # fact_orders resolves customer_key via buyer_username first, then buyer_user_id fallback.
        for _, row in customers.iterrows():
            ck = row['customer_key']
            self.master_keys['customers'][str(row[group_col])] = ck
            if 'buyer_user_id' in customers.columns:
                uid = row.get('buyer_user_id')
                if uid is not None and str(uid) not in ('None', 'nan', ''):
                    self.master_keys['customers'][str(uid)] = ck

        logger.info(
            f"Built customer dimension: {len(customers)} customers, "
            f"{len(self.master_keys['customers'])} master key entries"
        )

        customers = self._clean_dataframe_for_postgres(customers)
        return customers[output_cols]

    def build(self, orders_df: pd.DataFrame, direct_checkout_df: pd.DataFrame) -> pd.DataFrame:
        return self.build_customer_dimension(orders_df, direct_checkout_df)
