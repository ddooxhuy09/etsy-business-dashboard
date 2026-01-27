import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export const api = axios.create({
  baseURL: API_BASE,
});

export async function fetchProducts() {
  const { data } = await api.get('/api/products');
  return data;
}

export async function fetchVariants(productId) {
  const { data } = await api.get(`/api/products/${encodeURIComponent(productId)}/variants`);
  return data;
}

export async function fetchCogsBreakdown(productId) {
  const { data } = await api.get(
    `/api/products/${encodeURIComponent(productId)}/cogs_breakdown`,
  );
  return data;
}

export async function fetchEtsyFeeBreakdown(productId) {
  const { data } = await api.get(
    `/api/products/${encodeURIComponent(productId)}/etsy_fee_breakdown`,
  );
  return data;
}

export async function fetchMarginBreakdown(productId) {
  const { data } = await api.get(
    `/api/products/${encodeURIComponent(productId)}/margin_breakdown`,
  );
  return data;
}
