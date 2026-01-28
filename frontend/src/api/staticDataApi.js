import api from '../lib/axios';

// Product Catalog API
export function fetchProductCatalog({ limit = 100, offset = 0, search, sort_by, sort_order } = {}) {
  const params = { limit, offset };
  if (search) params.search = search;
  if (sort_by) params.sort_by = sort_by;
  if (sort_order) params.sort_order = sort_order;
  return api.get('/api/static/product-catalog', { params }).then((r) => r.data);
}

export function fetchProductCatalogCount() {
  return api.get('/api/static/product-catalog/count').then((r) => r.data);
}

export function uploadProductCatalog(file) {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/api/static/product-catalog/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then((r) => r.data);
}

export function importProductCatalogRow(row) {
  return api.post('/api/static/product-catalog/import-row', row).then((r) => r.data);
}

// Bank Transactions API
export function fetchBankTransactions({ limit = 100, offset = 0, search, sort_by, sort_order, account_number } = {}) {
  const params = { limit, offset };
  if (search) params.search = search;
  if (sort_by) params.sort_by = sort_by;
  if (sort_order) params.sort_order = sort_order;
  if (account_number) params.account_number = account_number;
  return api.get('/api/static/bank-transactions', { params }).then((r) => r.data);
}

export function fetchBankTransactionsCount(account_number) {
  const params = account_number ? { account_number } : {};
  return api.get('/api/static/bank-transactions/count', { params }).then((r) => r.data);
}

export function uploadBankTransactions(file) {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/api/static/bank-transactions/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then((r) => r.data);
}

export function importBankTransactionRow(row) {
  return api.post('/api/static/bank-transactions/import-row', row).then((r) => r.data);
}
