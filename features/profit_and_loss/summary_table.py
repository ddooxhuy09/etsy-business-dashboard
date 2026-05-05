import pandas as pd
from core.query_utils.db_query import execute_query
from features.profit_and_loss.formula_config import get_default_profit_expense_items
from features.dim_pl_accounts.helpers import get_cogs_accounts, get_expense_accounts, sql_in_list


def get_profit_loss_summary_table(start_date: str = None, end_date: str = None, view_mode: str = 'month', selected_items: list = None, use_default_formula: bool = True):
    """
    Get Profit and Loss Summary Table data with monthly or yearly breakdown.

    Args:
        start_date: Start date filter (YYYY-MM-DD)
        end_date: End date filter (YYYY-MM-DD)
        view_mode: 'month' | 'year' | 'month_year'
        selected_items: List of column names to subtract from Revenue for Net Profit calculation.
                       If None và use_default_formula=True, sử dụng công thức mặc định từ config.
                       Example: ['refund_cost', 'cost_of_goods', 'total_etsy_fees', ...]
        use_default_formula: Nếu True và selected_items=None, sử dụng công thức mặc định.
                            Nếu False và selected_items=None, Net Profit = 0.
    """

    # Base date filter for all queries
    date_filter = ""
    if start_date:
        date_filter += f" AND dt.date_key >= '{start_date}'"
    if end_date:
        date_filter += f" AND dt.date_key <= '{end_date}'"

    # Select keys based on view_mode (alias fields to stable column names for merges)
    if view_mode == 'year':
        key_select = "dt.year as year"
        key_group = "dt.year"
        key_order = "year"
        merge_cols = ["year"]
    elif view_mode == 'month_year':
        # For month/year view: group by year and month
        key_select = "dt.year as year, dt.month_num as month, dt.month_name as month_name"
        key_group = "dt.year, dt.month_num, dt.month_name"
        key_order = "year, month"
        merge_cols = ["year", "month", "month_name"]
    else:
        # For month view: group by month only (aggregate across all years)
        key_select = "dt.month_num as month, dt.month_name as month_name"
        key_group = "dt.month_num, dt.month_name"
        key_order = "month"
        merge_cols = ["month", "month_name"]

    # Period scaffold: include any period that appears in EITHER Etsy financial transactions OR bank transactions.
    periods_sql = f"""
    SELECT DISTINCT {", ".join(merge_cols)}
    FROM (
        SELECT {key_select}
        FROM fact_statement fft
        JOIN dim_time dt ON fft.entry_date = dt.date_key
        WHERE 1=1 {date_filter}
        UNION
        SELECT {key_select}
        FROM fact_bank_transactions fbt
        JOIN dim_time dt ON fbt.transaction_date::date = dt.date_key
        WHERE 1=1 {date_filter}
    ) p
    ORDER BY {key_order}
    """

    periods = execute_query(periods_sql, None)
    if periods is None or periods.empty:
        return pd.DataFrame({"Line Item": []})

    monthly_pl_sql = f"""
    SELECT
        {key_select},
        -- Revenue from Sales
        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'Sale' THEN fft.amount
            ELSE 0
        END), 0) as revenue,

        -- Refund Cost
        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'Refund' THEN ABS(fft.amount)
            ELSE 0
        END), 0) as refund_cost,

        -- Transaction Fee
        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'Fee'
                AND (fft.title ILIKE '%Transaction fee%' OR fft.title ILIKE '%transaction fee%')
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as transaction_fee,

        -- Processing Fee
        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'Fee'
                AND (fft.title ILIKE '%Processing fee%' OR fft.title ILIKE '%processing fee%')
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as processing_fee,

        -- Regulatory Operating Fee
        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'Fee'
                AND fft.title ILIKE '%Regulatory Operating fee%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as regulatory_fee,

        -- Listing Fee
        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'Fee'
                AND (fft.title ILIKE '%Listing fee%' OR fft.title ILIKE '%listing fee%')
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as listing_fee,

        -- Marketing Fee
        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'Marketing'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as marketing_fee,

        -- VAT Fees breakdown
        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'VAT'
                AND fft.title ILIKE '%auto-renew sold%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_auto_renew_sold,

        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'VAT'
                AND fft.title ILIKE '%shipping_transaction%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_shipping_transaction,

        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'VAT'
                AND fft.title ILIKE '%Processing Fee%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_processing_fee,

        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'VAT'
                AND fft.title ILIKE '%transaction credit%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_transaction_credit,

        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'VAT'
                AND fft.title ILIKE '%listing credit%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_listing_credit,

        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'VAT'
                AND fft.title ILIKE '%listing%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_listing,

        COALESCE(SUM(CASE
            WHEN fft.entry_type = 'VAT'
                AND fft.title ILIKE '%Etsy Plus subscription%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_etsy_plus_subscription

    FROM fact_statement fft
    JOIN dim_time dt ON fft.entry_date = dt.date_key
    WHERE 1=1 {date_filter}
    GROUP BY {key_group}
    ORDER BY {key_order}
    """

    revenue_data = execute_query(monthly_pl_sql, None)
    if revenue_data is None:
        revenue_data = pd.DataFrame(columns=merge_cols)

    # Base table = periods; left-join revenue
    monthly_data = periods.merge(revenue_data, on=merge_cols, how="left")
    for col in [
        "revenue", "refund_cost", "transaction_fee", "processing_fee",
        "regulatory_fee", "listing_fee", "marketing_fee", "vat_auto_renew_sold",
        "vat_shipping_transaction", "vat_processing_fee", "vat_transaction_credit",
        "vat_listing_credit", "vat_listing", "vat_etsy_plus_subscription",
    ]:
        if col not in monthly_data.columns:
            monthly_data[col] = 0
    monthly_data = monthly_data.fillna(0)

    # Calculate derived fields
    monthly_data['total_vat_fees'] = (
        monthly_data['vat_auto_renew_sold'] + monthly_data['vat_shipping_transaction'] +
        monthly_data['vat_processing_fee'] + monthly_data['vat_transaction_credit'] +
        monthly_data['vat_listing_credit'] + monthly_data['vat_listing'] +
        monthly_data['vat_etsy_plus_subscription']
    )
    monthly_data['total_etsy_fees'] = (
        monthly_data['transaction_fee'] + monthly_data['processing_fee'] +
        monthly_data['regulatory_fee'] + monthly_data['listing_fee'] +
        monthly_data['marketing_fee'] + monthly_data['total_vat_fees']
    )

    # Cost of Goods from fact_bank_transactions
    _cogs_in = sql_in_list(get_cogs_accounts())
    _expense_in = sql_in_list(get_expense_accounts())
    cogs_sql = f"""
    SELECT
        {key_select},
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6211' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as material_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6221' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as concept_design_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6222' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as chart_hook_spin_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6223' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as spinning_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6224' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as photo_spin_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6225' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as pattern_translation_cost,
        COALESCE(SUM(ABS(fbt.debit_amount)), 0) as cost_of_goods
    FROM fact_bank_transactions fbt
    JOIN dim_time dt ON fbt.transaction_date::date = dt.date_key
    WHERE 1=1 {date_filter}
    AND fbt.pl_account_number IN ({_cogs_in})
    GROUP BY {key_group}
    ORDER BY {key_order}
    """

    additional_costs_sql = f"""
    SELECT
        {key_select},
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6273' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as general_production_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6411' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as staff_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6412' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as material_packaging_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6413' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as platform_tool_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6414' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as tool_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6421' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as management_staff_cost,
        COALESCE(SUM(CASE WHEN fbt.pl_account_number = '6428' THEN ABS(fbt.debit_amount) ELSE 0 END), 0) as marketing_staff_cost
    FROM fact_bank_transactions fbt
    JOIN dim_time dt ON fbt.transaction_date::date = dt.date_key
    WHERE 1=1 {date_filter}
    AND fbt.pl_account_number IN ({_expense_in})
    GROUP BY {key_group}
    ORDER BY {key_order}
    """

    cogs_data = execute_query(cogs_sql, None)
    additional_costs_data = execute_query(additional_costs_sql, None)

    if cogs_data is not None and not cogs_data.empty:
        monthly_data = monthly_data.merge(cogs_data, on=merge_cols, how='left')
        for c in ['cost_of_goods', 'material_cost', 'concept_design_cost', 'chart_hook_spin_cost',
                  'spinning_cost', 'photo_spin_cost', 'pattern_translation_cost']:
            monthly_data[c] = monthly_data[c].fillna(0)
    else:
        for c in ['cost_of_goods', 'material_cost', 'concept_design_cost', 'chart_hook_spin_cost',
                  'spinning_cost', 'photo_spin_cost', 'pattern_translation_cost']:
            monthly_data[c] = 0

    if additional_costs_data is not None and not additional_costs_data.empty:
        monthly_data = monthly_data.merge(additional_costs_data, on=merge_cols, how='left')
        for c in ['general_production_cost', 'staff_cost', 'material_packaging_cost',
                  'platform_tool_cost', 'tool_cost', 'management_staff_cost', 'marketing_staff_cost']:
            monthly_data[c] = monthly_data[c].fillna(0)
    else:
        for c in ['general_production_cost', 'staff_cost', 'material_packaging_cost',
                  'platform_tool_cost', 'tool_cost', 'management_staff_cost', 'marketing_staff_cost']:
            monthly_data[c] = 0

    # Calculate Net Profit
    expense_items_to_use = selected_items
    if expense_items_to_use is None and use_default_formula:
        expense_items_to_use = get_default_profit_expense_items()

    if expense_items_to_use and len(expense_items_to_use) > 0:
        net_profit = monthly_data['revenue'].copy()
        for item in expense_items_to_use:
            if item in monthly_data.columns:
                net_profit = net_profit - monthly_data[item]
            else:
                import logging
                logging.warning(f"Column '{item}' not found in monthly_data. Available columns: {list(monthly_data.columns)}")
        monthly_data['net_profit'] = net_profit
    else:
        monthly_data['net_profit'] = 0

    # Format key for display
    if view_mode == 'year':
        monthly_data['col_key'] = monthly_data['year'].astype(str)
    elif view_mode == 'month_year':
        monthly_data['col_key'] = monthly_data['year'].astype(str) + ' ' + monthly_data['month_name']
    else:
        monthly_data['col_key'] = monthly_data['month_name']

    ordered_items_with_headers = [
        ("Revenue (Sales)", None),
        ("Revenue", 'revenue'),
        ("", None),
        ("Refund Cost", 'refund_cost'),
        ("COGS (Cost of Goods Sold)", None),
        ("Cost of Goods", 'cost_of_goods'),
        ('  - Chi phí len (Chi phí nguyên liệu, vật liệu trực tiếp)', 'material_cost'),
        ('  - Chi phí làm concept design (Chi phí nhân công trực tiếp)', 'concept_design_cost'),
        ('  - Chi phí làm chart + móc + quay (optional) (Chi phí nhân công trực tiếp)', 'chart_hook_spin_cost'),
        ('  - Chi phí quay (Chi phí nhân công trực tiếp)', 'spinning_cost'),
        ('  - Chi phí chụp + quay (Chi phí nhân công trực tiếp)', 'photo_spin_cost'),
        ('  - Chi phí viết pattern - dịch chart (Chi phí nhân công trực tiếp)', 'pattern_translation_cost'),
        ("Operating Expenses", None),
        ("Etsy Fees", 'total_etsy_fees'),
        ('  - Transaction Fee', 'transaction_fee'),
        ('  - Processing Fee', 'processing_fee'),
        ('  - Regulatory Operating Fee', 'regulatory_fee'),
        ('  - Listing Fee', 'listing_fee'),
        ('  - Marketing', 'marketing_fee'),
        ('  - VAT', 'total_vat_fees'),
        ('    --- auto-renew sold', 'vat_auto_renew_sold'),
        ('    --- shipping_transaction', 'vat_shipping_transaction'),
        ('    --- Processing Fee', 'vat_processing_fee'),
        ('    --- transaction credit', 'vat_transaction_credit'),
        ('    --- listing credit', 'vat_listing_credit'),
        ('    --- listing', 'vat_listing'),
        ('    --- Etsy Plus subscription', 'vat_etsy_plus_subscription'),
        ("Chi phí sản xuất chung", 'general_production_cost'),
        ("Chi phí nhân viên (Chi phí bán hàng)", 'staff_cost'),
        ("Chi phí nguyên vật liệu, bao bì (Chi phí bán hàng)", 'material_packaging_cost'),
        ("Chi phí dụng cụ tool sàn (Chi phí bán hàng)", 'platform_tool_cost'),
        ("Chi phí dụng cụ tool (Chi phí bán hàng)", 'tool_cost'),
        ("Chi phí nhân viên quản lý (Chi phí quản lý doanh nghiệp)", 'management_staff_cost'),
        ("Chi phí nhân viên marketing - đăng và quản lí kênh (Chi phí quản lý doanh nghiệp)", 'marketing_staff_cost'),
        ("Net Income (Profit)", None),
        ("Profit", 'net_profit')
    ]

    result_data = []
    for line_item, column_name in ordered_items_with_headers:
        row_data = {'Line Item': line_item}
        for _, period_row in monthly_data.iterrows():
            key_val = period_row['col_key']
            if column_name is None:
                row_data[key_val] = 0
            else:
                row_data[key_val] = period_row[column_name]
        if column_name is None:
            row_data['Full Year'] = 0
        else:
            row_data['Full Year'] = monthly_data[column_name].sum()
        result_data.append(row_data)

    result_df = pd.DataFrame(result_data)

    numeric_columns = [col for col in result_df.columns if col != 'Line Item']
    header_rows = set(['Revenue (Sales)', '', 'COGS (Cost of Goods Sold)', 'Operating Expenses', 'Net Income (Profit)'])
    is_header = result_df['Line Item'].isin(header_rows)

    result_df.loc[is_header, numeric_columns] = pd.NA
    result_df.loc[is_header, 'Full Year'] = result_df.loc[is_header, 'Full Year']

    data_mask = ~is_header
    result_df.loc[data_mask, numeric_columns] = result_df.loc[data_mask, numeric_columns].fillna(0)
    result_df.loc[data_mask, numeric_columns] = result_df.loc[data_mask, numeric_columns].round(2)

    return result_df
