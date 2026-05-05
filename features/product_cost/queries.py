"""
Database query functions for Product Cost API.
Uses PostgreSQL syntax.
"""
from typing import List, Dict, Any
from sqlalchemy import text

from .config import engine
from features.dim_pl_accounts.helpers import get_cogs_accounts, get_expense_accounts, sql_in_list

COGS_LABELS = {
    "6211": "Material cost (Yarn)",
    "6221": "Concept design cost",
    "6222": "Chart + hook + spinning",
    "6223": "Spinning cost",
    "6224": "Photo + video cost",
    "6225": "Pattern & translation",
    "6273": "Production overhead",
    "6411": "Selling staff cost",
    "6412": "Materials & packaging (selling)",
    "6413": "Platform tools cost (selling)",
    "6414": "Tools cost (selling)",
    "6421": "Admin staff cost",
    "6428": "Marketing & channel management",
}


def query_products_optimized() -> List[Dict[str, Any]]:
    """
    Optimized query using CTEs to pre-aggregate data instead of correlated subqueries.
    Refund and Etsy Fee are allocated from order level to product level based on sales ratio.
    This reduces query time from O(n*m) to O(n+m).
    """
    _cogs_in = sql_in_list(get_cogs_accounts())
    sql = f"""
    WITH 
    sales_agg AS (
        SELECT 
            fs.sku AS product_id,
            SUM(COALESCE(fs.price, 0)) AS sales,
            COUNT(*) AS unit,
            STRING_AGG(DISTINCT fs.order_id::text, ', ') AS order_ids
        FROM fact_order_items fs
        WHERE fs.sku IS NOT NULL
        GROUP BY fs.sku
    ),
    
    order_sales AS (
        SELECT 
            order_id,
            SUM(COALESCE(price, 0)) AS total_order_sales
        FROM fact_order_items
        WHERE sku IS NOT NULL
        GROUP BY order_id
    ),
    
    product_order_sales AS (
        SELECT 
            fs.order_id,
            fs.sku AS product_id,
            SUM(COALESCE(fs.price, 0)) AS product_sales_in_order
        FROM fact_order_items fs
        WHERE fs.sku IS NOT NULL
        GROUP BY fs.order_id, fs.sku
    ),
    
    order_refunds AS (
        SELECT
            ref_order_id AS order_id,
            SUM(ABS(COALESCE(amount, 0))) AS refund_amount
        FROM fact_statement
        WHERE entry_type = 'Refund'
        GROUP BY ref_order_id
    ),

    refund_allocated AS (
        SELECT
            pos.product_id,
            SUM(
                COALESCE(or_ref.refund_amount, 0) *
                CASE
                    WHEN os.total_order_sales > 0 THEN pos.product_sales_in_order / os.total_order_sales
                    ELSE 0
                END
            ) AS refund
        FROM product_order_sales pos
        LEFT JOIN order_sales os ON os.order_id = pos.order_id
        LEFT JOIN order_refunds or_ref ON or_ref.order_id = pos.order_id
        GROUP BY pos.product_id
    ),

    order_fees AS (
        SELECT
            ref_order_id AS order_id,
            SUM(ABS(COALESCE(fees_and_taxes, 0))) AS fee_amount
        FROM fact_statement
        WHERE fees_and_taxes IS NOT NULL
          AND (
              (entry_type = 'Fee' AND title ILIKE ANY(ARRAY['%%Transaction fee%%', '%%Processing fee%%', '%%Regulatory Operating fee%%', '%%Listing fee%%']))
              OR entry_type = 'Marketing'
              OR (entry_type = 'VAT' AND title ILIKE ANY(ARRAY[
                  '%%auto-renew sold%%', '%%shipping_transaction%%', '%%Processing Fee%%',
                  '%%transaction credit%%', '%%listing credit%%', '%%listing%%', '%%Etsy Plus subscription%%'
              ]))
          )
        GROUP BY ref_order_id
    ),

    fee_allocated AS (
        SELECT
            pos.product_id,
            SUM(
                COALESCE(of_fee.fee_amount, 0) *
                CASE
                    WHEN os.total_order_sales > 0 THEN pos.product_sales_in_order / os.total_order_sales
                    ELSE 0
                END
            ) AS etsy_fee
        FROM product_order_sales pos
        LEFT JOIN order_sales os ON os.order_id = pos.order_id
        LEFT JOIN order_fees of_fee ON of_fee.order_id = pos.order_id
        GROUP BY pos.product_id
    ),

    cogs_agg AS (
        SELECT
            fbt.parsed_product_id AS product_id,
            SUM(COALESCE(fbt.debit_amount, 0)) AS cogs
        FROM fact_bank_transactions fbt
        WHERE fbt.pl_account_number IN ({_cogs_in})
          AND fbt.debit_amount IS NOT NULL
          AND fbt.parsed_product_id IS NOT NULL
        GROUP BY fbt.parsed_product_id
    )

    SELECT
        pc.product_line_id,
        pc.product      AS product_name,
        pc.product_id,
        pc.variants     AS variant_name,
        COALESCE(sa.sales, 0) AS sales,
        COALESCE(sa.order_ids, '') AS order_ids,
        COALESCE(ra.refund, 0) AS refund,
        COALESCE(sa.unit, 0)::int AS unit,
        COALESCE(ca.cogs, 0) AS cogs,
        COALESCE(fa.etsy_fee, 0) AS etsy_fee,
        COALESCE(sa.sales, 0) - COALESCE(ra.refund, 0) - COALESCE(ca.cogs, 0) - COALESCE(fa.etsy_fee, 0) AS profit
    FROM dim_product_line pc
    LEFT JOIN sales_agg sa ON sa.product_id = pc.product_id
    LEFT JOIN refund_allocated ra ON ra.product_id = pc.product_id
    LEFT JOIN fee_allocated fa ON fa.product_id = pc.product_id
    LEFT JOIN cogs_agg ca ON ca.product_id = pc.product_id
    WHERE pc.product_id IS NOT NULL
      AND pc.variants IS NOT NULL
    ORDER BY pc.product_line_id, product_name, pc.product_id, variant_name;
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = [dict(r._mapping) for r in result]
    return rows


def query_variants_optimized(product_id: str) -> List[Dict[str, Any]]:
    """Optimized variant query using CTEs. Refund and Etsy Fee are allocated based on sales ratio."""
    _cogs_in = sql_in_list(get_cogs_accounts())
    sql = f"""
    WITH 
    sales_agg AS (
        SELECT 
            fs.sku AS product_id,
            SUM(COALESCE(fs.price, 0)) AS sales,
            COUNT(*) AS unit
        FROM fact_order_items fs
        WHERE fs.sku = :pid
        GROUP BY fs.sku
    ),
    
    order_sales AS (
        SELECT 
            order_id,
            SUM(COALESCE(price, 0)) AS total_order_sales
        FROM fact_order_items
        WHERE sku = :pid
        GROUP BY order_id
    ),
    
    product_order_sales AS (
        SELECT 
            fs.order_id,
            fs.sku AS product_id,
            SUM(COALESCE(fs.price, 0)) AS product_sales_in_order
        FROM fact_order_items fs
        WHERE fs.sku = :pid
        GROUP BY fs.order_id, fs.sku
    ),
    
    order_refunds AS (
        SELECT
            ref_order_id AS order_id,
            SUM(ABS(COALESCE(amount, 0))) AS refund_amount
        FROM fact_statement
        WHERE entry_type = 'Refund'
          AND ref_order_id IN (SELECT DISTINCT order_id FROM fact_order_items WHERE sku = :pid)
        GROUP BY ref_order_id
    ),

    refund_allocated AS (
        SELECT
            pos.product_id,
            SUM(
                COALESCE(or_ref.refund_amount, 0) *
                CASE
                    WHEN os.total_order_sales > 0 THEN pos.product_sales_in_order / os.total_order_sales
                    ELSE 0
                END
            ) AS refund
        FROM product_order_sales pos
        LEFT JOIN order_sales os ON os.order_id = pos.order_id
        LEFT JOIN order_refunds or_ref ON or_ref.order_id = pos.order_id
        GROUP BY pos.product_id
    ),

    order_fees AS (
        SELECT
            ref_order_id AS order_id,
            SUM(ABS(COALESCE(fees_and_taxes, 0))) AS fee_amount
        FROM fact_statement
        WHERE fees_and_taxes IS NOT NULL
          AND ref_order_id IN (SELECT DISTINCT order_id FROM fact_order_items WHERE sku = :pid)
          AND (
              (entry_type = 'Fee' AND title ILIKE ANY(ARRAY['%%Transaction fee%%', '%%Processing fee%%', '%%Regulatory Operating fee%%', '%%Listing fee%%']))
              OR entry_type = 'Marketing'
              OR (entry_type = 'VAT' AND title ILIKE ANY(ARRAY[
                  '%%auto-renew sold%%', '%%shipping_transaction%%', '%%Processing Fee%%',
                  '%%transaction credit%%', '%%listing credit%%', '%%listing%%', '%%Etsy Plus subscription%%'
              ]))
          )
        GROUP BY ref_order_id
    ),

    fee_allocated AS (
        SELECT
            pos.product_id,
            SUM(
                COALESCE(of_fee.fee_amount, 0) *
                CASE
                    WHEN os.total_order_sales > 0 THEN pos.product_sales_in_order / os.total_order_sales
                    ELSE 0
                END
            ) AS etsy_fee
        FROM product_order_sales pos
        LEFT JOIN order_sales os ON os.order_id = pos.order_id
        LEFT JOIN order_fees of_fee ON of_fee.order_id = pos.order_id
        GROUP BY pos.product_id
    ),

    cogs_agg AS (
        SELECT
            fbt.parsed_variant_id AS variant_id,
            SUM(COALESCE(fbt.debit_amount, 0)) AS cogs
        FROM fact_bank_transactions fbt
        WHERE fbt.parsed_product_id = :pid
          AND fbt.pl_account_number IN ({_cogs_in})
          AND fbt.debit_amount IS NOT NULL
        GROUP BY fbt.parsed_variant_id
    )
    
    SELECT DISTINCT
        pc.variants AS variant,
        COALESCE(sa.sales, 0) AS sales,
        COALESCE(sa.unit, 0)::int AS unit,
        COALESCE(ra.refund, 0) AS refund,
        COALESCE(ca.cogs, 0) AS cogs,
        COALESCE(fa.etsy_fee, 0) AS etsy_fee
    FROM dim_product_line pc
    LEFT JOIN sales_agg sa ON sa.product_id = pc.product_id
    LEFT JOIN refund_allocated ra ON ra.product_id = pc.product_id
    LEFT JOIN fee_allocated fa ON fa.product_id = pc.product_id
    LEFT JOIN cogs_agg ca ON ca.variant_id = pc.variant_id
    WHERE pc.product_id = :pid
      AND pc.variants IS NOT NULL
    ORDER BY pc.variants;
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), {"pid": product_id})
        rows = [dict(r._mapping) for r in result]
    return rows


def query_cogs_breakdown(product_id: str) -> List[Dict[str, Any]]:
    """Query COGS breakdown by account."""
    _all_in = sql_in_list(get_cogs_accounts() + get_expense_accounts())
    sql = f"""
    SELECT
        fbt.pl_account_number,
        SUM(fbt.debit_amount) AS amount
    FROM fact_bank_transactions fbt
    WHERE fbt.parsed_product_id = :pid
      AND fbt.pl_account_number IN ({_all_in})
      AND fbt.debit_amount IS NOT NULL
    GROUP BY fbt.pl_account_number
    ORDER BY fbt.pl_account_number;
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), {"pid": product_id})
        rows = [dict(r._mapping) for r in result]
    return rows


def query_etsy_fee_breakdown(product_id: str) -> List[Dict[str, Any]]:
    """Query Etsy Fee breakdown by fee type. Allocates fees from order level to product level based on sales ratio."""
    sql = """
    WITH 
    order_sales AS (
        SELECT 
            order_id,
            SUM(COALESCE(price, 0)) AS total_order_sales
        FROM fact_order_items
        WHERE sku = :pid
        GROUP BY order_id
    ),
    
    product_order_sales AS (
        SELECT 
            fs.order_id,
            fs.sku AS product_id,
            SUM(COALESCE(fs.price, 0)) AS product_sales_in_order
        FROM fact_order_items fs
        WHERE fs.sku = :pid
        GROUP BY fs.order_id, fs.sku
    ),
    
    fees_with_type AS (
        SELECT
            fft.ref_order_id AS order_id,
            fft.fees_and_taxes,
            CASE
                WHEN fft.entry_type = 'Fee' AND fft.title ILIKE '%%Transaction fee%%' THEN 'Transaction Fee'
                WHEN fft.entry_type = 'Fee' AND fft.title ILIKE '%%Processing fee%%' THEN 'Processing Fee'
                WHEN fft.entry_type = 'Fee' AND fft.title ILIKE '%%Regulatory Operating fee%%' THEN 'Regulatory Operating Fee'
                WHEN fft.entry_type = 'Fee' AND fft.title ILIKE '%%Listing fee%%' THEN 'Listing Fee'
                WHEN fft.entry_type = 'Marketing' THEN 'Marketing'
                WHEN fft.entry_type = 'VAT' AND fft.title ILIKE '%%auto-renew sold%%' THEN 'VAT - auto-renew sold'
                WHEN fft.entry_type = 'VAT' AND fft.title ILIKE '%%shipping_transaction%%' THEN 'VAT - shipping_transaction'
                WHEN fft.entry_type = 'VAT' AND fft.title ILIKE '%%Processing Fee%%' THEN 'VAT - Processing Fee'
                WHEN fft.entry_type = 'VAT' AND fft.title ILIKE '%%transaction credit%%' THEN 'VAT - transaction credit'
                WHEN fft.entry_type = 'VAT' AND fft.title ILIKE '%%listing credit%%' THEN 'VAT - listing credit'
                WHEN fft.entry_type = 'VAT' AND fft.title ILIKE '%%listing%%' THEN 'VAT - listing'
                WHEN fft.entry_type = 'VAT' AND fft.title ILIKE '%%Etsy Plus subscription%%' THEN 'VAT - Etsy Plus subscription'
                WHEN fft.entry_type = 'VAT' THEN 'VAT - Other'
                ELSE NULL
            END AS fee_type
        FROM fact_statement fft
        WHERE fft.fees_and_taxes IS NOT NULL
          AND fft.ref_order_id IN (SELECT DISTINCT order_id FROM fact_order_items WHERE sku = :pid)
          AND (
              (fft.entry_type = 'Fee' AND fft.title ILIKE ANY(ARRAY['%%Transaction fee%%', '%%Processing fee%%', '%%Regulatory Operating fee%%', '%%Listing fee%%']))
              OR fft.entry_type = 'Marketing'
              OR (fft.entry_type = 'VAT' AND fft.title ILIKE ANY(ARRAY[
                  '%%auto-renew sold%%', '%%shipping_transaction%%', '%%Processing Fee%%',
                  '%%transaction credit%%', '%%listing credit%%', '%%listing%%', '%%Etsy Plus subscription%%'
              ]))
          )
    ),
    order_fees_by_type AS (
        SELECT 
            order_id,
            fee_type,
            SUM(ABS(COALESCE(fees_and_taxes, 0))) AS fee_amount
        FROM fees_with_type
        WHERE fee_type IS NOT NULL
        GROUP BY order_id, fee_type
    ),
    
    fee_allocated_by_type AS (
        SELECT 
            pos.product_id,
            oft.fee_type,
            SUM(
                COALESCE(oft.fee_amount, 0) * 
                CASE 
                    WHEN os.total_order_sales > 0 THEN pos.product_sales_in_order / os.total_order_sales
                    ELSE 0
                END
            ) AS amount
        FROM product_order_sales pos
        LEFT JOIN order_sales os ON os.order_id = pos.order_id
        LEFT JOIN order_fees_by_type oft ON oft.order_id = pos.order_id
        WHERE oft.fee_type IS NOT NULL
        GROUP BY pos.product_id, oft.fee_type
    )
    
    SELECT 
        fee_type,
        SUM(amount) AS amount
    FROM fee_allocated_by_type
    GROUP BY fee_type
    HAVING SUM(amount) > 0
    ORDER BY 
        CASE fee_type
            WHEN 'Transaction Fee' THEN 1
            WHEN 'Processing Fee' THEN 2
            WHEN 'Regulatory Operating Fee' THEN 3
            WHEN 'Listing Fee' THEN 4
            WHEN 'Marketing' THEN 5
            WHEN 'VAT - auto-renew sold' THEN 6
            WHEN 'VAT - shipping_transaction' THEN 7
            WHEN 'VAT - Processing Fee' THEN 8
            WHEN 'VAT - transaction credit' THEN 9
            WHEN 'VAT - listing credit' THEN 10
            WHEN 'VAT - listing' THEN 11
            WHEN 'VAT - Etsy Plus subscription' THEN 12
            WHEN 'VAT - Other' THEN 13
            ELSE 99
        END;
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), {"pid": product_id})
        rows = [dict(r._mapping) for r in result]
    return rows


def query_margin_breakdown(product_id: str) -> List[Dict[str, Any]]:
    """Query margin breakdown by order for a product. Shows order_id, sales %, and margin %."""
    _cogs_in = sql_in_list(get_cogs_accounts())
    sql = f"""
    WITH 
    order_sales AS (
        SELECT 
            order_id,
            SUM(COALESCE(price, 0)) AS total_order_sales
        FROM fact_order_items
        WHERE sku = :pid
        GROUP BY order_id
    ),
    
    product_order_sales AS (
        SELECT 
            fs.order_id,
            fs.sku AS product_id,
            SUM(COALESCE(fs.price, 0)) AS product_sales_in_order
        FROM fact_order_items fs
        WHERE fs.sku = :pid
        GROUP BY fs.order_id, fs.sku
    ),
    
    order_refunds AS (
        SELECT
            ref_order_id AS order_id,
            SUM(ABS(COALESCE(amount, 0))) AS refund_amount
        FROM fact_statement
        WHERE entry_type = 'Refund'
          AND ref_order_id IN (SELECT DISTINCT order_id FROM fact_order_items WHERE sku = :pid)
        GROUP BY ref_order_id
    ),

    order_fees AS (
        SELECT
            ref_order_id AS order_id,
            SUM(ABS(COALESCE(fees_and_taxes, 0))) AS fee_amount
        FROM fact_statement
        WHERE fees_and_taxes IS NOT NULL
          AND ref_order_id IN (SELECT DISTINCT order_id FROM fact_order_items WHERE sku = :pid)
          AND (
              (entry_type = 'Fee' AND title ILIKE ANY(ARRAY['%%Transaction fee%%', '%%Processing fee%%', '%%Regulatory Operating fee%%', '%%Listing fee%%']))
              OR entry_type = 'Marketing'
              OR (entry_type = 'VAT' AND title ILIKE ANY(ARRAY[
                  '%%auto-renew sold%%', '%%shipping_transaction%%', '%%Processing Fee%%',
                  '%%transaction credit%%', '%%listing credit%%', '%%listing%%', '%%Etsy Plus subscription%%'
              ]))
          )
        GROUP BY ref_order_id
    ),

    product_cogs_by_order AS (
        SELECT 
            fs.order_id,
            SUM(COALESCE(fbt.debit_amount, 0)) AS cogs_amount
        FROM fact_order_items fs
        JOIN fact_bank_transactions fbt ON fbt.parsed_product_id = fs.sku
        WHERE fs.sku = :pid
          AND fbt.pl_account_number IN ({_cogs_in})
          AND fbt.debit_amount IS NOT NULL
        GROUP BY fs.order_id
    ),
    
    order_margins AS (
        SELECT 
            pos.order_id,
            pos.product_sales_in_order AS sales,
            CASE 
                WHEN os.total_order_sales > 0 
                THEN (pos.product_sales_in_order / os.total_order_sales) * 100
                ELSE 0
            END AS sales_percent,
            COALESCE(
                or_ref.refund_amount * 
                CASE 
                    WHEN os.total_order_sales > 0 THEN pos.product_sales_in_order / os.total_order_sales
                    ELSE 0
                END,
                0
            ) AS refund,
            COALESCE(pc.cogs_amount, 0) AS cogs,
            COALESCE(
                of_fee.fee_amount * 
                CASE 
                    WHEN os.total_order_sales > 0 THEN pos.product_sales_in_order / os.total_order_sales
                    ELSE 0
                END,
                0
            ) AS etsy_fee
        FROM product_order_sales pos
        LEFT JOIN order_sales os ON os.order_id = pos.order_id
        LEFT JOIN order_refunds or_ref ON or_ref.order_id = pos.order_id
        LEFT JOIN order_fees of_fee ON of_fee.order_id = pos.order_id
        LEFT JOIN product_cogs_by_order pc ON pc.order_id = pos.order_id
    )
    
    SELECT 
        order_id,
        sales,
        sales_percent,
        refund,
        cogs,
        etsy_fee,
        sales - refund - cogs - etsy_fee AS profit,
        CASE 
            WHEN sales > 0 
            THEN ((sales - refund - cogs - etsy_fee) / sales) * 100
            ELSE 0
        END AS margin_percent
    FROM order_margins
    ORDER BY order_id;
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), {"pid": product_id})
        rows = [dict(r._mapping) for r in result]
    return rows
