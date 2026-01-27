"""
PostgreSQL DB client for loading the star schema (moved from src.storage.db_factory).
"""
from __future__ import annotations

import logging
from typing import Dict
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text

from api.db import get_database_url

logger = logging.getLogger(__name__)


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
        """Load star schema dataframes into PostgreSQL tables."""
        assert self.conn is not None, "connect() must be called first"
        results: Dict[str, bool] = {}

        tables = list(star_schema.keys())
        logger.info(f"📊 Saving {len(tables)} tables: {', '.join(tables)}")
        
        if clear_existing and if_exists == "append":
            logger.info("🗑️ Clearing existing data...")
            # Delete facts first, then dimensions (respect foreign keys)
            ordered = sorted(tables, key=lambda t: (0 if t.startswith("fact_") else 1, t))
            for t in ordered:
                try:
                    self.conn.execute(text(f'DELETE FROM "{t}"'))
                    self.conn.commit()
                    logger.debug(f"Cleared table {t}")
                except Exception as e:
                    logger.warning(f"Could not clear table {t}: {e}")

        for table_name, df in star_schema.items():
            try:
                logger.info(f"💾 Saving {table_name} ({len(df)} rows, {len(df.columns)} columns)...")
                df_to_write = df.copy()
                df_to_write = df_to_write.where(pd.notnull(df_to_write), None)
                
                # Log sample data for debugging
                logger.debug(f"Sample columns: {list(df_to_write.columns[:5])}")
                logger.debug(f"Sample data types: {df_to_write.dtypes.head().to_dict()}")
                
                # Use SQLAlchemy engine for to_sql
                df_to_write.to_sql(table_name, self.engine, if_exists=if_exists, index=False, method='multi')
                results[table_name] = True
                logger.info(f"✅ Saved {len(df_to_write)} rows to {table_name}")
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
