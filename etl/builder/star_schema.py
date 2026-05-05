import pandas as pd
from pathlib import Path
import logging
from typing import Dict
from etl.db_factory import get_db_client

from .dimensions.dim_time import TimeDimensionBuilder
from .dimensions.dim_product import ProductDimensionBuilder
from .dimensions.dim_customer import CustomerDimensionBuilder
from .dimensions.dim_product_line import ProductCatalogDimensionBuilder

from .facts.fact_orders import OrderDimensionBuilder
from .facts.fact_order_items import SalesFactBuilder
from .facts.fact_statement import FinancialTransactionsFactBuilder
from .facts.bridge_deposits import DepositsFactBuilder
from .facts.fact_payments import PaymentsFactBuilder
from .facts.fact_bank_transactions import BankTransactionsFactBuilder

logger = logging.getLogger('star_schema')

class StarSchema:

    def __init__(self, output_path: str = "data/warehouse"):
        self.output_path = Path(output_path)

        self.time_builder = TimeDimensionBuilder(output_path)
        self.product_builder = ProductDimensionBuilder(output_path)
        self.customer_builder = CustomerDimensionBuilder(output_path)
        self.order_builder = OrderDimensionBuilder(output_path)
        self.product_catalog_builder = ProductCatalogDimensionBuilder(output_path)
        
        self.sales_builder = SalesFactBuilder(output_path)
        self.financial_builder = FinancialTransactionsFactBuilder(output_path)
        self.deposits_builder = DepositsFactBuilder(output_path)
        self.payments_builder = PaymentsFactBuilder(output_path)
        self.bank_transactions_builder = BankTransactionsFactBuilder(output_path)

    def generate_time_dimension(self, start_date: str = "2020-01-01", 
                              end_date: str = "2030-12-31") -> pd.DataFrame:
        logger.info("Generating time dimension...")
        return self.time_builder.generate_time_dimension(start_date, end_date)

    def build_product_dimension(self, listing_df: pd.DataFrame, order_items_df: pd.DataFrame = None) -> pd.DataFrame:
        logger.info("Building product dimension...")
        return self.product_builder.build(listing_df, order_items_df)

    def build_customer_dimension(self, orders_df: pd.DataFrame, 
                               order_items_df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Building customer dimension...")
        return self.customer_builder.build(orders_df, order_items_df)

    def build_order_dimension(self, orders_df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Building order dimension...")
        direct_checkout_df = self.datasets.get('direct_checkout', None) if hasattr(self, 'datasets') else None
        return self.order_builder.build(orders_df, direct_checkout_df)

    def build_sales_fact(self, order_items_df: pd.DataFrame,
                        datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        logger.info("Building order items fact table...")
        return self.sales_builder.build(order_items_df, datasets)

    def build_financial_transactions_fact(self, statement_df: pd.DataFrame, 
                                        datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        logger.info("Building statement fact table...")
        return self.financial_builder.build(statement_df, datasets)

    def build_deposits_fact(self, deposits_df: pd.DataFrame, 
                          star_schema: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        logger.info("Building deposits bridge table...")
        return self.deposits_builder.build(deposits_df)

    def build_payments_fact(self, direct_checkout_df: pd.DataFrame, 
                          datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        logger.info("Building payments fact table...")
        return self.payments_builder.build(direct_checkout_df, datasets)

    def build_product_catalog_dimension(self, product_catalog_df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Building product line dimension...")
        return self.product_catalog_builder.build(product_catalog_df)

    def build_bank_transactions_fact(self, bank_transactions_df: pd.DataFrame,
                                     dim_bank_account_df: pd.DataFrame = None,
                                     dim_product_catalog_df: pd.DataFrame = None) -> pd.DataFrame:
        logger.info("Building bank transactions fact table...")
        return self.bank_transactions_builder.build(
            bank_transactions_df, 
            dim_bank_account_df, 
            dim_product_catalog_df
        )

    def build_complete_star_schema(self, datasets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        logger.info("Building complete star schema...")
        
        self.datasets = datasets

        star_schema = {}

        # 1. Time Dimension
        time_dim = self.generate_time_dimension()
        star_schema['dim_time'] = time_dim

        # 2. Product Dimension
        if 'listing' in datasets or 'sold_order_items' in datasets:
            listing_df = datasets.get('listing', None)
            order_items_df = datasets.get('sold_order_items', None)
            product_dim = self.build_product_dimension(listing_df, order_items_df)
            star_schema['dim_product'] = product_dim

        # 3. Customer Dimension
        if 'sold_orders' in datasets:
            customer_dim = self.build_customer_dimension(
                datasets['sold_orders'],
                datasets.get('direct_checkout'),
            )
            star_schema['dim_customer'] = customer_dim
            self.order_builder.master_keys['customers'] = self.customer_builder.master_keys['customers'].copy()

        # 4. Orders Fact (was dim_order)
        if 'sold_orders' in datasets:
            order_dim = self.build_order_dimension(datasets['sold_orders'])
            star_schema['fact_orders'] = order_dim

        # 5. Product Line Dimension (was dim_product_catalog)
        if 'product_catalog' in datasets:
            product_line_dim = self.build_product_catalog_dimension(datasets['product_catalog'])
            star_schema['dim_product_line'] = product_line_dim

        # =====================================================================
        # FACT TABLES
        # =====================================================================
        self._copy_master_keys_to_fact_builders()

        # 6. Order Items Fact (was fact_sales)
        if 'sold_order_items' in datasets and 'sold_orders' in datasets:
            sales_fact = self.build_sales_fact(
                datasets['sold_order_items'],
                datasets
            )
            star_schema['fact_order_items'] = sales_fact

        # 7. Statement Fact (was fact_financial_transactions)
        if 'statement' in datasets:
            financial_fact = self.build_financial_transactions_fact(
                datasets['statement'],
                datasets
            )
            star_schema['fact_statement'] = financial_fact

        # 8. Deposits Bridge (was fact_deposits)
        if 'deposits' in datasets:
            deposits_fact = self.build_deposits_fact(
                datasets['deposits'],
                star_schema
            )
            star_schema['bridge_deposits'] = deposits_fact

        # 9. Payments Fact
        if 'direct_checkout' in datasets:
            payments_fact = self.build_payments_fact(
                datasets['direct_checkout'],
                datasets
            )
            star_schema['fact_payments'] = payments_fact

        # 10. Bank Transactions Fact
        if 'bank_transactions' in datasets:
            bank_transactions_fact = self.build_bank_transactions_fact(
                datasets['bank_transactions']
            )
            star_schema['fact_bank_transactions'] = bank_transactions_fact

        logger.info(f"Complete star schema built with {len(star_schema)} tables")
        return star_schema

    def _copy_master_keys_to_fact_builders(self):
        logger.info("Copying master keys from dimension builders to fact builders...")
        
        combined_master_keys = {
            'products': {},
            'customers': {},
            'orders': {},
            'product_lines': {},
        }
        
        dimension_builders = [
            self.product_builder,
            self.customer_builder,
            self.order_builder,
            self.product_catalog_builder,
        ]
        
        for builder in dimension_builders:
            for key_type in combined_master_keys.keys():
                if key_type in builder.master_keys:
                    combined_master_keys[key_type].update(builder.master_keys[key_type])
        
        logger.info(f"Combined master keys - products: {len(combined_master_keys['products'])}, "
                   f"customers: {len(combined_master_keys['customers'])}, "
                   f"orders: {len(combined_master_keys['orders'])}, "
                   f"product_lines: {len(combined_master_keys['product_lines'])}")
        
        fact_builders = [
            self.sales_builder,
            self.financial_builder,
            self.deposits_builder,
            self.payments_builder,
            self.bank_transactions_builder
        ]
        
        for builder in fact_builders:
            for key_type in combined_master_keys.keys():
                if key_type not in builder.master_keys:
                    builder.master_keys[key_type] = {}
                builder.master_keys[key_type] = combined_master_keys[key_type].copy()


    def save_star_schema(self, star_schema: Dict[str, pd.DataFrame], 
                        postgres_clear_existing: bool = False) -> Dict[str, bool]:
        results = {}
        db_client = get_db_client()
        logger.info("Loading star schema to database...")
        if db_client.connect():
            try:
                load_results = db_client.load_star_schema(
                    star_schema, if_exists="append", clear_existing=False
                )
                for table_name, success in load_results.items():
                    results[table_name] = success
                    if success:
                        logger.info(f"Table {table_name} saved successfully")
                    else:
                        logger.error(f"Table {table_name} failed to save")
                
                if all(load_results.values()):
                    logger.info("All tables saved successfully")
                else:
                    failed_tables = [t for t, s in load_results.items() if not s]
                    logger.error(f"Failed to save {len(failed_tables)} table(s): {', '.join(failed_tables)}")
            except Exception as e:
                logger.error(f"Failed to load to database: {e}")
                import traceback
                logger.error(f"Traceback:\n{traceback.format_exc()}")
                for table_name in star_schema:
                    results[table_name] = False
            finally:
                db_client.disconnect()
        else:
            logger.error("Failed to connect to database")
            for table_name in star_schema:
                results[table_name] = False
        return results
