import pandas as pd
from datetime import datetime
import logging
from typing import Dict
from ..base_builder import BaseBuilder

logger = logging.getLogger("fact_payments")

class PaymentsFactBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_payments_fact(self, direct_checkout_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        fact = direct_checkout_df.copy()

        fact['payment_key'] = range(1, len(fact) + 1)

        col_map = {}
        for col in fact.columns:
            if col == 'order_id':
                col_map[col] = 'order_id'
            elif col == 'payment_id':
                col_map[col] = 'payment_id'
            elif col == 'funds_available':
                col_map[col] = 'funds_available_date'
            elif col == 'gross_amount':
                col_map[col] = 'gross_amount'
            elif col == 'fees':
                col_map[col] = 'fees'
            elif col == 'net_amount':
                col_map[col] = 'net_amount'
            elif col == 'listing_amount':
                col_map[col] = 'listing_amount'
            elif col == 'refund_amount':
                col_map[col] = 'refund_amount'
            elif col == 'exchange_rate':
                col_map[col] = 'exchange_rate'
            elif col == 'vat_amount':
                col_map[col] = 'vat_amount'
            elif col == 'status':
                col_map[col] = 'payment_status'
        if col_map:
            fact = fact.rename(columns=col_map)

        if 'funds_available_date' in fact.columns:
            fact['funds_available_date'] = pd.to_datetime(fact['funds_available_date'], errors='coerce').dt.date
        else:
            fact['funds_available_date'] = None

        numeric_cols = ['gross_amount', 'fees', 'net_amount', 'listing_amount', 
                       'refund_amount', 'exchange_rate', 'vat_amount']
        for col in numeric_cols:
            if col in fact.columns:
                fact[col] = pd.to_numeric(fact[col], errors='coerce')

        fact_cols = [
            'payment_key', 'payment_id', 'order_id',
            'funds_available_date',
            'gross_amount', 'fees', 'net_amount', 'listing_amount',
            'refund_amount', 'exchange_rate', 'vat_amount',
            'payment_status'
        ]

        for col in fact_cols:
            if col not in fact.columns:
                fact[col] = None

        fact = self._clean_dataframe_for_postgres(fact)

        return fact[fact_cols]

    def build(self, direct_checkout_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        return self.build_payments_fact(direct_checkout_df, datasets)
