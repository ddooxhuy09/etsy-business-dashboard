/**
 * Giải thích công thức tính cho từng chart.
 * Hiển thị khi click nút annotation (info) trên mỗi chart.
 */
export const CHART_ANNOTATIONS = {
  totalRevenue: {
    title: 'Tổng doanh thu',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> Total Revenue = SUM(Item Total) − SUM(Discount Amount)
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li><strong>Item Total</strong>: Cột trong file EtsySoldOrderItems</li>
          <li><strong>Discount Amount</strong>: Cột trong file EtsySoldOrderItems</li>
        </ul>
      </div>
    ),
  },
  totalOrders: {
    title: 'Tổng đơn hàng',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> Total Orders = COUNT(DISTINCT order_key)
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li>Đếm số đơn hàng riêng biệt từ fact_sales (Order ID trong EtsySoldOrderItems)</li>
        </ul>
      </div>
    ),
  },
  totalCustomers: {
    title: 'Tổng khách hàng',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> Total Customers = COUNT(DISTINCT customer_key)
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li>Đếm số khách hàng riêng biệt (Buyer trong EtsySoldOrderItems)</li>
        </ul>
      </div>
    ),
  },
  aov: {
    title: 'Giá trị đơn hàng trung bình (AOV)',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> AOV = Total Revenue / Total Orders
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li><strong>Total Revenue</strong>: SUM(Item Total) − SUM(Discount Amount) từ EtsySoldOrderItems</li>
          <li><strong>Total Orders</strong>: COUNT(DISTINCT order_key)</li>
        </ul>
      </div>
    ),
  },
  revenueByMonth: {
    title: 'Doanh thu theo tháng',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức mỗi tháng:</strong> Revenue = SUM(Item Total) − SUM(Discount Amount)
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li>Nhóm theo tháng, lấy Item Total và Discount Amount từ EtsySoldOrderItems</li>
        </ul>
      </div>
    ),
  },
  profitByMonth: {
    title: 'Lợi nhuận theo tháng',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> Profit = SUM(Net Amount)
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li><strong>Net Amount</strong>: Cột trong file EtsyDirectCheckoutPayments</li>
          <li>Nhóm theo tháng theo payment_date</li>
        </ul>
      </div>
    ),
  },
  newVsReturning: {
    title: 'Doanh thu: Khách mới vs Khách quay lại',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Phân nhóm:</strong>
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li><strong>New Customers</strong>: Khách có đúng 1 đơn (order_count = 1)</li>
          <li><strong>Returning Customers</strong>: Khách có &gt; 1 đơn</li>
        </ul>
        <p style={{ marginTop: 8, marginBottom: 0 }}>
          <strong>Revenue</strong> = SUM(Item Total) − SUM(Discount Amount) từ EtsySoldOrderItems
        </p>
      </div>
    ),
  },
  newCustomersOverTime: {
    title: 'Khách hàng mới theo thời gian',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Định nghĩa:</strong> New Customers = Khách hàng chỉ có đúng 1 đơn
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li>Đếm COUNT(DISTINCT customer_key) WHERE customer có COUNT(order_key) = 1</li>
          <li>Nhóm theo ngày</li>
        </ul>
      </div>
    ),
  },
  customersByLocation: {
    title: 'Khách hàng theo tiểu bang (US)',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong>
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li><strong>Customers</strong>: COUNT(DISTINCT customer_key) theo State</li>
          <li><strong>Revenue</strong>: SUM(Item Total) − SUM(Discount Amount) theo State</li>
          <li>Lọc country = United States, hiển thị top 12 tiểu bang</li>
        </ul>
      </div>
    ),
  },
  retention: {
    title: 'Tỷ lệ giữ chân khách hàng',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> Retention Rate = (Khách quay lại / Tổng khách hàng) × 100
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li><strong>Khách quay lại</strong>: Customer có &gt; 1 đơn hàng</li>
          <li><strong>Tổng khách hàng</strong>: Tất cả khách trong kỳ</li>
        </ul>
      </div>
    ),
  },
  salesByProduct: {
    title: 'Top 10 sản phẩm theo doanh thu',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> Revenue = SUM(Item Total) − SUM(Discount Amount) theo từng sản phẩm
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li>Item Total, Discount Amount từ EtsySoldOrderItems</li>
          <li>Join với dim_product để lấy tên sản phẩm</li>
          <li>Top 10 sản phẩm có doanh thu cao nhất</li>
        </ul>
      </div>
    ),
  },
  cac: {
    title: 'Chi phí thu hút khách hàng (CAC)',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> CAC = Tổng chi phí marketing ÷ Số khách hàng mới
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li><strong>Tổng chi phí marketing</strong>: Tổng cột Fees &amp; Taxes với những dòng mà cột Type = &quot;Marketing&quot; trong file etsy_statement</li>
          <li><strong>Số khách hàng mới</strong>: Khách hàng chỉ có đúng 1 đơn</li>
        </ul>
      </div>
    ),
  },
  ltv: {
    title: 'Giá trị vòng đời khách hàng (LTV)',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> LTV = AOV × Tần suất mua trung bình
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li><strong>AOV (Average Order Value)</strong>: Tổng doanh thu / Tổng số đơn hàng trong kỳ</li>
          <li><strong>Avg Purchase Frequency</strong>: Tổng số đơn hàng / Tổng số khách hàng trong kỳ</li>
        </ul>
        <p style={{ marginTop: 8, marginBottom: 0, fontStyle: 'italic', color: '#666' }}>
          AOV và Tần suất mua được tính cho cùng một khoảng thời gian (30, 60, hoặc 90 ngày).
        </p>
      </div>
    ),
  },
  cacClvRatio: {
    title: 'LTV/CAC Ratio theo tháng (30d / 60d / 90d)',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Theo từng tháng:</strong>
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li><strong>CAC</strong>: Tổng Marketing fees (Fees &amp; Taxes, Type=Marketing từ statement) / Số khách mới trong tháng</li>
          <li><strong>LTV(30d)</strong>: AOV × Avg Freq tính trên 30 ngày gần nhất tính đến cuối tháng</li>
          <li><strong>LTV(60d)</strong>: AOV × Avg Freq tính trên 60 ngày gần nhất tính đến cuối tháng</li>
          <li><strong>LTV(90d)</strong>: AOV × Avg Freq tính trên 90 ngày gần nhất tính đến cuối tháng</li>
          <li><strong>LTV/CAC (x)</strong>: LTV ÷ CAC — 3 đường line cho 3 window</li>
        </ul>
      </div>
    ),
  },
  ordersByMonth: {
    title: 'Số đơn hàng theo tháng',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> Orders = COUNT(DISTINCT order_key) GROUP BY tháng
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li>order_key từ fact_sales (Order ID trong EtsySoldOrderItems)</li>
        </ul>
      </div>
    ),
  },
  aovOverTime: {
    title: 'Giá trị đơn hàng trung bình theo thời gian',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức mỗi ngày:</strong> AOV = (SUM(Item Total) − SUM(Discount Amount)) / COUNT(DISTINCT order_key)
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li>Item Total, Discount Amount từ EtsySoldOrderItems</li>
        </ul>
      </div>
    ),
  },
  revenueComparison: {
    title: 'So sánh doanh thu theo tháng',
    content: (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <strong>Công thức:</strong> Daily Revenue = SUM(Item Total − Discount Amount) GROUP BY ngày
        <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
          <li>So sánh doanh thu theo ngày giữa 2 tháng được chọn</li>
          <li>Order Total %, Revenue %, Profit %: phần trăm thay đổi tháng 1 vs tháng 2</li>
        </ul>
      </div>
    ),
  },
};
