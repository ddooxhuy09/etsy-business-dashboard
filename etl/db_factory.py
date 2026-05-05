from __future__ import annotations

import logging
import uuid
from typing import Dict
import pandas as pd
from sqlalchemy import create_engine, text

from core.database import get_database_url

logger = logging.getLogger(__name__)

def _upsert_dim_time(conn, engine, df: pd.DataFrame, log) -> None:
    temp = f"temp_dim_time_{uuid.uuid4().hex[:12]}"
    cols = list(df.columns)
    cols_sql = ", ".join(f'"{c}"' for c in cols)
    try:
        df.to_sql(temp, conn, if_exists="replace", index=False, method="multi")
        conn.execute(text(
            f'INSERT INTO dim_time ({cols_sql}) SELECT {cols_sql} FROM "{temp}" '
            'ON CONFLICT (date_key) DO NOTHING'
        ))
        conn.commit()
    finally:
        conn.execute(text(f'DROP TABLE IF EXISTS "{temp}"'))
        conn.commit()


def _sync_sequence(conn, table_name: str, surrogate_key: str, log) -> None:
    try:
        seq_name = f"{table_name}_{surrogate_key}_seq"
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
    if df.empty:
        log.info(f"{table_name} DataFrame is empty, skipping.")
        return
    
    if business_key not in df.columns:
        log.warning(f"{table_name} has no {business_key} column, cannot upsert. Skipping insert.")
        return
    
    _sync_sequence(conn, table_name, surrogate_key, log)
    
    where_clause = f"WHERE {extra_filter}" if extra_filter else ""
    res = conn.execute(text(f"SELECT {business_key}, {surrogate_key} FROM {table_name} {where_clause}"))
    existing_map = {r[0]: r[1] for r in res.fetchall() if r[0] is not None}
    log.info(f"Found {len(existing_map)} existing {table_name} records in DB")
    
    df_clean = df.dropna(subset=[business_key])
    df_new = df_clean[~df_clean[business_key].isin(existing_map.keys())]
    log.info(f"New {table_name} records to insert: {len(df_new)}")
    
    if not df_new.empty:
        cols = [c for c in df_new.columns if c != surrogate_key]
        df_insert = df_new[cols].copy()
        df_insert = df_insert.drop_duplicates(subset=[business_key], keep="first")
        log.info(f"After dedup: {len(df_insert)} unique {table_name} records to insert")
        
        temp = f"temp_{table_name}_{uuid.uuid4().hex[:12]}"
        cols_sql = ", ".join(f'"{c}"' for c in cols)
        try:
            df_insert.to_sql(temp, conn, if_exists="replace", index=False, method="multi")
            
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
    
    def _normalize_key(k):
        if k is None: return None
        try: return str(int(float(k)))
        except (ValueError, TypeError): return str(k).strip().lower()

    res = conn.execute(text(f"SELECT {business_key}, {surrogate_key} FROM {table_name} {where_clause}"))
    bk_to_sk = {_normalize_key(r[0]): r[1] for r in res.fetchall() if r[0] is not None}
    
    old_to_new = {}
    for _, row in df.iterrows():
        bk = row.get(business_key)
        if bk is None or pd.isna(bk):
            continue
        old_key = row.get(surrogate_key)
        if old_key is None or pd.isna(old_key):
            continue
        new_key = bk_to_sk.get(_normalize_key(bk))
        if new_key is not None:
            try:
                old_to_new[int(old_key)] = int(new_key)
            except (ValueError, TypeError):
                pass
    
    log.info(f"{table_name} key mapping: {len(old_to_new)} keys to remap")
    
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


def _upsert_dim_product_line(conn, engine, df: pd.DataFrame, star_schema: dict, log) -> None:
    if df.empty:
        log.info("dim_product_line DataFrame is empty, skipping.")
        return
    
    if 'product_line_id' not in df.columns:
        log.warning("dim_product_line has no product_line_id column, skipping.")
        return
    
    _sync_sequence(conn, "dim_product_line", "dim_product_line_key", log)
    
    res = conn.execute(text("SELECT product_line_id, product_id, variant_id, dim_product_line_key FROM dim_product_line"))
    existing_map = {}
    for r in res.fetchall():
        key = f"{r[0]}_{r[1]}_{r[2]}"
        existing_map[key] = r[3]
    log.info(f"Found {len(existing_map)} existing dim_product_line records in DB")
    
    df_clean = df.dropna(subset=['product_line_id'])
    df_new = df_clean[~df_clean.apply(lambda row: f"{row.get('product_line_id')}_{row.get('product_id')}_{row.get('variant_id')}" in existing_map, axis=1)]
    log.info(f"New dim_product_line records to insert: {len(df_new)}")
    
    if not df_new.empty:
        cols = [c for c in df_new.columns if c != 'dim_product_line_key' and c != 'product_code']
        df_insert = df_new[cols].copy()
        df_insert = df_insert.drop_duplicates(subset=['product_line_id', 'product_id', 'variant_id'], keep="first")
        
        temp = f"temp_dim_product_line_{uuid.uuid4().hex[:12]}"
        cols_sql = ", ".join(f'"{c}"' for c in cols)
        try:
            df_insert.to_sql(temp, conn, if_exists="replace", index=False, method="multi")
            conn.execute(text(
                f'INSERT INTO dim_product_line ({cols_sql}) SELECT {cols_sql} FROM "{temp}" '
                'ON CONFLICT (product_line_id, product_id, variant_id) DO NOTHING'
            ))
            conn.commit()
            log.info(f"Inserted new dim_product_line records")
        except Exception as e:
            log.error(f"Error inserting dim_product_line: {e}")
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


def _patch_null_foreign_keys(conn, engine, df: pd.DataFrame, table_name: str,
                             business_key: str, fk_cols: list, log) -> None:
    """Batch-update null FK columns in existing rows using values from df."""
    for fk_col in fk_cols:
        if fk_col not in df.columns:
            continue
        patch_df = df[[business_key, fk_col]].dropna(subset=[fk_col, business_key]).copy()
        if patch_df.empty:
            continue
        temp = f"temp_patch_{table_name}_{uuid.uuid4().hex[:8]}"
        try:
            patch_df.to_sql(temp, conn, if_exists="replace", index=False, method="multi")
            conn.execute(text(
                f'UPDATE {table_name} t '
                f'SET "{fk_col}" = p."{fk_col}" '
                f'FROM "{temp}" p '
                f'WHERE CAST(t.{business_key} AS TEXT) = CAST(p."{business_key}" AS TEXT) '
                f'AND t."{fk_col}" IS NULL'
            ))
            conn.commit()
            log.info(f"Patched null {fk_col} in {table_name}")
        except Exception as e:
            log.warning(f"Could not patch {fk_col} in {table_name}: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.execute(text(f'DROP TABLE IF EXISTS "{temp}"'))
                conn.commit()
            except Exception:
                pass


class PostgreSQLDBClient:

    def __init__(self):
        self.url = get_database_url()
        dsn = self.url.replace("postgresql+psycopg2://", "postgresql://") if "postgresql" in self.url else self.url
        self.engine = create_engine(dsn, future=True)
        self.conn = None

    def connect(self) -> bool:
        try:
            self.conn = self.engine.connect()
            self.ensure_schema()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            self.conn = None
            return False

    def ensure_schema(self) -> None:
        if self.conn is None:
            return
        try:
            result = self.conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'dim_time')"
            ))
            exists = result.scalar()
            if not exists:
                logger.warning("Schema tables not found. Please run create_postgres_tables.sql first.")
        except Exception as e:
            logger.warning(f"Could not check schema: {e}")

    def disconnect(self) -> None:
        try:
            if self.conn is not None:
                self.conn.close()
        finally:
            self.conn = None

    def load_star_schema(self, star_schema: Dict[str, pd.DataFrame], *, if_exists: str = "append", clear_existing: bool = False) -> Dict[str, bool]:
        assert self.conn is not None, "connect() must be called first"
        assert clear_existing is False, "clear_existing must be False; clearing is disabled."
        results: Dict[str, bool] = {}

        tables = list(star_schema.keys())
        logger.info(f"Saving {len(tables)} tables: {', '.join(tables)}")

        for table_name, df in star_schema.items():
            try:
                logger.info(f"Saving {table_name} ({len(df)} rows, {len(df.columns)} columns)...")
                df_to_write = df.copy()
                df_to_write = df_to_write.where(pd.notnull(df_to_write), None)
                
                if table_name == "dim_time" and if_exists == "append":
                    logger.info("Upserting dim_time (ON CONFLICT DO NOTHING)...")
                    _upsert_dim_time(self.conn, self.engine, df_to_write, logger)
                elif table_name == "dim_product" and if_exists == "append":
                    logger.info("Merging dim_product by listing_id...")
                    _upsert_dimension(self.conn, self.engine, df_to_write, star_schema, logger,
                                     table_name="dim_product", business_key="listing_id", 
                                     surrogate_key="product_key",
                                     fact_tables=[("fact_order_items", "product_key")])
                elif table_name == "dim_customer" and if_exists == "append":
                    logger.info("Merging dim_customer by buyer_user_name...")
                    _upsert_dimension(self.conn, self.engine, df_to_write, star_schema, logger,
                                     table_name="dim_customer", business_key="buyer_user_name",
                                     surrogate_key="customer_key",
                                     fact_tables=[("fact_orders", "customer_key"),
                                                  ("fact_order_items", "customer_key")])
                elif table_name == "fact_orders" and if_exists == "append":
                    logger.info("Merging fact_orders by order_id...")
                    _upsert_dimension(self.conn, self.engine, df_to_write, star_schema, logger,
                                     table_name="fact_orders", business_key="order_id",
                                     surrogate_key="order_key",
                                     fact_tables=[("fact_order_items", "order_key")],
                                     has_unique_constraint=True)
                    _patch_null_foreign_keys(self.conn, self.engine, df_to_write, "fact_orders",
                                            "order_id", ["customer_key"], logger)
                elif table_name == "dim_product_line" and if_exists == "append":
                    logger.info("Merging dim_product_line by composite key...")
                    _upsert_dim_product_line(self.conn, self.engine, df_to_write, star_schema, logger)
                else:
                    fact_surrogate_keys = {
                        'fact_order_items': 'order_item_key',
                        'fact_statement': 'statement_key',
                        'bridge_deposits': 'deposit_key',
                        'fact_payments': 'payment_key',
                        'fact_bank_transactions': 'bank_transaction_key'
                    }
                    
                    if table_name in fact_surrogate_keys:
                        sk = fact_surrogate_keys[table_name]
                        _sync_sequence(self.conn, table_name, sk, logger)
                        if sk in df_to_write.columns:
                            df_to_write = df_to_write.drop(columns=[sk])
                            logger.info(f"Removed {sk} column, letting DB auto-generate")
                    
                    df_to_write.to_sql(table_name, self.engine, if_exists=if_exists, index=False, method='multi')
                results[table_name] = True
                logger.info(f"Saved {table_name}")
            except Exception as e:
                results[table_name] = False
                logger.error(f"Failed to save {table_name}: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"Traceback for {table_name}:\n{traceback.format_exc()}")
        return results

    def validate_data_integrity(self, star_schema: Dict[str, pd.DataFrame]) -> None:
        return None


def get_db_client() -> PostgreSQLDBClient:
    return PostgreSQLDBClient()
