import API from '../lib/axios';

function params(p) {
  const q = { ...p };
  Object.keys(q).forEach((k) => (q[k] == null || q[k] === '') && delete q[k]);
  return q;
}

export function chartsTotalRevenue(f) {
  return API.get('/api/charts/total-revenue', { params: params(f) }).then((r) => r.data);
}
export function chartsTotalOrders(f) {
  return API.get('/api/charts/total-orders', { params: params(f) }).then((r) => r.data);
}
export function chartsTotalCustomers(f) {
  return API.get('/api/charts/total-customers', { params: params(f) }).then((r) => r.data);
}
export function chartsAov(f) {
  return API.get('/api/charts/average-order-value', { params: params(f) }).then((r) => r.data);
}
export function chartsRevenueByMonth(f) {
  return API.get('/api/charts/revenue-by-month', { params: params(f) }).then((r) => r.data);
}
export function chartsProfitByMonth(f) {
  return API.get('/api/charts/profit-by-month', { params: params(f) }).then((r) => r.data);
}
export function chartsNewVsReturning(f) {
  return API.get('/api/charts/new-vs-returning', { params: params(f) }).then((r) => r.data);
}
export function chartsNewCustomersOverTime(f) {
  return API.get('/api/charts/new-customers-over-time', { params: params(f) }).then((r) => r.data);
}
export function chartsCustomersByLocation(f) {
  return API.get('/api/charts/customers-by-location', { params: params(f) }).then((r) => r.data);
}
export function chartsRetention(f) {
  return API.get('/api/charts/customer-retention-rate', { params: params(f) }).then((r) => r.data);
}
export function chartsSalesByProduct(f) {
  return API.get('/api/charts/total-sales-by-product', { params: params(f) }).then((r) => r.data);
}
export function chartsCac(f) {
  return API.get('/api/charts/customer-acquisition-cost', { params: params(f) }).then((r) => r.data);
}
export function chartsClv(f) {
  return API.get('/api/charts/customer-lifetime-value', { params: params(f) }).then((r) => r.data);
}
export function chartsCacClv(f) {
  return API.get('/api/charts/cac-clv-ratio-over-time', { params: params(f) }).then((r) => r.data);
}
export function chartsOrdersByMonth(f) {
  return API.get('/api/charts/total-orders-by-month', { params: params(f) }).then((r) => r.data);
}
export function chartsAovOverTime(f) {
  return API.get('/api/charts/average-order-value-over-time', { params: params(f) }).then((r) => r.data);
}
export function chartsRevenueComparison(m1y, m1m, m2y, m2m) {
  return API.get('/api/charts/revenue-comparison', {
    params: { month1_year: m1y, month1_month: m1m, month2_year: m2y, month2_month: m2m },
  }).then((r) => r.data);
}
