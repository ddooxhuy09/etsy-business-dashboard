"""
API routes for importing static data: Product Catalog and Bank Transactions.
Supports CSV file upload and single row import.
"""
import io
import re
import math
import logging
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from typing import Optional, Dict, Any
from pydantic import BaseModel

from api.db import run_query, execute_query, get_database_url
from etl.cleaners.process_product_catalog import clean_product_catalog_data
from etl.cleaners.process_bank_transactions import clean_bank_transactions_data, parse_description
from etl.expected_columns import validate_columns, get_raw_columns_list

router = APIRouter(prefix="/api/static", tags=["static"])
logger = logging.getLogger(__name__)


def _to_records(df):
    """Convert DataFrame to JSON-safe records."""
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    out = pd.DataFrame(df).replace({pd.NA: None}).to_dict(orient="records")
    
    def _js(v):
        if v is None or (isinstance(v, float) and (math.isnan(v) or not math.isfinite(v))):
            return None
        if hasattr(v, "item"):
            return v.item()
        return v
    
    return [{k: _js(v) for k, v in row.items()} for row in out]


def _get_or_create_time_key(date_str: str) -> Optional[int]:
    """Get or create time_key from date string (YYYY-MM-DD or DD/MM/YYYY)."""
    if not date_str:
        return None
    
    try:
        # Try YYYY-MM-DD format first
        if '-' in date_str and len(date_str) == 10:
            dt = pd.to_datetime(date_str, format='%Y-%m-%d', errors='raise')
        # Try DD/MM/YYYY format
        elif '/' in date_str:
            dt = pd.to_datetime(date_str, format='%d/%m/%Y', errors='raise')
        else:
            dt = pd.to_datetime(date_str, errors='raise')
        
        if pd.isna(dt):
            return None
        
        time_key = int(dt.strftime('%Y%m%d'))
        
        # Check if time_key exists in dim_time, if not create it
        df = run_query("SELECT time_key FROM dim_time WHERE time_key = %s", (time_key,))
        if df.empty:
            # Create time dimension entry
            full_date = dt.strftime('%Y-%m-%d')
            year = dt.year
            quarter = (dt.month - 1) // 3 + 1
            month = dt.month
            iso_cal = dt.isocalendar()
            week_of_year = iso_cal[1] if isinstance(iso_cal, tuple) else iso_cal.week
            day_of_month = dt.day
            day_of_week = dt.weekday() + 1  # Monday = 1
            day_of_year = dt.timetuple().tm_yday
            month_name = dt.strftime('%B')
            day_name = dt.strftime('%A')
            quarter_name = f'Q{quarter}'
            is_weekend = 1 if dt.weekday() >= 5 else 0
            is_holiday = 0
            is_business_day = 1 if dt.weekday() < 5 else 0
            
            execute_query("""
                INSERT INTO dim_time (
                    time_key, full_date, year, quarter, month, week_of_year,
                    day_of_month, day_of_week, day_of_year, month_name, day_name,
                    quarter_name, is_weekend, is_holiday, is_business_day
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                time_key, full_date, year, quarter, month, week_of_year,
                day_of_month, day_of_week, day_of_year, month_name, day_name,
                quarter_name, is_weekend, is_holiday, is_business_day
            ))
        
        return time_key
    except Exception as e:
        import logging
        logging.error(f"Error parsing date '{date_str}': {str(e)}")
        return None


def _get_or_create_bank_account_key(account_number: str, account_name: str = None, opening_date: str = None) -> Optional[int]:
    """Get or create bank_account_key from account_number."""
    if not account_number:
        return None
    
    # Check if exists
    df = run_query("SELECT bank_account_key FROM dim_bank_account WHERE account_number = %s", (account_number,))
    if not df.empty:
        return int(df.iloc[0]['bank_account_key'])
    
    # Create new bank account
    account_name = account_name or account_number
    opening_date = opening_date or None
    
    # Get max key
    max_key_df = run_query("SELECT MAX(bank_account_key) as max_key FROM dim_bank_account")
    max_key = int(max_key_df.iloc[0]['max_key']) if not max_key_df.empty and max_key_df.iloc[0]['max_key'] is not None else 0
    new_key = max_key + 1
    
    execute_query("""
        INSERT INTO dim_bank_account (
            bank_account_key, account_number, account_name, opening_date,
            is_active, currency_code, created_date, updated_date
        ) VALUES (%s, %s, %s, %s, TRUE, 'VND', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (new_key, account_number, account_name, opening_date))
    
    return new_key


def _get_product_catalog_key(product_line_id: str, product_id: str, variant_id: str) -> Optional[int]:
    """Get product_catalog_key from composite key."""
    if not all([product_line_id, product_id, variant_id]):
        return None
    
    df = run_query("""
        SELECT product_catalog_key FROM dim_product_catalog
        WHERE product_line_id = %s AND product_id = %s AND variant_id = %s
    """, (product_line_id, product_id, variant_id))
    
    if not df.empty:
        return int(df.iloc[0]['product_catalog_key'])
    return None


# ========== Product Catalog Import ==========

@router.post("/product-catalog/upload")
async def upload_product_catalog(file: UploadFile = File(...)):
    """Upload and import product_catalog.csv file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be CSV format")
    
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content), encoding='utf-8')

        # Validate header columns match expected schema
        header_errors = validate_columns("product_catalog", df.columns.tolist())
        if header_errors:
            expected = get_raw_columns_list("product_catalog")
            return {
                "ok": False,
                "message": "Sai định dạng cột product_catalog.csv",
                "imported": 0,
                "errors": header_errors,
                "expected_columns": expected,
                "received_columns": list(df.columns),
            }
        
        # Clean data
        df_clean = clean_product_catalog_data(df)
        
        if df_clean.empty:
            return {"ok": False, "message": "No valid data after cleaning", "imported": 0}
        
        # ==========================
        # FAST PATH: batch upsert (giống bank-transactions, 1 DB connection)
        # - Không insert từng dòng (rất chậm)
        # - Dùng ON CONFLICT trên (product_line_id, product_id, variant_id)
        # ==========================
        import psycopg2
        from psycopg2.extras import execute_values

        # Chỉ giữ các cột cần thiết
        cols = ["product_line_id", "product_id", "variant_id", "product_line_name", "product_name", "variant_name"]
        for c in cols:
            if c not in df_clean.columns:
                df_clean[c] = None

        # Chuẩn hóa text: strip khoảng trắng
        for c in ["product_line_id", "product_id", "variant_id"]:
            df_clean[c] = df_clean[c].astype(str).str.strip()

        # Bỏ các dòng thiếu key chính
        df_clean = df_clean.dropna(subset=["product_line_id", "product_id", "variant_id"])
        if df_clean.empty:
            return {"ok": False, "message": "No valid key rows after cleaning", "imported": 0}

        # Loại bỏ trùng lặp để tránh upsert lặp
        df_upsert = df_clean[cols].drop_duplicates(subset=["product_line_id", "product_id", "variant_id"]).copy()

        dsn = get_database_url().replace("postgresql+psycopg2://", "postgresql://")
        imported = 0

        try:
            with psycopg2.connect(dsn) as conn:
                with conn.cursor() as cur:
                    rows = list(
                        zip(
                            df_upsert["product_line_id"].tolist(),
                            df_upsert["product_id"].tolist(),
                            df_upsert["variant_id"].tolist(),
                            df_upsert["product_line_name"].tolist(),
                            df_upsert["product_name"].tolist(),
                            df_upsert["variant_name"].tolist(),
                        )
                    )
                    execute_values(
                        cur,
                        """
                        INSERT INTO dim_product_catalog (
                            product_line_id, product_id, variant_id,
                            product_line_name, product_name, variant_name
                        )
                        VALUES %s
                        ON CONFLICT (product_line_id, product_id, variant_id)
                        DO NOTHING
                        """,
                        rows,
                        page_size=2000,
                    )
                    imported = len(rows)
                conn.commit()
        except Exception:
            # Cho log chi tiết rồi bắn HTTPException phía dưới
            raise

        return {
            "ok": True,
            "message": f"Imported or updated {imported} rows",
            "imported": imported,
            "errors": [],
        }
    except Exception as e:
        # Log đầy đủ traceback ra terminal để debug khi deploy / chạy server
        logger.exception("Error in product-catalog upload")
        # In thêm ra stdout để chắc chắn thấy trong mọi môi trường (dev, exe, log mặc định của uvicorn)
        import traceback
        print("Error in product-catalog upload:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


class ProductCatalogRow(BaseModel):
    product_line_id: str
    product_id: str
    variant_id: str
    product_line_name: Optional[str] = None
    product_name: Optional[str] = None
    variant_name: Optional[str] = None


@router.post("/product-catalog/import-row")
def import_product_catalog_row(row: ProductCatalogRow):
    """Import a single product catalog row."""
    try:
        # Check if exists
        existing = run_query("""
            SELECT product_catalog_key FROM dim_product_catalog
            WHERE product_line_id = %s AND product_id = %s AND variant_id = %s
        """, (row.product_line_id, row.product_id, row.variant_id))
        
        if not existing.empty:
            # Update
            execute_query("""
                UPDATE dim_product_catalog
                        SET product_line_name = %s, product_name = %s, variant_name = %s,
                            updated_date = CURRENT_TIMESTAMP
                        WHERE product_line_id = %s AND product_id = %s AND variant_id = %s
            """, (
                row.product_line_name, row.product_name, row.variant_name,
                row.product_line_id, row.product_id, row.variant_id
            ))
            return {"ok": True, "message": "Updated existing row", "action": "update"}
        else:
            # Insert
            execute_query("""
                INSERT INTO dim_product_catalog (
                    product_line_id, product_id, variant_id,
                    product_line_name, product_name, variant_name,
                    created_date, updated_date
                ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                row.product_line_id, row.product_id, row.variant_id,
                row.product_line_name, row.product_name, row.variant_name
            ))
            return {"ok": True, "message": "Inserted new row", "action": "insert"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error importing row: {str(e)}")


# ========== Bank Transactions Import ==========

@router.post("/bank-transactions/upload")
async def upload_bank_transactions(file: UploadFile = File(...)):
    """Upload and import bank transactions CSV file.
    
    Expected columns:
    - Transaction Date (Ngày GD)
    - Reference No. (Mã giao dịch)
    - Account Number (Số tài khoản truy vấn)
    - Account Name (Tên tài khoản truy vấn)
    - Opening Date (Ngày mở tài khoản) - optional
    - Credit Amount (Phát sinh có)
    - Debit Amount (Phát sinh nợ)
    - Balance (Số dư)
    - Description (Diễn giải)
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be CSV format")
    
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content), encoding='utf-8')

        # Validate header columns match expected schema (bank_transactions)
        header_errors = validate_columns("bank_transactions", df.columns.tolist())
        if header_errors:
            expected = get_raw_columns_list("bank_transactions")
            return {
                "ok": False,
                "message": "Sai định dạng cột bank_transactions CSV",
                "imported": 0,
                "errors": header_errors,
                "expected_columns": expected,
                "received_columns": list(df.columns),
            }
        
        # Map column names (handle both English and Vietnamese)
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'transaction date' in col_lower or 'ngày gd' in col_lower or 'ngay gd' in col_lower:
                column_mapping[col] = 'transaction_date'
            elif 'reference' in col_lower or 'mã giao dịch' in col_lower or 'ma giao dich' in col_lower:
                column_mapping[col] = 'reference_number'
            elif 'account number' in col_lower and ('truy vấn' in col_lower or 'truy van' in col_lower):
                column_mapping[col] = 'account_number'
            elif 'account name' in col_lower and ('truy vấn' in col_lower or 'truy van' in col_lower):
                column_mapping[col] = 'account_name'
            elif 'opening date' in col_lower or 'ngày mở' in col_lower or 'ngay mo' in col_lower:
                column_mapping[col] = 'opening_date'
            elif 'credit amount' in col_lower or 'phát sinh có' in col_lower or 'phat sinh co' in col_lower:
                column_mapping[col] = 'credit_amount'
            elif 'debit amount' in col_lower or 'phát sinh nợ' in col_lower or 'phat sinh no' in col_lower:
                column_mapping[col] = 'debit_amount'
            elif 'balance' in col_lower and 'after' not in col_lower or 'số dư' in col_lower or 'so du' in col_lower:
                column_mapping[col] = 'balance_after_transaction'
            elif 'description' in col_lower or 'diễn giải' in col_lower or 'dien giai' in col_lower:
                column_mapping[col] = 'transaction_description'
        
        df = df.rename(columns=column_mapping)
        
        # Clean and process
        # Parse description for product info
        if 'transaction_description' in df.columns:
            parsed_data = df['transaction_description'].apply(parse_description)
            parsed_df = pd.DataFrame(parsed_data.tolist())
            df['pl_account_number'] = parsed_df['pl_account_number']
            df['parsed_product_line_id'] = parsed_df['parsed_product_line_id']
            df['parsed_product_id'] = parsed_df['parsed_product_id']
            df['parsed_variant_id'] = parsed_df['parsed_variant_id']
        
        # Convert date formats
        if 'transaction_date' in df.columns:
            df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce', format='%d/%m/%Y')
            df['transaction_date'] = df['transaction_date'].dt.strftime('%Y-%m-%d')
        
        if 'opening_date' in df.columns:
            df['opening_date'] = pd.to_datetime(df['opening_date'], errors='coerce', format='%d/%m/%Y')
            df['opening_date'] = df['opening_date'].dt.strftime('%Y-%m-%d')
        
        # Convert numeric columns
        numeric_cols = ['credit_amount', 'debit_amount', 'balance_after_transaction']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # ==========================
        # FAST PATH: batch upsert + batch insert (1 DB connection)
        # - Không lưu file CSV
        # - Không insert từng dòng (rất chậm)
        # - Không tự tạo dim_product_catalog khi import bank (tránh "tự có data")
        # ==========================
        import psycopg2
        from psycopg2.extras import execute_values

        errors = []

        # Normalize key columns
        if "account_number" not in df.columns:
            return {"ok": False, "message": "Missing account_number column after mapping", "imported": 0, "errors": ["Missing account_number"]}

        df["account_number"] = df["account_number"].astype(str).str.strip()
        # Some files might have "nan" string after astype(str)
        df.loc[df["account_number"].str.lower().isin(["nan", "none", ""]), "account_number"] = None

        if "account_name" in df.columns:
            df["account_name"] = df["account_name"].astype(str).str.strip()
            df.loc[df["account_name"].str.lower().isin(["nan", "none", ""]), "account_name"] = None
        else:
            df["account_name"] = None

        # Fill required NOT NULL account_name in dim_bank_account
        df["account_name"] = df["account_name"].fillna(df["account_number"])

        # Compute transaction_date_key as int (YYYYMMDD)
        if "transaction_date" in df.columns:
            dt = pd.to_datetime(df["transaction_date"], errors="coerce")
            df["transaction_date_key"] = dt.dt.strftime("%Y%m%d")
            df.loc[dt.isna(), "transaction_date_key"] = None
            df["transaction_date_key"] = pd.to_numeric(df["transaction_date_key"], errors="coerce").astype("Int64")
        else:
            df["transaction_date_key"] = None

        # Drop rows missing required account_number
        missing_acct = df["account_number"].isna()
        if missing_acct.any():
            bad_idx = df.index[missing_acct].tolist()[:10]
            for i in bad_idx:
                errors.append(f"Row {int(i) + 1}: Missing account_number")
            df = df.loc[~missing_acct].copy()

        if df.empty:
            return {"ok": True, "message": "No valid rows to import", "imported": 0, "errors": errors[:10]}

        # is_business_related = parsed_product_line_id not null
        if "parsed_product_line_id" in df.columns:
            df["is_business_related"] = df["parsed_product_line_id"].notna().astype(int)
        else:
            df["is_business_related"] = 0

        dsn = get_database_url().replace("postgresql+psycopg2://", "postgresql://")

        imported = 0
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                # 1) Ensure dim_time for transaction dates (batch)
                time_keys = df["transaction_date_key"].dropna().astype(int).unique().tolist()
                if time_keys:
                    cur.execute("SELECT time_key FROM dim_time WHERE time_key = ANY(%s)", (time_keys,))
                    existing = {r[0] for r in cur.fetchall()}
                    missing = [k for k in time_keys if k not in existing]
                    if missing:
                        # Build rows for dim_time
                        missing_dates = pd.to_datetime(pd.Series(missing, dtype="int64").astype(str), format="%Y%m%d", errors="coerce")
                        tdf = pd.DataFrame({"time_key": missing, "dt": missing_dates})
                        tdf = tdf.dropna(subset=["dt"])
                        if not tdf.empty:
                            tdf["full_date"] = tdf["dt"].dt.date
                            tdf["year"] = tdf["dt"].dt.year
                            tdf["quarter"] = ((tdf["dt"].dt.month - 1) // 3 + 1).astype(int)
                            tdf["month"] = tdf["dt"].dt.month
                            tdf["week_of_year"] = tdf["dt"].dt.isocalendar().week.astype(int)
                            tdf["day_of_month"] = tdf["dt"].dt.day
                            tdf["day_of_week"] = (tdf["dt"].dt.weekday + 1).astype(int)
                            tdf["day_of_year"] = tdf["dt"].dt.dayofyear
                            tdf["month_name"] = tdf["dt"].dt.strftime("%B")
                            tdf["day_name"] = tdf["dt"].dt.strftime("%A")
                            tdf["quarter_name"] = "Q" + tdf["quarter"].astype(str)
                            tdf["is_weekend"] = (tdf["dt"].dt.weekday >= 5).astype(bool)
                            tdf["is_holiday"] = False
                            tdf["is_business_day"] = (tdf["dt"].dt.weekday < 5).astype(bool)

                            time_rows = list(
                                zip(
                                    tdf["time_key"].astype(int).tolist(),
                                    tdf["full_date"].tolist(),
                                    tdf["year"].astype(int).tolist(),
                                    tdf["quarter"].astype(int).tolist(),
                                    tdf["month"].astype(int).tolist(),
                                    tdf["week_of_year"].astype(int).tolist(),
                                    tdf["day_of_month"].astype(int).tolist(),
                                    tdf["day_of_week"].astype(int).tolist(),
                                    tdf["day_of_year"].astype(int).tolist(),
                                    tdf["month_name"].tolist(),
                                    tdf["day_name"].tolist(),
                                    tdf["quarter_name"].tolist(),
                                    tdf["is_weekend"].tolist(),
                                    tdf["is_holiday"].tolist(),
                                    tdf["is_business_day"].tolist(),
                                )
                            )
                            execute_values(
                                cur,
                                """
                                INSERT INTO dim_time (
                                    time_key, full_date, year, quarter, month, week_of_year,
                                    day_of_month, day_of_week, day_of_year, month_name, day_name,
                                    quarter_name, is_weekend, is_holiday, is_business_day
                                ) VALUES %s
                                ON CONFLICT (time_key) DO NOTHING
                                """,
                                time_rows,
                                page_size=1000,
                            )

                # 2) Upsert dim_bank_account (batch) and build mapping account_number -> bank_account_key
                acct_df = df[["account_number", "account_name"]].drop_duplicates(subset=["account_number"]).copy()
                # opening_date is optional
                if "opening_date" in df.columns:
                    od = pd.to_datetime(df["opening_date"], errors="coerce")
                    df["opening_date_norm"] = od.dt.date
                    acct_df = df[["account_number", "account_name", "opening_date_norm"]].drop_duplicates(subset=["account_number"]).copy()
                else:
                    df["opening_date_norm"] = None
                    acct_df["opening_date_norm"] = None

                acct_rows = list(
                    zip(
                        acct_df["account_number"].tolist(),
                        acct_df["account_name"].tolist(),
                        acct_df["opening_date_norm"].tolist(),
                    )
                )
                execute_values(
                    cur,
                    """
                    INSERT INTO dim_bank_account (account_number, account_name, opening_date)
                    VALUES %s
                    ON CONFLICT (account_number)
                    DO UPDATE SET
                        account_name = EXCLUDED.account_name,
                        opening_date = COALESCE(EXCLUDED.opening_date, dim_bank_account.opening_date),
                        updated_date = CURRENT_TIMESTAMP
                    RETURNING bank_account_key, account_number
                    """,
                    acct_rows,
                    page_size=1000,
                )
                returned = cur.fetchall()
                acct_map = {acc: key for (key, acc) in returned}
                # Some rows might already exist and still RETURN due to DO UPDATE; to be safe, load all keys for involved accounts
                cur.execute(
                    "SELECT bank_account_key, account_number FROM dim_bank_account WHERE account_number = ANY(%s)",
                    (acct_df["account_number"].tolist(),),
                )
                acct_map.update({acc: key for (key, acc) in cur.fetchall()})

                # 3) Insert fact_bank_transactions in batch
                def _safe_str(v):
                    if v is None or (isinstance(v, float) and (math.isnan(v) or not math.isfinite(v))):
                        return None
                    s = str(v)
                    if s.lower() in ["nan", "none", ""]:
                        return None
                    return s

                insert_rows = []
                for _, row in df.iterrows():
                    bank_account_key = acct_map.get(row["account_number"])
                    if not bank_account_key:
                        continue
                    # Convert is_business_related (stored as Int/NaN) -> proper bool for PostgreSQL
                    is_business_val = row.get("is_business_related")
                    if pd.isna(is_business_val):
                        is_business_flag = False
                    else:
                        try:
                            is_business_flag = bool(int(is_business_val))
                        except Exception:
                            is_business_flag = False
                    insert_rows.append(
                        (
                            int(bank_account_key),
                            int(row["transaction_date_key"]) if pd.notna(row.get("transaction_date_key")) else None,
                            None,  # product_catalog_key: không tự tạo ở bước import bank
                            _safe_str(row.get("reference_number")),
                            _safe_str(row.get("account_number")),
                            _safe_str(row.get("transaction_description")),
                            _safe_str(row.get("pl_account_number")),
                            _safe_str(row.get("parsed_product_line_id")),
                            _safe_str(row.get("parsed_product_id")),
                            _safe_str(row.get("parsed_variant_id")),
                            float(row["credit_amount"]) if pd.notna(row.get("credit_amount")) else None,
                            float(row["debit_amount"]) if pd.notna(row.get("debit_amount")) else None,
                            float(row["balance_after_transaction"]) if pd.notna(row.get("balance_after_transaction")) else None,
                            is_business_flag,
                            "bank_statement",
                        )
                    )

                if insert_rows:
                    execute_values(
                        cur,
                        """
                        INSERT INTO fact_bank_transactions (
                            bank_account_key, transaction_date_key, product_catalog_key,
                            reference_number, account_number, transaction_description,
                            pl_account_number, parsed_product_line_id, parsed_product_id, parsed_variant_id,
                            credit_amount, debit_amount, balance_after_transaction,
                            is_business_related, data_source
                        ) VALUES %s
                        """,
                        insert_rows,
                        page_size=2000,
                    )
                    imported = len(insert_rows)
                conn.commit()
        
        return {
            "ok": True,
            "message": f"Imported {imported} rows",
            "imported": imported,
            "errors": errors[:10]
        }
    except Exception as e:
        # Ghi đầy đủ traceback ra terminal (stdout/stderr) qua logging
        logger.exception("Error in bank-transactions upload")
        # In thêm ra stdout để chắc chắn thấy trong mọi môi trường (dev, exe, log mặc định của uvicorn)
        import traceback
        print("Error in bank-transactions upload:", repr(e))
        traceback.print_exc()
        # Trả về thông điệp gọn cho frontend, tránh bị cắt chuỗi quá dài
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


class BankTransactionRow(BaseModel):
    transaction_date: str  # YYYY-MM-DD or DD/MM/YYYY
    reference_number: str
    account_number: str
    account_name: Optional[str] = None
    opening_date: Optional[str] = None
    credit_amount: Optional[float] = None
    debit_amount: Optional[float] = None
    balance_after_transaction: Optional[float] = None
    transaction_description: Optional[str] = None


@router.post("/bank-transactions/import-row")
def import_bank_transaction_row(row: BankTransactionRow):
    """Import a single bank transaction row."""
    try:
        # Get or create time_key
        transaction_date_key = _get_or_create_time_key(row.transaction_date)
        if transaction_date_key is None:
            raise HTTPException(status_code=400, detail="Invalid transaction_date format. Expected YYYY-MM-DD or DD/MM/YYYY")
        
        # Get or create bank_account_key
        if not row.account_number:
            raise HTTPException(status_code=400, detail="account_number is required")
        
        bank_account_key = _get_or_create_bank_account_key(
            row.account_number,
            row.account_name,
            row.opening_date
        )
        if bank_account_key is None:
            raise HTTPException(status_code=400, detail="Failed to create or retrieve bank_account_key")
        
        # Parse description for product info
        try:
            parsed = parse_description(row.transaction_description or '')
            if parsed is None or not isinstance(parsed, dict):
                parsed = {
                    'pl_account_number': None,
                    'parsed_product_line_id': None,
                    'parsed_product_id': None,
                    'parsed_variant_id': None
                }
        except Exception:
            parsed = {
                'pl_account_number': None,
                'parsed_product_line_id': None,
                'parsed_product_id': None,
                'parsed_variant_id': None
            }

        # Fallback parsing: hỗ trợ format đơn giản "X_Y_Z" (ví dụ: "1_1_1")
        if (
            parsed.get('parsed_product_line_id') is None
            and parsed.get('parsed_product_id') is None
            and parsed.get('parsed_variant_id') is None
            and (row.transaction_description or '').strip()
        ):
            desc = (row.transaction_description or '').strip()
            first_token = desc.split()[0]  # lấy phần đầu tiên trước dấu cách
            if '_' in first_token:
                parts = first_token.split('_')
                if len(parts) == 3:
                    parsed['parsed_product_line_id'] = parts[0].upper()
                    parsed['parsed_product_id'] = parts[1].upper()
                    parsed['parsed_variant_id'] = parts[2].upper()
        
        # Chỉ cố gắng link tới dim_product_catalog nếu đã tồn tại; KHÔNG tự tạo mới
        product_catalog_key = None
        if parsed.get('parsed_product_line_id') and parsed.get('parsed_product_id') and parsed.get('parsed_variant_id'):
            product_catalog_key = _get_product_catalog_key(
                parsed['parsed_product_line_id'],
                parsed['parsed_product_id'],
                parsed['parsed_variant_id']
            )
        
        # Determine if transaction is business-related (có parse được product info hay không)
        is_business_related = bool(
            parsed.get('parsed_product_line_id')
            and parsed.get('parsed_product_id')
            and parsed.get('parsed_variant_id')
        )

        # Prepare values for INSERT - ensure all are proper types
        insert_values = (
            int(bank_account_key),
            int(transaction_date_key),
            int(product_catalog_key) if product_catalog_key is not None else None,
            str(row.reference_number) if row.reference_number else None,
            str(row.account_number) if row.account_number else None,
            str(row.transaction_description) if row.transaction_description else None,
            str(parsed.get('pl_account_number')) if parsed.get('pl_account_number') else None,
            str(parsed.get('parsed_product_line_id')) if parsed.get('parsed_product_line_id') else None,
            str(parsed.get('parsed_product_id')) if parsed.get('parsed_product_id') else None,
            str(parsed.get('parsed_variant_id')) if parsed.get('parsed_variant_id') else None,
            float(row.credit_amount) if row.credit_amount is not None else None,
            float(row.debit_amount) if row.debit_amount is not None else None,
            float(row.balance_after_transaction) if row.balance_after_transaction is not None else None,
            is_business_related,
        )
        
        # Insert transaction
        execute_query("""
            INSERT INTO fact_bank_transactions (
                bank_account_key, transaction_date_key, product_catalog_key,
                reference_number, account_number, transaction_description,
                pl_account_number, parsed_product_line_id, parsed_product_id, parsed_variant_id,
                credit_amount, debit_amount, balance_after_transaction,
                is_business_related, data_source
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'bank_statement')
        """, insert_values)
        
        return {"ok": True, "message": "Imported row successfully"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=400, detail=f"Error importing row: {error_detail}")
