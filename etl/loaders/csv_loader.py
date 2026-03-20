import json
import os
import pandas as pd
from pathlib import Path
import logging
from typing import Dict, Optional, List
from config import DATA_FILES, get_app_root, get_latest_available_period, parse_period

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"


def _default_raw_base() -> str:
    return str(get_app_root() / "data" / "raw")


class CSVLoader:
    """Load CSV từ data/raw hoặc đường dẫn RAW_BASE khi đặt.
    Nếu có manifest.json trong thư mục, dùng filename trong manifest (tên file mỗi tháng có thể khác)."""
    
    def __init__(self, period: Optional[str] = None):
        """
        Initialize CSV Loader
        
        Args:
            period: Period in YYYY-MM format (e.g., '2025-01')
                   If None, uses latest available period
        """
        self.period = period or get_latest_available_period()
        self.year, self.month = parse_period(self.period)
        raw_base = os.getenv("RAW_BASE") or _default_raw_base()
        self.raw_data_path = Path(raw_base) / self.period
        
        logger.info(f"📁 CSV Loader initialized for period: {self.period}")
        logger.info(f"📂 Data path: {self.raw_data_path}")
        
        # Validate path exists
        if not self.raw_data_path.exists():
            raise FileNotFoundError(f"Data folder not found: {self.raw_data_path}")
    
    def _read_manifest(self) -> dict:
        p = self.raw_data_path / MANIFEST_FILENAME
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    
    def list_available_files(self) -> List[str]:
        """List all CSV files in the raw data folder"""
        csv_files = list(self.raw_data_path.glob("*.csv"))
        logger.info(f"📋 Found {len(csv_files)} CSV files:")
        for file in csv_files:
            logger.info(f"  - {file.name}")
        return [f.name for f in csv_files]
    
    def load_csv(self, filename: str, **kwargs) -> Optional[pd.DataFrame]:
        """
        Load a single CSV file
        
        Args:
            filename: Name of CSV file (e.g., 'EtsyListingsDownload.csv')
            **kwargs: Additional arguments to pass to pd.read_csv
            
        Returns:
            DataFrame or None if file not found
        """
        file_path = self.raw_data_path / filename
        
        if not file_path.exists():
            logger.error(f"❌ File not found: {filename}")
            return None
        
        try:
            logger.info(f"📥 Loading {filename}...")
            df = pd.read_csv(file_path, **kwargs)
            logger.info(f"✅ Loaded {len(df):,} rows from {filename}")
            return df
        except Exception as e:
            logger.error(f"❌ Error loading {filename}: {e}")
            return None
    
    def load_all_datasets(self) -> Dict[str, pd.DataFrame]:
        """
        Load all available CSV files in the period folder.
        Nếu có manifest.json: ưu tiên filename trong manifest (tên file mỗi tháng có thể khác).
        Không có manifest hoặc key không trong manifest: dùng pattern match như cũ.
        """
        datasets = {}
        manifest = self._read_manifest()
        
        # Map pattern -> dataset_key (để fallback khi không có manifest)
        file_mappings = {
            "EtsyListingsDownload.csv": "listing",
            "EtsySoldOrders": "sold_orders",
            "EtsySoldOrderItems": "sold_order_items",
            "etsy_statement_": "statement",
            "EtsyDeposits": "deposits",
            "EtsyDirectCheckoutPayments": "direct_checkout",
            "fact_bank_transactions.csv": "bank_transactions",
            "product_catalog.csv": "product_catalog",
            "dim_bank_account.csv": "dim_bank_account",
        }
        
        csv_files = self.list_available_files()
        logger.info(f"\n📥 Loading datasets...")
        
        for pattern, dataset_key in file_mappings.items():
            ent = manifest.get(dataset_key)
            filenames = []
            if isinstance(ent, dict) and ent.get("filename"):
                filenames = [ent["filename"]]
            elif isinstance(ent, list):
                filenames = [e["filename"] for e in ent if isinstance(e, dict) and e.get("filename")]
            if filenames:
                dfs = [self.load_csv(f) for f in filenames]
                dfs = [x for x in dfs if x is not None]
                if dfs:
                    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
                    datasets[dataset_key] = df
                    logger.info(f"✅ Mapped {', '.join(filenames)} → {dataset_key} ({len(dfs)} file, manifest)")
            if dataset_key in datasets:
                continue
            # Fallback: pattern match
            for csv_file in csv_files:
                if pattern in csv_file:
                    df = self.load_csv(csv_file)
                    if df is not None:
                        datasets[dataset_key] = df
                        logger.info(f"✅ Mapped {csv_file} → {dataset_key}")
                    break
        
        logger.info(f"\n📊 Loaded {len(datasets)} datasets:")
        for key, df in datasets.items():
            logger.info(f"  • {key}: {len(df):,} rows × {len(df.columns)} columns")
        
        return datasets
    
    def load_dataset(self, dataset_name: str) -> Optional[pd.DataFrame]:
        """
        Load a specific dataset by name.
        Ưu tiên manifest.json nếu có; không thì pattern match.
        """
        manifest = self._read_manifest()
        ent = manifest.get(dataset_name)
        if isinstance(ent, dict) and ent.get("filename"):
            return self.load_csv(ent["filename"])
        if isinstance(ent, list):
            dfs = [self.load_csv(e["filename"]) for e in ent if isinstance(e, dict) and e.get("filename")]
            dfs = [x for x in dfs if x is not None]
            return pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else (dfs[0] if dfs else None)
        
        dataset_to_pattern = {
            "listing": "EtsyListingsDownload.csv",
            "sold_orders": "EtsySoldOrders",
            "sold_order_items": "EtsySoldOrderItems",
            "statement": "etsy_statement_",
            "deposits": "EtsyDeposits",
            "direct_checkout": "EtsyDirectCheckoutPayments",
            "bank_transactions": "fact_bank_transactions.csv",
            "product_catalog": "product_catalog.csv",
            "dim_bank_account": "dim_bank_account.csv",
        }
        pattern = dataset_to_pattern.get(dataset_name)
        if not pattern:
            logger.error(f"❌ Unknown dataset name: {dataset_name}")
            return None
        
        csv_files = self.list_available_files()
        for csv_file in csv_files:
            if pattern in csv_file:
                return self.load_csv(csv_file)
        
        logger.error(f"❌ No file found for dataset: {dataset_name}")
        return None


# Convenience functions
def load_all_data(period: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """Convenience function to load all datasets for a period"""
    loader = CSVLoader(period)
    return loader.load_all_datasets()


def load_dataset(dataset_name: str, period: Optional[str] = None) -> Optional[pd.DataFrame]:
    """Convenience function to load a specific dataset"""
    loader = CSVLoader(period)
    return loader.load_dataset(dataset_name)


if __name__ == "__main__":
    # Test the loader
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Load all datasets
    datasets = load_all_data()
    
    print("\n" + "="*60)
    print("📊 LOADED DATASETS SUMMARY")
    print("="*60)
    for name, df in datasets.items():
        print(f"\n{name.upper()}:")
        print(f"  Rows: {len(df):,}")
        print(f"  Columns: {list(df.columns[:5])} ...")



