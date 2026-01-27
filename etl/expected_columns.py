"""
Định nghĩa cột raw (header CSV) mong đợi cho từng loại file input và hàm kiểm tra.
Dùng khi upload (đọc header) và trước khi chạy ETL.
"""

from typing import List

# ─── Danh sách cột raw theo từng file (để báo lỗi và tài liệu) ─────────────────
#
# 1) statement (Bảng kê Etsy) — etsy_statement_*.csv
RAW_COLUMNS_STATEMENT = [
    "Date",
    "Type",
    "Title",
    "Info",
    "Currency",
    "Amount",
    "Fees & Taxes",
    "Net",
    "Tax Details",
]

# 2) direct_checkout (Thanh toán trực tiếp) — EtsyDirectCheckoutPayments*.csv
RAW_COLUMNS_DIRECT_CHECKOUT = [
    "Payment ID",
    "Buyer Username",
    "Buyer Name",
    "Order ID",
    "Gross Amount",
    "Fees",
    "Net Amount",
    "Posted Gross",
    "Posted Fees",
    "Posted Net",
    "Adjusted Gross",
    "Adjusted Fees",
    "Adjusted Net",
    "Currency",
    "Listing Amount",
    "Listing Currency",
    "Exchange Rate",
    "VAT Amount",
    "Gift Card Applied?",
    "Status",
    "Funds Available",
    "Order Date",
    "Buyer",
    "Order Type",
    "Payment Type",
    "Refund Amount",
]

# 3) listing (Danh sách sản phẩm) — EtsyListingsDownload.csv
RAW_COLUMNS_LISTING = [
    "TITLE",
    "DESCRIPTION",
    "PRICE",
    "CURRENCY_CODE",
    "QUANTITY",
    "TAGS",
    "MATERIALS",
    "IMAGE1",
    "IMAGE2",
    "IMAGE3",
    "IMAGE4",
    "IMAGE5",
    "IMAGE6",
    "IMAGE7",
    "IMAGE8",
    "IMAGE9",
    "IMAGE10",
    "VARIATION 1 TYPE",
    "VARIATION 1 NAME",
    "VARIATION 1 VALUES",
    "VARIATION 2 TYPE",
    "VARIATION 2 NAME",
    "VARIATION 2 VALUES",
    "SKU",
]

# 4) sold_order_items (Chi tiết đơn hàng) — EtsySoldOrderItems*.csv
RAW_COLUMNS_SOLD_ORDER_ITEMS = [
    "Sale Date",
    "Item Name",
    "Buyer",
    "Quantity",
    "Price",
    "Coupon Code",
    "Coupon Details",
    "Discount Amount",
    "Shipping Discount",
    "Order Shipping",
    "Order Sales Tax",
    "Item Total",
    "Currency",
    "Transaction ID",
    "Listing ID",
    "Date Paid",
    "Date Shipped",
    "Ship Name",
    "Ship Address1",
    "Ship Address2",
    "Ship City",
    "Ship State",
    "Ship Zipcode",
    "Ship Country",
    "Order ID",
    "Variations",
    "Order Type",
    "Listings Type",
    "Payment Type",
    "InPerson Discount",
    "InPerson Location",
    "VAT Paid by Buyer",
    "SKU",
]

# 5) sold_orders (Đơn hàng đã bán) — EtsySoldOrders*.csv
RAW_COLUMNS_SOLD_ORDERS = [
    "Sale Date",
    "Order ID",
    "Buyer User ID",
    "Full Name",
    "First Name",
    "Last Name",
    "Number of Items",
    "Payment Method",
    "Date Shipped",
    "Street 1",
    "Street 2",
    "Ship City",
    "Ship State",
    "Ship Zipcode",
    "Ship Country",
    "Currency",
    "Order Value",
    "Coupon Code",
    "Coupon Details",
    "Discount Amount",
    "Shipping Discount",
    "Shipping",
    "Sales Tax",
    "Order Total",
    "Status",
    "Card Processing Fees",
    "Order Net",
    "Adjusted Order Total",
    "Adjusted Card Processing Fees",
    "Adjusted Net Order Amount",
    "Buyer",
    "Order Type",
    "Payment Type",
    "InPerson Discount",
    "InPerson Location",
    "SKU",
]

# 6) deposits (Tiền gửi) — EtsyDeposits*.csv
RAW_COLUMNS_DEPOSITS = [
    "Date",
    "Amount",
    "Currency",
    "Status",
    "Bank Account Ending Digits",
]

# 7) bank_transactions (Giao dịch ngân hàng) — fact_bank_transactions.csv
# Tên cột có thể tiếng Việt hoặc có phần tiếng Anh trong ngoặc.
RAW_COLUMNS_BANK_TRANSACTIONS = [
    "Ngày GD (Transaction Date)",
    "Mã giao dịch (Reference No.)",
    "Số tài khoản truy vấn (Account Number)",
    "Tên tài khoản truy vấn (Account Name)",
    "Ngày mở tài khoản (Opening Date)",
    "Phát sinh có (Credit Amount)",
    "Phát sinh nợ (Debit Amount)",
    "Số dư (Balance)",
    "Diễn giải (Description)",
]

# 8) product_catalog (Danh mục sản phẩm) — product_catalog.csv
RAW_COLUMNS_PRODUCT_CATALOG = [
    "Product line ID",
    "Product line",
    "Product ID",
    "Product",
    "Variant ID",
    "Variants",
]

# Map key → danh sách cột (chỉ để tham khảo / tài liệu)
RAW_COLUMNS_BY_KEY = {
    "statement": RAW_COLUMNS_STATEMENT,
    "direct_checkout": RAW_COLUMNS_DIRECT_CHECKOUT,
    "listing": RAW_COLUMNS_LISTING,
    "sold_order_items": RAW_COLUMNS_SOLD_ORDER_ITEMS,
    "sold_orders": RAW_COLUMNS_SOLD_ORDERS,
    "deposits": RAW_COLUMNS_DEPOSITS,
    "bank_transactions": RAW_COLUMNS_BANK_TRANSACTIONS,
    "product_catalog": RAW_COLUMNS_PRODUCT_CATALOG,
}


# ─── Quy tắc validation: required, required_any, required_contains ─────────────

def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _columns_set(columns: List[str]) -> set:
    return {_norm(c) for c in columns}


def validate_columns(key: str, columns: List[str]) -> List[str]:
    """
    Kiểm tra các cột raw (header CSV) có đủ theo từng loại file hay không.
    Trả về danh sách chuỗi lỗi (rỗng nếu hợp lệ).
    """
    errors: List[str] = []
    col_set = _columns_set(columns)

    if key == "statement":
        required = ["Date", "Type", "Currency"]
        for r in required:
            if _norm(r) not in col_set:
                errors.append(f"Thiếu cột bắt buộc: {r}")
        any_of = ["Amount", "Fees & Taxes", "Net"]
        if not any(_norm(x) in col_set for x in any_of):
            errors.append(f"Thiếu ít nhất một trong: {', '.join(any_of)}")

    elif key == "direct_checkout":
        required = ["Order Date", "Currency"]
        for r in required:
            if _norm(r) not in col_set:
                errors.append(f"Thiếu cột bắt buộc: {r}")
        any_of = ["Gross Amount", "Net Amount", "Posted Gross", "Posted Net"]
        if not any(_norm(x) in col_set for x in any_of):
            errors.append(f"Thiếu ít nhất một trong: {', '.join(any_of)}")

    elif key == "listing":
        if "title" not in col_set:
            errors.append("Thiếu cột bắt buộc: TITLE")

    elif key == "sold_order_items":
        required = ["Order ID", "Listing ID", "Sale Date"]
        for r in required:
            if _norm(r) not in col_set:
                errors.append(f"Thiếu cột bắt buộc: {r}")
        any_of = ["Price", "Item Total"]
        if not any(_norm(x) in col_set for x in any_of):
            errors.append(f"Thiếu ít nhất một trong: {', '.join(any_of)}")

    elif key == "sold_orders":
        required = ["Order ID", "Sale Date"]
        for r in required:
            if _norm(r) not in col_set:
                errors.append(f"Thiếu cột bắt buộc: {r}")
        any_of = ["Order Value", "Order Total"]
        if not any(_norm(x) in col_set for x in any_of):
            errors.append(f"Thiếu ít nhất một trong: {', '.join(any_of)}")

    elif key == "deposits":
        required = ["Date", "Amount", "Currency"]
        for r in required:
            if _norm(r) not in col_set:
                errors.append(f"Thiếu cột bắt buộc: {r}")

    elif key == "bank_transactions":
        has_desc = any("description" in _norm(c) or "diễn giải" in _norm(c) for c in columns)
        if not has_desc:
            errors.append("Thiếu cột chứa 'Description' hoặc 'Diễn giải' (cần cho xử lý giao dịch)")

    elif key == "product_catalog":
        required = [
            "Product line ID", "Product line", "Product ID", "Product",
            "Variant ID", "Variants",
        ]
        for r in required:
            if _norm(r) not in col_set:
                errors.append(f"Thiếu cột bắt buộc: {r}")

    else:
        # Key không có trong schema → bỏ qua (không báo lỗi)
        pass

    return errors


def get_raw_columns_list(key: str) -> List[str]:
    """Trả về danh sách tên cột raw tham khảo cho key. Dùng để hiển thị tài liệu."""
    return list(RAW_COLUMNS_BY_KEY.get(key, []))
