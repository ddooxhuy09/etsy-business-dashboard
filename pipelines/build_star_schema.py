from typing import Dict, Any
import pandas as pd
import logging
import sys
from pathlib import Path

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../dashboard
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from etl.builder.star_schema import StarSchema
from etl.loaders.csv_loader import CSVLoader

logger = logging.getLogger(__name__)


def build_star_schema(datasets: Dict[str, pd.DataFrame], *, save: bool = True) -> Dict[str, pd.DataFrame]:
    """Build the complete star schema using the refactored builder.

    Expected dataset keys if available:
      - 'listing'
      - 'sold_orders'
      - 'sold_order_items'
      - 'statement'
      - 'deposits'
      - 'direct_checkout'
    """
    builder = StarSchema()
    star_schema = builder.build_complete_star_schema(datasets)
    if save:
        builder.save_star_schema(star_schema, 
                               postgres_clear_existing=True)
    return star_schema


def save_star_schema(star_schema: Dict[str, pd.DataFrame]) -> Dict[str, bool]:
    """Persist built star schema to PostgreSQL."""
    builder = StarSchema()
    return builder.save_star_schema(star_schema, 
                                   postgres_clear_existing=True)


def build_and_save_star_schema(datasets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Convenience wrapper: build the star schema and save it to PostgreSQL."""
    return build_star_schema(datasets, save=True)


if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    parser = argparse.ArgumentParser(description="Build the Star Schema from CSV and save to PostgreSQL.")
    parser.add_argument("--period", type=str, help="Period (YYYY-MM) to read from data/raw (default: latest)")
    args = parser.parse_args()
    
    # Load datasets from CSV (CSVLoader uses RAW_BASE env or data/raw)
    logger.info(f"Loading datasets from data/raw/{args.period or 'latest'}...")
    csv_loader = CSVLoader(period=args.period)
    datasets = csv_loader.load_all_datasets()
    
    if not datasets:
        logger.error(f"No CSV files found for period. Nothing to build.")
        sys.exit(1)
    
    # Build and save to PostgreSQL
    star_schema = build_star_schema(datasets)
    
    logger.info(f"Built star schema with tables: {list(star_schema.keys())}")
    
    # Show table sizes
    for table_name, df in star_schema.items():
        logger.info(f"📊 {table_name}: {len(df):,} rows")
    
    logger.info("✅ Star schema saved to PostgreSQL successfully!")
