import pandas as pd
from datetime import datetime
import logging
import json
from ..base_builder import BaseBuilder
from etl.utils_core import clean_text_field, clean_currency_amount

logger = logging.getLogger('product')

class ProductDimensionBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_product_dimension(self, listing_df: pd.DataFrame, order_items_df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Building product dimension...")

        has_listing = listing_df is not None and not listing_df.empty
        has_order_items = order_items_df is not None and not order_items_df.empty
        
        if not has_listing and not has_order_items:
            logger.warning("No listing or order_items data provided, returning empty product dimension")
            return pd.DataFrame(columns=['product_key', 'listing_id', 'title', 'description', 'price', 
                                        'quantity', 'materials', 'tags', 'sku'])

        if not has_listing:
            listing_df = pd.DataFrame()
        if not has_order_items:
            order_items_df = pd.DataFrame()

        listing_needed_cols = []
        listing_col_mapping = {}

        for col in listing_df.columns if has_listing else []:
            if col == 'title':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'title'
            elif col == 'description':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'description'
            elif col == 'price':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'price'
            elif col == 'tags':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'tags'
            elif col == 'materials':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'materials'
            elif col == 'quantity':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'quantity'
            elif col == 'sku':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'sku'
            elif col == 'variation_1_type':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'variation_1_type'
            elif col == 'variation_1_name':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'variation_1_name'
            elif col == 'variation_1_values':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'variation_1_values'
            elif col == 'variation_2_type':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'variation_2_type'
            elif col == 'variation_2_name':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'variation_2_name'
            elif col == 'variation_2_values':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'variation_2_values'
            elif col == 'image_urls':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'image_urls'

        if listing_needed_cols:
            listing_df = listing_df[listing_needed_cols].rename(columns=listing_col_mapping)

        items_needed_cols = []
        items_col_mapping = {}

        for col in order_items_df.columns if has_order_items else []:
            if col == 'listing_id':
                items_needed_cols.append(col)
                items_col_mapping[col] = 'listing_id'
            elif col == 'item_name':
                items_needed_cols.append(col)
                items_col_mapping[col] = 'item_name'
            elif col == 'sku':
                items_needed_cols.append(col)
                items_col_mapping[col] = 'item_sku'

        if items_needed_cols:
            order_items_df = order_items_df[items_needed_cols].rename(columns=items_col_mapping)

        if has_order_items and 'listing_id' in order_items_df.columns:
            before_dupe = len(order_items_df)
            order_items_df = order_items_df.sort_index().drop_duplicates(subset=['listing_id'], keep='first')
            logger.info(f"Deduplicated order_items by listing_id: {before_dupe} -> {len(order_items_df)}")

        def _norm(s):
            try:
                return str(s).strip().lower()
            except Exception:
                return None

        if has_listing and has_order_items:
            if 'title' in listing_df.columns:
                listing_df['__join_key__'] = listing_df['title'].apply(_norm)
            else:
                listing_df['__join_key__'] = None

            if 'item_name' in order_items_df.columns:
                order_items_df['__join_key__'] = order_items_df['item_name'].apply(_norm)
            else:
                order_items_df['__join_key__'] = None

            products = pd.merge(listing_df, order_items_df, on='__join_key__', how='outer', suffixes=('_listing', '_items'))
            products = products.drop(columns=['__join_key__'], errors='ignore')
        elif has_listing:
            products = listing_df.copy()
        else:
            products = order_items_df.copy()

        products = self._process_product_data(products, logger)

        products['product_key'] = range(self.key_counters['product_key'], 
                                      self.key_counters['product_key'] + len(products))
        self.key_counters['product_key'] += len(products)

        for _, row in products.iterrows():
            listing_id_key = str(int(float(row['listing_id']))) if pd.notna(row['listing_id']) else None
            if listing_id_key:
                self.master_keys['products'][listing_id_key] = row['product_key']

        products_clean = self._clean_dataframe_for_postgres(products)

        return products_clean

    def _process_product_data(self, products: pd.DataFrame, logger) -> pd.DataFrame:
        if 'item_name' in products.columns:
            if 'title' in products.columns:
                products['title'] = products['title'].fillna(products['item_name'])
            else:
                products['title'] = products['item_name']
            products = products.drop(columns=['item_name'], errors='ignore')

        if 'item_price' in products.columns:
            if 'price' in products.columns:
                products['price'] = products['price'].fillna(products['item_price'])
            else:
                products['price'] = products['item_price']
            products = products.drop(columns=['item_price'], errors='ignore')

        if 'item_sku' in products.columns:
            if 'sku' in products.columns:
                products['sku'] = products['sku'].fillna(products['item_sku'])
            else:
                products['sku'] = products['item_sku']
            products = products.drop(columns=['item_sku'], errors='ignore')
            
        if 'item_quantity' in products.columns:
            products = products.drop(columns=['item_quantity'], errors='ignore')
        
        if 'title' in products.columns:
            products['title'] = products['title'].apply(lambda x: clean_text_field(x, None) if pd.notna(x) else None)
        else:
            products['title'] = None
            
        if 'description' in products.columns:
            products['description'] = products['description'].apply(lambda x: clean_text_field(x, None) if pd.notna(x) else None)
        else:
            products['description'] = None

        if 'tags' in products.columns:
            products['tags'] = products['tags'].apply(
                lambda x: json.dumps(self._parse_comma_separated(x)) if isinstance(x, str) and x.strip() else (json.dumps(self._parse_comma_separated(x)) if pd.notna(x) else None)
            )
        else:
            products['tags'] = None

        if 'materials' in products.columns:
            products['materials'] = products['materials'].apply(
                lambda x: json.dumps(self._parse_comma_separated(x)) if isinstance(x, str) and x.strip() else (json.dumps(self._parse_comma_separated(x)) if pd.notna(x) else None)
            )
        else:
            products['materials'] = None

        if 'quantity' in products.columns:
            products['quantity'] = pd.to_numeric(products['quantity'], errors='coerce').astype('Int64')
        else:
            products['quantity'] = pd.Series(dtype='Int64')

        output_columns = [
            'product_key', 'listing_id', 'title', 'description', 'price', 
            'quantity', 'materials', 'tags',
            'variation_1_type', 'variation_1_name', 'variation_1_values',
            'variation_2_type', 'variation_2_name', 'variation_2_values',
            'image_urls', 'sku'
        ]
        
        for col in output_columns:
            if col not in products.columns:
                products[col] = None

        return products[output_columns]

    def build(self, listing_df: pd.DataFrame, order_items_df: pd.DataFrame) -> pd.DataFrame:
        return self.build_product_dimension(listing_df, order_items_df)
