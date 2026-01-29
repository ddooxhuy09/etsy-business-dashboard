"""
PostgreSQL DB client for loading the star schema (moved from src.storage.db_factory).
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict
import pandas as pd
from sqlalchemy import create_engine, text

from api.db import get_database_url

logger = logging.getLogger(__name__)

def _upsert_dim_time(conn, engine, df: pd.DataFrame, log) -> None:
    """Insert dim_time rows, skip existing time_key (ON CONFLICT DO NOTHING)."""
    temp = f"temp_dim_time_{uuid.uuid4().hex[:12]}"
    cols = list(df.columns)
    cols_sql = ", ".join(f'"{c}"' for c in cols)
    try:
        df.to_sql(temp, conn, if_exists="replace", index=False, method="multi")
        conn.execute(text(
            f'INSERT INTO dim_time ({cols_sql}) SELECT {cols_sql} FROM "{temp}" '
            'ON CONFLICT (time_key) DO NOTHING'
        ))
        conn.commit()
    finally:
        conn.execute(text(f'DROP TABLE IF EXISTS "{temp}"'))
        conn.commit()


def _sync_sequence(conn, table_name: str, surrogate_key: str, log) -> None:
    """Sync PostgreSQL sequence to max value in table to avoid duplicate key errors."""
    try:
        # Get sequence name (PostgreSQL naming convention: table_column_seq)
        seq_name = f"{table_name}_{surrogate_key}_seq"
        # Sync sequence to max value + 1
        conn.execute(text(f"""
            SELECT setval('{seq_name}', COALESCE((SELECT MAX({surrogate_key}) FROM {table_name}), 0) + 1, false)
        """))
        conn.commit()
        log.info(f"Synced sequence {seq_name}")
    except Exception as e:
        log.warning(f"Could not sync sequence for {table_name}: {e}")
        try:
            conn.rollback()
        except:
            pass


def _upsert_dimension(conn, engine, df: pd.DataFrame, star_schema: dict, log, 
                      table_name: str, business_key: str, surrogate_key: str,
                      fact_tables: list = None, extra_filter: str = None,
                      has_unique_constraint: bool = False) -> None:
    """
    Generic upsert for dimension tables:
    - If business_key exists in DB → reuse existing surrogate_key
    - If business_key is new → insert new record (DB auto-generates surrogate_key)
    - Remap surrogate_key in fact tables to match DB keys
    
    Args:
        table_name: Name of dimension table (e.g., 'dim_product')
        business_key: Column name for business key (e.g., 'listing_id')
        surrogate_key: Column name for surrogate key (e.g., 'product_key')
        fact_tables: List of (fact_table_name, fk_column_name) tuples to remap
        extra_filter: Additional SQL filter for SELECT (e.g., 'is_current = TRUE')
        has_unique_constraint: If True, use ON CONFLICT DO NOTHING for safety
    """
    if df.empty:
        log.info(f"{table_name} DataFrame is empty, skipping.")
        return
    
    if business_key not in df.columns:
        log.warning(f"{table_name} has no {business_key} column, cannot upsert. Skipping insert.")
        return
    
    # Step 0: Sync sequence to avoid duplicate key errors
    _sync_sequence(conn, table_name, surrogate_key, log)
    
    # Step 1: Get existing business_key -> surrogate_key mapping from DB
    where_clause = f"WHERE {extra_filter}" if extra_filter else ""
    res = conn.execute(text(f"SELECT {business_key}, {surrogate_key} FROM {table_name} {where_clause}"))
    existing_map = {r[0]: r[1] for r in res.fetchall() if r[0] is not None}
    log.info(f"Found {len(existing_map)} existing {table_name} records in DB")
    
    # Step 2: Filter new records (business_key not in DB)
    df_clean = df.dropna(subset=[business_key])
    df_new = df_clean[~df_clean[business_key].isin(existing_map.keys())]
    log.info(f"New {table_name} records to insert: {len(df_new)}")
    
    # Step 3: Insert new records
    if not df_new.empty:
        # Remove surrogate_key column - let DB auto-generate via SERIAL/IDENTITY
        cols = [c for c in df_new.columns if c != surrogate_key]
        df_insert = df_new[cols].copy()
        
        # Drop duplicates within the DataFrame itself (keep first occurrence)
        df_insert = df_insert.drop_duplicates(subset=[business_key], keep="first")
        log.info(f"After dedup: {len(df_insert)} unique {table_name} records to insert")
        
        # Use temp table for insertion
        temp = f"temp_{table_name}_{uuid.uuid4().hex[:12]}"
        cols_sql = ", ".join(f'"{c}"' for c in cols)
        try:
            df_insert.to_sql(temp, conn, if_exists="replace", index=False, method="multi")
            
            # Build INSERT statement - use ON CONFLICT if table has unique constraint
            if has_unique_constraint:
                insert_sql = (
                    f'INSERT INTO {table_name} ({cols_sql}) SELECT {cols_sql} FROM "{temp}" '
                    f'ON CONFLICT ({business_key}) DO NOTHING'
                )
            else:
                insert_sql = f'INSERT INTO {table_name} ({cols_sql}) SELECT {cols_sql} FROM "{temp}"'
            
            conn.execute(text(insert_sql))
            conn.commit()
            log.info(f"Inserted new {table_name} records")
        except Exception as e:
            log.error(f"Error inserting {table_name}: {e}")
            try:
                conn.rollback()
            except:
                pass
            raise
        finally:
            try:
                conn.execute(text(f'DROP TABLE IF EXISTS "{temp}"'))
                conn.commit()
            except:
                pass
    
    # Step 4: Query DB again to get complete business_key -> surrogate_key mapping
    res = conn.execute(text(f"SELECT {business_key}, {surrogate_key} FROM {table_name} {where_clause}"))
    bk_to_sk = {r[0]: r[1] for r in res.fetchall() if r[0] is not None}
    
    # Step 5: Build mapping from old (builder-generated) key to new (DB) key
    old_to_new = {}
    for _, row in df.iterrows():
        bk = row.get(business_key)
        if bk is None or pd.isna(bk):
            continue
        old_key = row.get(surrogate_key)
        if old_key is None or pd.isna(old_key):
            continue
        new_key = bk_to_sk.get(bk)
        if new_key is not None:
            try:
                old_to_new[int(old_key)] = int(new_key)
            except (ValueError, TypeError):
                pass
    
    log.info(f"{table_name} key mapping: {len(old_to_new)} keys to remap")
    
    # Step 6: Remap surrogate_key in fact tables
    if fact_tables and old_to_new:
        def _remap(k):
            if pd.isna(k):
                return k
            try:
                ik = int(k) if isinstance(k, (int, float)) and k == int(k) else k
                return old_to_new.get(ik, k)
            except (ValueError, TypeError):
                return k
        
        for fact_name, fk_col in fact_tables:
            fs = star_schema.get(fact_name)
            if fs is not None and fk_col in fs.columns:
                fs[fk_col] = fs[fk_col].map(_remap)
                log.info(f"Remapped {fk_col} in {fact_name}")


def _upsert_dim_geography(conn, engine, df: pd.DataFrame, star_schema: dict, log) -> None:
    """
    Upsert dim_geography by location_hash:
    - If location_hash exists in DB → reuse existing geography_key
    - If location_hash is new → insert new record (DB auto-generates geography_key)
    - Remap geography_key in fact_sales to match DB keys
    """
    if df.empty:
        log.info("dim_geography DataFrame is empty, skipping.")
        return
    
    if "location_hash" not in df.columns:
        log.warning("dim_geography has no location_hash column, cannot upsert. Skipping insert.")
        return
    
    df_clean = df.dropna(subset=["location_hash"])
    if df_clean.empty:
        log.info("No valid location_hash in dim_geography, skipping.")
        return
    
    # Step 1: Get existing location_hash -> geography_key mapping from DB
    res = conn.execute(text("SELECT location_hash, geography_key FROM dim_geography"))
    existing_map = {r[0]: r[1] for r in res.fetchall() if r[0] is not None}
    log.info(f"Found {len(existing_map)} existing geography records in DB")
    
    # Step 2: Filter new records (location_hash not in DB)
    df_new = df_clean[~df_clean["location_hash"].isin(existing_map.keys())]
    log.info(f"New geography records to insert: {len(df_new)}")
    
    # Step 3: Insert new records using ON CONFLICT DO NOTHING (via temp table)
    if not df_new.empty:
        # Remove geography_key column - let DB auto-generate via SERIAL/IDENTITY
        cols = [c for c in df_new.columns if c != "geography_key"]
        df_insert = df_new[cols].copy()
        
        # Drop duplicates within the DataFrame itself (keep first occurrence)
        df_insert = df_insert.drop_duplicates(subset=["location_hash"], keep="first")
        log.info(f"After dedup: {len(df_insert)} unique geography records to insert")
        
        # Use temp table + INSERT ON CONFLICT for safety
        temp = f"temp_dim_geography_{uuid.uuid4().hex[:12]}"
        cols_sql = ", ".join(f'"{c}"' for c in cols)
        try:
            df_insert.to_sql(temp, conn, if_exists="replace", index=False, method="multi")
            conn.execute(text(
                f'INSERT INTO dim_geography ({cols_sql}) SELECT {cols_sql} FROM "{temp}" '
                'ON CONFLICT (location_hash) DO NOTHING'
            ))
            conn.commit()
            log.info(f"Inserted {len(df_new)} new geography records")
        finally:
            conn.execute(text(f'DROP TABLE IF EXISTS "{temp}"'))
            conn.commit()
    
    # Step 4: Query DB again to get complete location_hash -> geography_key mapping
    res = conn.execute(text("SELECT location_hash, geography_key FROM dim_geography"))
    lh_to_key = {r[0]: r[1] for r in res.fetchall() if r[0] is not None}
    
    # Step 5: Build mapping from old (builder-generated) geography_key to new (DB) geography_key
    old_to_new = {}
    for _, row in df.iterrows():
        lh = row.get("location_hash")
        if lh is None or pd.isna(lh):
            continue
        old_key = row.get("geography_key")
        if old_key is None or pd.isna(old_key):
            continue
        new_key = lh_to_key.get(lh)
        if new_key is not None:
            old_to_new[int(old_key)] = int(new_key)
    
    log.info(f"Geography key mapping: {len(old_to_new)} keys to remap")
    
    # Step 6: Remap geography_key in fact_sales
    fs = star_schema.get("fact_sales")
    if fs is not None and "geography_key" in fs.columns and old_to_new:
        def _remap(k):
            if pd.isna(k):
                return k
            ik = int(k) if isinstance(k, (int, float)) and k == int(k) else k
            return old_to_new.get(ik, k)
        fs["geography_key"] = fs["geography_key"].map(_remap)
        log.info("Remapped geography_key in fact_sales")


class PostgreSQLDBClient:
    """PostgreSQL database client for loading star schema data."""
    
    def __init__(self):
        self.url = get_database_url()
        # Remove psycopg2 prefix if present for SQLAlchemy
        dsn = self.url.replace("postgresql+psycopg2://", "postgresql://") if "postgresql" in self.url else self.url
        self.engine = create_engine(dsn, future=True)
        self.conn = None

    def connect(self) -> bool:
        """Connect to PostgreSQL database."""
        try:
            self.conn = self.engine.connect()
            # Ensure schema exists (tables should already be created)
            self.ensure_schema()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            self.conn = None
            return False

    def ensure_schema(self) -> None:
        """Check if schema exists. Tables should be created separately using create_postgres_tables.sql."""
        if self.conn is None:
            return
        
        try:
            # Check if dim_time table exists
            result = self.conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'dim_time')"
            ))
            exists = result.scalar()
            
            if not exists:
                logger.warning("⚠️ Schema tables not found. Please run create_postgres_tables.sql first.")
        except Exception as e:
            logger.warning(f"⚠️ Could not check schema: {e}")

    def disconnect(self) -> None:
        """Disconnect from database."""
        try:
            if self.conn is not None:
                self.conn.close()
        finally:
            self.conn = None

    def load_star_schema(self, star_schema: Dict[str, pd.DataFrame], *, if_exists: str = "append", clear_existing: bool = False) -> Dict[str, bool]:
        """Load star schema vào PostgreSQL. Chỉ append, không clear (dim_time upsert)."""
        assert self.conn is not None, "connect() must be called first"
        assert clear_existing is False, "clear_existing must be False; clearing is disabled."
        results: Dict[str, bool] = {}

        tables = list(star_schema.keys())
        logger.info(f"📊 Saving {len(tables)} tables: {', '.join(tables)}")

        for table_name, df in star_schema.items():
            try:
                logger.info(f"💾 Saving {table_name} ({len(df)} rows, {len(df.columns)} columns)...")
                df_to_write = df.copy()
                df_to_write = df_to_write.where(pd.notnull(df_to_write), None)
                logger.debug(f"Sample columns: {list(df_to_write.columns[:5])}")
                logger.debug(f"Sample data types: {df_to_write.dtypes.head().to_dict()}")
                if table_name == "dim_time" and if_exists == "append":
                    logger.info("🔄 Upserting dim_time (ON CONFLICT DO NOTHING)...")
                    _upsert_dim_time(self.conn, self.engine, df_to_write, logger)
                elif table_name == "dim_product" and if_exists == "append":
                    logger.info("🔄 Merging dim_product by listing_id...")
                    _upsert_dimension(self.conn, self.engine, df_to_write, star_schema, logger,
                                     table_name="dim_product", business_key="listing_id", 
                                     surrogate_key="product_key", extra_filter="is_current = TRUE",
                                     fact_tables=[("fact_sales", "product_key"), 
                                                  ("fact_financial_transactions", "product_key")])
                elif table_name == "dim_customer" and if_exists == "append":
                    logger.info("🔄 Merging dim_customer by buyer_user_name...")
                    _upsert_dimension(self.conn, self.engine, df_to_write, star_schema, logger,
                                     table_name="dim_customer", business_key="buyer_user_name",
                                     surrogate_key="customer_key", extra_filter="is_current = TRUE",
                                     fact_tables=[("fact_sales", "customer_key"),
                                                  ("fact_financial_transactions", "customer_key"),
                                                  ("fact_payments", "customer_key")])
                elif table_name == "dim_order" and if_exists == "append":
                    logger.info("🔄 Merging dim_order by order_id...")
                    _upsert_dimension(self.conn, self.engine, df_to_write, star_schema, logger,
                                     table_name="dim_order", business_key="order_id",
                                     surrogate_key="order_key",
                                     fact_tables=[("fact_sales", "order_key"),
                                                  ("fact_financial_transactions", "order_key"),
                                                  ("fact_payments", "order_key")],
                                     has_unique_constraint=True)  # order_id has UNIQUE constraint
                elif table_name == "dim_geography" and if_exists == "append":
                    logger.info("🔄 Merging dim_geography by location_hash...")
                    _upsert_dim_geography(self.conn, self.engine, df_to_write, star_schema, logger)
                elif table_name == "dim_payment" and if_exists == "append":
                    logger.info("🔄 Merging dim_payment by payment_method...")
                    _upsert_dimension(self.conn, self.engine, df_to_write, star_schema, logger,
                                     table_name="dim_payment", business_key="payment_method",
                                     surrogate_key="payment_key",
                                     fact_tables=[("fact_sales", "payment_key"),
                                                  ("fact_payments", "payment_method_key")])
                elif table_name == "dim_bank_account" and if_exists == "append":
                    logger.info("🔄 Merging dim_bank_account by account_number...")
                    _upsert_dimension(self.conn, self.engine, df_to_write, star_schema, logger,
                                     table_name="dim_bank_account", business_key="account_number",
                                     surrogate_key="bank_account_key",
                                     fact_tables=[("fact_bank_transactions", "bank_account_key")],
                                     has_unique_constraint=True)  # account_number has UNIQUE constraint
                else:
                    # For fact tables, remove surrogate key columns to let DB auto-generate
                    fact_surrogate_keys = {
                        'fact_sales': 'sales_key',
                        'fact_financial_transactions': 'financial_transaction_key',
                        'fact_deposits': 'deposit_key',
                        'fact_payments': 'payment_transaction_key',
                        'fact_bank_transactions': 'bank_transaction_key'
                    }
                    
                    if table_name in fact_surrogate_keys:
                        sk = fact_surrogate_keys[table_name]
                        # Sync sequence first
                        _sync_sequence(self.conn, table_name, sk, logger)
                        # Remove surrogate key column if present
                        if sk in df_to_write.columns:
                            df_to_write = df_to_write.drop(columns=[sk])
                            logger.info(f"Removed {sk} column, letting DB auto-generate")
                    
                    df_to_write.to_sql(table_name, self.engine, if_exists=if_exists, index=False, method='multi')
                results[table_name] = True
                logger.info(f"✅ Saved {table_name}")
            except Exception as e:
                results[table_name] = False
                logger.error(f"❌ Failed to save {table_name}: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"Traceback for {table_name}:\n{traceback.format_exc()}")
        return results

    def validate_data_integrity(self, star_schema: Dict[str, pd.DataFrame]) -> None:
        """Validate data integrity (placeholder for future implementation)."""
        return None


def get_db_client() -> PostgreSQLDBClient:
    """Get PostgreSQL database client."""
    return PostgreSQLDBClient()
