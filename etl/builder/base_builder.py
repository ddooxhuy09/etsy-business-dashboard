"""
Base builder class for star schema dimensions and facts
Contains common functionality and utilities
"""

import pandas as pd
import numpy as np
from datetime import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from etl.utils_core import setup_logging, clean_text_field, get_schema_for_dataframe
import hashlib
import json

# Setup logging
logger = setup_logging()

class BaseBuilder:
    """Base class for all dimension and fact builders"""

    def __init__(self, output_path: str = "data/warehouse"):
        self.output_path = Path(output_path) if isinstance(output_path, str) else output_path
        # Không mkdir: pipeline chỉ ghi DB. output_path dùng cho save_to_parquet nếu gọi.

        # Surrogate key counters
        self.key_counters = {
            'product_key': 1,
            'customer_key': 1, 
            'order_key': 1,
            'geography_key': 1,
            'payment_key': 1
        }
        
        # Master data lookups for referential integrity
        self.master_keys = {
            'products': {},      # listing_id -> product_key
            'customers': {},     # buyer_user_id -> customer_key
            'orders': {},        # order_id -> order_key
            'geographies': {},   # location_hash -> geography_key
            'payments': {}       # payment_method -> payment_key
        }

    def _parse_comma_separated(self, text) -> List[str]:
        """Parse comma-separated string into list with comprehensive error handling"""
        try:
            # Safe check for None/NaN values first
            try:
                if text is None:
                    return []
                # Safe NaN check
                if hasattr(text, '__class__') and 'numpy' in str(text.__class__) and hasattr(text, 'isnan'):
                    if text.isnan():
                        return []
                elif str(text).lower() in ['nan', 'none', 'null', '']:
                    return []
            except:
                pass

            # Handle numpy/pandas arrays safely
            text_type_str = str(type(text))
            if 'numpy' in text_type_str or 'array' in text_type_str.lower():
                try:
                    if hasattr(text, 'tolist'):
                        text_list = text.tolist()
                    else:
                        try:
                            text_list = list(text)
                        except:
                            text_list = []

                    if len(text_list) == 0:
                        return []

                    result = []
                    for item in text_list:
                        try:
                            if item is not None:
                                item_str = str(item).strip()
                                if item_str:
                                    result.append(item_str)
                        except:
                            continue
                    return result
                except Exception as e:
                    return []

            # Handle regular strings
            if isinstance(text, str):
                text_str = text.strip()
                if not text_str:
                    return []

                # Handle JSON string format
                if text_str.startswith('[') and text_str.endswith(']'):
                    try:
                        parsed_list = json.loads(text_str)
                        if isinstance(parsed_list, list):
                            result = []
                            for item in parsed_list:
                                try:
                                    if item is not None:
                                        item_str = str(item).strip()
                                        if item_str:
                                            result.append(item_str)
                                except:
                                    continue
                            return result
                    except:
                        pass

                # Regular comma-separated string
                try:
                    items = text_str.split(',')
                    result = []
                    for item in items:
                        item_str = item.strip()
                        if item_str:
                            result.append(item_str)
                    return result
                except:
                    return []

            # Handle other types (lists, etc.)
            if isinstance(text, list):
                result = []
                for item in text:
                    try:
                        if item is not None:
                            item_str = str(item).strip()
                            if item_str:
                                result.append(item_str)
                    except:
                        continue
                return result

            # Convert to string as fallback
            try:
                text_str = str(text).strip()
                if not text_str:
                    return []
                items = text_str.split(',')
                result = []
                for item in items:
                    item_str = item.strip()
                    if item_str:
                        result.append(item_str)
                return result
            except:
                return []

        except:
            return []

    def _clean_dataframe_for_postgres(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean DataFrame for PostgreSQL insertion"""
        df_clean = df.copy()
        
        # Replace 'None' strings and pd.NA with actual None/NaN for all columns
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':  # String columns
                try:
                    # Check if column contains arrays that would cause comparison issues
                    sample_val = df_clean[col].dropna().iloc[0] if not df_clean[col].dropna().empty else None
                    
                    # If sample value is array-like, skip string replacement for this column
                    if sample_val is not None and hasattr(sample_val, '__len__') and not isinstance(sample_val, (str, bytes)):
                        continue
                    
                    # Replace string representations of None/NA
                    df_clean[col] = df_clean[col].replace(['None', 'none', 'NONE', 'null', 'NULL', 'nan', 'NaN'], None)
                    df_clean[col] = df_clean[col].replace(['', ' '], None)  # Empty strings
                    # Replace pd.NA with None
                    df_clean[col] = df_clean[col].where(df_clean[col] != pd.NA, None)
                except Exception:
                    # Skip problematic columns
                    continue
        
        # Convert numeric columns that might have 'None' strings or pd.NA
        for col in df_clean.columns:
            if col.endswith('_key') and df_clean[col].dtype == 'object':
                # Convert foreign key columns to proper numeric type
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            elif col in ['listing_id', 'order_id', 'transaction_id'] and df_clean[col].dtype == 'object':
                # Convert ID columns to proper numeric type
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        
        # Convert price columns to proper decimal type
        price_columns = ['price', 'item_price', 'item_total', 'discount_amount', 'shipping_amount', 
                        'sales_tax', 'net_sales', 'processing_fees', 'etsy_fees', 'total_fees', 
                        'gross_profit', 'profit_margin']
        for col in price_columns:
            if col in df_clean.columns and df_clean[col].dtype == 'object':
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        
        # Special handling for listing_id column
        if 'listing_id' in df_clean.columns:
            # Convert pd.NA to None for listing_id
            df_clean['listing_id'] = df_clean['listing_id'].where(df_clean['listing_id'] != pd.NA, None)
            # Convert to numeric, but keep None values
            df_clean['listing_id'] = pd.to_numeric(df_clean['listing_id'], errors='coerce')
        
        # Final cleanup: replace any remaining 'None' strings
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                try:
                    # Check if column contains arrays that would cause comparison issues
                    sample_val = df_clean[col].dropna().iloc[0] if not df_clean[col].dropna().empty else None
                    
                    # If sample value is array-like, skip string replacement for this column
                    if sample_val is not None and hasattr(sample_val, '__len__') and not isinstance(sample_val, (str, bytes)):
                        continue
                    
                    df_clean[col] = df_clean[col].replace(['None', 'none', 'NONE', 'null', 'NULL', 'nan', 'NaN'], None)
                except Exception:
                    # Skip problematic columns
                    continue
        
        logger.info(f"Cleaned DataFrame for PostgreSQL: {df_clean.shape}")
        return df_clean

    def _get_etsy_season(self, month: int) -> str:
        """Map month to Etsy selling season"""
        seasons = {
            1: 'Winter/Post-Holiday', 2: 'Winter/Valentine', 3: 'Spring',
            4: 'Spring/Easter', 5: 'Spring/Mother Day', 6: 'Summer',
            7: 'Summer', 8: 'Back-to-School', 9: 'Fall/Halloween',
            10: 'Fall/Halloween', 11: 'Holiday Season', 12: 'Holiday Season'
        }
        return seasons.get(month, 'Unknown')

    def _get_selling_season(self, month: int) -> str:
        """Map month to general selling season"""
        if month in [11, 12, 1]:
            return 'Holiday'
        elif month in [8, 9]:
            return 'Back-to-School'
        elif month in [4, 5]:
            return 'Spring'
        elif month in [6, 7]:
            return 'Summer'
        else:
            return 'Regular'

    def _get_holidays(self, dates) -> List:
        """Get major holidays for business calendar"""
        # Simplified - would implement proper holiday calculation
        return []

    def _get_continent(self, country: str) -> str:
        """Map country to continent"""
        continent_map = {
            'United States': 'North America',
            'Canada': 'North America', 
            'Mexico': 'North America',
            'United Kingdom': 'Europe',
            'Germany': 'Europe',
            'France': 'Europe',
            'Australia': 'Oceania',
            'Japan': 'Asia'
        }
        return continent_map.get(country, 'Unknown')

    def _get_region(self, country: str) -> str:
        """Map country to business region"""
        region_map = {
            'United States': 'North America',
            'Canada': 'North America',
            'United Kingdom': 'Western Europe',
            'Germany': 'Western Europe',
            'Australia': 'Asia Pacific'
        }
        return region_map.get(country, 'Other')

    def _get_etsy_market(self, country: str) -> str:
        """Map country to Etsy primary market"""
        if country == 'United States':
            return 'US'
        elif country in ['United Kingdom', 'Germany', 'France']:
            return 'EU'
        else:
            return 'International'

    def _get_country_currency(self, country: str) -> str:
        """Map country to primary currency"""
        currency_map = {
            'United States': 'USD',
            'Canada': 'CAD',
            'United Kingdom': 'GBP',
            'Germany': 'EUR',
            'France': 'EUR',
            'Australia': 'AUD',
            'Japan': 'JPY'
        }
        return currency_map.get(country, 'USD')

    def _get_timezone(self, country: str) -> str:
        """Map country to primary timezone"""
        timezone_map = {
            'United States': 'America/New_York',
            'Canada': 'America/Toronto',
            'United Kingdom': 'Europe/London',
            'Germany': 'Europe/Berlin',
            'Australia': 'Australia/Sydney'
        }
        return timezone_map.get(country, 'UTC')

    def save_to_parquet(self, df: pd.DataFrame, table_name: str, data_type: str = None):
        """Save DataFrame to Parquet with proper schema"""
        import pyarrow as pa
        import pyarrow.parquet as pq
        
        file_path = self.output_path / f"{table_name}.parquet"
        
        # Get proper schema
        if data_type:
            schema = get_schema_for_dataframe(data_type, df)
        else:
            schema = pa.Schema.from_pandas(df)
        
        # Convert to PyArrow table and save
        table = pa.Table.from_pandas(df, schema=schema)
        pq.write_table(table, file_path)
        
        logger.info(f"Saved {len(df)} rows to {file_path}")
