/**
 * Giải thích công thức / nguồn dữ liệu cho từng cột của các bảng.
 * Profit & Loss và Product Cost.
 */
import React from 'react';

// Annotation cho cột Period (tháng, năm, Full Year) - dùng fallback khi không có annotation riêng
const PL_PERIOD_ANNOTATION = (
  <div style={{ fontSize: 13, lineHeight: 1.7 }}>
    <strong>Giá trị cho kỳ này.</strong>
    <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
      <li>Mỗi dòng (Line Item) có công thức tính khác nhau</li>
      <li><strong>Full Year</strong>: Tổng các tháng trong phạm vi lọc</li>
    </ul>
  </div>
);

export const PROFIT_LOSS_COLUMN_ANNOTATIONS = {
  'Line Item': (
    <div style={{ fontSize: 13, lineHeight: 1.7 }}>
      <strong>Các khoản mục trong báo cáo P&amp;L:</strong>
      <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
        <li><strong>Revenue</strong>: fact_financial_transactions (Type=Sale), cột Amount</li>
        <li><strong>Refund Cost</strong>: fact_financial_transactions (Type=Refund)</li>
        <li><strong>COGS</strong>: fact_bank_transactions (PL 6211–6225) — nguyên liệu, nhân công trực tiếp</li>
        <li><strong>Etsy Fees</strong>: Transaction, Processing, Regulatory, Listing, Marketing, VAT (từ statement)</li>
        <li><strong>Operating Expenses</strong>: Chi phí sản xuất chung, bán hàng, quản lý (PL 6273, 6411–6414, 6421, 6428)</li>
        <li><strong>Profit</strong> = Revenue − tổng các chi phí được chọn</li>
      </ul>
    </div>
  ),
  __PERIOD__: PL_PERIOD_ANNOTATION,
  'Full Year': (
    <div style={{ fontSize: 13, lineHeight: 1.7 }}>
      <strong>Tổng cho cả năm</strong> (trong phạm vi ngày lọc)
      <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
        <li>SUM các giá trị theo tháng của từng Line Item</li>
      </ul>
    </div>
  ),
};

export const PRODUCT_COST_COLUMN_ANNOTATIONS = {
  'Product Line': {
    title: 'Product Line',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Product Line lấy từ product_catalog.csv (cột Product line ID)</li>
        </ul>
      </div>
    ),
  },
  'Product Name': {
    title: 'Product Name',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Tên sản phẩm từ product_catalog.csv (cột Product)</li>
        </ul>
      </div>
    ),
  },
  'Product ID': {
    title: 'Product ID',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Product ID product_catalog.csv (cột Product ID)</li>
        </ul>
      </div>
    ),
  },
  'Sales': {
    title: 'Sales',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Cộng item_price trong fact_sales (từ EtsySoldOrderItems)</li>
          <li>Mapping product_id và SKU</li>
        </ul>
      </div>
    ),
  },
  'Refund': {
    title: 'Refund',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Lấy từ etsy_statement (giao dịch Type = Refund)</li>
          <li>Refund ghi theo order, không theo từng sản phẩm nên phải chia cho từng sản phẩm theo tỷ lệ doanh thu trong order</li>
          <li>Refund sản phẩm = (Tổng refund order) × (Doanh thu sản phẩm trong order / Tổng doanh thu order)</li>
        </ul>
      </div>
    ),
  },
  'Units': {
    title: 'Units',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Đếm số lần bán mỗi sản phẩm trong fact_sales</li>
          <li>Mỗi dòng trong EtsySoldOrderItems = 1 đơn vị</li>
        </ul>
      </div>
    ),
  },
  'COGS': {
    title: 'COGS',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Dùng cột Debit Amount có các PL number là 6211, 6221, 6222, 6223, 6224, 6225</li>
          <li>Tách variant_id, product_id từ cột Description</li>
          <li>Cộng theo product–variant</li>
        </ul>
      </div>
    ),
  },
  'Etsy Fee': {
    title: 'Etsy Fee',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Lấy theo order từ etsy_statement (cột Fees &amp; Taxes)</li>
          <li>Bao gồm: Fee (Transaction, Processing, Regulatory, Listing), Marketing, VAT</li>
          <li>Phân bổ theo tỷ lệ doanh thu: Phí sản phẩm = (Tổng phí order) × (Doanh thu sản phẩm / Tổng doanh thu order)</li>
          <li>Doanh thu sản phẩm = tổng theo sku ở trong order </li>
          <li>Cộng theo product_id (product_id trong product catalog = sku)</li>
        </ul>
      </div>
    ),
  },
  'Profit': {
    title: 'Profit',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Lợi nhuận = Doanh thu − Refund − COGS − Phí Etsy</li>
        </ul>
      </div>
    ),
  },
  'Margin %': {
    title: 'Margin %',
    content: (
      <div style={{ fontSize: 12, lineHeight: 1.65 }}>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Biên lợi nhuận = (Lợi nhuận / Doanh thu) × 100%</li>
          <li>Nếu không có doanh thu thì margin = 0</li>
        </ul>
      </div>
    ),
  },
};
