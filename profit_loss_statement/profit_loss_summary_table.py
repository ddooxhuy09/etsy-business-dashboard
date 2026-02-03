import pandas as pd
from utils.db_query import execute_query
from profit_loss_statement.profit_formula_config import get_default_profit_expense_items


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
        date_filter += f" AND dt.full_date >= '{start_date}'"
    if end_date:
        date_filter += f" AND dt.full_date <= '{end_date}'"

    # Select keys based on view_mode
    if view_mode == 'year':
        key_select = "dt.year"
        key_group_order = "GROUP BY dt.year ORDER BY dt.year"
    elif view_mode == 'month_year':
        # For month/year view: group by year and month
        key_select = "dt.year, dt.month, dt.month_name"
        key_group_order = "GROUP BY dt.year, dt.month, dt.month_name ORDER BY dt.year, dt.month"
    else:
        # For month view: group by month only (aggregate across all years)
        key_select = "dt.month, dt.month_name"
        key_group_order = "GROUP BY dt.month, dt.month_name ORDER BY dt.month"

    # Get data with all components
    monthly_pl_sql = f"""
    SELECT
        {key_select},
        -- Revenue from Sales
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'Sale' THEN fft.amount
            ELSE 0
        END), 0) as revenue,

        -- Refund Cost
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'Refund' THEN ABS(fft.amount)
            ELSE 0
        END), 0) as refund_cost,

        -- Transaction Fee
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'Fee'
                AND (fft.transaction_title ILIKE '%Transaction fee%' OR fft.transaction_title ILIKE '%transaction fee%')
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as transaction_fee,

        -- Processing Fee
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'Fee'
                AND (fft.transaction_title ILIKE '%Processing fee%' OR fft.transaction_title ILIKE '%processing fee%')
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as processing_fee,

        -- Regulatory Operating Fee
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'Fee'
                AND fft.transaction_title ILIKE '%Regulatory Operating fee%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as regulatory_fee,

        -- Listing Fee
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'Fee'
                AND (fft.transaction_title ILIKE '%Listing fee%' OR fft.transaction_title ILIKE '%listing fee%')
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as listing_fee,

        -- Marketing Fee
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'Marketing'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as marketing_fee,

        -- VAT Fees breakdown
        -- auto-renew sold
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'VAT'
                AND fft.transaction_title ILIKE '%auto-renew sold%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_auto_renew_sold,

        -- shipping_transaction
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'VAT'
                AND fft.transaction_title ILIKE '%shipping_transaction%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_shipping_transaction,

        -- Processing Fee
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'VAT'
                AND fft.transaction_title ILIKE '%Processing Fee%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_processing_fee,

        -- transaction credit
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'VAT'
                AND fft.transaction_title ILIKE '%transaction credit%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_transaction_credit,

        -- listing credit
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'VAT'
                AND fft.transaction_title ILIKE '%listing credit%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_listing_credit,

        -- listing
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'VAT'
                AND fft.transaction_title ILIKE '%listing%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_listing,

        -- Etsy Plus subscription
        COALESCE(SUM(CASE
            WHEN fft.transaction_type = 'VAT'
                AND fft.transaction_title ILIKE '%Etsy Plus subscription%'
            THEN ABS(fft.fees_and_taxes)
            ELSE 0
        END), 0) as vat_etsy_plus_subscription

    FROM fact_financial_transactions fft
    JOIN dim_time dt ON fft.transaction_date_key = dt.time_key
    WHERE 1=1 {date_filter}
    {key_group_order}
    """

    monthly_data = execute_query(monthly_pl_sql, None)

    if monthly_data is None or monthly_data.empty:
        # Return empty structure if no data
        return pd.DataFrame({
            'Line Item': [],
        })

    # Calculate derived fields
    monthly_data['total_vat_fees'] = (monthly_data['vat_auto_renew_sold'] +
                                    monthly_data['vat_shipping_transaction'] +
                                    monthly_data['vat_processing_fee'] +
                                    monthly_data['vat_transaction_credit'] +
                                    monthly_data['vat_listing_credit'] +
                                    monthly_data['vat_listing'] +
                                    monthly_data['vat_etsy_plus_subscription'])

    monthly_data['total_etsy_fees'] = (monthly_data['transaction_fee'] +
                                     monthly_data['processing_fee'] +
                                     monthly_data['regulatory_fee'] +
                                     monthly_data['listing_fee'] +
                                     monthly_data['marketing_fee'] +
                                     monthly_data['total_vat_fees'])

    # Calculate Cost of Goods from fact_bank_transactions with specific PL account numbers
    cogs_sql = f"""
    SELECT
        {key_select},
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6211' THEN fbt.debit_amount
            ELSE 0
        END), 0) as material_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6221' THEN fbt.debit_amount
            ELSE 0
        END), 0) as concept_design_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6222' THEN fbt.debit_amount
            ELSE 0
        END), 0) as chart_hook_spin_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6223' THEN fbt.debit_amount
            ELSE 0
        END), 0) as spinning_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6224' THEN fbt.debit_amount
            ELSE 0
        END), 0) as photo_spin_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6225' THEN fbt.debit_amount
            ELSE 0
        END), 0) as pattern_translation_cost,
        COALESCE(SUM(fbt.debit_amount), 0) as cost_of_goods
    FROM fact_bank_transactions fbt
    JOIN dim_time dt ON fbt.transaction_date_key = dt.time_key
    WHERE 1=1 {date_filter}
    AND fbt.pl_account_number IN ('6211', '6221', '6222', '6223', '6224', '6225')
    {key_group_order}
    """

    additional_costs_sql = f"""
    SELECT
        {key_select},
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6273' THEN fbt.debit_amount
            ELSE 0
        END), 0) as general_production_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6411' THEN fbt.debit_amount
            ELSE 0
        END), 0) as staff_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6412' THEN fbt.debit_amount
            ELSE 0
        END), 0) as material_packaging_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6413' THEN fbt.debit_amount
            ELSE 0
        END), 0) as platform_tool_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6414' THEN fbt.debit_amount
            ELSE 0
        END), 0) as tool_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6421' THEN fbt.debit_amount
            ELSE 0
        END), 0) as management_staff_cost,
        COALESCE(SUM(CASE
            WHEN fbt.pl_account_number = '6428' THEN fbt.debit_amount
            ELSE 0
        END), 0) as marketing_staff_cost
    FROM fact_bank_transactions fbt
    JOIN dim_time dt ON fbt.transaction_date_key = dt.time_key
    WHERE 1=1 {date_filter}
    AND fbt.pl_account_number IN ('6273', '6411', '6412', '6413', '6414', '6421', '6428')
    {key_group_order}
    """

    cogs_data = execute_query(cogs_sql, None)
    additional_costs_data = execute_query(additional_costs_sql, None)

    # Merge cost of goods data with main data
    if cogs_data is not None and not cogs_data.empty:
        if view_mode == 'year':
            merge_cols = ['year']
        elif view_mode == 'month_year':
            merge_cols = ['year', 'month', 'month_name']
        else:
            merge_cols = ['month', 'month_name']

        monthly_data = monthly_data.merge(cogs_data, on=merge_cols, how='left')
        monthly_data['cost_of_goods'] = monthly_data['cost_of_goods'].fillna(0)
        monthly_data['material_cost'] = monthly_data['material_cost'].fillna(0)
        monthly_data['concept_design_cost'] = monthly_data['concept_design_cost'].fillna(0)
        monthly_data['chart_hook_spin_cost'] = monthly_data['chart_hook_spin_cost'].fillna(0)
        monthly_data['spinning_cost'] = monthly_data['spinning_cost'].fillna(0)
        monthly_data['photo_spin_cost'] = monthly_data['photo_spin_cost'].fillna(0)
        monthly_data['pattern_translation_cost'] = monthly_data['pattern_translation_cost'].fillna(0)
    else:
        monthly_data['cost_of_goods'] = 0
        monthly_data['material_cost'] = 0
        monthly_data['concept_design_cost'] = 0
        monthly_data['chart_hook_spin_cost'] = 0
        monthly_data['spinning_cost'] = 0
        monthly_data['photo_spin_cost'] = 0
        monthly_data['pattern_translation_cost'] = 0

    # Merge additional costs data with main data
    if additional_costs_data is not None and not additional_costs_data.empty:
        if view_mode == 'year':
            merge_cols = ['year']
        elif view_mode == 'month_year':
            merge_cols = ['year', 'month', 'month_name']
        else:
            merge_cols = ['month', 'month_name']

        monthly_data = monthly_data.merge(additional_costs_data, on=merge_cols, how='left')
        monthly_data['general_production_cost'] = monthly_data['general_production_cost'].fillna(0)
        monthly_data['staff_cost'] = monthly_data['staff_cost'].fillna(0)
        monthly_data['material_packaging_cost'] = monthly_data['material_packaging_cost'].fillna(0)
        monthly_data['platform_tool_cost'] = monthly_data['platform_tool_cost'].fillna(0)
        monthly_data['tool_cost'] = monthly_data['tool_cost'].fillna(0)
        monthly_data['management_staff_cost'] = monthly_data['management_staff_cost'].fillna(0)
        monthly_data['marketing_staff_cost'] = monthly_data['marketing_staff_cost'].fillna(0)
    else:
        monthly_data['general_production_cost'] = 0
        monthly_data['staff_cost'] = 0
        monthly_data['material_packaging_cost'] = 0
        monthly_data['platform_tool_cost'] = 0
        monthly_data['tool_cost'] = 0
        monthly_data['management_staff_cost'] = 0
        monthly_data['marketing_staff_cost'] = 0

    # Calculate Net Profit = Revenue - (tổng các cột được chọn)
    # Nếu selected_items được cung cấp, tính Net Profit linh hoạt dựa trên các item được chọn
    # Nếu không có selected_items và use_default_formula=True, sử dụng công thức mặc định
    
    expense_items_to_use = selected_items
    if expense_items_to_use is None and use_default_formula:
        expense_items_to_use = get_default_profit_expense_items()
    
    if expense_items_to_use and len(expense_items_to_use) > 0:
        # Tính Net Profit = Revenue - sum(các cột được chọn)
        net_profit = monthly_data['revenue'].copy()
        for item in expense_items_to_use:
            if item in monthly_data.columns:
                net_profit = net_profit - monthly_data[item]
            else:
                # Log warning nếu column không tồn tại
                import logging
                logging.warning(f"Column '{item}' not found in monthly_data. Available columns: {list(monthly_data.columns)}")
        monthly_data['net_profit'] = net_profit
    else:
        # Nếu không có expense items, để Net Profit = 0
        monthly_data['net_profit'] = 0

    # Format key for display
    if view_mode == 'year':
        monthly_data['col_key'] = monthly_data['year'].astype(str)
    elif view_mode == 'month_year':
        monthly_data['col_key'] = monthly_data['year'].astype(str) + ' ' + monthly_data['month_name']
    else:
        monthly_data['col_key'] = monthly_data['month_name']

    # Prepare data for transposition with category headers
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
    header_rows = set([
        'Revenue (Sales)',
        '',
        'COGS (Cost of Goods Sold)',
        'Operating Expenses',
        'Net Income (Profit)'
    ])
    is_header = result_df['Line Item'].isin(header_rows)

    result_df.loc[is_header, numeric_columns] = pd.NA
    result_df.loc[is_header, 'Full Year'] = result_df.loc[is_header, 'Full Year']

    data_mask = ~is_header
    result_df.loc[data_mask, numeric_columns] = result_df.loc[data_mask, numeric_columns].fillna(0)
    result_df.loc[data_mask, numeric_columns] = result_df.loc[data_mask, numeric_columns].round(2)

    return result_df
