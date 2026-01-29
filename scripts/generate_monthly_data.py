"""
Generate Etsy CSV data for months 2–12 from January template (datatest/2025-01).
Creates datatest/2025-02 ... datatest/2025-12 with same structure and similar data.
"""
from __future__ import annotations

import calendar
import csv
import re
import shutil
from pathlib import Path


MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

YEAR = 2025
TEMPLATE_MONTH = 1
BASE_DIR = Path(__file__).resolve().parent.parent / "datatest"
TEMPLATE_DIR = BASE_DIR / "2025-01"


def day_in_month(year: int, month: int, day: int) -> int:
    """Clamp day to valid range for year/month."""
    last = calendar.monthrange(year, month)[1]
    return min(day, last)


def parse_mdy(s: str, fmt: str) -> tuple[int, int, int] | None:
    """Parse date string to (month, day, year). Returns None if invalid."""
    try:
        if fmt == "month_dd_yyyy":
            # "January 31, 2025"
            m = re.match(r"(\w+)\s+(\d{1,2}),\s*(\d{4})", s.strip())
            if not m:
                return None
            name, d, y = m.group(1), int(m.group(2)), int(m.group(3))
            mo = next((i for i, n in enumerate(MONTH_NAMES) if n == name), None)
            if mo is None:
                return None
            return mo, d, y
        if fmt == "mmddyy":
            # "01/31/25"
            parts = s.strip().split("/")
            if len(parts) != 3:
                return None
            mo, d, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 2000
            return mo, d, y
        if fmt == "mmddyyyy":
            # "01/31/2025"
            parts = s.strip().split("/")
            if len(parts) != 3:
                return None
            mo, d, y = int(parts[0]), int(parts[1]), int(parts[2])
            return mo, d, y
    except Exception:
        pass
    return None


def format_mdy(mm: int, dd: int, yy: int, fmt: str) -> str:
    if fmt == "month_dd_yyyy":
        return f"{MONTH_NAMES[mm]} {dd}, {yy}"
    if fmt == "mmddyy":
        return f"{mm:02d}/{dd:02d}/{yy % 100:02d}"
    if fmt == "mmddyyyy":
        return f"{mm:02d}/{dd:02d}/{yy:04d}"
    return ""


def shift_date(date_str: str, target_month: int, fmt: str) -> str:
    """Shift date to target month (same day if valid, else last day). Year = YEAR."""
    parsed = parse_mdy(date_str, fmt)
    if not parsed:
        return date_str
    mo, d, y = parsed
    d2 = day_in_month(YEAR, target_month, d)
    return format_mdy(target_month, d2, YEAR, fmt)


def main() -> None:
    base = BASE_DIR
    template = TEMPLATE_DIR
    if not template.exists():
        raise SystemExit(f"Template folder not found: {template}")

    # 1) Listings: same for all months
    listing_src = template / "EtsyListingsDownload.csv"
    if not listing_src.exists():
        raise SystemExit(f"Listings not found: {listing_src}")

    # 2) Load Jan data to build ID mappings and generate monthly files
    deposits_path = template / "EtsyDeposits2025-1.csv"
    dc_path = template / "EtsyDirectCheckoutPayments2025-1.csv"
    orders_path = template / "EtsySoldOrders2025-1.csv"
    items_path = template / "EtsySoldOrderItems2025-1.csv"
    statement_path = template / "etsy_statement_2025_1.csv"

    for p in (deposits_path, dc_path, orders_path, items_path, statement_path):
        if not p.exists():
            raise SystemExit(f"Required file not found: {p}")

    # Unique Order IDs, Payment IDs, Transaction IDs from Jan data
    order_ids_jan: list[str] = []
    payment_ids_jan: list[str] = []
    tx_ids_jan: list[str] = []

    with open(dc_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        dc_rows = list(r)
        dc_header = r.fieldnames or []
    for row in dc_rows:
        oid = (row.get("Order ID") or "").strip()
        pid = (row.get("Payment ID") or "").strip()
        if oid and oid not in order_ids_jan:
            order_ids_jan.append(oid)
        if pid and pid not in payment_ids_jan:
            payment_ids_jan.append(pid)

    with open(items_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        items_rows = list(r)
        items_header = r.fieldnames or []
    for row in items_rows:
        tx = (row.get("Transaction ID") or "").strip()
        if tx and tx not in tx_ids_jan:
            tx_ids_jan.append(tx)

    with open(orders_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        orders_rows = list(r)
        orders_header = r.fieldnames or []

    def gen_mappings(target_month: int):
        """Order ID, Payment ID, Transaction ID mappings for target month."""
        base_o = 358_910_1143 + (target_month - 1) * 1_000_000
        base_p = 172_956_507_441 + (target_month - 1) * 1_000_000
        base_t = 4_469_469_337 + (target_month - 1) * 100_000
        o_map = {old: str(base_o + i) for i, old in enumerate(order_ids_jan)}
        p_map = {old: str(base_p + i) for i, old in enumerate(payment_ids_jan)}
        t_map = {old: str(base_t + i) for i, old in enumerate(tx_ids_jan)}
        return o_map, p_map, t_map

    for month in range(2, 13):
        out_dir = base / f"2025-{month:02d}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Copy listings
        shutil.copy2(listing_src, out_dir / "EtsyListingsDownload.csv")

        o_map, p_map, t_map = gen_mappings(month)

        # Deposits
        dep_out = out_dir / f"EtsyDeposits2025-{month}.csv"
        with open(deposits_path, newline="", encoding="utf-8") as fin:
            r = csv.DictReader(fin)
            dep_header = r.fieldnames or []
            dep_data = list(r)
        with open(dep_out, "w", newline="", encoding="utf-8") as fout:
            w = csv.DictWriter(fout, fieldnames=dep_header)
            w.writeheader()
            for row in dep_data:
                d = dict(row)
                raw = d.get("Date", "")
                new_date = shift_date(raw, month, "month_dd_yyyy")
                if new_date:
                    d["Date"] = new_date
                w.writerow(d)

        # Direct checkout
        dc_out = out_dir / f"EtsyDirectCheckoutPayments2025-{month}.csv"
        with open(dc_out, "w", newline="", encoding="utf-8") as fout:
            w = csv.DictWriter(fout, fieldnames=dc_header)
            w.writeheader()
            for row in dc_rows:
                d = dict(row)
                oid = (d.get("Order ID") or "").strip()
                pid = (d.get("Payment ID") or "").strip()
                if oid and oid in o_map:
                    d["Order ID"] = o_map[oid]
                if pid and pid in p_map:
                    d["Payment ID"] = p_map[pid]
                for col in ("Order Date", "Funds Available"):
                    if col in d and d[col]:
                        d[col] = shift_date(d[col], month, "mmddyyyy")
                w.writerow(d)

        # Sold orders
        ord_out = out_dir / f"EtsySoldOrders2025-{month}.csv"
        with open(ord_out, "w", newline="", encoding="utf-8") as fout:
            w = csv.DictWriter(fout, fieldnames=orders_header)
            w.writeheader()
            for row in orders_rows:
                d = dict(row)
                oid = (d.get("Order ID") or "").strip()
                if oid and oid in o_map:
                    d["Order ID"] = o_map[oid]
                for col in ("Sale Date", "Date Shipped"):
                    if col in d and d[col]:
                        d[col] = shift_date(d[col], month, "mmddyy")
                w.writerow(d)

        # Sold order items
        it_out = out_dir / f"EtsySoldOrderItems2025-{month}.csv"
        with open(it_out, "w", newline="", encoding="utf-8") as fout:
            w = csv.DictWriter(fout, fieldnames=items_header)
            w.writeheader()
            for row in items_rows:
                d = dict(row)
                oid = (d.get("Order ID") or "").strip()
                tx = (d.get("Transaction ID") or "").strip()
                if oid and oid in o_map:
                    d["Order ID"] = o_map[oid]
                if tx and tx in t_map:
                    d["Transaction ID"] = t_map[tx]
                if "Sale Date" in d and d["Sale Date"]:
                    d["Sale Date"] = shift_date(d["Sale Date"], month, "mmddyy")
                for col in ("Date Paid", "Date Shipped"):
                    if col in d and d[col]:
                        d[col] = shift_date(d[col], month, "mmddyyyy")
                w.writerow(d)

        # Statement: text replace (preserve VND formatting)
        st_out = out_dir / f"etsy_statement_2025_{month}.csv"
        month_name = MONTH_NAMES[month]
        with open(statement_path, "r", encoding="utf-8") as fin:
            lines = fin.readlines()

        def replace_statement_line(line: str) -> str:
            out = line
            # "January 31, 2025" -> "February 28, 2025" etc. (template is Jan only)
            pat = re.compile(
                r'"January (\d{1,2}), ' + re.escape(str(YEAR)) + r'"',
                re.IGNORECASE,
            )
            def repl(match):
                day = int(match.group(1))
                d2 = day_in_month(YEAR, month, day)
                return f'"{month_name} {d2}, {YEAR}"'
            out = pat.sub(repl, out)
            # Order #OLD -> Order #NEW
            for old_oid, new_oid in o_map.items():
                out = out.replace(f"Order #{old_oid}", f"Order #{new_oid}")
            # transaction: OLD -> transaction: NEW; multi-quantity: OLD -> multi-quantity: NEW
            for old_tx, new_tx in t_map.items():
                out = out.replace(f"transaction: {old_tx}", f"transaction: {new_tx}")
                out = out.replace(f"multi-quantity: {old_tx}", f"multi-quantity: {new_tx}")
            return out

        with open(st_out, "w", encoding="utf-8") as fout:
            for line in lines:
                fout.write(replace_statement_line(line))

        print(f"Generated {out_dir}")

    print("Done. Months 2025-02 .. 2025-12 created in datatest/.")


if __name__ == "__main__":
    main()
