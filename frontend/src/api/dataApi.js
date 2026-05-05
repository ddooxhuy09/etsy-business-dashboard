import API from '../lib/axios';

export function fetchSources() {
  return API.get('/api/data/sources').then((r) => r.data);
}

export function fetchDataRows(source, { period, search, page = 1, page_size = 50 } = {}) {
  const params = { page, page_size };
  if (period) params.period = period;
  if (search) params.search = search;
  return API.get(`/api/data/${source}`, { params }).then((r) => r.data);
}

export function updateDataRow(source, pk, data) {
  return API.put(`/api/data/${source}/${pk}`, { data }).then((r) => r.data);
}

export function deleteDataRow(source, pk) {
  return API.delete(`/api/data/${source}/${pk}`).then((r) => r.data);
}
