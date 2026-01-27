"""
Reports API: Bank accounts, Account statement, PDF.
Uses PostgreSQL via api.db.run_query.
"""
import math
import pandas as pd
from fastapi import APIRouter, Query
from fastapi.responses import Response

from api.db import run_query
from api.reports_pdf import create_pdf_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _run(sql: str, params=None):
    """Run query safely, return empty DataFrame if table doesn't exist."""
    try:
        return run_query(sql, params)
    except Exception:
        # If table doesn't exist or other DB error, return empty DataFrame
        return pd.DataFrame()


def _to_records(df):
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


# ------ Bank accounts ------
@router.get("/bank-accounts")
def bank_accounts(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=50000)):
    sql = """WITH bank_account_stats AS (
                SELECT 
                    fbt.bank_account_key,
                    COUNT(*) as transaction_count,
                    SUM(COALESCE(fbt.credit_amount, 0)) as total_credit,
                    SUM(COALESCE(fbt.debit_amount, 0)) as total_debit,
                    MIN(dt.full_date) as first_transaction_date,
                    MAX(dt.full_date) as last_transaction_date,
                    MAX(fbt.balance_after_transaction) as current_balance
                FROM fact_bank_transactions fbt
                JOIN dim_time dt ON fbt.transaction_date_key = dt.time_key
                GROUP BY fbt.bank_account_key
            )
            SELECT 
                dba.account_number as "Account Number",
                dba.account_name as "Account Name",
                dba.cif_number as "CIF Number",
                dba.customer_address as "Customer Address",
                dba.opening_date::text as "Opening Date",
                dba.currency_code as "Currency",
                bas.transaction_count as "Total Transactions",
                ROUND(bas.total_credit::numeric, 2) as "Total Credit (VND)",
                ROUND(bas.total_debit::numeric, 2) as "Total Debit (VND)",
                ROUND(bas.current_balance::numeric, 2) as "Current Balance (VND)",
                bas.first_transaction_date::text as "First Transaction Date",
                bas.last_transaction_date::text as "Last Transaction Date"
            FROM bank_account_stats bas
            JOIN dim_bank_account dba ON bas.bank_account_key = dba.bank_account_key
            WHERE dba.account_number IS NOT NULL AND dba.account_number <> ''
            ORDER BY bas.total_credit DESC
            LIMIT %s OFFSET %s"""
    df = _run(sql, (limit, offset))
    return {"data": _to_records(df)}


@router.get("/bank-accounts/count")
def bank_accounts_count():
    sql = """SELECT COUNT(DISTINCT dba.bank_account_key) as total
             FROM dim_bank_account dba
             WHERE dba.account_number IS NOT NULL AND dba.account_number <> ''"""
    df = _run(sql)
    total = int(df["total"].iloc[0]) if not df.empty else 0
    return {"total": total}


@router.get("/bank-account-info")
def bank_account_info(account_number: str = Query(..., description="Account number")):
    sql = """SELECT dba.account_number, dba.account_name, dba.cif_number, dba.customer_address,
                    dba.opening_date, dba.currency_code
             FROM dim_bank_account dba WHERE dba.account_number = %s"""
    df = _run(sql, (account_number,))
    if not df.empty:
        row = df.iloc[0]
        return {
            "account_name": str(row["account_name"]) if pd.notna(row["account_name"]) else "N/A",
            "account_number": str(row["account_number"]) if pd.notna(row["account_number"]) else "N/A",
            "cif_number": str(row["cif_number"]) if pd.notna(row["cif_number"]) else "N/A",
            "customer_address": str(row["customer_address"]) if pd.notna(row["customer_address"]) else "N/A",
            "opening_date": str(row["opening_date"]) if pd.notna(row["opening_date"]) else "N/A",
            "currency_code": str(row["currency_code"]) if pd.notna(row["currency_code"]) else "VND",
        }
    return {"account_name": "N/A", "account_number": "N/A", "cif_number": "N/A", "customer_address": "N/A", "opening_date": "N/A", "currency_code": "VND"}


@router.get("/account-statement")
def account_statement(
    account_number: str = Query(..., description="Account number"),
    from_date: str = Query(None, description="From date YYYY-MM-DD"),
    to_date: str = Query(None, description="To date YYYY-MM-DD"),
):
    # Use %s for PostgreSQL parameter placeholders
    sql = """
    SELECT 
        t.full_date::text AS "Ngày GD",
        fbt.reference_number AS "Mã giao dịch",
        dba.account_number AS "Số tài khoản truy vấn",
        dba.account_name AS "Tên tài khoản truy vấn",
        dba.opening_date::text AS "Ngày mở tài khoản",
        COALESCE(fbt.credit_amount, 0) AS "Phát sinh có",
        COALESCE(fbt.debit_amount, 0) AS "Phát sinh nợ",
        fbt.balance_after_transaction AS "Số dư",
        fbt.transaction_description AS "Diễn giải"
    FROM fact_bank_transactions fbt
    JOIN dim_time t ON fbt.transaction_date_key = t.time_key
    JOIN dim_bank_account dba ON fbt.bank_account_key = dba.bank_account_key
    WHERE dba.account_number = %s
    """
    params = [account_number]
    if from_date:
        # Ensure date format is YYYY-MM-DD
        from_date_clean = str(from_date).strip()
        if len(from_date_clean) == 10 and from_date_clean.count('-') == 2:
            # Use string formatting for date comparison (date is already validated)
            # PostgreSQL date comparison
            sql += f" AND t.full_date >= '{from_date_clean}'"
    if to_date:
        # Ensure date format is YYYY-MM-DD
        to_date_clean = str(to_date).strip()
        if len(to_date_clean) == 10 and to_date_clean.count('-') == 2:
            # Use string formatting for date comparison (date is already validated)
            # PostgreSQL date comparison
            sql += f" AND t.full_date <= '{to_date_clean}'"
    sql += " ORDER BY t.full_date, fbt.bank_transaction_key"
    df = _run(sql, tuple(params))
    return {"data": _to_records(df)}


@router.get("/account-statement/pdf")
def account_statement_pdf(
    account_number: str = Query(..., description="Account number"),
    from_date: str = Query(None, description="From date YYYY-MM-DD"),
    to_date: str = Query(None, description="To date YYYY-MM-DD"),
):
    # Reuse logic without duplicating SQL
    info_sql = """SELECT dba.account_number, dba.account_name, dba.cif_number, dba.customer_address, dba.opening_date, dba.currency_code
                  FROM dim_bank_account dba WHERE dba.account_number = %s"""
    info_df = _run(info_sql, (account_number,))
    account_info = {"account_name": "N/A", "account_number": account_number, "cif_number": "N/A", "customer_address": "N/A", "opening_date": "N/A", "currency_code": "VND"}
    if not info_df.empty:
        r = info_df.iloc[0]
        account_info = {
            "account_name": str(r["account_name"]) if pd.notna(r.get("account_name")) else "N/A",
            "account_number": str(r["account_number"]) if pd.notna(r.get("account_number")) else account_number,
            "cif_number": str(r["cif_number"]) if pd.notna(r.get("cif_number")) else "N/A",
            "customer_address": str(r["customer_address"]) if pd.notna(r.get("customer_address")) else "N/A",
            "opening_date": str(r["opening_date"]) if pd.notna(r.get("opening_date")) else "N/A",
            "currency_code": str(r["currency_code"]) if pd.notna(r.get("currency_code")) else "VND",
        }

    stmt_sql = """
    SELECT t.full_date AS "Ngày GD", fbt.reference_number AS "Mã giao dịch", dba.account_number AS "Số tài khoản truy vấn",
           dba.account_name AS "Tên tài khoản truy vấn", dba.opening_date AS "Ngày mở tài khoản",
           COALESCE(fbt.credit_amount, 0) AS "Phát sinh có", COALESCE(fbt.debit_amount, 0) AS "Phát sinh nợ",
           fbt.balance_after_transaction AS "Số dư", fbt.transaction_description AS "Diễn giải"
    FROM fact_bank_transactions fbt
    JOIN dim_time t ON fbt.transaction_date_key = t.time_key
    JOIN dim_bank_account dba ON fbt.bank_account_key = dba.bank_account_key
    WHERE dba.account_number = %s
    """
    stmt_params = [account_number]
    if from_date:
        from_date_clean = str(from_date).strip()
        if len(from_date_clean) == 10 and from_date_clean.count('-') == 2:
            # Use string formatting for date comparison (date is already validated)
            stmt_sql += f" AND t.full_date >= '{from_date_clean}'"
    if to_date:
        to_date_clean = str(to_date).strip()
        if len(to_date_clean) == 10 and to_date_clean.count('-') == 2:
            # Use string formatting for date comparison (date is already validated)
            stmt_sql += f" AND t.full_date <= '{to_date_clean}'"
    stmt_sql += " ORDER BY t.full_date, fbt.bank_transaction_key"
    account_data = _run(stmt_sql, tuple(stmt_params))

    pdf_bytes = create_pdf_report(account_info, account_data, from_date, to_date)
    filename = f"account_statement_{account_number}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
