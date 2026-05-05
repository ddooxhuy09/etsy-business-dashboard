import pandas as pd
from datetime import datetime
import logging
from ..base_builder import BaseBuilder
from etl.utils_core import clean_text_field

logger = logging.getLogger('product_line')

COLUMN_MAP = {
    'Product line ID': 'product_line_id',
    'Product line': 'product_line',
    'Product ID': 'product_id',
    'Product': 'product',
    'Variant ID': 'variant_id',
    'Variants': 'variants',
    'product_line_name': 'product_line',
    'product_name': 'product',
    'variant_name': 'variants',
}


class ProductCatalogDimensionBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_product_catalog_dimension(self, product_catalog_df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Building product line dimension...")
        
        dim = product_catalog_df.copy()
        
        for old_col, new_col in COLUMN_MAP.items():
            if old_col in dim.columns:
                dim = dim.rename(columns={old_col: new_col})

        text_fields = ['product_line_id', 'product_line', 'product_id', 
                       'product', 'variant_id', 'variants']
        
        for field in text_fields:
            if field in dim.columns:
                dim[field] = dim[field].apply(
                    lambda x: clean_text_field(x, 200) if pd.notna(x) else None
                )

        dim['dim_product_line_key'] = range(
            self.key_counters.get('product_line_key', 1),
            self.key_counters.get('product_line_key', 1) + len(dim)
        )
        self.key_counters['product_line_key'] = (
            self.key_counters.get('product_line_key', 1) + len(dim)
        )

        for _, row in dim.iterrows():
            composite_key = f"{row['product_line_id']}_{row['product_id']}_{row['variant_id']}"
            self.master_keys['product_lines'][composite_key] = row['dim_product_line_key']

        output_columns = [
            'dim_product_line_key',
            'variant_id',
            'product_line_id',
            'product_line',
            'product_id',
            'product',
            'variants',
        ]
        
        for col in output_columns:
            if col not in dim.columns:
                dim[col] = None

        dim_clean = self._clean_dataframe_for_postgres(dim)
        
        logger.info(f"Built product line dimension with {len(dim_clean):,} records")
        
        return dim_clean[output_columns]

    def build(self, product_catalog_df: pd.DataFrame) -> pd.DataFrame:
        return self.build_product_catalog_dimension(product_catalog_df)
