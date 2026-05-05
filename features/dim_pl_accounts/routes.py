import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.database import run_query, execute_query

router = APIRouter(prefix="/api/pl-accounts", tags=["pl-account-config"])
logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"COGS", "EXPENSE", "REVENUE", "DEDUCTION", "OTHER"}


class PlAccountIn(BaseModel):
    pl_account_number: str
    description: str = ""
    category: str


class PlAccountUpdate(BaseModel):
    pl_account_number: str | None = None
    description: str | None = None
    category: str | None = None


@router.get("")
def list_pl_accounts():
    try:
        df = run_query(
            "SELECT pl_account_number, description, category "
            "FROM dim_pl_accounts "
            "ORDER BY category, pl_account_number",
            None,
        )
        return {"data": df.to_dict(orient="records") if df is not None and not df.empty else []}
    except Exception as e:
        logger.exception("list_pl_accounts failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch PL account config")


@router.post("")
def create_pl_account(body: PlAccountIn):
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{body.category}'. Must be one of: {sorted(VALID_CATEGORIES)}",
        )
    try:
        execute_query(
            "INSERT INTO dim_pl_accounts (pl_account_number, description, category) "
            "VALUES (%s, %s, %s)",
            (body.pl_account_number.strip(), body.description, body.category),
        )
        return {"ok": True}
    except Exception as e:
        logger.exception("create_pl_account failed: %s", e)
        err = str(e).lower()
        if "duplicate" in err or "unique" in err:
            raise HTTPException(
                status_code=409,
                detail=f"Account '{body.pl_account_number}' already exists",
            )
        raise HTTPException(status_code=500, detail="Failed to create PL account config")


@router.put("/{pl_account_number}")
def update_pl_account(pl_account_number: str, body: PlAccountUpdate):
    if body.category is not None and body.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{body.category}'. Must be one of: {sorted(VALID_CATEGORIES)}",
        )
    fields, values = [], []
    if body.pl_account_number is not None:
        new_num = body.pl_account_number.strip()
        if not new_num:
            raise HTTPException(status_code=400, detail="pl_account_number cannot be empty")
        fields.append("pl_account_number = %s")
        values.append(new_num)
    if body.description is not None:
        fields.append("description = %s")
        values.append(body.description)
    if body.category is not None:
        fields.append("category = %s")
        values.append(body.category)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    values.append(pl_account_number)
    try:
        execute_query(
            f"UPDATE dim_pl_accounts SET {', '.join(fields)} WHERE pl_account_number = %s",
            values,
        )
        return {"ok": True}
    except Exception as e:
        logger.exception("update_pl_account failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update PL account config")


@router.delete("/{pl_account_number}")
def delete_pl_account(pl_account_number: str):
    try:
        execute_query(
            "DELETE FROM dim_pl_accounts WHERE pl_account_number = %s",
            (pl_account_number,),
        )
        return {"ok": True}
    except Exception as e:
        logger.exception("delete_pl_account failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete PL account config")
