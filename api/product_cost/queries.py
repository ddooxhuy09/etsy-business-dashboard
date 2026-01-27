"""
Database query functions for Product Cost API.
Uses PostgreSQL syntax.
"""
from typing import List, Dict, Any
from sqlalchemy import text

from .config import engine

# Labels for COGS breakdown
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
    sql = """
    WITH 
    -- Pre-aggregate sales metrics by product
    sales_agg AS (
        SELECT 
            fs.sku AS product_id,
            SUM(COALESCE(fs.item_price, 0)) AS sales,
            COUNT(*) AS unit,
            STRING_AGG(DISTINCT fs.order_id::text, ', ') AS order_ids
        FROM fact_sales fs
        WHERE fs.sku IS NOT NULL
        GROUP BY fs.sku
    ),
    
    -- Calculate total sales per order (for allocation ratio)
    order_sales AS (
        SELECT 
            order_id,
            SUM(COALESCE(item_price, 0)) AS total_order_sales
        FROM fact_sales
        WHERE sku IS NOT NULL
        GROUP BY order_id
    ),
    
    -- Calculate sales per product per order (for allocation ratio)
    product_order_sales AS (
        SELECT 
            fs.order_id,
            fs.sku AS product_id,
            SUM(COALESCE(fs.item_price, 0)) AS product_sales_in_order
        FROM fact_sales fs
        WHERE fs.sku IS NOT NULL
        GROUP BY fs.order_id, fs.sku
    ),
    
    -- Get refunds at order level
    order_refunds AS (
        SELECT 
            order_id,
            SUM(ABS(COALESCE(amount, 0))) AS refund_amount
        FROM fact_financial_transactions
        WHERE transaction_type = 'Refund'
        GROUP BY order_id
    ),
    
    -- Allocate refunds to products based on sales ratio
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
    
    -- Get Etsy fees at order level
    order_fees AS (
        SELECT 
            order_id,
            SUM(ABS(COALESCE(fees_and_taxes, 0))) AS fee_amount
        FROM fact_financial_transactions
        WHERE fees_and_taxes IS NOT NULL
          AND (
              (transaction_type = 'Fee' AND transaction_title ILIKE ANY(ARRAY['%Transaction fee%', '%Processing fee%', '%Regulatory Operating fee%', '%Listing fee%']))
              OR transaction_type = 'Marketing'
              OR (transaction_type = 'VAT' AND transaction_title ILIKE ANY(ARRAY[
                  '%auto-renew sold%', '%shipping_transaction%', '%Processing Fee%',
                  '%transaction credit%', '%listing credit%', '%listing%', '%Etsy Plus subscription%'
              ]))
          )
        GROUP BY order_id
    ),
    
    -- Allocate Etsy fees to products based on sales ratio
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
    
    -- Pre-aggregate COGS by product+variant (using indexed parsed columns for faster joins)
    cogs_agg AS (
        SELECT 
            fbt.parsed_product_id AS product_id,
            fbt.parsed_variant_id AS variant_id,
            SUM(COALESCE(fbt.debit_amount, 0)) AS cogs
        FROM fact_bank_transactions fbt 
        WHERE fbt.pl_account_number IN ('6211','6221','6222','6223','6224','6225')
          AND fbt.debit_amount IS NOT NULL
          AND fbt.parsed_product_id IS NOT NULL
        GROUP BY fbt.parsed_product_id, fbt.parsed_variant_id
    )
    
    SELECT 
        pc.product_line_id,
        pc.product_name,
        pc.product_id,
        pc.variant_name,
        COALESCE(sa.sales, 0) AS sales,
        COALESCE(sa.order_ids, '') AS order_ids,
        COALESCE(ra.refund, 0) AS refund,
        COALESCE(sa.unit, 0)::int AS unit,
        COALESCE(ca.cogs, 0) AS cogs,
        COALESCE(fa.etsy_fee, 0) AS etsy_fee,
        COALESCE(sa.sales, 0) - COALESCE(ra.refund, 0) - COALESCE(ca.cogs, 0) - COALESCE(fa.etsy_fee, 0) AS profit
    FROM dim_product_catalog pc
    LEFT JOIN sales_agg sa ON sa.product_id = pc.product_id
    LEFT JOIN refund_allocated ra ON ra.product_id = pc.product_id
    LEFT JOIN fee_allocated fa ON fa.product_id = pc.product_id
    LEFT JOIN cogs_agg ca ON ca.product_id = pc.product_id AND ca.variant_id = pc.variant_id
    WHERE pc.product_id IS NOT NULL
      AND pc.variant_name IS NOT NULL
    ORDER BY pc.product_line_id, pc.product_name, pc.product_id, pc.variant_name;
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = [dict(r._mapping) for r in result]
    return rows


def query_variants_optimized(product_id: str) -> List[Dict[str, Any]]:
    """Optimized variant query using CTEs. Refund and Etsy Fee are allocated based on sales ratio."""
    sql = """
    WITH 
    sales_agg AS (
        SELECT 
            fs.sku AS product_id,
            SUM(COALESCE(fs.item_price, 0)) AS sales,
            COUNT(*) AS unit
        FROM fact_sales fs
        WHERE fs.sku = :pid
        GROUP BY fs.sku
    ),
    
    -- Calculate total sales per order (for allocation ratio)
    order_sales AS (
        SELECT 
            order_id,
            SUM(COALESCE(item_price, 0)) AS total_order_sales
        FROM fact_sales
        WHERE sku = :pid
        GROUP BY order_id
    ),
    
    -- Calculate sales per product per order (for allocation ratio)
    product_order_sales AS (
        SELECT 
            fs.order_id,
            fs.sku AS product_id,
            SUM(COALESCE(fs.item_price, 0)) AS product_sales_in_order
        FROM fact_sales fs
        WHERE fs.sku = :pid
        GROUP BY fs.order_id, fs.sku
    ),
    
    -- Get refunds at order level
    order_refunds AS (
        SELECT 
            order_id,
            SUM(ABS(COALESCE(amount, 0))) AS refund_amount
        FROM fact_financial_transactions
        WHERE transaction_type = 'Refund'
          AND order_id IN (SELECT DISTINCT order_id FROM fact_sales WHERE sku = :pid)
        GROUP BY order_id
    ),
    
    -- Allocate refunds to products based on sales ratio
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
    
    -- Get Etsy fees at order level
    order_fees AS (
        SELECT 
            order_id,
            SUM(ABS(COALESCE(fees_and_taxes, 0))) AS fee_amount
        FROM fact_financial_transactions
        WHERE fees_and_taxes IS NOT NULL
          AND order_id IN (SELECT DISTINCT order_id FROM fact_sales WHERE sku = :pid)
          AND (
              (transaction_type = 'Fee' AND transaction_title ILIKE ANY(ARRAY['%Transaction fee%', '%Processing fee%', '%Regulatory Operating fee%', '%Listing fee%']))
              OR transaction_type = 'Marketing'
              OR (transaction_type = 'VAT' AND transaction_title ILIKE ANY(ARRAY[
                  '%auto-renew sold%', '%shipping_transaction%', '%Processing Fee%',
                  '%transaction credit%', '%listing credit%', '%listing%', '%Etsy Plus subscription%'
              ]))
          )
        GROUP BY order_id
    ),
    
    -- Allocate Etsy fees to products based on sales ratio
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
          AND fbt.pl_account_number IN ('6211','6221','6222','6223','6224','6225')
          AND fbt.debit_amount IS NOT NULL
        GROUP BY fbt.parsed_variant_id
    )
    
    SELECT DISTINCT
        pc.variant_name AS variant,
        COALESCE(sa.sales, 0) AS sales,
        COALESCE(sa.unit, 0)::int AS unit,
        COALESCE(ra.refund, 0) AS refund,
        COALESCE(ca.cogs, 0) AS cogs,
        COALESCE(fa.etsy_fee, 0) AS etsy_fee
    FROM dim_product_catalog pc
    LEFT JOIN sales_agg sa ON sa.product_id = pc.product_id
    LEFT JOIN refund_allocated ra ON ra.product_id = pc.product_id
    LEFT JOIN fee_allocated fa ON fa.product_id = pc.product_id
    LEFT JOIN cogs_agg ca ON ca.variant_id = pc.variant_id
    WHERE pc.product_id = :pid
      AND pc.variant_name IS NOT NULL
    ORDER BY pc.variant_name;
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), {"pid": product_id})
        rows = [dict(r._mapping) for r in result]
    return rows


def query_cogs_breakdown(product_id: str) -> List[Dict[str, Any]]:
    """Query COGS breakdown by account."""
    sql = """
    SELECT
        fbt.pl_account_number,
        SUM(fbt.debit_amount) AS amount
    FROM fact_bank_transactions fbt
    WHERE fbt.parsed_product_id = :pid
      AND fbt.pl_account_number IN (
        '6211','6221','6222','6223','6224','6225',
        '6273',
        '6411','6412','6413','6414',
        '6421','6428'
      )
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
    -- Calculate total sales per order (for allocation ratio)
    order_sales AS (
        SELECT 
            order_id,
            SUM(COALESCE(item_price, 0)) AS total_order_sales
        FROM fact_sales
        WHERE sku = :pid
        GROUP BY order_id
    ),
    
    -- Calculate sales per product per order (for allocation ratio)
    product_order_sales AS (
        SELECT 
            fs.order_id,
            fs.sku AS product_id,
            SUM(COALESCE(fs.item_price, 0)) AS product_sales_in_order
        FROM fact_sales fs
        WHERE fs.sku = :pid
        GROUP BY fs.order_id, fs.sku
    ),
    
    -- Get Etsy fees at order level, broken down by fee type
    fees_with_type AS (
        SELECT 
            fft.order_id,
            fft.fees_and_taxes,
            CASE 
                WHEN fft.transaction_type = 'Fee' AND fft.transaction_title ILIKE '%Transaction fee%' THEN 'Transaction Fee'
                WHEN fft.transaction_type = 'Fee' AND fft.transaction_title ILIKE '%Processing fee%' THEN 'Processing Fee'
                WHEN fft.transaction_type = 'Fee' AND fft.transaction_title ILIKE '%Regulatory Operating fee%' THEN 'Regulatory Operating Fee'
                WHEN fft.transaction_type = 'Fee' AND fft.transaction_title ILIKE '%Listing fee%' THEN 'Listing Fee'
                WHEN fft.transaction_type = 'Marketing' THEN 'Marketing'
                WHEN fft.transaction_type = 'VAT' AND fft.transaction_title ILIKE '%auto-renew sold%' THEN 'VAT - auto-renew sold'
                WHEN fft.transaction_type = 'VAT' AND fft.transaction_title ILIKE '%shipping_transaction%' THEN 'VAT - shipping_transaction'
                WHEN fft.transaction_type = 'VAT' AND fft.transaction_title ILIKE '%Processing Fee%' THEN 'VAT - Processing Fee'
                WHEN fft.transaction_type = 'VAT' AND fft.transaction_title ILIKE '%transaction credit%' THEN 'VAT - transaction credit'
                WHEN fft.transaction_type = 'VAT' AND fft.transaction_title ILIKE '%listing credit%' THEN 'VAT - listing credit'
                WHEN fft.transaction_type = 'VAT' AND fft.transaction_title ILIKE '%listing%' THEN 'VAT - listing'
                WHEN fft.transaction_type = 'VAT' AND fft.transaction_title ILIKE '%Etsy Plus subscription%' THEN 'VAT - Etsy Plus subscription'
                WHEN fft.transaction_type = 'VAT' THEN 'VAT - Other'
                ELSE NULL
            END AS fee_type
        FROM fact_financial_transactions fft
        WHERE fft.fees_and_taxes IS NOT NULL
          AND fft.order_id IN (SELECT DISTINCT order_id FROM fact_sales WHERE sku = :pid)
          AND (
              (fft.transaction_type = 'Fee' AND fft.transaction_title ILIKE ANY(ARRAY['%Transaction fee%', '%Processing fee%', '%Regulatory Operating fee%', '%Listing fee%']))
              OR fft.transaction_type = 'Marketing'
              OR (fft.transaction_type = 'VAT' AND fft.transaction_title ILIKE ANY(ARRAY[
                  '%auto-renew sold%', '%shipping_transaction%', '%Processing Fee%',
                  '%transaction credit%', '%listing credit%', '%listing%', '%Etsy Plus subscription%'
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
    
    -- Allocate Etsy fees to products based on sales ratio
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
    sql = """
    WITH 
    -- Calculate total sales per order (for allocation ratio)
    order_sales AS (
        SELECT 
            order_id,
            SUM(COALESCE(item_price, 0)) AS total_order_sales
        FROM fact_sales
        WHERE sku = :pid
        GROUP BY order_id
    ),
    
    -- Calculate sales per product per order
    product_order_sales AS (
        SELECT 
            fs.order_id,
            fs.sku AS product_id,
            SUM(COALESCE(fs.item_price, 0)) AS product_sales_in_order
        FROM fact_sales fs
        WHERE fs.sku = :pid
        GROUP BY fs.order_id, fs.sku
    ),
    
    -- Get refunds at order level
    order_refunds AS (
        SELECT 
            order_id,
            SUM(ABS(COALESCE(amount, 0))) AS refund_amount
        FROM fact_financial_transactions
        WHERE transaction_type = 'Refund'
          AND order_id IN (SELECT DISTINCT order_id FROM fact_sales WHERE sku = :pid)
        GROUP BY order_id
    ),
    
    -- Get Etsy fees at order level
    order_fees AS (
        SELECT 
            order_id,
            SUM(ABS(COALESCE(fees_and_taxes, 0))) AS fee_amount
        FROM fact_financial_transactions
        WHERE fees_and_taxes IS NOT NULL
          AND order_id IN (SELECT DISTINCT order_id FROM fact_sales WHERE sku = :pid)
          AND (
              (transaction_type = 'Fee' AND transaction_title ILIKE ANY(ARRAY['%Transaction fee%', '%Processing fee%', '%Regulatory Operating fee%', '%Listing fee%']))
              OR transaction_type = 'Marketing'
              OR (transaction_type = 'VAT' AND transaction_title ILIKE ANY(ARRAY[
                  '%auto-renew sold%', '%shipping_transaction%', '%Processing Fee%',
                  '%transaction credit%', '%listing credit%', '%listing%', '%Etsy Plus subscription%'
              ]))
          )
        GROUP BY order_id
    ),
    
    -- Get COGS for product in each order (using indexed parsed columns)
    product_cogs_by_order AS (
        SELECT 
            fs.order_id,
            SUM(COALESCE(fbt.debit_amount, 0)) AS cogs_amount
        FROM fact_sales fs
        JOIN fact_bank_transactions fbt ON fbt.parsed_product_id = fs.sku
        WHERE fs.sku = :pid
          AND fbt.pl_account_number IN ('6211','6221','6222','6223','6224','6225')
          AND fbt.debit_amount IS NOT NULL
        GROUP BY fs.order_id
    ),
    
    -- Calculate allocated costs and profits per order
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
        order_id::text AS order_id,
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

