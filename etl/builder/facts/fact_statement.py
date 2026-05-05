import pandas as pd
from datetime import datetime
import logging
from typing import Dict
from ..base_builder import BaseBuilder

logger = logging.getLogger("fact_statement")

class FinancialTransactionsFactBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_financial_transactions_fact(self, statement_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        fact = statement_df.copy()

        fact['statement_key'] = range(1, len(fact) + 1)

        if 'date' in fact.columns:
            fact['entry_date'] = pd.to_datetime(fact['date'], errors='coerce').dt.date
        else:
            fact['entry_date'] = None

        if 'type' in fact.columns:
            fact['entry_type'] = fact['type']
        else:
            fact['entry_type'] = None

        fact['title'] = fact.get('title')
        fact['info'] = fact.get('info')
        fact['amount'] = fact.get('amount')
        
        if 'fees_taxes' in fact.columns:
            fact['fees_and_taxes'] = fact['fees_taxes']
        elif 'fees_and_taxes' in fact.columns:
            pass
        else:
            fact['fees_and_taxes'] = None
        
        fact['net'] = fact.get('net')
        fact['tax_details'] = fact.get('tax_details')

        if 'ref_order_id' not in fact.columns:
            fact['ref_order_id'] = None

        fact_cols = [
            'statement_key', 'entry_date', 'entry_type', 'title', 'info',
            'amount', 'fees_and_taxes', 'net', 'tax_details', 'ref_order_id'
        ]

        for col in fact_cols:
            if col not in fact.columns:
                fact[col] = None

        fact = self._clean_dataframe_for_postgres(fact)

        return fact[fact_cols]

    def build(self, statement_df: pd.DataFrame, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        return self.build_financial_transactions_fact(statement_df, datasets)
