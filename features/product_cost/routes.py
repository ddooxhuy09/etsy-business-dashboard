"""
API route handlers for Product Cost endpoints.
"""
import logging
import traceback
from typing import List
from datetime import datetime
from fastapi import HTTPException

from .models import ProductSummary, VariantDetail, CogsBreakdown, EtsyFeeBreakdown, MarginBreakdown
from .queries import query_products_optimized, query_variants_optimized, query_cogs_breakdown, query_etsy_fee_breakdown, query_margin_breakdown, COGS_LABELS

logger = logging.getLogger(__name__)


def register_routes(app):
    """Register all API routes to the FastAPI app."""

    @app.get("/api/products", response_model=List[ProductSummary])
    def list_products():
        """List all products with cost metrics."""
        try:
            rows = query_products_optimized()
            return [
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
        except Exception as e:
            logger.error("list_products failed: %s\n%s", e, traceback.format_exc())
            return []

    @app.get("/api/products/{product_id}/variants", response_model=List[VariantDetail])
    def product_variants(product_id: str):
        """Get variants for a specific product."""
        try:
            rows = query_variants_optimized(product_id)
            if not rows:
                raise HTTPException(status_code=404, detail="Product not found")
            return [
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
        except HTTPException:
            raise
        except Exception:
            return []

    @app.get("/api/products/{product_id}/cogs_breakdown", response_model=List[CogsBreakdown])
    def product_cogs_breakdown(product_id: str):
        """Get COGS breakdown by account for a product."""
        try:
            rows = query_cogs_breakdown(product_id)
            return [
                CogsBreakdown(
                    pl_account_number=r["pl_account_number"],
                    label=COGS_LABELS.get(r["pl_account_number"], r["pl_account_number"]),
                    amount=float(r["amount"] or 0),
                )
                for r in rows
            ]
        except Exception:
            return []

    @app.get("/api/products/{product_id}/etsy_fee_breakdown", response_model=List[EtsyFeeBreakdown])
    def product_etsy_fee_breakdown(product_id: str):
        """Get Etsy Fee breakdown by fee type for a product."""
        try:
            rows = query_etsy_fee_breakdown(product_id)
            return [
                EtsyFeeBreakdown(
                    fee_type=r["fee_type"],
                    label=r["fee_type"],
                    amount=float(r["amount"] or 0),
                )
                for r in rows
            ]
        except Exception:
            return []

    @app.get("/api/products/{product_id}/margin_breakdown", response_model=List[MarginBreakdown])
    def product_margin_breakdown(product_id: str):
        """Get margin breakdown by order for a product."""
        try:
            rows = query_margin_breakdown(product_id)
            return [
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
        except Exception:
            return []

    @app.get("/api/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
