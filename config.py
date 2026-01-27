import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def get_app_root() -> Path:
    """Thư mục gốc: khi chạy từ exe = thư mục chứa .exe; khi dev = thư mục chứa config.py."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# data/raw (bên trong data)
_RAW_DIR = get_app_root() / "data" / "raw"


def _is_valid_period_format(folder_name: str) -> bool:
    """Check if folder name matches YYYY-MM format"""
    return bool(re.match(r"^\d{4}-\d{2}$", folder_name))


def get_available_raw_periods() -> List[str]:
    """Scan data/raw/ folder to get available periods."""
    raw_path = _RAW_DIR
    available_periods = []
    if raw_path.exists():
        for item in raw_path.iterdir():
            if item.is_dir() and _is_valid_period_format(item.name):
                available_periods.append(item.name)
    available_periods.sort()
    return available_periods


def get_latest_available_period() -> str:
    """Get the latest period available in raw data folders."""
    periods = get_available_raw_periods()
    return periods[-1] if periods else datetime.now().strftime("%Y-%m")


def get_current_period() -> str:
    """Get current period in YYYY-MM format."""
    return datetime.now().strftime("%Y-%m")


def get_previous_period() -> str:
    """Get previous month period in YYYY-MM format."""
    current = datetime.now()
    if current.month == 1:
        previous = current.replace(year=current.year - 1, month=12)
    else:
        previous = current.replace(month=current.month - 1)
    return previous.strftime("%Y-%m")


def get_period_for_date(year: int, month: int) -> str:
    """Get period string for specific year/month."""
    return f"{year:04d}-{month:02d}"


def parse_period(period_str: str) -> tuple:
    """Parse period string to (year, month)."""
    try:
        year, month = period_str.split("-")
        return int(year), int(month)
    except Exception:
        n = datetime.now()
        return n.year, n.month


def get_raw_files_for_period(period: str) -> List[str]:
    """Get list of raw CSV files for a specific period."""
    p = _RAW_DIR / period
    return [f.name for f in p.glob("*.csv")] if p.exists() else []


def get_data_files_for_period(period: str) -> Dict[str, str]:
    """Get data file names for a specific period."""
    year, month = parse_period(period)
    return {
        "statement": f"etsy_statement_{year}_{month}.csv",
        "deposits": f"EtsyDeposits{year}-{month}.csv",
        "direct_checkout": f"EtsyDirectCheckoutPayments{year}-{month}.csv",
        "listing": "EtsyListingsDownload.csv",
        "sold_order_items": f"EtsySoldOrderItems{year}-{month}.csv",
        "sold_orders": f"EtsySoldOrders{year}-{month}.csv",
    }


# Default to latest available raw period or current period
DEFAULT_PERIOD = get_latest_available_period()
DATA_FILES = get_data_files_for_period(DEFAULT_PERIOD)


# Date formats (cho etl/cleaners)
DATE_FORMATS = {
    "statement": "%B %d, %Y",
    "deposits": "%B %d, %Y",
    "sold_orders": "%m/%d/%y",
    "sold_items": "%m/%d/%y",
    "sold_items_paid_shipped": "%m/%d/%Y",
    "direct_checkout": "%m/%d/%Y",
    "output": "%Y-%m-%d",
}

# Exchange rate (e.g., VND per USD)
EXCHANGE_RATE = 24708.655
