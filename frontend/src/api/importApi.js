import api from '../lib/axios';

/** Tên file lưu trên đĩa (pattern) */
export const FILE_LABELS = {
  statement: 'etsy_statement_{year}_{month}.csv',
  direct_checkout: 'EtsyDirectCheckoutPayments{year}-{month}.csv',
  listing: 'EtsyListingsDownload.csv',
  sold_order_items: 'EtsySoldOrderItems{year}-{month}.csv',
  sold_orders: 'EtsySoldOrders{year}-{month}.csv',
  deposits: 'EtsyDeposits{year}-{month}.csv',
};

/** Tên hiển thị ngắn (cột "Tên") */
export const FILE_DISPLAY_NAMES = {
  statement: 'Bảng kê Etsy',
  direct_checkout: 'Thanh toán trực tiếp',
  listing: 'Danh sách sản phẩm',
  sold_order_items: 'Chi tiết đơn hàng',
  sold_orders: 'Đơn hàng đã bán',
  deposits: 'Tiền gửi',
};

export function fetchImportPeriods() {
  return api.get('/api/import/periods').then((r) => r.data);
}

export function createImportPeriod(year, month) {
  const form = new FormData();
  form.append('year', year);
  form.append('month', month);
  return api
    .post('/api/import/periods', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    .then((r) => r.data);
}

export function fetchImportFiles(year, month) {
  return api.get('/api/import/files', { params: { year, month } }).then((r) => r.data);
}

export function uploadImportFiles(year, month, files) {
  const form = new FormData();
  form.append('year', year);
  form.append('month', month);
  Object.entries(files).forEach(([key, file]) => {
    if (file && file instanceof File) form.append(key, file);
  });
  return api.post('/api/import/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data);
}

export function runImportEtl(year, month, opts = {}) {
  const params = { year, month, force: opts.force === true };
  return api.post('/api/import/run-etl', null, { params }).then((r) => r.data);
}

export function fetchExpectedColumns() {
  return api.get('/api/import/expected-columns').then((r) => r.data);
}

export function deleteImportFile(year, month, key, filename) {
  return api.delete('/api/import/files', { params: { year, month, key, filename } }).then((r) => r.data);
}
