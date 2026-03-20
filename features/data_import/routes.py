"""
Import CSV by month: upload files to Supabase Storage bucket etsy-raw-data/{YYYY}-{MM}/ and run ETL.
Each folder has manifest.json to track uploaded files.
"""
import json
import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Form, File, UploadFile, Query, HTTPException
import pandas as pd

from config import get_app_root

if not getattr(sys, "frozen", False) and str(get_app_root()) not in sys.path:
    sys.path.insert(0, str(get_app_root()))

from pipelines.run_etl import run_etl as run_etl_pipeline
from etl.expected_columns import validate_columns, RAW_COLUMNS_BY_KEY
from config import get_available_raw_periods, get_period_for_date, parse_period
from shared.storage import (
    upload_file_to_storage,
    file_exists_in_storage,
    delete_file_from_storage,
    read_json_from_storage,
    write_json_to_storage,
    list_files_in_folder,
    list_all_periods,
    add_period_to_list,
    verify_supabase_setup
)

router = APIRouter(prefix="/api/import", tags=["import"])

MANIFEST_FILENAME = "manifest.json"
ETL_STATUS_FILENAME = "etl_status.json"

FILE_KEYS = [
    ("statement", "etsy_statement_{year}_{month}.csv"),
    ("direct_checkout", "EtsyDirectCheckoutPayments{year}-{month}.csv"),
    ("listing", "EtsyListingsDownload.csv"),
    ("sold_order_items", "EtsySoldOrderItems{year}-{month}.csv"),
    ("sold_orders", "EtsySoldOrders{year}-{month}.csv"),
    ("deposits", "EtsyDeposits{year}-{month}.csv"),
]


def _period(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _filename_default(key: str, year: int, month: int) -> str:
    for k, pat in FILE_KEYS:
        if k == key:
            return pat.format(year=year, month=month)
    return ""


def _matches_key(key: str, filename: str) -> bool:
    if not filename or not filename.lower().endswith(".csv"):
        return False
    if key == "listing":
        return filename == "EtsyListingsDownload.csv"
    if key == "statement":
        return filename.startswith("etsy_statement_")
    if key == "direct_checkout":
        return "EtsyDirectCheckoutPayments" in filename
    if key == "sold_order_items":
        return "EtsySoldOrderItems" in filename
    if key == "sold_orders":
        return filename.startswith("EtsySoldOrders") and "EtsySoldOrderItems" not in filename
    if key == "deposits":
        return filename.startswith("EtsyDeposits")
    return False


def _find_files_by_pattern(key: str, storage_file_map: dict) -> list:
    out = []
    for fname, size in storage_file_map.items():
        if _matches_key(key, fname):
            out.append({"filename": fname, "size": size})
    return out


def _manifest_entries(ent) -> list:
    if not ent:
        return []
    if isinstance(ent, dict) and ent.get("filename"):
        return [ent]
    if isinstance(ent, list):
        return [e for e in ent if isinstance(e, dict) and e.get("filename")]
    return []


@router.get("/verify")
def verify_storage_setup():
    """Verify Supabase Storage configuration and bucket access."""
    return verify_supabase_setup()


@router.get("/periods")
def list_periods():
    """List period folders in Supabase Storage bucket (YYYY-MM format)."""
    periods_list = list_all_periods()

    if not periods_list:
        return {"periods": [], "metadata": {}}

    result = []
    for p in periods_list:
        try:
            year, month = parse_period(p)
            etl = _read_etl_status(year, month)
            snapshot = _get_file_snapshot(year, month)
            file_count = len([k for k, files in snapshot.items() if files])
            result.append({
                "period": p,
                "etl_done_at": etl.get("etl_done_at") if etl else None,
                "file_count": file_count,
            })
        except Exception:
            pass

    return {
        "periods": [r["period"] for r in result],
        "metadata": {r["period"]: {"etl_done_at": r["etl_done_at"], "file_count": r["file_count"]} for r in result}
    }


def _is_valid_period_format(folder_name: str) -> bool:
    import re
    return bool(re.match(r"^\d{4}-\d{2}$", folder_name))


@router.post("/periods")
def create_period(
    year: int = Form(..., ge=2000, le=2100),
    month: int = Form(..., ge=1, le=12),
):
    """Create a new data period (year-month) in Supabase Storage bucket."""
    period = get_period_for_date(year, month)

    try:
        add_success = add_period_to_list(period)
        if not add_success:
            print(f"Warning: Failed to add period {period} to periods.json, but continuing...")

        manifest_path = f"{period}/{MANIFEST_FILENAME}"
        manifest_exists = file_exists_in_storage(manifest_path)

        if not manifest_exists:
            manifest_result = _write_manifest(year, month, {})
            if manifest_result:
                print(f"Successfully created manifest for {period}")
            else:
                print(f"Failed to create manifest for {period}")

        periods = list_all_periods()
        if period not in periods:
            periods.append(period)
            periods = sorted(periods)

        return {"ok": True, "period": period, "periods": periods}
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error creating period {period}: {e}")
        print(error_trace)
        return {"ok": False, "period": period, "periods": list_all_periods(), "error": str(e), "traceback": error_trace}


def _read_manifest(year: int, month: int) -> dict:
    period = _period(year, month)
    file_path = f"{period}/{MANIFEST_FILENAME}"
    result = read_json_from_storage(file_path)
    return result if result is not None else {}


def _write_manifest(year: int, month: int, data: dict) -> bool:
    period = _period(year, month)
    file_path = f"{period}/{MANIFEST_FILENAME}"
    result = write_json_to_storage(file_path, data)
    if not result:
        print(f"Failed to write manifest.json to {file_path}")
    return result


def _get_file_snapshot(year: int, month: int) -> dict:
    period = _period(year, month)
    man = _read_manifest(year, month)

    storage_files = list_files_in_folder(period)
    storage_file_map = {f.get("name"): f.get("metadata", {}).get("size", 0) for f in storage_files if storage_files}

    out = {}
    for key, _ in FILE_KEYS:
        entries = _manifest_entries(man.get(key))
        if not entries:
            fname = _filename_default(key, year, month)
            if fname and fname in storage_file_map:
                out[key] = [{"filename": fname, "size": storage_file_map[fname]}]
                continue
            found = _find_files_by_pattern(key, storage_file_map)
            if found:
                out[key] = found
            continue
        arr = []
        for e in entries:
            fname = e.get("filename")
            if fname and fname in storage_file_map:
                arr.append({"filename": fname, "size": storage_file_map[fname]})
        if arr:
            out[key] = arr
    return out


def _read_etl_status(year: int, month: int) -> dict | None:
    period = _period(year, month)
    file_path = f"{period}/{ETL_STATUS_FILENAME}"
    return read_json_from_storage(file_path)


def _write_etl_status(year: int, month: int, etl_done_at: str, files_snapshot: dict) -> None:
    period = _period(year, month)
    file_path = f"{period}/{ETL_STATUS_FILENAME}"
    data = {"etl_done_at": etl_done_at, "files_snapshot": files_snapshot}
    write_json_to_storage(file_path, data)


def _same_snapshot(snap: dict, current: dict) -> bool:
    if set(snap.keys()) != set(current.keys()):
        return False
    for k in snap:
        sa = snap[k] if isinstance(snap[k], list) else [snap[k]]
        ca = current[k] if isinstance(current[k], list) else [current[k]]
        if len(sa) != len(ca):
            return False
        for i, (s, c) in enumerate(zip(sa, ca)):
            if s.get("filename") != c.get("filename") or s.get("size") != c.get("size"):
                return False
    return True


@router.get("/expected-columns")
def get_expected_columns():
    """List expected raw column names for each file type."""
    return {"columns_by_key": {k: v for k, v in RAW_COLUMNS_BY_KEY.items() if v}}


@router.get("/files")
def list_files(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    """List files already imported for a period from Supabase Storage."""
    period = _period(year, month)
    man = _read_manifest(year, month)

    storage_files = list_files_in_folder(period)
    storage_file_map = {f.get("name"): f.get("metadata", {}).get("size", 0) for f in storage_files if storage_files}

    out = {}
    for key, _ in FILE_KEYS:
        entries = _manifest_entries(man.get(key))
        if not entries:
            fname = _filename_default(key, year, month)
            if fname and fname in storage_file_map:
                entries = [{"filename": fname, "size": storage_file_map[fname], "uploaded_at": None}]
            else:
                found = _find_files_by_pattern(key, storage_file_map)
                if found:
                    entries = [{"filename": e["filename"], "size": e["size"], "uploaded_at": None} for e in found]
                else:
                    out[key] = {"filename": fname or "", "exists": False, "size": 0, "uploaded_at": None, "files": []}
                    continue
        files = []
        total_size = 0
        any_exists = False
        for e in entries:
            fname = e.get("filename", "")
            ex = fname in storage_file_map
            sz = storage_file_map.get(fname, e.get("size", 0))
            files.append({"filename": fname, "size": sz, "uploaded_at": e.get("uploaded_at"), "exists": ex})
            total_size += sz
            any_exists = any_exists or ex
        out[key] = {
            "filename": ", ".join(f["filename"] for f in files) if files else _filename_default(key, year, month),
            "exists": any_exists,
            "size": total_size,
            "uploaded_at": files[0].get("uploaded_at") if files else None,
            "files": files,
        }

    etl = _read_etl_status(year, month)
    return {"period": _period(year, month), "files": out, "etl_done_at": etl.get("etl_done_at") if etl else None}


@router.post("/upload")
async def upload(
    year: int = Form(..., ge=2000, le=2100),
    month: int = Form(..., ge=1, le=12),
    statement: UploadFile = File(None),
    direct_checkout: UploadFile = File(None),
    listing: UploadFile = File(None),
    sold_order_items: UploadFile = File(None),
    sold_orders: UploadFile = File(None),
    deposits: UploadFile = File(None),
):
    """Upload CSV files to Supabase Storage bucket etsy-raw-data/{year}-{month}/, update manifest.json."""
    uploads = {
        "statement": statement, "direct_checkout": direct_checkout, "listing": listing,
        "sold_order_items": sold_order_items, "sold_orders": sold_orders, "deposits": deposits,
    }
    saved = []
    t = datetime.now(timezone.utc).isoformat()
    period = _period(year, month)
    validation = {}

    for key, u in uploads.items():
        if u is None or u.filename is None or u.filename == "":
            continue

        try:
            content = await u.read()
        except Exception as e:
            validation[key] = {"ok": False, "errors": [f"Không đọc được file: {e}"]}
            continue

        errs = []
        try:
            df = pd.read_csv(io.BytesIO(content), nrows=0, encoding="utf-8")
            errs = validate_columns(key, df.columns.tolist())
        except Exception as e:
            errs = [f"Không đọc được header CSV: {e}"]

        validation[key] = {"ok": len(errs) == 0, "errors": errs}

        if errs:
            continue

        raw = (u.filename or "").strip()
        fname = Path(raw).name if raw else _filename_default(key, year, month)
        if not fname.lower().endswith(".csv"):
            fname = fname + ".csv"

        period = _period(year, month)
        storage_path = f"{period}/{fname}"

        stem, suf = Path(fname).stem, Path(fname).suffix
        n = 1
        while file_exists_in_storage(storage_path):
            fname = f"{stem} ({n}){suf}"
            storage_path = f"{period}/{fname}"
            n += 1

        try:
            upload_result = upload_file_to_storage(
                file_path=storage_path, file_content=content, content_type="text/csv", upsert=True
            )
            if upload_result["success"]:
                saved.append({"key": key, "filename": fname, "size": len(content), "storage_path": storage_path})
            else:
                validation[key] = {"ok": False, "errors": [f"Failed to upload to storage: {upload_result.get('error', 'Unknown error')}"]}
        except Exception as e:
            validation[key] = {"ok": False, "errors": [f"Failed to upload: {e}"]}

    if saved:
        m = _read_manifest(year, month)
        for s in saved:
            prev = _manifest_entries(m.get(s["key"]))
            new_entry = {"filename": s["filename"], "size": s["size"], "uploaded_at": t}
            m[s["key"]] = prev + [new_entry]
        _write_manifest(year, month, m)

    return {"period": _period(year, month), "saved": saved, "validation": validation}


@router.delete("/files")
def delete_file(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    key: str = Query(..., description="Loại file (statement, sold_orders, ...)"),
    filename: str = Query(..., description="Tên file cần xóa"),
):
    """Delete an uploaded file from Supabase Storage. Updates manifest.json."""
    period = _period(year, month)
    man = _read_manifest(year, month)

    entries = _manifest_entries(man.get(key))
    updated_entries = [e for e in entries if e.get("filename") != filename]

    storage_path = f"{period}/{filename}"
    delete_result = delete_file_from_storage(storage_path)

    if not delete_result["success"]:
        if "not found" not in delete_result.get("error", "").lower():
            raise HTTPException(status_code=500, detail=f"Không thể xóa file từ storage: {delete_result.get('error', 'Unknown error')}")

    if updated_entries:
        man[key] = updated_entries
    else:
        man.pop(key, None)

    _write_manifest(year, month, man)

    period = _period(year, month)
    etl_status_path = f"{period}/{ETL_STATUS_FILENAME}"
    delete_file_from_storage(etl_status_path)

    return {"ok": True, "message": f"Đã xóa file {filename}"}


@router.post("/run-etl")
def run_etl_endpoint(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    force: bool = Query(False, description="Run ETL even if files haven't changed"),
):
    """Run ETL in-process. Skips if already run and files unchanged (unless force=True)."""
    period = _period(year, month)

    storage_files = list_files_in_folder(period)
    if not storage_files:
        raise HTTPException(status_code=400, detail=f"Kỳ dữ liệu {period} chưa có file trong Storage. Hãy tải file lên trước.")

    current = _get_file_snapshot(year, month)
    if not force:
        etl = _read_etl_status(year, month)
        if etl and _same_snapshot(etl.get("files_snapshot") or {}, current):
            return {
                "ok": True,
                "message": "Đã ETL rồi, file không thay đổi. Bỏ qua. (Bật 'Force' nếu cần chạy lại.)",
                "skipped": True,
                "stdout": "",
                "stderr": "",
                "etl_done_at": etl.get("etl_done_at"),
            }

    try:
        r = run_etl_pipeline(period=period, clean_existing=True, raw_base=None)
        if r.get("ok"):
            _write_etl_status(year, month, datetime.now(timezone.utc).isoformat(), current)
        return r
    except Exception as e:
        return {"ok": False, "message": str(e), "stdout": "", "stderr": ""}
