import React from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import ProductCost from '../components/product_cost/ProductCost';
import ProductDetail from '../components/product_cost/ProductDetail';
import '../styles/productCost.css';

export default function ProductCostPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const productId = searchParams.get('product_id');
  const productName = searchParams.get('product_name') || '';

  return (
    <div className="product-cost-page">
      {productId ? (
        <ProductDetail
          productId={productId}
          productName={productName}
          onBack={() => navigate('/product-cost')}
        />
      ) : (
        <ProductCost />
      )}
    </div>
  );
}
