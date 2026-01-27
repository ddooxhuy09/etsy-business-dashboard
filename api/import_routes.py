"""
Import CSV by month: upload files to Supabase Storage bucket etsy-raw-data/{YYYY}-{MM}/ và chạy ETL.
Mỗi thư mục có manifest.json để ghi nhận file đã import (hoặc dùng pattern tên file).
"""
import json
import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Form, File, UploadFile, Query, HTTPException
import pandas as pd

# Khi chạy từ exe: cần add app root vào sys.path để import được modules.
from config import get_app_root

if not getattr(sys, "frozen", False) and str(get_app_root()) not in sys.path:
    sys.path.insert(0, str(get_app_root()))

from pipelines.run_etl import run_etl as run_etl_pipeline
from etl.expected_columns import validate_columns, RAW_COLUMNS_BY_KEY
from config import get_available_raw_periods, get_period_for_date, parse_period
from api.storage import (
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


@router.get("/verify")
def verify_storage_setup():
    """
    Verify Supabase Storage configuration and bucket access.
    Use this endpoint to diagnose RLS policy errors.
    """
    return verify_supabase_setup()
ETL_STATUS_FILENAME = "etl_status.json"

# (key, filename pattern mặc định). Key trùng với csv_loader (manifest) khi cần.
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


def _manifest_entries(ent) -> list:
    """Chuyển manifest entry (dict cũ hoặc list) thành list [{filename, size?, uploaded_at?}]."""
    if not ent:
        return []
    if isinstance(ent, dict) and ent.get("filename"):
        return [ent]
    if isinstance(ent, list):
        return [e for e in ent if isinstance(e, dict) and e.get("filename")]
    return []


# _dir() function removed - no longer needed as we use Supabase Storage


# _manifest_path() removed - using Supabase Storage now


@router.get("/periods")
def list_periods():
    """
    Danh sách các folder kỳ dữ liệu đang có trong Supabase Storage bucket (định dạng YYYY-MM).
    Trả về metadata (etl_done_at, file_count) cho mỗi period.
    Hiển thị tất cả periods, kể cả khi chưa có files (để user có thể upload).
    """
    # List all periods from Supabase Storage
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
            
            # Include all periods, even if they have no files yet
            # This allows users to see newly created periods and upload files
            result.append({
                "period": p,
                "etl_done_at": etl.get("etl_done_at") if etl else None,
                "file_count": file_count,
            })
        except Exception:
            # Skip periods that cause errors
            pass
    
    return {"periods": [r["period"] for r in result], "metadata": {r["period"]: {"etl_done_at": r["etl_done_at"], "file_count": r["file_count"]} for r in result}}


def _is_valid_period_format(folder_name: str) -> bool:
    """Check if folder name matches YYYY-MM format"""
    import re
    return bool(re.match(r"^\d{4}-\d{2}$", folder_name))


@router.post("/periods")
def create_period(
    year: int = Form(..., ge=2000, le=2100),
    month: int = Form(..., ge=1, le=12),
):
    """
    Tạo kỳ dữ liệu mới (năm-tháng) trong Supabase Storage bucket.
    Nếu đã tồn tại thì chỉ đơn giản trả về danh sách kỳ.
    """
    # Chuẩn hóa period
    period = get_period_for_date(year, month)

    try:
        # Add period to periods list (will be shown when files are uploaded)
        add_success = add_period_to_list(period)
        if not add_success:
            print(f"Warning: Failed to add period {period} to periods.json, but continuing...")
        
        # Create empty manifest.json if it doesn't exist yet
        manifest_path = f"{period}/{MANIFEST_FILENAME}"
        manifest_exists = file_exists_in_storage(manifest_path)
        print(f"Manifest exists for {period}: {manifest_exists}")
        
        if not manifest_exists:
            manifest_result = _write_manifest(year, month, {})
            if manifest_result:
                print(f"Successfully created manifest for {period}")
            else:
                print(f"Failed to create manifest for {period}")
        else:
            print(f"Manifest already exists for {period}")

        # Get updated periods list
        periods = list_all_periods()
        print(f"Current periods list: {periods}")
        
        # Ensure the created period is in the list
        if period not in periods:
            periods.append(period)
            periods = sorted(periods)
            print(f"Added {period} to periods list: {periods}")
        
        return {"ok": True, "period": period, "periods": periods}
    except Exception as e:
        # Return error if something fails
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error creating period {period}: {e}")
        print(error_trace)
        return {"ok": False, "period": period, "periods": list_all_periods(), "error": str(e), "traceback": error_trace}


def _read_manifest(year: int, month: int) -> dict:
    """Read manifest.json from Supabase Storage. Returns {} if file doesn't exist or is empty."""
    period = _period(year, month)
    file_path = f"{period}/{MANIFEST_FILENAME}"
    result = read_json_from_storage(file_path)
    # Return empty dict if file doesn't exist, or the actual content if it exists
    return result if result is not None else {}


def _write_manifest(year: int, month: int, data: dict) -> bool:
    """Write manifest.json to Supabase Storage. Returns True if successful."""
    period = _period(year, month)
    file_path = f"{period}/{MANIFEST_FILENAME}"
    result = write_json_to_storage(file_path, data)
    if not result:
        print(f"Failed to write manifest.json to {file_path}")
    return result


def _get_file_snapshot(year: int, month: int) -> dict:
    """Trả về {key: [{filename, size}, ...]} cho các file tồn tại trong Supabase Storage."""
    period = _period(year, month)
    man = _read_manifest(year, month)
    
    # List all files in the period folder from Storage
    storage_files = list_files_in_folder(period)
    storage_file_map = {f.get("name"): f.get("metadata", {}).get("size", 0) for f in storage_files if storage_files}
    
    out = {}
    for key, _ in FILE_KEYS:
        entries = _manifest_entries(man.get(key))
        if not entries:
            # Fallback: file mặc định
            fname = _filename_default(key, year, month)
            if fname and fname in storage_file_map:
                out[key] = [{"filename": fname, "size": storage_file_map[fname]}]
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
    """Read etl_status.json from Supabase Storage."""
    period = _period(year, month)
    file_path = f"{period}/{ETL_STATUS_FILENAME}"
    return read_json_from_storage(file_path)


def _write_etl_status(year: int, month: int, etl_done_at: str, files_snapshot: dict) -> None:
    """Write etl_status.json to Supabase Storage."""
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
    """Danh sách tên cột raw (header CSV) mong đợi cho từng loại file. Dùng để kiểm tra định dạng."""
    return {"columns_by_key": {k: v for k, v in RAW_COLUMNS_BY_KEY.items() if v}}


@router.get("/files")
def list_files(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    """Danh sách file đã import từ Supabase Storage. Mỗi key có thể có nhiều file (list)."""
    period = _period(year, month)
    man = _read_manifest(year, month)
    
    # Get files from Storage
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
    """Upload CSV files to Supabase Storage bucket etsy-raw-data/{year}-{month}/, cập nhật manifest.json."""
    uploads = {
        "statement": statement,
        "direct_checkout": direct_checkout,
        "listing": listing,
        "sold_order_items": sold_order_items,
        "sold_orders": sold_orders,
        "deposits": deposits,
    }
    saved = []
    t = datetime.now(timezone.utc).isoformat()
    period = _period(year, month)

    # Validate và lưu file
    validation = {}
    
    for key, u in uploads.items():
        if u is None or u.filename is None or u.filename == "":
            continue
        
        # Đọc file vào memory để validate
        try:
            content = await u.read()
        except Exception as e:
            validation[key] = {"ok": False, "errors": [f"Không đọc được file: {e}"]}
            continue
        
        # Validate header CSV trước khi lưu
        errs = []
        try:
            df = pd.read_csv(io.BytesIO(content), nrows=0, encoding="utf-8")
            errs = validate_columns(key, df.columns.tolist())
        except Exception as e:
            errs = [f"Không đọc được header CSV: {e}"]
        
        validation[key] = {"ok": len(errs) == 0, "errors": errs}
        
        # Nếu có lỗi validation, không lưu file
        if errs:
            continue
        
        # Upload file to Supabase Storage
        raw = (u.filename or "").strip()
        fname = Path(raw).name if raw else _filename_default(key, year, month)
        if not fname.lower().endswith(".csv"):
            fname = fname + ".csv"
        
        # Storage path: {year}-{month}/filename.csv
        period = _period(year, month)
        storage_path = f"{period}/{fname}"
        
        # Không ghi đè: nếu đã tồn tại thì thêm hậu tố (1), (2), ...
        stem, suf = Path(fname).stem, Path(fname).suffix
        n = 1
        while file_exists_in_storage(storage_path):
            fname = f"{stem} ({n}){suf}"
            storage_path = f"{period}/{fname}"
            n += 1
        
        try:
            # Upload to Supabase Storage
            upload_result = upload_file_to_storage(
                file_path=storage_path,
                file_content=content,
                content_type="text/csv",
                upsert=True
            )
            
            if upload_result["success"]:
                saved.append({
                    "key": key,
                    "filename": fname,
                    "size": len(content),
                    "storage_path": storage_path
                })
            else:
                validation[key] = {"ok": False, "errors": [f"Failed to upload to storage: {upload_result.get('error', 'Unknown error')}"]}
        except Exception as e:
            validation[key] = {"ok": False, "errors": [f"Failed to upload: {e}"]}

    # Chỉ cập nhật manifest nếu có file được lưu thành công
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
    """Xóa một file đã upload từ Supabase Storage. Cập nhật manifest.json."""
    period = _period(year, month)
    man = _read_manifest(year, month)
    
    # Tìm và xóa file trong manifest
    entries = _manifest_entries(man.get(key))
    updated_entries = [e for e in entries if e.get("filename") != filename]
    
    # Xóa file từ Supabase Storage
    storage_path = f"{period}/{filename}"
    delete_result = delete_file_from_storage(storage_path)
    
    if not delete_result["success"]:
        # Nếu file không tồn tại trong storage, vẫn tiếp tục (có thể đã bị xóa trước đó)
        if "not found" not in delete_result.get("error", "").lower():
            raise HTTPException(status_code=500, detail=f"Không thể xóa file từ storage: {delete_result.get('error', 'Unknown error')}")
    
    # Cập nhật manifest
    if updated_entries:
        man[key] = updated_entries
    else:
        man.pop(key, None)
    
    _write_manifest(year, month, man)
    
    # Nếu đã ETL rồi, xóa trạng thái ETL từ Storage (vì file đã thay đổi)
    period = _period(year, month)
    etl_status_path = f"{period}/{ETL_STATUS_FILENAME}"
    delete_file_from_storage(etl_status_path)  # Ignore errors if file doesn't exist
    
    return {"ok": True, "message": f"Đã xóa file {filename}"}


@router.post("/run-etl")
def run_etl_endpoint(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    force: bool = Query(False, description="Chạy ETL dù file không đổi (đã ETL rồi)"),
):
    """Chạy ETL in-process. Nếu đã ETL rồi và files không đổi thì bỏ qua (trừ khi force=True)."""
    period = _period(year, month)
    
    # Check if period has files in Storage
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
        # Default: ETL sẽ tải input từ Supabase Storage về thư mục tạm (không dùng data/raw).
        r = run_etl_pipeline(period=period, clean_existing=True, raw_base=None)
        if r.get("ok"):
            _write_etl_status(year, month, datetime.now(timezone.utc).isoformat(), current)
        return r
    except Exception as e:
        return {"ok": False, "message": str(e), "stdout": "", "stderr": ""}
