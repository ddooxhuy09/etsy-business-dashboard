"""
FastAPI routes for chart data. Uses get_* from dashboard/charts (local, no src).
Charts use api.db.run_query via utils.db_query.
"""
import re
import calendar
import logging
import pandas as pd
from fastapi import APIRouter, Query

from charts.get_total_revenue import get_total_revenue

logger = logging.getLogger(__name__)
from charts.get_total_orders import get_total_orders
from charts.get_total_customers import get_total_customers
from charts.get_average_order_value import get_average_order_value
from charts.get_revenue_by_month import get_revenue_by_month
from charts.get_profit_by_month import get_profit_by_month
from charts.get_new_vs_returning_customer_sales import get_new_vs_returning_customer_sales
from charts.get_new_customers_over_time import get_new_customers_over_time
from charts.get_customers_by_location import get_customers_by_location
from charts.get_customer_retention_rate import get_customer_retention_rate
from charts.get_total_sales_by_product import get_total_sales_by_product
from charts.get_customer_acquisition_cost import get_customer_acquisition_cost
from charts.get_customer_lifetime_value import get_customer_lifetime_value
from charts.get_cac_clv_ratio_over_time import get_cac_clv_ratio_over_time
from charts.get_total_orders_by_month import get_total_orders_by_month
from charts.get_average_order_value_over_time import get_average_order_value_over_time
from charts.get_revenue_comparison_by_month import (
    get_revenue_comparison_by_month,
    get_comparison_percentages,
    get_month_name,
)

router = APIRouter(prefix="/api/charts", tags=["charts"])

def StrOpt():
    """Each call returns a NEW Query instance so FastAPI doesn't link params."""
    return Query(None, description="YYYY-MM-DD")


def _sanitize_dates(start_date, end_date):
    """
    Fix date parameters.
    When user selects a month filter (e.g. Jan 2026), the frontend may send
    start_date=2026-01-01 and end_date=2026-01-01 (both = first-of-month).
    We expand end_date to the last day of that month so the filter covers the whole month.
    """
    if start_date and end_date and start_date == end_date:
        m = re.match(r'^(\d{4})-(\d{2})-01$', end_date)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
            last_day = calendar.monthrange(year, month)[1]
            end_date = f"{year}-{month:02d}-{last_day:02d}"
    return start_date, end_date


def _to_records(df):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    return pd.DataFrame(df).where(pd.notnull(df), None).to_dict(orient="records")


def _safe_chart_call(chart_func, *args, **kwargs):
    """Wrapper để gọi chart function an toàn: trả về empty DataFrame nếu có lỗi."""
    try:
        df = chart_func(*args, **kwargs)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        logger.exception("Chart %s failed: %s", chart_func.__name__, e)
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
@router.get("/total-revenue")
def charts_total_revenue(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_total_revenue, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


@router.get("/total-orders")
def charts_total_orders(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_total_orders, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


@router.get("/total-customers")
def charts_total_customers(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_total_customers, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


@router.get("/average-order-value")
def charts_aov(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_average_order_value, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------
@router.get("/revenue-by-month")
def charts_revenue_by_month(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_revenue_by_month, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


@router.get("/profit-by-month")
def charts_profit_by_month(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_profit_by_month, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
@router.get("/new-vs-returning")
def charts_new_vs_returning(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_new_vs_returning_customer_sales, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


@router.get("/new-customers-over-time")
def charts_new_customers_over_time(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_new_customers_over_time, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


@router.get("/customers-by-location")
def charts_customers_by_location(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_customers_by_location, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


@router.get("/customer-retention-rate")
def charts_retention(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_customer_retention_rate, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
@router.get("/total-sales-by-product")
def charts_sales_by_product(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_total_sales_by_product, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


# ---------------------------------------------------------------------------
# Financial (CAC, CLV, CAC/CLV)
# ---------------------------------------------------------------------------
@router.get("/customer-acquisition-cost")
def charts_cac(start_date: str = StrOpt(), end_date: str = StrOpt()):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_customer_acquisition_cost, start_date, end_date)
    return {"data": _to_records(df)}


@router.get("/customer-lifetime-value")
def charts_clv(
    start_date: str = StrOpt(),
    end_date: str = StrOpt(),
    customer_type: str = Query("all"),
    customer_lifespan_months: int = Query(12, ge=1, le=60),
):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_customer_lifetime_value, start_date, end_date, customer_type, customer_lifespan_months)
    return {"data": _to_records(df)}


@router.get("/cac-clv-ratio-over-time")
def charts_cac_clv(
    start_date: str = StrOpt(),
    end_date: str = StrOpt(),
    customer_lifespan_months: int = Query(12, ge=1, le=60),
):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_cac_clv_ratio_over_time, start_date, end_date, customer_lifespan_months)
    return {"data": _to_records(df)}


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
@router.get("/total-orders-by-month")
def charts_orders_by_month(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_total_orders_by_month, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


@router.get("/average-order-value-over-time")
def charts_aov_over_time(start_date: str = StrOpt(), end_date: str = StrOpt(), customer_type: str = Query("all")):
    start_date, end_date = _sanitize_dates(start_date, end_date)
    df = _safe_chart_call(get_average_order_value_over_time, start_date, end_date, customer_type)
    return {"data": _to_records(df)}


# ---------------------------------------------------------------------------
# Revenue comparison (month1 vs month2)
# ---------------------------------------------------------------------------
@router.get("/revenue-comparison")
def charts_revenue_comparison(
    month1_year: int = Query(..., ge=2020),
    month1_month: int = Query(..., ge=1, le=12),
    month2_year: int = Query(..., ge=2020),
    month2_month: int = Query(..., ge=1, le=12),
):
    try:
        df = get_revenue_comparison_by_month(month1_year, month1_month, month2_year, month2_month)
        cmp = get_comparison_percentages(month1_year, month1_month, month2_year, month2_month)
        return {
            "data": _to_records(df),
            "comparison": {
                "orders_pct": cmp.get("orders_pct"),
                "revenue_pct": cmp.get("revenue_pct"),
                "profit_pct": cmp.get("profit_pct"),
            },
            "month1_name": get_month_name(month1_month),
            "month2_name": get_month_name(month2_month),
        }
    except Exception:
        # Không log lỗi, chỉ trả về empty để frontend hiển "No data"
        return {
            "data": [],
            "comparison": {"orders_pct": None, "revenue_pct": None, "profit_pct": None},
            "month1_name": get_month_name(month1_month),
            "month2_name": get_month_name(month2_month),
        }


@router.get("/month-names")
def charts_month_names():
    return {i: get_month_name(i) for i in range(1, 13)}


