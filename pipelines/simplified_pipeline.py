from __future__ import annotations

import logging
from typing import Dict

import pandas as pd

from etl.builder.star_schema import StarSchema
from etl.loaders.csv_loader import CSVLoader

from etl.cleaners.process_statement import clean_statement_data
from etl.cleaners.process_sold_orders import clean_sold_orders_data
from etl.cleaners.process_sold_order_items import clean_sold_order_items_data
from etl.cleaners.process_direct_checkout import clean_direct_checkout_data
from etl.cleaners.process_deposits import clean_deposits_data
from etl.cleaners.process_listing import clean_listing_data
from etl.cleaners.process_bank_transactions import clean_bank_transactions_data
from etl.cleaners.process_product_catalog import clean_product_catalog_data


logger = logging.getLogger(__name__)


class SimplifiedETLPipeline:
    def __init__(self, *, period: str, clean_existing: bool = True):
        self.period = period
        self.clean_existing = clean_existing

    def _clean(self, datasets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        cleaned: Dict[str, pd.DataFrame] = {}

        if "statement" in datasets:
            cleaned["statement"] = clean_statement_data(datasets["statement"])
        if "sold_orders" in datasets:
            cleaned["sold_orders"] = clean_sold_orders_data(datasets["sold_orders"])
        if "sold_order_items" in datasets:
            cleaned["sold_order_items"] = clean_sold_order_items_data(datasets["sold_order_items"])
        if "direct_checkout" in datasets:
            cleaned["direct_checkout"] = clean_direct_checkout_data(datasets["direct_checkout"])
        if "deposits" in datasets:
            cleaned["deposits"] = clean_deposits_data(datasets["deposits"])
        if "listing" in datasets:
            cleaned["listing"] = clean_listing_data(datasets["listing"])
        if "bank_transactions" in datasets:
            cleaned["bank_transactions"] = clean_bank_transactions_data(datasets["bank_transactions"])
        if "product_catalog" in datasets:
            cleaned["product_catalog"] = clean_product_catalog_data(datasets["product_catalog"])

        if "dim_bank_account" in datasets and "bank_account" not in cleaned:
            cleaned["bank_account"] = datasets["dim_bank_account"]

        return cleaned

    def run(self) -> bool:
        logger.info("Starting ETL for period=%s", self.period)
        loader = CSVLoader(period=self.period)
        raw = loader.load_all_datasets()
        if not raw:
            logger.error("No datasets found for period=%s", self.period)
            return False

        cleaned = self._clean(raw)
        if not cleaned:
            logger.error("No datasets could be cleaned for period=%s", self.period)
            return False

        builder = StarSchema()
        star = builder.build_complete_star_schema(cleaned)
        # Luôn append, không clear (dim_time upsert; fact_bank_transactions giữ nguyên).
        results = builder.save_star_schema(star, postgres_clear_existing=False)
        ok = bool(results) and all(results.values())
        logger.info("ETL finished ok=%s", ok)
        return ok

