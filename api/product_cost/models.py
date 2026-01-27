"""
Pydantic models for API responses.
"""
from pydantic import BaseModel


class ProductSummary(BaseModel):
    product_line_id: str
    product_name: str
    product_id: str
    variant_name: str
    sales: float
    order_ids: str
    refund: float
    unit: int
    cogs: float
    etsy_fee: float
    profit: float


class VariantDetail(BaseModel):
    variant: str
    sales: float
    unit: int
    refund: float
    cogs: float
    etsy_fee: float
    profit: float
    margin: float


class CogsBreakdown(BaseModel):
    pl_account_number: str
    label: str
    amount: float


class EtsyFeeBreakdown(BaseModel):
    fee_type: str
    label: str
    amount: float


class MarginBreakdown(BaseModel):
    order_id: str
    sales: float
    sales_percent: float
    refund: float
    cogs: float
    etsy_fee: float
    profit: float
    margin_percent: float
