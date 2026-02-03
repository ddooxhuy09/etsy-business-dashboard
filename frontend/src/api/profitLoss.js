import api from '../lib/axios';

function params(p) {
  const q = { ...p };
  Object.keys(q).forEach((k) => (q[k] == null || q[k] === '') && delete q[k]);
  return q;
}

export function fetchProfitLossSummaryTable(filters) {
  return api.get('/api/profit-loss/summary-table', { params: params(filters) }).then((r) => r.data);
}

export function fetchProfitFormulaConfig() {
  return api.get('/api/profit-loss/formula-config').then((r) => r.data);
}
