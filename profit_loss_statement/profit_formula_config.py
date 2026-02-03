"""
Profit Formula Configuration

Cấu hình công thức tính Profit linh hoạt.
Profit = Revenue - sum(PROFIT_EXPENSE_ITEMS)

Bạn có thể thay đổi danh sách PROFIT_EXPENSE_ITEMS để điều chỉnh công thức tính profit.
"""

# Danh sách các column names được trừ khỏi Revenue để tính Net Profit
# Thứ tự: Refund Cost, Cost of Goods, Etsy Fees, các chi phí khác
PROFIT_EXPENSE_ITEMS = [
    # Refund Cost
    'refund_cost',
    
    # Cost of Goods (COGS) - Chi phí giá vốn hàng bán
    'cost_of_goods',
    
    # Etsy Fees - Phí sàn Etsy
    'total_etsy_fees',
    
    # Chi phí sản xuất chung (6273)
    'general_production_cost',
    
    # Chi phí nhân viên - Chi phí bán hàng (6411)
    'staff_cost',
    
    # Chi phí nguyên vật liệu, bao bì - Chi phí bán hàng (6412)
    'material_packaging_cost',
    
    # Chi phí dụng cụ tool sàn - Chi phí bán hàng (6413)
    'platform_tool_cost',
    
    # Chi phí dụng cụ tool - Chi phí bán hàng (6414)
    'tool_cost',
    
    # Chi phí nhân viên quản lý - Chi phí quản lý doanh nghiệp (6421)
    'management_staff_cost',
    
    # Chi phí nhân viên marketing - đăng và quản lí kênh - Chi phí quản lý doanh nghiệp (6428)
    'marketing_staff_cost',
]

# Mapping từ column name sang display name (để hiển thị trong UI)
EXPENSE_ITEM_LABELS = {
    'refund_cost': 'Refund Cost',
    'cost_of_goods': 'Cost of Goods',
    'total_etsy_fees': 'Etsy Fees',
    'general_production_cost': 'Chi phí sản xuất chung',
    'staff_cost': 'Chi phí nhân viên (Chi phí bán hàng)',
    'material_packaging_cost': 'Chi phí nguyên vật liệu, bao bì (Chi phí bán hàng)',
    'platform_tool_cost': 'Chi phí dụng cụ tool sàn (Chi phí bán hàng)',
    'tool_cost': 'Chi phí dụng cụ tool (Chi phí bán hàng)',
    'management_staff_cost': 'Chi phí nhân viên quản lý (Chi phí quản lý doanh nghiệp)',
    'marketing_staff_cost': 'Chi phí nhân viên marketing - đăng và quản lí kênh (Chi phí quản lý doanh nghiệp)',
}

# Mapping từ PL account number sang column name (để tham khảo)
PL_ACCOUNT_MAPPING = {
    '6211': 'material_cost',                 # Chi phí len
    '6221': 'concept_design_cost',           # Chi phí làm concept design
    '6222': 'chart_hook_spin_cost',          # Chi phí làm chart + móc + quay
    '6223': 'spinning_cost',                 # Chi phí quay
    '6224': 'photo_spin_cost',               # Chi phí chụp + quay
    '6225': 'pattern_translation_cost',      # Chi phí viết pattern - dịch chart
    '6273': 'general_production_cost',       # Chi phí sản xuất chung
    '6411': 'staff_cost',                    # Chi phí nhân viên (bán hàng)
    '6412': 'material_packaging_cost',       # Chi phí nguyên vật liệu, bao bì
    '6413': 'platform_tool_cost',            # Chi phí dụng cụ tool sàn
    '6414': 'tool_cost',                     # Chi phí dụng cụ tool
    '6421': 'management_staff_cost',         # Chi phí nhân viên quản lý
    '6428': 'marketing_staff_cost',          # Chi phí nhân viên marketing
}


def get_default_profit_expense_items():
    """Trả về danh sách các expense items mặc định để tính profit."""
    return PROFIT_EXPENSE_ITEMS.copy()


def get_profit_formula_display():
    """Trả về công thức profit dạng text để hiển thị."""
    labels = [EXPENSE_ITEM_LABELS.get(item, item) for item in PROFIT_EXPENSE_ITEMS]
    return f"Profit = Revenue − ({' + '.join(labels)})"


def calculate_profit(revenue: float, expense_data: dict, expense_items: list = None) -> float:
    """
    Tính profit dựa trên revenue và các expense items.
    
    Args:
        revenue: Doanh thu
        expense_data: Dict chứa các giá trị expense (key là column name)
        expense_items: Danh sách các expense items cần trừ. Nếu None, dùng mặc định.
    
    Returns:
        Net profit = Revenue - sum(expense_items)
    
    Example:
        >>> expense_data = {
        ...     'refund_cost': 100,
        ...     'cost_of_goods': 200,
        ...     'total_etsy_fees': 50,
        ...     'general_production_cost': 30,
        ... }
        >>> calculate_profit(1000, expense_data)
        620.0
    """
    if expense_items is None:
        expense_items = PROFIT_EXPENSE_ITEMS
    
    total_expenses = sum(expense_data.get(item, 0) for item in expense_items)
    return revenue - total_expenses
