import pandas as pd
from datetime import datetime
import logging
from ..base_builder import BaseBuilder

logger = logging.getLogger('deposits')

class DepositsFactBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_deposits_fact(self, deposits_df: pd.DataFrame) -> pd.DataFrame:
        fact = deposits_df.copy()

        fact['deposit_key'] = range(1, len(fact) + 1)

        if 'date' in fact.columns:
            fact['deposit_date'] = pd.to_datetime(fact['date'], errors='coerce').dt.date
        else:
            fact['deposit_date'] = None

        fact['amount'] = fact.get('amount')
        fact['deposit_status'] = fact.get('status')

        if 'bank_account_ending_digits' not in fact.columns:
            fact['bank_account_ending_digits'] = None

        fact_cols = [
            'deposit_key', 'deposit_date', 'amount', 'deposit_status',
            'bank_account_ending_digits'
        ]

        for col in fact_cols:
            if col not in fact.columns:
                fact[col] = None

        fact = self._clean_dataframe_for_postgres(fact)

        return fact[fact_cols]

    def build(self, deposits_df: pd.DataFrame) -> pd.DataFrame:
        return self.build_deposits_fact(deposits_df)
