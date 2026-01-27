import axios from 'axios';

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE || '' });

function params(p) {
  const q = { ...p };
  Object.keys(q).forEach((k) => (q[k] == null || q[k] === '') && delete q[k]);
  return q;
}

export function fetchProfitLossSummaryTable(filters) {
  return api.get('/api/profit-loss/summary-table', { params: params(filters) }).then((r) => r.data);
}
