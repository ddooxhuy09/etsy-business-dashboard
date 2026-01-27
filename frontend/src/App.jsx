import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Charts from './pages/Charts';
import ProductCost from './pages/ProductCost';
import ProfitLossStatement from './pages/ProfitLossStatement';
import Report from './pages/Report';
import ProductCatalog from './pages/ProductCatalog';
import BankAccount from './pages/BankAccount';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="charts" element={<Charts />} />
          <Route path="product-cost" element={<ProductCost />} />
          <Route path="profit-loss" element={<ProfitLossStatement />} />
          <Route path="report" element={<Report />} />
          <Route path="product-catalog" element={<ProductCatalog />} />
          <Route path="bank-account" element={<BankAccount />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
