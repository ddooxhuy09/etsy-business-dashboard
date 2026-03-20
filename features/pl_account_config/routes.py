"""
CRUD API routes for pl_account_config.
Manages which bank P&L account numbers map to which category (COGS / EXPENSE / etc.).
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from shared.db import run_query, execute_query

router = APIRouter(prefix="/api/pl-accounts", tags=["pl-account-config"])
logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"COGS", "EXPENSE", "REVENUE", "DEDUCTION", "OTHER"}


class PlAccountIn(BaseModel):
    account_number: str
    description: str = ""
    category: str
    is_active: bool = True


class PlAccountUpdate(BaseModel):
    description: str | None = None
    category: str | None = None
    is_active: bool | None = None


@router.get("")
def list_pl_accounts():
    """List all PL account config entries."""
    try:
        df = run_query(
            "SELECT account_number, description, category, is_active "
            "FROM pl_account_config "
            "ORDER BY category, account_number",
            None,
        )
        return {"data": df.to_dict(orient="records") if df is not None and not df.empty else []}
    except Exception as e:
        logger.exception("list_pl_accounts failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch PL account config")


@router.post("")
def create_pl_account(body: PlAccountIn):
    """Add a new PL account config entry."""
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{body.category}'. Must be one of: {sorted(VALID_CATEGORIES)}",
        )
    try:
        execute_query(
            "INSERT INTO pl_account_config (account_number, description, category, is_active) "
            "VALUES (%s, %s, %s, %s)",
            (body.account_number.strip(), body.description, body.category, body.is_active),
        )
        return {"ok": True}
    except Exception as e:
        logger.exception("create_pl_account failed: %s", e)
        err = str(e).lower()
        if "duplicate" in err or "unique" in err:
            raise HTTPException(
                status_code=409,
                detail=f"Account '{body.account_number}' already exists",
            )
        raise HTTPException(status_code=500, detail="Failed to create PL account config")


@router.put("/{account_number}")
def update_pl_account(account_number: str, body: PlAccountUpdate):
    """Update category and/or is_active for an existing entry."""
    if body.category is not None and body.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{body.category}'. Must be one of: {sorted(VALID_CATEGORIES)}",
        )
    fields, values = [], []
    if body.description is not None:
        fields.append("description = %s")
        values.append(body.description)
    if body.category is not None:
        fields.append("category = %s")
        values.append(body.category)
    if body.is_active is not None:
        fields.append("is_active = %s")
        values.append(body.is_active)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    values.append(account_number)
    try:
        execute_query(
            f"UPDATE pl_account_config SET {', '.join(fields)} WHERE account_number = %s",
            values,
        )
        return {"ok": True}
    except Exception as e:
        logger.exception("update_pl_account failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update PL account config")


@router.delete("/{account_number}")
def delete_pl_account(account_number: str):
    """Delete a PL account config entry."""
    try:
        execute_query(
            "DELETE FROM pl_account_config WHERE account_number = %s",
            (account_number,),
        )
        return {"ok": True}
    except Exception as e:
        logger.exception("delete_pl_account failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete PL account config")
