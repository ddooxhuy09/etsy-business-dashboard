"""
Product Dimension Builder
Builds product master dimension with SCD Type 2
"""

import pandas as pd
from datetime import datetime
import logging
import json
from ..base_builder import BaseBuilder
from etl.utils_core import clean_text_field, clean_currency_amount

logger = logging.getLogger('product')

class ProductDimensionBuilder(BaseBuilder):
    """Build product dimension from listing and order items data"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def build_product_dimension(self, listing_df: pd.DataFrame, order_items_df: pd.DataFrame) -> pd.DataFrame:
        """Build product master dimension with SCD Type 2"""
        logger.info("Building product dimension...")

        # Handle None inputs - not all months have all files
        has_listing = listing_df is not None and not listing_df.empty
        has_order_items = order_items_df is not None and not order_items_df.empty
        
        if not has_listing and not has_order_items:
            logger.warning("No listing or order_items data provided, returning empty product dimension")
            return pd.DataFrame(columns=['product_key', 'listing_id', 'title', 'description', 'price', 
                                        'currency_code', 'quantity', 'is_current', 'effective_date', 
                                        'expiry_date', 'created_date', 'updated_date'])

        # Initialize empty DataFrames if None
        if not has_listing:
            logger.info("No listing data, building product dimension from order_items only")
            listing_df = pd.DataFrame()
        if not has_order_items:
            logger.info("No order_items data, building product dimension from listing only")
            order_items_df = pd.DataFrame()

        # STEP 1: Map column names for listing_df
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
            elif col == 'currency_code':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'currency_code'
            elif col == 'quantity':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'quantity'
            elif col == 'sku':
                listing_needed_cols.append(col)
                listing_col_mapping[col] = 'sku'

        # Lấy chỉ các cột cần thiết và rename
        if listing_needed_cols:
            listing_df = listing_df[listing_needed_cols].rename(columns=listing_col_mapping)

        # STEP 2: Map column names for order_items_df
        items_needed_cols = []
        items_col_mapping = {}

        for col in order_items_df.columns if has_order_items else []:
            if col == 'listing_id':
                items_needed_cols.append(col)
                items_col_mapping[col] = 'listing_id'
            elif col == 'item_name':
                items_needed_cols.append(col)
                items_col_mapping[col] = 'item_name'
            elif col == 'price':
                items_needed_cols.append(col)
                items_col_mapping[col] = 'item_price'
            elif col == 'quantity':
                items_needed_cols.append(col)
                items_col_mapping[col] = 'quantity'  # Map quantity from order_items
            elif col == 'sku':
                items_needed_cols.append(col)
                items_col_mapping[col] = 'item_sku'

        # Lấy chỉ các cột cần thiết và rename
        if items_needed_cols:
            order_items_df = order_items_df[items_needed_cols].rename(columns=items_col_mapping)

        # STEP 3: Deduplicate order items and full join by title vs item_name

        # Deduplicate order items by listing_id (keep first)
        if has_order_items and 'listing_id' in order_items_df.columns:
            before_dupe = len(order_items_df)
            order_items_df = order_items_df.sort_index().drop_duplicates(subset=['listing_id'], keep='first')
            logger.info(f"Deduplicated order_items by listing_id: {before_dupe} -> {len(order_items_df)}")

        # Prepare keys for join by normalized names
        def _norm(s):
            try:
                return str(s).strip().lower()
            except Exception:
                return None

        # Handle different scenarios based on available data
        if has_listing and has_order_items:
            # Both available - do full outer join
            if 'title' in listing_df.columns:
                listing_df['__join_key__'] = listing_df['title'].apply(_norm)
            else:
                listing_df['__join_key__'] = None

            if 'item_name' in order_items_df.columns:
                order_items_df['__join_key__'] = order_items_df['item_name'].apply(_norm)
            else:
                order_items_df['__join_key__'] = None

            # Full outer join by normalized title/item_name
            products = pd.merge(listing_df, order_items_df, on='__join_key__', how='outer', suffixes=('_listing', '_items'))
            products = products.drop(columns=['__join_key__'], errors='ignore')
        elif has_listing:
            # Only listing available
            products = listing_df.copy()
        else:
            # Only order_items available
            products = order_items_df.copy()

        # STEP 4: Process product data (common logic)
        products = self._process_product_data(products, logger)

        # STEP 5: Generate surrogate keys
        logger.info("Step 5: Generating surrogate keys...")
        products['product_key'] = range(self.key_counters['product_key'], 
                                      self.key_counters['product_key'] + len(products))
        self.key_counters['product_key'] += len(products)
        
        # STEP 6: SCD Type 2 fields
        logger.info("Step 6: Adding SCD Type 2 fields...")
        current_time = datetime.now()
        products['effective_date'] = current_time
        # Use a future date within pandas timestamp limits
        products['expiry_date'] = pd.to_datetime('2262-04-11')
        products['is_current'] = True
        products['created_date'] = current_time
        products['updated_date'] = current_time

        # Update master key lookup with string keys for consistency
        for _, row in products.iterrows():
            # Convert listing_id to int first to remove .0, then to string
            listing_id_key = str(int(float(row['listing_id']))) if pd.notna(row['listing_id']) else None
            if listing_id_key:
                self.master_keys['products'][listing_id_key] = row['product_key']

        # STEP 7: Clean DataFrame for PostgreSQL insertion
        logger.info("Step 7: Cleaning DataFrame for PostgreSQL insertion...")
        products_clean = self._clean_dataframe_for_postgres(products)

        return products_clean

    def _process_product_data(self, products: pd.DataFrame, logger) -> pd.DataFrame:
        """Common logic to process product data after merge"""
        # Prefer listing title; fill missing with item_name
        if 'item_name' in products.columns:
            if 'title' in products.columns:
                products['title'] = products['title'].fillna(products['item_name'])
            else:
                products['title'] = products['item_name']
            products = products.drop(columns=['item_name'], errors='ignore')

        # Prefer listing price; fill missing with item_price
        if 'item_price' in products.columns:
            if 'price' in products.columns:
                products['price'] = products['price'].fillna(products['item_price'])
            else:
                products['price'] = products['item_price']
            products = products.drop(columns=['item_price'], errors='ignore')

        # Prefer listing sku; fill missing with item_sku
        if 'item_sku' in products.columns:
            if 'sku' in products.columns:
                products['sku'] = products['sku'].fillna(products['item_sku'])
            else:
                products['sku'] = products['item_sku']
            products = products.drop(columns=['item_sku'], errors='ignore')
        
        # Clean text fields - handle NULL values (no length limit for TEXT columns)
        if 'title' in products.columns:
            products['title'] = products['title'].apply(lambda x: clean_text_field(x, None) if pd.notna(x) else None)
        else:
            products['title'] = None
            
        if 'description' in products.columns:
            products['description'] = products['description'].apply(lambda x: clean_text_field(x, None) if pd.notna(x) else None)
        else:
            products['description'] = None
        
        # Parse tags and materials into lists with error handling
        if 'tags' in products.columns:
            try:
                products['tags_list'] = products['tags'].apply(self._parse_comma_separated)
            except Exception as e:
                logger.warning(f"Error parsing tags: {e}")
                products['tags_list'] = [[]] * len(products)
        else:
            products['tags_list'] = [[]] * len(products)

        if 'materials' in products.columns:
            try:
                products['materials_list'] = products['materials'].apply(self._parse_comma_separated)
            except Exception as e:
                logger.warning(f"Error parsing materials: {e}")
                products['materials_list'] = [[]] * len(products)
        else:
            products['materials_list'] = [[]] * len(products)

        # Convert lists to JSON strings for PostgreSQL TEXT columns
        try:
            products['tags_list'] = products['tags_list'].apply(lambda x: json.dumps(x) if isinstance(x, list) else '[]')
        except Exception as e:
            logger.warning(f"Error converting tags_list to JSON: {e}")
            products['tags_list'] = '[]'

        try:
            products['materials_list'] = products['materials_list'].apply(lambda x: json.dumps(x) if isinstance(x, list) else '[]')
        except Exception as e:
            logger.warning(f"Error converting materials_list to JSON: {e}")
            products['materials_list'] = '[]'
        
        # Remove original tags and materials columns since we only need the _list versions
        products = products.drop(columns=['tags'], errors='ignore')
        products = products.drop(columns=['materials'], errors='ignore')
        
        # No classification - set to NULL
        products['category'] = None
        products['subcategory'] = None
        products['product_type'] = None
        
        # Set default values
        products['currency_code'] = products.get('currency_code', 'USD')
        # Ensure quantity is numeric to match INTEGER column in PostgreSQL
        if 'quantity' in products.columns:
            products['quantity'] = pd.to_numeric(products['quantity'], errors='coerce')
        else:
            products['quantity'] = None
        products['color'] = products.get('color', None)
        products['material'] = products.get('material', None)
        products['dimensions'] = products.get('dimensions', None)
        products['how_made'] = products.get('how_made', None)
        products['variation_1_type'] = products.get('variation_1_type', None)
        products['variation_1_name'] = products.get('variation_1_name', None)
        products['variation_1_values'] = products.get('variation_1_values', None)
        products['variation_2_type'] = products.get('variation_2_type', None)
        products['variation_2_name'] = products.get('variation_2_name', None)
        products['variation_2_values'] = products.get('variation_2_values', None)
        products['image_urls'] = '[]'
        products['primary_image_url'] = products.get('primary_image_url', None)
        # Handle SKU column - convert to list format for JSON
        def process_sku(x):
            try:
                # Handle numpy arrays first
                if hasattr(x, 'shape') and hasattr(x, 'dtype'):  # numpy array
                    if x.size == 0:
                        return '[]'
                    return json.dumps(x.tolist())
                
                # Handle pandas Series or other array-like objects
                if hasattr(x, '__len__') and not isinstance(x, (str, bytes)):
                    if len(x) == 0:
                        return '[]'
                    if isinstance(x, list):
                        return json.dumps(x)
                    else:
                        return json.dumps(list(x))
                
                # Handle scalar values
                if pd.isna(x) or x is None or x == '':
                    return '[]'
                
                # Handle strings
                if isinstance(x, str):
                    # If it looks like a list string, try to parse
                    if x.startswith('[') and x.endswith(']'):
                        try:
                            parsed = json.loads(x)
                            return json.dumps(parsed) if isinstance(parsed, list) else json.dumps([parsed])
                        except:
                            return json.dumps([x])
                    else:
                        return json.dumps([x])
                
                # For other scalar types
                return json.dumps([str(x)])
                
            except Exception:
                return '[]'
        
        products['sku_list'] = products.get('sku', '').apply(process_sku)
        
        # Remove original sku column since we only need the sku_list version
        products = products.drop(columns=['sku'], errors='ignore')
        
        products['story'] = products.get('story', None)
        products['instructions'] = products.get('instructions', None)
        products['how_use'] = products.get('how_use', None)
        products['fit_for'] = products.get('fit_for', None)
        products['country_origin'] = products.get('country_origin', None)


        return products

    def build(self, listing_df: pd.DataFrame, order_items_df: pd.DataFrame) -> pd.DataFrame:
        """Main build method for product dimension"""
        return self.build_product_dimension(listing_df, order_items_df)
