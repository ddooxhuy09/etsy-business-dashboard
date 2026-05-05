import logging
from core.database import run_query

logger = logging.getLogger(__name__)

_FALLBACK: dict[str, list[str]] = {
    "COGS":    ["6211", "6221", "6222", "6223", "6224", "6225"],
    "EXPENSE": ["6273", "6411", "6412", "6413", "6414", "6421", "6428"],
}


def get_active_accounts(category: str) -> list[str]:
    try:
        df = run_query(
            "SELECT pl_account_number FROM dim_pl_accounts "
            "WHERE category = %s "
            "ORDER BY pl_account_number",
            (category,),
        )
        if df is not None and not df.empty:
            return df["pl_account_number"].tolist()
    except Exception:
        logger.debug(
            "dim_pl_accounts unavailable or empty for category=%s -- using fallback",
            category,
        )
    return _FALLBACK.get(category, []).copy()


def get_cogs_accounts() -> list[str]:
    return get_active_accounts("COGS")


def get_expense_accounts() -> list[str]:
    return get_active_accounts("EXPENSE")


def sql_in_list(accounts: list[str]) -> str:
    if not accounts:
        return "'0'"
    return ",".join(f"'{a}'" for a in accounts)
