"""
API route handlers for Product Cost endpoints.
"""
from typing import List
from datetime import datetime
from fastapi import HTTPException

from .models import ProductSummary, VariantDetail, CogsBreakdown, EtsyFeeBreakdown, MarginBreakdown
from .queries import query_products_optimized, query_variants_optimized, query_cogs_breakdown, query_etsy_fee_breakdown, query_margin_breakdown, COGS_LABELS
from .cache import products_cache, variants_cache, cogs_cache, etsy_fee_cache, margin_cache


def register_routes(app):
    """Register all API routes to the FastAPI app."""
    
    @app.get("/api/products", response_model=List[ProductSummary])
    def list_products():
        """List all products with cost metrics. Results are cached for 5 minutes."""
        try:
            # Check cache first
            cached = products_cache.get("all_products")
            if cached is not None:
                return cached
            
            # Query and cache
            rows = query_products_optimized()
            result = [
                ProductSummary(
                    product_line_id=r["product_line_id"] or "",
                    product_name=r["product_name"] or "",
                    product_id=r["product_id"] or "",
                    variant_name=r["variant_name"] or "",
                    sales=float(r["sales"] or 0),
                    order_ids=r["order_ids"] or "",
                    refund=float(r["refund"] or 0),
                    unit=int(r["unit"] or 0),
                    cogs=float(r["cogs"] or 0),
                    etsy_fee=float(r["etsy_fee"] or 0),
                    profit=float(r["profit"] or 0),
                )
                for r in rows
            ]
            products_cache.set("all_products", result)
            return result
        except Exception:
            # If table doesn't exist or other DB error, return empty list
            # Don't log error to avoid noise when database is empty
            return []
    
    
    @app.get("/api/products/{product_id}/variants", response_model=List[VariantDetail])
    def product_variants(product_id: str):
        """Get variants for a specific product."""
        try:
            # Check cache
            cache_key = f"variants_{product_id}"
            cached = variants_cache.get(cache_key)
            if cached is not None:
                return cached
            
            rows = query_variants_optimized(product_id)
            if not rows:
                raise HTTPException(status_code=404, detail="Product not found")
            
            result = [
                VariantDetail(
                    variant=r["variant"] or "",
                    sales=float(r["sales"] or 0),
                    unit=int(r["unit"] or 0),
                    refund=float(r["refund"] or 0),
                    cogs=float(r["cogs"] or 0),
                    etsy_fee=float(r["etsy_fee"] or 0),
                    profit=float(r["sales"] or 0) - float(r["refund"] or 0) - float(r["cogs"] or 0) - float(r["etsy_fee"] or 0),
                    margin=(
                        (
                            float(r["sales"] or 0)
                            - float(r["refund"] or 0)
                            - float(r["cogs"] or 0)
                            - float(r["etsy_fee"] or 0)
                        )
                        / float(r["sales"] or 1)
                        * 100
                        if float(r["sales"] or 0) != 0
                        else 0.0
                    ),
                )
                for r in rows
            ]
            variants_cache.set(cache_key, result)
            return result
        except HTTPException:
            raise
        except Exception:
            # If table doesn't exist or other DB error, return empty list
            # Don't log error to avoid noise when database is empty
            return []
    
    
    @app.get("/api/products/{product_id}/cogs_breakdown", response_model=List[CogsBreakdown])
    def product_cogs_breakdown(product_id: str):
        """Get COGS breakdown by account for a product."""
        try:
            # Check cache
            cache_key = f"cogs_{product_id}"
            cached = cogs_cache.get(cache_key)
            if cached is not None:
                return cached
            
            rows = query_cogs_breakdown(product_id)
            result = [
                CogsBreakdown(
                    pl_account_number=r["pl_account_number"],
                    label=COGS_LABELS.get(r["pl_account_number"], r["pl_account_number"]),
                    amount=float(r["amount"] or 0),
                )
                for r in rows
            ]
            cogs_cache.set(cache_key, result)
            return result
        except Exception:
            # If table doesn't exist or other DB error, return empty list
            # Don't log error to avoid noise when database is empty
            return []
    
    
    @app.get("/api/products/{product_id}/etsy_fee_breakdown", response_model=List[EtsyFeeBreakdown])
    def product_etsy_fee_breakdown(product_id: str):
        """Get Etsy Fee breakdown by fee type for a product."""
        try:
            # Check cache
            cache_key = f"etsy_fee_{product_id}"
            cached = etsy_fee_cache.get(cache_key)
            if cached is not None:
                return cached
            
            rows = query_etsy_fee_breakdown(product_id)
            result = [
                EtsyFeeBreakdown(
                    fee_type=r["fee_type"],
                    label=r["fee_type"],
                    amount=float(r["amount"] or 0),
                )
                for r in rows
            ]
            etsy_fee_cache.set(cache_key, result)
            return result
        except Exception:
            # If table doesn't exist or other DB error, return empty list
            # Don't log error to avoid noise when database is empty
            return []
    
    
    @app.get("/api/products/{product_id}/margin_breakdown", response_model=List[MarginBreakdown])
    def product_margin_breakdown(product_id: str):
        """Get margin breakdown by order for a product. Shows order_id, sales %, and margin %."""
        try:
            # Check cache
            cache_key = f"margin_{product_id}"
            cached = margin_cache.get(cache_key)
            if cached is not None:
                return cached
            
            rows = query_margin_breakdown(product_id)
            result = [
                MarginBreakdown(
                    order_id=str(r["order_id"] or ""),
                    sales=float(r["sales"] or 0),
                    sales_percent=float(r["sales_percent"] or 0),
                    refund=float(r["refund"] or 0),
                    cogs=float(r["cogs"] or 0),
                    etsy_fee=float(r["etsy_fee"] or 0),
                    profit=float(r["profit"] or 0),
                    margin_percent=float(r["margin_percent"] or 0),
                )
                for r in rows
            ]
            margin_cache.set(cache_key, result)
            return result
        except Exception:
            # If table doesn't exist or other DB error, return empty list
            # Don't log error to avoid noise when database is empty
            return []
    
    
    @app.post("/api/cache/clear")
    def clear_cache():
        """Clear all caches. Useful after data updates."""
        products_cache.clear()
        variants_cache.clear()
        cogs_cache.clear()
        etsy_fee_cache.clear()
        margin_cache.clear()
        return {"status": "ok", "message": "All caches cleared"}
    
    
    @app.get("/api/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
