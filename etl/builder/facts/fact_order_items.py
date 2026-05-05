import pandas as pd
from datetime import datetime
import logging
from typing import Dict
from ..base_builder import BaseBuilder

logger = logging.getLogger("fact_order_items")

class SalesFactBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_sales_fact(self, sold_order_items_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        if sold_order_items_df is None or sold_order_items_df.empty:
            logger.warning("sold_order_items_df is None or empty, returning empty fact_order_items")
            return pd.DataFrame(columns=['order_item_key', 'order_id', 'transaction_id', 'quantity_sold'])
        
        fact = sold_order_items_df.copy()

        fact['order_item_key'] = range(1, len(fact) + 1)

        col_map = {}
        for col in fact.columns:
            if col == 'order_id':
                col_map[col] = 'order_id'
            elif col == 'listing_id':
                col_map[col] = 'listing_id'
            elif col == 'transaction_id':
                col_map[col] = 'transaction_id'
            elif col == 'price':
                col_map[col] = 'price'
            elif col == 'quantity':
                col_map[col] = 'quantity_sold'
            elif col == 'item_total':
                col_map[col] = 'item_total'
            elif col == 'sku':
                col_map[col] = 'sku'
            elif col == 'variations':
                col_map[col] = 'variations'
            elif col == 'vat_paid_by_buyer':
                col_map[col] = 'vat_paid_by_buyer'
            elif col == 'date_paid':
                col_map[col] = 'date_paid'
        if col_map:
            fact = fact.rename(columns=col_map)

        try:
            logger.info(f"Fact order_items - Master keys products: {len(self.master_keys['products'])} entries")
            logger.info(f"Fact order_items - Master keys orders: {len(self.master_keys['orders'])} entries")

            if 'listing_id' in fact.columns:
                fact['listing_id'] = fact['listing_id'].apply(
                    lambda x: str(int(float(x))) if pd.notna(x) else None
                )
                fact['product_key'] = fact['listing_id'].map(self.master_keys['products'])
                logger.info(f"Fact order_items - Mapped product_key: {fact['product_key'].notna().sum()} non-null values")
            else:
                fact['product_key'] = None

            if 'order_id' in fact.columns:
                fact['order_id'] = fact['order_id'].astype(str)
                fact['order_key'] = fact['order_id'].map(self.master_keys['orders'])
                logger.info(f"Fact order_items - Mapped order_key: {fact['order_key'].notna().sum()} non-null values")
            else:
                fact['order_key'] = None

        except Exception as e:
            logger.warning(f"Error mapping keys in order_items: {e}")
            fact['product_key'] = None
            fact['order_key'] = None

        if 'date_paid' in fact.columns:
            fact['date_paid'] = pd.to_datetime(fact['date_paid'], errors='coerce').dt.date
        else:
            fact['date_paid'] = None

        fact_cols = [
            'order_item_key', 'order_key', 'product_key',
            'transaction_id', 'order_id', 'sku', 'listing_id', 'quantity_sold',
            'price', 'item_total', 'variations', 'date_paid',
            'vat_paid_by_buyer'
        ]

        for col in fact_cols:
            if col not in fact.columns:
                fact[col] = None

        fact = self._clean_dataframe_for_postgres(fact)

        return fact[fact_cols]

    def build(self, sold_order_items_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        return self.build_sales_fact(sold_order_items_df, datasets)
