"""
API routes for importing Bank Transactions data.
Supports CSV/Excel file upload and single-row import.
"""
import io
import math
import logging
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from typing import Optional
from pydantic import BaseModel

from core.database import run_query, execute_query, get_database_url
from etl.cleaners.process_bank_transactions import (
    clean_bank_transactions_data,
    get_allowed_pl_accounts,
    parse_description,
)
from etl.expected_columns import validate_columns, get_raw_columns_list

# Exchange rate: 1 USD = 24,000 VND
# All imported monetary values are in VND and are converted to USD at import time.
VND_TO_USD_RATE = 24_000


def _vnd_to_usd(value) -> float | None:
    """Convert a VND amount to USD and ensure non-negative.

    - Takes the absolute value first (bank statement debits are sometimes stored negative).
    - Divides by VND_TO_USD_RATE.
    - Returns None for null/NaN inputs.
    """
    if value is None:
        return None
    try:
        v = float(value)
        if math.isnan(v) or not math.isfinite(v):
            return None
        return abs(v) / VND_TO_USD_RATE
    except (TypeError, ValueError):
        return None

router = APIRouter(prefix="/api/static", tags=["bank-account"])
logger = logging.getLogger(__name__)


def _get_or_create_time_key(date_str: str) -> Optional[str]:
    """Get or create date_key from date string (YYYY-MM-DD or DD/MM/YYYY).
    Returns date string YYYY-MM-DD instead of integer key.
    """
    if not date_str:
        return None

    try:
        if '-' in date_str and len(date_str) == 10:
            dt = pd.to_datetime(date_str, format='%Y-%m-%d', errors='raise')
        elif '/' in date_str:
            dt = pd.to_datetime(date_str, format='%d/%m/%Y', errors='raise')
        else:
            dt = pd.to_datetime(date_str, errors='raise')

        if pd.isna(dt):
            return None

        date_key = dt.strftime('%Y-%m-%d')

        df = run_query("SELECT date_key FROM dim_time WHERE date_key = %s", (date_key,))
        if df.empty:
            year = dt.year
            quarter = f'Q{(dt.month - 1) // 3 + 1}'
            month_num = dt.month
            iso_cal = dt.isocalendar()
            week_of_year = iso_cal[1] if isinstance(iso_cal, tuple) else iso_cal.week
            month_name = dt.strftime('%B')
            day_of_week = dt.strftime('%A')
            is_weekend = True if dt.weekday() >= 5 else False

            execute_query("""
                INSERT INTO dim_time (
                    date_key, year, quarter, month_num, week_of_year,
                    month_name, day_of_week, is_weekend
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                date_key, year, quarter, month_num, week_of_year,
                month_name, day_of_week, is_weekend
            ))

        return date_key
    except Exception as e:
        logging.error(f"Error parsing date '{date_str}': {str(e)}")
        return None


def _get_product_line_key(product_line_id: str, product_id: str, variant_id: str) -> Optional[int]:
    """Get dim_product_line_key from composite key."""
    if not all([product_line_id, product_id, variant_id]):
        return None

    df = run_query("""
        SELECT dim_product_line_key FROM dim_product_line
        WHERE product_line_id = %s AND product_id = %s AND variant_id = %s
    """, (product_line_id, product_id, variant_id))

    if not df.empty:
        return int(df.iloc[0]['dim_product_line_key'])
    return None


@router.post("/bank-transactions/upload")
async def upload_bank_transactions(file: UploadFile = File(...)):
    """Upload and import bank transactions file (CSV or Excel).

    Expected columns:
    - Transaction Date / Ngày GD
    - Reference No. / Mã giao dịch
    - Account Number / Số tài khoản truy vấn
    - Account Name / Tên tài khoản truy vấn
    - Opening Date / Ngày mở tài khoản (optional)
    - Credit Amount / Phát sinh có
    - Debit Amount / Phát sinh nợ
    - Balance / Số dư
    - Description / Diễn giải
    """
    filename = (file.filename or "").lower()
    if not (filename.endswith(".csv") or filename.endswith(".xlsx") or filename.endswith(".xls")):
        raise HTTPException(status_code=400, detail="File must be CSV or Excel (.xlsx, .xls) format")

    try:
        content = await file.read()

        if filename.endswith(".csv"):
            df_raw = pd.read_csv(io.BytesIO(content), header=None)
        else:
            if filename.endswith(".xls") and not filename.endswith(".xlsx"):
                try:
                    import xlrd  # type: ignore
                    df_raw = pd.read_excel(io.BytesIO(content), header=None, engine="xlrd")
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Không đọc được file .xls. Vui lòng lưu lại thành .xlsx hoặc CSV. Chi tiết: {e}",
                    )
            else:
                df_raw = pd.read_excel(io.BytesIO(content), header=None)

        header_row_idx = None
        for i, row in df_raw.iterrows():
            values = [str(v) for v in row.values if pd.notna(v)]
            joined = " ".join(values).lower()
            if "description" in joined or "diễn giải" in joined or "dien giai" in joined:
                header_row_idx = i
                break

        if header_row_idx is None:
            header = df_raw.iloc[0]
            df = df_raw.iloc[1:].copy()
            df.columns = header
        else:
            header = df_raw.iloc[header_row_idx]
            df = df_raw.iloc[header_row_idx + 1:].copy()
            df.columns = header

        df = df.dropna(how="all")
        if df.empty:
            raise HTTPException(status_code=400, detail="Không tìm thấy bảng giao dịch trong file")
        df.columns = [str(c) if c is not None else "" for c in df.columns]

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

        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if "transaction date" in col_lower or "ngày gd" in col_lower or "ngay gd" in col_lower:
                column_mapping[col] = "transaction_date"
            elif "reference" in col_lower or "mã giao dịch" in col_lower or "ma giao dich" in col_lower:
                column_mapping[col] = "reference_number"
            elif "account number" in col_lower and ("truy vấn" in col_lower or "truy van" in col_lower):
                column_mapping[col] = "account_number"
            elif "account name" in col_lower and ("truy vấn" in col_lower or "truy van" in col_lower):
                column_mapping[col] = "account_name"
            elif "opening date" in col_lower or "ngày mở" in col_lower or "ngay mo" in col_lower:
                column_mapping[col] = "opening_date"
            elif "credit amount" in col_lower or "phát sinh có" in col_lower or "phat sinh co" in col_lower:
                column_mapping[col] = "credit_amount"
            elif "debit amount" in col_lower or "phát sinh nợ" in col_lower or "phat sinh no" in col_lower:
                column_mapping[col] = "debit_amount"
            elif ("balance" in col_lower and "after" not in col_lower) or "số dư" in col_lower or "so du" in col_lower:
                column_mapping[col] = "balance"
            elif "description" in col_lower or "diễn giải" in col_lower or "dien giai" in col_lower:
                column_mapping[col] = "transaction_description"
        df = df.rename(columns=column_mapping)

        if "transaction_description" in df.columns:
            allowed_pl_accounts = get_allowed_pl_accounts()
            parsed_df = df["transaction_description"].apply(
                lambda d: pd.Series(parse_description(d, allowed_pl_accounts))
            )
            for col in ["pl_account_number", "parsed_product_line_id", "parsed_product_id", "parsed_variant_id"]:
                if col in parsed_df.columns:
                    df[col] = parsed_df[col]

        if "transaction_date" in df.columns:
            df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce", dayfirst=True)
            df["transaction_date"] = df["transaction_date"].dt.strftime("%Y-%m-%d")
        if "opening_date" in df.columns:
            df["opening_date"] = pd.to_datetime(df["opening_date"], errors="coerce", dayfirst=True)
            df["opening_date"] = df["opening_date"].dt.strftime("%Y-%m-%d")

        for col in ["credit_amount", "debit_amount", "balance"]:
            if col in df.columns:
                df[col] = (
                    df[col].astype(str).str.replace(",", "", regex=False).str.replace(" ", "", regex=False)
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")
                df[col] = df[col].apply(_vnd_to_usd)

        try:
            debug_cols = ['transaction_date', 'reference_number', 'account_number', 'transaction_description',
                          'pl_account_number', 'debit_amount', 'credit_amount', 'balance']
            existing_debug_cols = [c for c in debug_cols if c in df.columns]
            if existing_debug_cols:
                print("\n=== BANK UPLOAD DEBUG (first 20 rows) ===")
                import pandas as _pd
                with _pd.option_context("display.max_columns", None, "display.width", 200):
                    print(df[existing_debug_cols].head(20).to_string(index=False))
        except Exception as _dbg_e:
            print("BANK UPLOAD DEBUG failed:", repr(_dbg_e))

        import psycopg2
        from psycopg2.extras import execute_values

        errors = []

        if "account_number" not in df.columns:
            return {"ok": False, "message": "Missing account_number column after mapping", "imported": 0, "errors": ["Missing account_number"]}

        df["account_number"] = df["account_number"].astype(str).str.strip()
        df.loc[df["account_number"].str.lower().isin(["nan", "none", ""]), "account_number"] = None

        if "account_name" in df.columns:
            df["account_name"] = df["account_name"].astype(str).str.strip()
            df.loc[df["account_name"].str.lower().isin(["nan", "none", ""]), "account_name"] = None
        else:
            df["account_name"] = None

        df["account_name"] = df["account_name"].fillna(df["account_number"])

        if "transaction_date" in df.columns:
            dt = pd.to_datetime(df["transaction_date"], errors="coerce")
            df["transaction_date_norm"] = dt
            df.loc[dt.isna(), "transaction_date_norm"] = None
        else:
            df["transaction_date_norm"] = None

        missing_acct = df["account_number"].isna()
        if missing_acct.any():
            bad_idx = df.index[missing_acct].tolist()[:10]
            for i in bad_idx:
                errors.append(f"Row {int(i) + 1}: Missing account_number")
            df = df.loc[~missing_acct].copy()

        if df.empty:
            return {"ok": True, "message": "No valid rows to import", "imported": 0, "errors": errors[:10]}

        dsn = get_database_url().replace("postgresql+psycopg2://", "postgresql://")

        imported = 0
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                valid_dates = df["transaction_date_norm"].dropna()
                if not valid_dates.empty:
                    date_keys = valid_dates.dt.strftime("%Y-%m-%d").unique().tolist()
                    cur.execute("SELECT date_key FROM dim_time WHERE date_key = ANY(%s::date[])", (date_keys,))
                    existing = {str(r[0]) for r in cur.fetchall()}
                    missing = [k for k in date_keys if k not in existing]
                    if missing:
                        missing_dates = pd.to_datetime(missing, errors="coerce")
                        tdf = pd.DataFrame({"date_key": missing, "dt": missing_dates})
                        tdf = tdf.dropna(subset=["dt"])
                        if not tdf.empty:
                            tdf["year"] = tdf["dt"].dt.year
                            tdf["quarter"] = "Q" + ((tdf["dt"].dt.month - 1) // 3 + 1).astype(str)
                            tdf["month_num"] = tdf["dt"].dt.month
                            tdf["week_of_year"] = tdf["dt"].dt.isocalendar().week.astype(int)
                            tdf["month_name"] = tdf["dt"].dt.strftime("%B")
                            tdf["day_of_week"] = tdf["dt"].dt.strftime("%A")
                            tdf["is_weekend"] = (tdf["dt"].dt.weekday >= 5).astype(bool)

                            time_rows = list(zip(
                                tdf["date_key"].tolist(),
                                tdf["year"].astype(int).tolist(),
                                tdf["quarter"].tolist(),
                                tdf["month_num"].astype(int).tolist(),
                                tdf["week_of_year"].astype(int).tolist(),
                                tdf["month_name"].tolist(),
                                tdf["day_of_week"].tolist(),
                                tdf["is_weekend"].tolist(),
                            ))
                            execute_values(cur, """
                                INSERT INTO dim_time (
                                    date_key, year, quarter, month_num, week_of_year,
                                    month_name, day_of_week, is_weekend
                                ) VALUES %s ON CONFLICT (date_key) DO NOTHING
                            """, time_rows, page_size=1000)

                def _safe_str(v):
                    if v is None or (isinstance(v, float) and (math.isnan(v) or not math.isfinite(v))):
                        return None
                    s = str(v)
                    if s.lower() in ["nan", "none", ""]:
                        return None
                    return s

                insert_rows = []
                for _, row in df.iterrows():
                    insert_rows.append((
                        row["transaction_date_norm"].to_pydatetime() if pd.notna(row.get("transaction_date_norm")) else None,
                        _safe_str(row.get("reference_number")),
                        _safe_str(row.get("account_number")),
                        _safe_str(row.get("account_name")),
                        _safe_str(row.get("opening_date")),
                        _safe_str(row.get("transaction_description")),
                        _safe_str(row.get("pl_account_number")),
                        _safe_str(row.get("parsed_product_line_id")),
                        _safe_str(row.get("parsed_product_id")),
                        _safe_str(row.get("parsed_variant_id")),
                        float(row["credit_amount"]) if pd.notna(row.get("credit_amount")) else None,
                        float(row["debit_amount"]) if pd.notna(row.get("debit_amount")) else None,
                        float(row["balance"]) if pd.notna(row.get("balance")) else None,
                    ))

                if insert_rows:
                    try:
                        execute_values(cur, """
                            INSERT INTO fact_bank_transactions (
                                transaction_date,
                                reference_number, account_number, account_name, opening_date,
                                transaction_description,
                                pl_account_number, parsed_product_line_id, parsed_product_id, parsed_variant_id,
                                credit_amount, debit_amount, balance
                            ) VALUES %s
                        """, insert_rows, page_size=2000)
                    except Exception as db_err:
                        from psycopg2.errors import UniqueViolation  # type: ignore
                        if isinstance(db_err, UniqueViolation) or "duplicate key value violates unique constraint" in str(db_err):
                            raise HTTPException(
                                status_code=400,
                                detail="Duplicate bank transactions detected (same account_number + reference_number). Có thể file sao kê này đã được import trước đó."
                            )
                        raise
                    imported = len(insert_rows)
                conn.commit()

        return {
            "ok": True,
            "message": f"Imported {imported} rows",
            "imported": imported,
            "errors": errors[:10]
        }
    except Exception as e:
        logger.exception("Error in bank-transactions upload")
        import traceback
        print("Error in bank-transactions upload:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


class BankTransactionRow(BaseModel):
    transaction_date: str  # YYYY-MM-DD or DD/MM/YYYY
    reference_number: str
    account_number: str
    account_name: Optional[str] = None
    opening_date: Optional[str] = None
    credit_amount: Optional[float] = None
    debit_amount: Optional[float] = None
    balance: Optional[float] = None
    transaction_description: Optional[str] = None


@router.post("/bank-transactions/import-row")
def import_bank_transaction_row(row: BankTransactionRow):
    """Import a single bank transaction row."""
    try:
        transaction_date_str = _get_or_create_time_key(row.transaction_date)
        if transaction_date_str is None:
            raise HTTPException(status_code=400, detail="Invalid transaction_date format. Expected YYYY-MM-DD or DD/MM/YYYY")

        if not row.account_number:
            raise HTTPException(status_code=400, detail="account_number is required")

        try:
            parsed = parse_description(row.transaction_description or '')
            if parsed is None or not isinstance(parsed, dict):
                parsed = {'pl_account_number': None, 'parsed_product_line_id': None, 'parsed_product_id': None, 'parsed_variant_id': None}
        except Exception:
            parsed = {'pl_account_number': None, 'parsed_product_line_id': None, 'parsed_product_id': None, 'parsed_variant_id': None}

        if (
            parsed.get('parsed_product_line_id') is None
            and parsed.get('parsed_product_id') is None
            and parsed.get('parsed_variant_id') is None
            and (row.transaction_description or '').strip()
        ):
            desc = (row.transaction_description or '').strip()
            first_token = desc.split()[0]
            if '_' in first_token:
                parts = first_token.split('_')
                if len(parts) == 3:
                    parsed['parsed_product_line_id'] = parts[0].upper()
                    parsed['parsed_product_id'] = parts[1].upper()
                    parsed['parsed_variant_id'] = parts[2].upper()

        insert_values = (
            transaction_date_str,
            str(row.reference_number) if row.reference_number else None,
            str(row.account_number) if row.account_number else None,
            str(row.account_name) if row.account_name else None,
            str(row.opening_date) if row.opening_date else None,
            str(row.transaction_description) if row.transaction_description else None,
            str(parsed.get('pl_account_number')) if parsed.get('pl_account_number') else None,
            str(parsed.get('parsed_product_line_id')) if parsed.get('parsed_product_line_id') else None,
            str(parsed.get('parsed_product_id')) if parsed.get('parsed_product_id') else None,
            str(parsed.get('parsed_variant_id')) if parsed.get('parsed_variant_id') else None,
            _vnd_to_usd(row.credit_amount),
            _vnd_to_usd(row.debit_amount),
            _vnd_to_usd(row.balance),
        )

        execute_query("""
            INSERT INTO fact_bank_transactions (
                transaction_date,
                reference_number, account_number, account_name, opening_date,
                transaction_description,
                pl_account_number, parsed_product_line_id, parsed_product_id, parsed_variant_id,
                credit_amount, debit_amount, balance
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, insert_values)

        return {"ok": True, "message": "Imported row successfully"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=400, detail=f"Error importing row: {error_detail}")
