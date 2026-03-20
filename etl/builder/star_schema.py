"""
ETSY DATA WAREHOUSE - STAR SCHEMA BUILDER
Orchestrates building the complete star schema using dimension and fact builders
Flow: file -> clean -> star schema builder -> database
"""

import pandas as pd
from pathlib import Path
import logging
from typing import Dict
from etl.db_factory import get_db_client

# Import dimension builders
from .dimensions.dim_time import TimeDimensionBuilder
from .dimensions.dim_product import ProductDimensionBuilder
from .dimensions.dim_customer import CustomerDimensionBuilder
from .dimensions.dim_geography import GeographyDimensionBuilder
from .dimensions.dim_payment import PaymentDimensionBuilder
from .dimensions.dim_order import OrderDimensionBuilder
from .dimensions.dim_bank_account import BankAccountDimensionBuilder
from .dimensions.dim_product_catalog import ProductCatalogDimensionBuilder

# Import fact builders
from .facts.fact_sales import SalesFactBuilder
from .facts.fact_financial_transactions import FinancialTransactionsFactBuilder
from .facts.fact_deposits import DepositsFactBuilder
from .facts.fact_payments import PaymentsFactBuilder
from .facts.fact_bank_transactions import BankTransactionsFactBuilder

# Setup logging
logger = logging.getLogger('star_schema')

class StarSchema:
    """Orchestrates building the complete star schema using dimension and fact builders"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        """output_path: chỉ dùng nếu gọi save_to_parquet (legacy). Pipeline này ghi vào PostgreSQL."""
        self.output_path = Path(output_path)

        # Initialize dimension builders
        self.time_builder = TimeDimensionBuilder(output_path)
        self.product_builder = ProductDimensionBuilder(output_path)
        self.customer_builder = CustomerDimensionBuilder(output_path)
        self.geography_builder = GeographyDimensionBuilder(output_path)
        self.payment_builder = PaymentDimensionBuilder(output_path)
        self.order_builder = OrderDimensionBuilder(output_path)
        self.bank_account_builder = BankAccountDimensionBuilder(output_path)
        self.product_catalog_builder = ProductCatalogDimensionBuilder(output_path)
        
        # Initialize fact builders
        self.sales_builder = SalesFactBuilder(output_path)
        self.financial_builder = FinancialTransactionsFactBuilder(output_path)
        self.deposits_builder = DepositsFactBuilder(output_path)
        self.payments_builder = PaymentsFactBuilder(output_path)
        self.bank_transactions_builder = BankTransactionsFactBuilder(output_path)

    def generate_time_dimension(self, start_date: str = "2020-01-01", 
                              end_date: str = "2030-12-31") -> pd.DataFrame:
        """Generate comprehensive time dimension table"""
        logger.info("Generating time dimension...")
        return self.time_builder.generate_time_dimension(start_date, end_date)

    def build_product_dimension(self, listing_df: pd.DataFrame, order_items_df: pd.DataFrame = None) -> pd.DataFrame:
        """Build product master dimension with SCD Type 2"""
        logger.info("Building product dimension...")
        return self.product_builder.build(listing_df, order_items_df)

    def build_customer_dimension(self, orders_df: pd.DataFrame, 
                               order_items_df: pd.DataFrame) -> pd.DataFrame:
        """Build customer master dimension with analytics"""
        logger.info("Building customer dimension...")
        return self.customer_builder.build(orders_df, order_items_df)

    def build_geography_dimension(self, orders_df: pd.DataFrame) -> pd.DataFrame:
        """Build geography dimension from shipping addresses"""
        logger.info("Building geography dimension...")
        return self.geography_builder.build(orders_df)

    def build_payment_dimension(self, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build Payment Dimension"""
        logger.info("Building payment dimension...")
        return self.payment_builder.build(datasets)

    def build_order_dimension(self, orders_df: pd.DataFrame) -> pd.DataFrame:
        """Build Order Dimension"""
        logger.info("Building order dimension...")
        # Get direct_checkout data if available
        direct_checkout_df = self.datasets.get('direct_checkout', None) if hasattr(self, 'datasets') else None
        return self.order_builder.build(orders_df, direct_checkout_df)

    def build_sales_fact(self, order_items_df: pd.DataFrame,
                        datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build primary sales fact table"""
        logger.info("Building sales fact table...")
        return self.sales_builder.build(order_items_df, datasets)

    def build_financial_transactions_fact(self, statement_df: pd.DataFrame, 
                                        datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build Financial Transactions Fact Table"""
        logger.info("Building financial transactions fact table...")
        return self.financial_builder.build(statement_df, datasets)

    def build_deposits_fact(self, deposits_df: pd.DataFrame, 
                          star_schema: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build Deposits Fact Table"""
        logger.info("Building deposits fact table...")
        return self.deposits_builder.build(deposits_df)

    def build_payments_fact(self, direct_checkout_df: pd.DataFrame, 
                          datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build Payments Fact Table"""
        logger.info("Building payments fact table...")
        return self.payments_builder.build(direct_checkout_df, datasets)

    def build_bank_account_dimension(self, bank_account_df: pd.DataFrame) -> pd.DataFrame:
        """Build Bank Account Dimension"""
        logger.info("Building bank account dimension...")
        return self.bank_account_builder.build(bank_account_df)

    def build_product_catalog_dimension(self, product_catalog_df: pd.DataFrame) -> pd.DataFrame:
        """Build Product Catalog Dimension"""
        logger.info("Building product catalog dimension...")
        return self.product_catalog_builder.build(product_catalog_df)

    def build_bank_transactions_fact(self, bank_transactions_df: pd.DataFrame,
                                     dim_bank_account_df: pd.DataFrame = None,
                                     dim_product_catalog_df: pd.DataFrame = None) -> pd.DataFrame:
        """Build Bank Transactions Fact Table"""
        logger.info("Building bank transactions fact table...")
        return self.bank_transactions_builder.build(
            bank_transactions_df, 
            dim_bank_account_df, 
            dim_product_catalog_df
        )

    def build_complete_star_schema(self, datasets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Build complete star schema with all dimensions and facts"""
        logger.info("🏗️ Building complete star schema...")
        
        # Store datasets for access by other methods
        self.datasets = datasets

        star_schema = {}

        # 1. Time Dimension (static)
        time_dim = self.generate_time_dimension()
        star_schema['dim_time'] = time_dim

        # 2. Geography Dimension
        if 'sold_orders' in datasets:
            geo_dim = self.build_geography_dimension(datasets['sold_orders'])
            star_schema['dim_geography'] = geo_dim

        # 3. Product Dimension (SCD Type 2) - MUST BE FIRST
        if 'listing' in datasets or 'sold_order_items' in datasets:
            listing_df = datasets.get('listing', None)
            order_items_df = datasets.get('sold_order_items', None)
            product_dim = self.build_product_dimension(listing_df, order_items_df)
            star_schema['dim_product'] = product_dim

        # 4. Customer Dimension (SCD Type 2)
        if 'sold_orders' in datasets and 'direct_checkout' in datasets:
            customer_dim = self.build_customer_dimension(
                datasets['sold_orders'],
                datasets['direct_checkout']
            )
            star_schema['dim_customer'] = customer_dim

        # 5. Payment Dimension
        payment_dim = self.build_payment_dimension(datasets)
        star_schema['dim_payment'] = payment_dim

        # 6. Order Dimension
        if 'sold_orders' in datasets:
            order_dim = self.build_order_dimension(datasets['sold_orders'])
            star_schema['dim_order'] = order_dim

        # 7. Bank Account Dimension
        # If dim_bank_account.csv is not provided, derive from bank_transactions (best-effort)
        if 'bank_account' not in datasets and 'bank_transactions' in datasets:
            bt = datasets['bank_transactions']
            acct_col = next((c for c in bt.columns if 'account_number' in c.lower()), None)
            name_col = next((c for c in bt.columns if 'account_name' in c.lower()), None)
            addr_col = next((c for c in bt.columns if 'address' in c.lower()), None)
            currency_col = next((c for c in bt.columns if 'currency' in c.lower()), None)
            # Tìm cột opening_date: "Ngày mở tài khoản (Opening Date)"
            opening_date_col = next((c for c in bt.columns if ('opening' in c.lower() and 'date' in c.lower()) or ('mo_tai_khoan' in c.lower())), None)
            if acct_col:
                # Chỉ lấy các cột thực sự tồn tại
                cols = [c for c in [acct_col, name_col, addr_col, currency_col, opening_date_col] if c and c in bt.columns]
                df_acct = bt[cols].copy()
                # Build rename mapping: chỉ rename cột thực sự tồn tại
                rename_map = {acct_col: 'account_number'}
                if name_col and name_col in bt.columns:
                    rename_map[name_col] = 'account_name'
                if addr_col and addr_col in bt.columns:
                    rename_map[addr_col] = 'customer_address'
                if currency_col and currency_col in bt.columns:
                    rename_map[currency_col] = 'currency_code'
                if opening_date_col and opening_date_col in bt.columns:
                    rename_map[opening_date_col] = 'opening_date'
                df_acct = df_acct.rename(columns=rename_map)
                # Đảm bảo account_name tồn tại (fallback từ account_number nếu không có)
                if 'account_name' not in df_acct.columns:
                    df_acct['account_name'] = df_acct['account_number']
                # Chỉ tiếp tục nếu sau khi rename thực sự có cột account_number
                if 'account_number' in df_acct.columns:
                    df_acct = df_acct.dropna(subset=['account_number'])
                    df_acct = df_acct.drop_duplicates(subset=['account_number'])
                    # Default currency if missing
                    if 'currency_code' not in df_acct.columns:
                        df_acct['currency_code'] = 'VND'
                    datasets['bank_account'] = df_acct

        if 'bank_account' in datasets:
            bank_account_dim = self.build_bank_account_dimension(datasets['bank_account'])
            star_schema['dim_bank_account'] = bank_account_dim

        # 8. Product Catalog Dimension
        if 'product_catalog' in datasets:
            product_catalog_dim = self.build_product_catalog_dimension(datasets['product_catalog'])
            star_schema['dim_product_catalog'] = product_catalog_dim

        # =====================================================================
        # FACT TABLES
        # =====================================================================
        # Copy master keys from dimension builders to fact builders
        self._copy_master_keys_to_fact_builders()

        # 9.1. Primary Sales Fact Table
        if 'sold_order_items' in datasets and 'sold_orders' in datasets:
                sales_fact = self.build_sales_fact(
                    datasets['sold_order_items'],
                    datasets  # Pass all datasets
                )
                star_schema['fact_sales'] = sales_fact

        # 9.2. Financial Transactions Fact Table
        if 'statement' in datasets:
            financial_fact = self.build_financial_transactions_fact(
                datasets['statement'],
                datasets
            )
            star_schema['fact_financial_transactions'] = financial_fact

        # 9.3. Deposits Fact Table
        if 'deposits' in datasets:
            deposits_fact = self.build_deposits_fact(
                datasets['deposits'],
                star_schema
            )
            star_schema['fact_deposits'] = deposits_fact

        # 9.4. Payments Fact Table
        if 'direct_checkout' in datasets:
            payments_fact = self.build_payments_fact(
                datasets['direct_checkout'],
                datasets
            )
            star_schema['fact_payments'] = payments_fact

        # 9.5. Bank Transactions Fact Table
        if 'bank_transactions' in datasets:
            bank_transactions_fact = self.build_bank_transactions_fact(
                datasets['bank_transactions'],
                star_schema.get('dim_bank_account', None),
                star_schema.get('dim_product_catalog', None)
            )
            star_schema['fact_bank_transactions'] = bank_transactions_fact

        logger.info(f"✅ Complete star schema built with {len(star_schema)} tables")
        return star_schema

    def _copy_master_keys_to_fact_builders(self):
        """Copy master keys from dimension builders to fact builders"""
        logger.info("Copying master keys from dimension builders to fact builders...")
        
        # Collect master keys from all dimension builders
        combined_master_keys = {
            'products': {},
            'customers': {},
            'orders': {},
            'geographies': {},
            'payments': {},
            'bank_accounts': {},
            'product_catalog': {}
        }
        
        # Copy from each dimension builder
        dimension_builders = [
            self.product_builder,
            self.customer_builder,
            self.order_builder,
            self.geography_builder,
            self.payment_builder,
            self.bank_account_builder,
            self.product_catalog_builder
        ]
        
        for builder in dimension_builders:
            for key_type in combined_master_keys.keys():
                if key_type in builder.master_keys:
                    combined_master_keys[key_type].update(builder.master_keys[key_type])
        
        # Log the combined master keys
        logger.info(f"Combined master keys - products: {len(combined_master_keys['products'])}, "
                   f"customers: {len(combined_master_keys['customers'])}, "
                   f"orders: {len(combined_master_keys['orders'])}, "
                   f"geographies: {len(combined_master_keys['geographies'])}, "
                   f"payments: {len(combined_master_keys['payments'])}, "
                   f"bank_accounts: {len(combined_master_keys['bank_accounts'])}, "
                   f"product_catalog: {len(combined_master_keys['product_catalog'])}")
        
        # Copy to fact builders
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
        """Save star schema vào PostgreSQL database. Luôn append, không clear."""
        results = {}
        db_client = get_db_client()
        logger.info("🗄️ Loading star schema to database...")
        # Luôn append (clear_existing=False). dim_time upsert; fact_bank_transactions giữ nguyên.
        if db_client.connect():
            try:
                load_results = db_client.load_star_schema(
                    star_schema, if_exists="append", clear_existing=False
                )
                for table_name, success in load_results.items():
                    results[table_name] = success
                    if success:
                        logger.info(f"✅ Table {table_name} saved successfully")
                    else:
                        logger.error(f"❌ Table {table_name} failed to save")
                
                if all(load_results.values()):
                    logger.info("✅ All tables saved successfully")
                    db_client.validate_data_integrity(star_schema)
                else:
                    failed_tables = [t for t, s in load_results.items() if not s]
                    logger.error(f"❌ Failed to save {len(failed_tables)} table(s): {', '.join(failed_tables)}")
            except Exception as e:
                logger.error(f"❌ Failed to load to database: {e}")
                import traceback
                logger.error(f"Traceback:\n{traceback.format_exc()}")
                for table_name in star_schema:
                    results[table_name] = False
            finally:
                db_client.disconnect()
        else:
            logger.error("❌ Failed to connect to database")
            for table_name in star_schema:
                results[table_name] = False
        return results


def main():
    """Main execution function"""
    logger.info("Starting Star Schema build process...")
    
    # Initialize builder
    builder = StarSchema()
    
    # TODO: Load your cleaned datasets here
    # This would typically load from your cleaned parquet files
    """
    listing_df = pd.read_parquet('data/clean/listing.parquet')
    orders_df = pd.read_parquet('data/clean/sold_orders.parquet') 
    order_items_df = pd.read_parquet('data/clean/sold_order_items.parquet')
    statement_df = pd.read_parquet('data/clean/statement.parquet')
    deposits_df = pd.read_parquet('data/clean/deposits.parquet')
    direct_checkout_df = pd.read_parquet('data/clean/direct_checkout.parquet')
    """
    
    # For now, create sample structure
    logger.info("This script provides the framework for building the star schema.")
    logger.info("Replace the TODO section above with your actual data loading logic.")
    logger.info("The schema design is documented in star_schema_design.md")
    
    logger.info("Star Schema builder ready for implementation!")


if __name__ == "__main__":
    main()
