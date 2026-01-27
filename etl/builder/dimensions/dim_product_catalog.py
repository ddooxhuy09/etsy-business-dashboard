"""
Product Catalog Dimension Builder
Builds dim_product_catalog. Input thường đã qua process_product_catalog (product_line_id, …).
product_code do DB generate: (product_line_id||'_'||product_id||'_'||variant_id) STORED.
"""

import pandas as pd
from datetime import datetime
import logging
from ..base_builder import BaseBuilder
from etl.utils_core import clean_text_field

logger = logging.getLogger('product_catalog')

# Map cột CSV gốc → tên DB (fallback khi chưa qua process_product_catalog)
COLUMN_MAP = {
    'Product line ID': 'product_line_id',
    'Product line': 'product_line_name',
    'Product ID': 'product_id',
    'Product': 'product_name',
    'Variant ID': 'variant_id',
    'Variants': 'variant_name',
}


class ProductCatalogDimensionBuilder(BaseBuilder):
    """Build product catalog dimension from product catalog data"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_product_catalog_dimension(self, product_catalog_df: pd.DataFrame) -> pd.DataFrame:
        """Build product catalog dimension. Không thêm product_code (DB generated)."""
        logger.info("Building product catalog dimension...")
        
        dim_product_catalog = product_catalog_df.copy()
        
        # STEP 1: Map column names (chỉ khi còn tên CSV gốc; sau process_product_catalog thì bỏ qua)
        for old_col, new_col in COLUMN_MAP.items():
            if old_col in dim_product_catalog.columns:
                dim_product_catalog = dim_product_catalog.rename(columns={old_col: new_col})
        
        # STEP 2: Clean text fields
        logger.info("Step 2: Cleaning text fields...")
        text_fields = ['product_line_id', 'product_line_name', 'product_id', 
                       'product_name', 'variant_id', 'variant_name']
        
        for field in text_fields:
            if field in dim_product_catalog.columns:
                dim_product_catalog[field] = dim_product_catalog[field].apply(
                    lambda x: clean_text_field(x, 200) if pd.notna(x) else None
                )
        
        # STEP 3: Generate surrogate keys
        logger.info("Step 3: Generating surrogate keys...")
        dim_product_catalog['product_catalog_key'] = range(
            self.key_counters.get('product_catalog_key', 1),
            self.key_counters.get('product_catalog_key', 1) + len(dim_product_catalog)
        )
        self.key_counters['product_catalog_key'] = (
            self.key_counters.get('product_catalog_key', 1) + len(dim_product_catalog)
        )
        
        # STEP 4: Add audit fields
        logger.info("Step 4: Adding audit fields...")
        current_time = datetime.now()
        dim_product_catalog['created_date'] = current_time
        dim_product_catalog['updated_date'] = current_time
        
        # STEP 5: Build lookup dictionary for foreign key resolution
        logger.info("Step 5: Building lookup dictionary...")
        # Create composite key for lookup: product_line_id_product_id_variant_id
        for _, row in dim_product_catalog.iterrows():
            composite_key = f"{row['product_line_id']}_{row['product_id']}_{row['variant_id']}"
            if not hasattr(self.master_keys, 'product_catalog'):
                self.master_keys['product_catalog'] = {}
            self.master_keys['product_catalog'][composite_key] = row['product_catalog_key']
        
        # STEP 6: Select and order columns
        logger.info("Step 6: Selecting and ordering columns...")
        output_columns = [
            'product_catalog_key',
            'product_line_id',
            'product_id',
            'variant_id',
            'product_line_name',
            'product_name',
            'variant_name',
            'created_date',
            'updated_date'
        ]
        
        # Ensure all columns exist
        for col in output_columns:
            if col not in dim_product_catalog.columns:
                dim_product_catalog[col] = None
        
        # STEP 7: Clean DataFrame for PostgreSQL
        logger.info("Step 7: Cleaning DataFrame for PostgreSQL insertion...")
        dim_product_catalog_clean = self._clean_dataframe_for_postgres(dim_product_catalog)
        
        logger.info(f"✅ Built product catalog dimension with {len(dim_product_catalog_clean):,} records")
        
        return dim_product_catalog_clean[output_columns]

    def build(self, product_catalog_df: pd.DataFrame) -> pd.DataFrame:
        """Main build method for product catalog dimension"""
        return self.build_product_catalog_dimension(product_catalog_df)

