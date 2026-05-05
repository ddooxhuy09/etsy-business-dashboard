import React, { createContext, useContext, useState } from 'react';

const EXCHANGE_RATE = 24708.655; // VND per USD

const CurrencyContext = createContext();

export function CurrencyProvider({ children }) {
  const [currency, setCurrency] = useState(
    () => localStorage.getItem('preferred_currency') || 'USD'
  );

  const toggle = () => {
    setCurrency((prev) => {
      const next = prev === 'USD' ? 'VND' : 'USD';
      localStorage.setItem('preferred_currency', next);
      return next;
    });
  };

  // Format a USD-denominated number to the current currency string
  const fmt = (value, decimals) => {
    if (value == null || value === '') return '—';
    const n = Number(value);
    if (isNaN(n)) return String(value);
    if (currency === 'VND') {
      return '₫' + Math.round(n * EXCHANGE_RATE).toLocaleString('vi-VN');
    }
    const d = decimals ?? 2;
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  };

  // Convert a USD value to the active currency (numeric)
  const convert = (value) => {
    const n = Number(value);
    if (isNaN(n)) return n;
    return currency === 'VND' ? Math.round(n * EXCHANGE_RATE) : n;
  };

  return (
    <CurrencyContext.Provider value={{ currency, toggle, fmt, convert, exchangeRate: EXCHANGE_RATE }}>
      {children}
    </CurrencyContext.Provider>
  );
}

export const useCurrency = () => useContext(CurrencyContext);
