"""
Loader for pl_account_config — maps PL account numbers to categories (COGS / EXPENSE / etc.).

Queries the `pl_account_config` database table at runtime.
Falls back to hardcoded defaults if the table is empty or does not exist yet.
"""
import logging
from shared.db import run_query

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Hardcoded fallbacks (used when the config table is empty / missing)
# These mirror the values previously scattered across queries.py and
# summary_table.py and must not be changed without updating the DB seed.
# --------------------------------------------------------------------------- #
_FALLBACK: dict[str, list[str]] = {
    "COGS":    ["6211", "6221", "6222", "6223", "6224", "6225"],
    "EXPENSE": ["6273", "6411", "6412", "6413", "6414", "6421", "6428"],
}


def get_active_accounts(category: str) -> list[str]:
    """
    Return list of active account_numbers for the given category.
    Falls back to hardcoded defaults when the table is empty or missing.
    """
    try:
        df = run_query(
            "SELECT account_number FROM pl_account_config "
            "WHERE category = %s AND is_active = true "
            "ORDER BY account_number",
            (category,),
        )
        if df is not None and not df.empty:
            return df["account_number"].tolist()
    except Exception:
        logger.debug(
            "pl_account_config unavailable or empty for category=%s — using fallback",
            category,
        )
    return _FALLBACK.get(category, []).copy()


def get_cogs_accounts() -> list[str]:
    """Return active COGS account numbers."""
    return get_active_accounts("COGS")


def get_expense_accounts() -> list[str]:
    """Return active EXPENSE account numbers."""
    return get_active_accounts("EXPENSE")


def sql_in_list(accounts: list[str]) -> str:
    """
    Format a list of account numbers as a SQL-safe single-quoted, comma-separated string
    for use inside an IN (...) clause.

    e.g. ['6211', '6221'] -> "'6211','6221'"

    If the list is empty, returns '0' so the IN clause is syntactically valid but
    matches nothing (avoids a SQL parse error).
    """
    if not accounts:
        return "'0'"
    return ",".join(f"'{a}'" for a in accounts)
