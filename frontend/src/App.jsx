import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import Home from './pages/Home';
import Charts from './pages/Charts';
import ProductCost from './pages/ProductCost';
import ProfitLossStatement from './pages/ProfitLossStatement';
import Report from './pages/Report';
import ProductCatalog from './pages/ProductCatalog';
import BankAccount from './pages/BankAccount';
import ChangePassword from './pages/ChangePassword';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Home />} />
            <Route path="charts" element={<Charts />} />
            <Route path="product-cost" element={<ProductCost />} />
            <Route path="profit-loss" element={<ProfitLossStatement />} />
            <Route path="report" element={<Report />} />
            <Route path="product-catalog" element={<ProductCatalog />} />
            <Route path="bank-account" element={<BankAccount />} />
            <Route path="change-password" element={<ChangePassword />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
