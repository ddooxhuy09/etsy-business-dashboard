"""
Executable entrypoint for Windows/PyInstaller.

Why this exists:
- `api/main.py` only defines the FastAPI `app` object. If you package that file directly,
  the program will start and immediately exit (no server process).
- This script starts Uvicorn so the `.exe` stays running and prints logs to the console.
"""

from __future__ import annotations

import os
from pathlib import Path
from multiprocessing import freeze_support

# Load .env file if exists
try:
    from dotenv import load_dotenv
    # Load .env from project root
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try loading from current directory
        load_dotenv()
except ImportError:
    # python-dotenv not installed, skip loading .env
    pass


def main() -> None:
    # Import the FastAPI app explicitly so PyInstaller detects and bundles `api/*`.
    # If we only pass "api.main:app" as a string to uvicorn, PyInstaller may miss it,
    # leading to: ModuleNotFoundError("No module named 'api'") at runtime.
    from api.main import app  # noqa: F401

    import uvicorn

    # Railway automatically sets PORT environment variable
    # Use 0.0.0.0 to bind to all interfaces (required for Railway)
    host = os.getenv("DASHBOARD_HOST") or os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("DASHBOARD_PORT", "8001"))

    print(f"[dashboard] starting server at http://{host}:{port}/")
    print("[dashboard] press Ctrl+C to stop")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("DASHBOARD_LOG_LEVEL", "info"),
        reload=False,
    )


if __name__ == "__main__":
    freeze_support()
    try:
        main()
    except Exception as e:
        import traceback

        # If user double-clicks the exe and something crashes early, keep the window visible.
        traceback.print_exc()
        print(f"[dashboard] failed to start: {e!r}")
        input("Press Enter to exit...")

