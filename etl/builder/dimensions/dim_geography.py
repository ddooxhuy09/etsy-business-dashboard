"""
Geography Dimension Builder
Builds geography dimension from shipping addresses
"""

import pandas as pd
from datetime import datetime
import logging
import hashlib
from ..base_builder import BaseBuilder

logger = logging.getLogger('geography')

class GeographyDimensionBuilder(BaseBuilder):
    """Build geography dimension from shipping addresses"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_geography_dimension(self, orders_df: pd.DataFrame) -> pd.DataFrame:
        """Build geography dimension from shipping addresses"""
        logger.info("Building geography dimension...")

        # Map column names for geography (handle case sensitivity)
        geo_column_mapping = {}
        for col in orders_df.columns:
            if col.upper() == 'SHIP_COUNTRY':
                geo_column_mapping[col] = 'ship_country'
            elif col.upper() == 'SHIP_STATE':
                geo_column_mapping[col] = 'ship_state'
            elif col.upper() == 'SHIP_CITY':
                geo_column_mapping[col] = 'ship_city'
            elif col.upper() == 'SHIP_ZIPCODE':
                geo_column_mapping[col] = 'ship_zipcode'

        if geo_column_mapping:
            orders_df = orders_df.rename(columns=geo_column_mapping)

        # Check if required columns exist
        if 'ship_country' not in orders_df.columns:
            logger.error("ship_country column not found in orders data")
            return pd.DataFrame(columns=['geography_key', 'country_name', 'continent'])
        
        # Extract unique geographic combinations
        geo_columns = ['ship_country', 'ship_state', 'ship_city', 'ship_zipcode']
        unique_geos = orders_df[geo_columns].drop_duplicates().dropna(subset=['ship_country'])
        
        # Generate location hash for lookup
        unique_geos['location_hash'] = unique_geos.apply(
            lambda row: hashlib.md5(f"{row['ship_country']}|{row['ship_state']}|{row['ship_city']}".encode()).hexdigest()[:16],
            axis=1
        )
        
        # Generate surrogate keys
        unique_geos['geography_key'] = range(self.key_counters['geography_key'],
                                           self.key_counters['geography_key'] + len(unique_geos))
        self.key_counters['geography_key'] += len(unique_geos)
        
        # Add geographic hierarchies and business logic
        unique_geos['continent'] = unique_geos['ship_country'].map(self._get_continent)
        unique_geos['region'] = unique_geos['ship_country'].map(self._get_region)
        unique_geos['etsy_market'] = unique_geos['ship_country'].map(self._get_etsy_market)
        unique_geos['shipping_zone'] = unique_geos['ship_country'].apply(
            lambda x: 'Domestic' if x == 'United States' else 'International'
        )
        unique_geos['currency_code'] = unique_geos['ship_country'].map(self._get_country_currency)
        unique_geos['timezone'] = unique_geos['ship_country'].map(self._get_timezone)
        
        # Rename columns to match schema
        unique_geos = unique_geos.rename(columns={
            'ship_country': 'country_name',
            'ship_state': 'state_name',
            'ship_city': 'city_name',
            'ship_zipcode': 'postal_code'
        })

        # Add missing columns for geography dimension
        # Note: country_code, state_code, sub_region are not in PostgreSQL schema
        
        unique_geos['created_date'] = datetime.now()
        unique_geos['updated_date'] = datetime.now()
        
        # Update master key lookup
        for _, row in unique_geos.iterrows():
            self.master_keys['geographies'][row['location_hash']] = row['geography_key']
        
        # Clean DataFrame for PostgreSQL insertion
        unique_geos_clean = self._clean_dataframe_for_postgres(unique_geos)
        
        return unique_geos_clean

    def build(self, orders_df: pd.DataFrame) -> pd.DataFrame:
        """Main build method for geography dimension"""
        return self.build_geography_dimension(orders_df)
