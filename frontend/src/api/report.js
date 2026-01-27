import axios from 'axios';

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '' });

function params(p) {
  const q = { ...p };
  Object.keys(q).forEach((k) => (q[k] == null || q[k] === '') && delete q[k]);
  return q;
}

export function fetchBankAccounts(pagination) {
  return api.get('/api/reports/bank-accounts', { params: { offset: (pagination.page - 1) * pagination.pageSize, limit: pagination.pageSize } }).then((r) => r.data);
}

export function fetchBankAccountsCount() {
  return api.get('/api/reports/bank-accounts/count').then((r) => r.data.total);
}

export function fetchBankAccountInfo(accountNumber) {
  return api.get('/api/reports/bank-account-info', { params: { account_number: accountNumber } }).then((r) => r.data);
}

export function fetchAccountStatement(filters) {
  return api.get('/api/reports/account-statement', { params: params({ account_number: filters.account_number, from_date: filters.from_date, to_date: filters.to_date }) }).then((r) => r.data);
}

/**
 * Returns the URL for the PDF (attachment). Use as href for download or window.open for preview.
 */
export function getAccountStatementPdfUrl(accountNumber, fromDate, toDate) {
  const base = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
  const q = new URLSearchParams({ account_number: accountNumber });
  if (fromDate) q.set('from_date', fromDate);
  if (toDate) q.set('to_date', toDate);
  return `${base}/api/reports/account-statement/pdf?${q.toString()}`;
}
