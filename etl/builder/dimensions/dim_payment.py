"""
Payment Dimension Builder
Builds payment dimension from multiple data sources
"""

import pandas as pd
from datetime import datetime
import logging
from typing import Dict
from ..base_builder import BaseBuilder

logger = logging.getLogger('payment')

class PaymentDimensionBuilder(BaseBuilder):
    """Build payment dimension from multiple sources"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_payment_dimension(self, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build Payment Dimension theo chuẩn Etsy MDM"""
        payment_methods = set()

        # Collect payment methods from different sources
        if 'sold_orders' in datasets:
            payment_methods.update(datasets['sold_orders'].get('payment_method', pd.Series()).dropna().unique())

        if 'direct_checkout' in datasets:
            payment_methods.update(datasets['direct_checkout'].get('payment_type', pd.Series()).dropna().unique())

        # Create payment dimension
        payments = pd.DataFrame({
            'payment_method': list(payment_methods)
        })

        if payments.empty:
            payments = pd.DataFrame({'payment_method': ['Unknown']})

        # Generate surrogate keys
        payments['payment_key'] = range(self.key_counters['payment_key'],
                                       self.key_counters['payment_key'] + len(payments))
        self.key_counters['payment_key'] += len(payments)

        # Update master key lookup with string keys for consistency
        for _, row in payments.iterrows():
            self.master_keys['payments'][str(row['payment_method'])] = row['payment_key']

        # Payment Method Details
        payments['payment_type'] = payments['payment_method'].apply(
            lambda x: 'Online' if 'online' in str(x).lower() else 'In-person' if 'inperson' in str(x).lower() else 'Online'
        )
        payments['payment_provider'] = payments['payment_method'].apply(
            lambda x: 'Etsy Payments' if 'credit' in str(x).lower() else 'PayPal' if 'paypal' in str(x).lower() else 'Other'
        )


        # Audit Fields
        payments['created_date'] = datetime.now()
        payments['updated_date'] = datetime.now()

        # Select columns theo schema design
        payment_cols = [
            'payment_key', 'payment_method', 'payment_type', 'payment_provider',
            'created_date', 'updated_date'
        ]

        return payments[payment_cols]

    def build(self, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Main build method for payment dimension"""
        return self.build_payment_dimension(datasets)
