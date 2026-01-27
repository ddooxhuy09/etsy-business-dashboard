"""
Chạy ETL in-process cho Dashboard.
Gọi SimplifiedETLPipeline từ `src.pipelines.run_etl` (shim local trong repo này).
Thiết lập RAW_BASE để CSVLoader đọc dữ liệu.

Mặc định: tải CSV từ Supabase Storage về thư mục tạm, không dùng `data/raw`.
Chỉ dùng `data/raw` khi truyền `raw_base=...` (legacy/dev).
"""
import logging
import os
import sys
import traceback
from io import StringIO
from pathlib import Path
from typing import Optional

from config import get_app_root

if not getattr(sys, "frozen", False) and str(get_app_root()) not in sys.path:
    sys.path.insert(0, str(get_app_root()))

DEFAULT_RAW_BASE = get_app_root() / "data" / "raw"

_ETSY_MONTHLY_KEYS = [
    "statement",
    "direct_checkout",
    "listing",
    "sold_order_items",
    "sold_orders",
    "deposits",
]


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_json(path: Path, data: dict) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_raw_from_supabase_storage(*, period: str, tmp_root: Path) -> Path:
    """
    Download period inputs from Supabase Storage bucket into a local temp folder
    that matches CSVLoader's expected layout: {RAW_BASE}/{period}/*.csv + manifest.json.
    """
    from api.storage import download_file_from_storage, read_json_from_storage, list_files_in_folder

    period_dir = tmp_root / period
    period_dir.mkdir(parents=True, exist_ok=True)

    # Prefer manifest.json in Storage for deterministic filenames.
    manifest_path = f"{period}/manifest.json"
    manifest = read_json_from_storage(manifest_path) or {}

    # Always materialize manifest locally so CSVLoader can use it.
    _write_json(period_dir / "manifest.json", manifest)

    def _filenames_for_key(key: str) -> list[str]:
        ent = manifest.get(key)
        if isinstance(ent, dict) and ent.get("filename"):
            return [ent["filename"]]
        if isinstance(ent, list):
            return [e["filename"] for e in ent if isinstance(e, dict) and e.get("filename")]
        return []

    # Download only monthly Etsy files. Do NOT download product_catalog/bank_transactions here.
    downloaded_any = False
    for key in _ETSY_MONTHLY_KEYS:
        for filename in _filenames_for_key(key):
            content = download_file_from_storage(f"{period}/{filename}")
            if content is None:
                continue
            _write_bytes(period_dir / filename, content)
            downloaded_any = True

    # Fallback: no manifest entries (or empty manifest). Try listing Storage folder.
    if not downloaded_any:
        items = list_files_in_folder(period) or []
        for item in items:
            name = item.get("name")
            if not name or not isinstance(name, str):
                continue
            if name == "manifest.json":
                continue
            if not name.lower().endswith(".csv"):
                continue
            content = download_file_from_storage(f"{period}/{name}")
            if content is None:
                continue
            _write_bytes(period_dir / name, content)

    return tmp_root


def run_etl(
        period: str,
        clean_existing: bool = True,
        raw_base: Optional[Path] = None,
    ) -> dict:
    import tempfile

    saved = os.environ.get("RAW_BASE")

    log_buf = StringIO()
    handler = logging.StreamHandler(log_buf)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    old_level = root.level
    # Bật DEBUG trong suốt ETL để log đầy đủ (schema mismatch, traceback, sample cols, ...).
    root.setLevel(logging.DEBUG)

    out = {"ok": False, "message": "", "stdout": "", "stderr": ""}

    try:
        # Default behavior: read raw inputs from Supabase Storage, not from local data/raw.
        # If caller explicitly passes raw_base, keep legacy behavior.
        tmp_ctx = None
        if raw_base is not None:
            raw_path = Path(raw_base).resolve()
        else:
            tmp_ctx = tempfile.TemporaryDirectory(prefix="etsy_raw_")
            tmp_root = Path(tmp_ctx.name).resolve()
            raw_path = _prepare_raw_from_supabase_storage(period=period, tmp_root=tmp_root)

        os.environ["RAW_BASE"] = str(raw_path)

        # Kiểm tra định dạng (cột) trước khi chạy ETL
        from etl.loaders.csv_loader import CSVLoader
        from etl.expected_columns import validate_columns

        loader = CSVLoader(period=period)
        raw_datasets = loader.load_all_datasets()
        val_errors = []
        for k, df in raw_datasets.items():
            for e in validate_columns(k, df.columns.tolist()):
                val_errors.append(f"[{k}] {e}")
        if val_errors:
            out["message"] = "Lỗi định dạng file (sai hoặc thiếu cột)."
            out["stderr"] = "\n".join(val_errors)
            return out

        from pipelines.simplified_pipeline import SimplifiedETLPipeline

        pipeline = SimplifiedETLPipeline(period=period, clean_existing=clean_existing)
        success = pipeline.run()

        out["stdout"] = log_buf.getvalue()

        if success:
            out["ok"] = True
            out["message"] = "ETL hoàn thành"
        else:
            out["message"] = "ETL thất bại. Xem log bên dưới."
            out["stderr"] = out["stdout"]

    except Exception as e:
        out["message"] = f"ETL lỗi: {e}"
        out["stdout"] = log_buf.getvalue()
        out["stderr"] = traceback.format_exc()
    finally:
        try:
            # Cleanup temp folder if used.
            if "tmp_ctx" in locals() and tmp_ctx is not None:
                tmp_ctx.cleanup()
        except Exception:
            pass
        if saved is not None:
            os.environ["RAW_BASE"] = saved
        elif "RAW_BASE" in os.environ:
            del os.environ["RAW_BASE"]
        root.removeHandler(handler)
        root.setLevel(old_level)
        handler.close()

    return out
