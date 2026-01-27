"""
Supabase Storage helper for uploading CSV files.
"""
import os
from pathlib import Path
from typing import Optional, List, Dict
from supabase import create_client, Client
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

BUCKET_NAME = "etsy-raw-data"


def verify_supabase_setup() -> dict:
    """
    Verify Supabase configuration and bucket access.
    
    Returns:
        dict with verification results
    """
    result = {
        "url_set": False,
        "key_set": False,
        "key_type": None,  # "service_role" or "anon" or None
        "bucket_exists": False,
        "bucket_accessible": False,
        "errors": []
    }
    
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        result["url_set"] = bool(supabase_url)
        result["key_set"] = bool(supabase_key)
        
        if not supabase_url:
            result["errors"].append("SUPABASE_URL not set in .env")
            return result
        
        if not supabase_key:
            result["errors"].append(
                "SUPABASE_SERVICE_ROLE_KEY not set in .env. "
                "Get it from Supabase Dashboard > Settings > API > service_role key (secret)"
            )
            return result
        
        # Try to decode JWT to check key type
        try:
            import base64
            import json
            # JWT has 3 parts: header.payload.signature
            parts = supabase_key.split(".")
            if len(parts) >= 2:
                # Decode payload (add padding if needed)
                payload = parts[1]
                payload += "=" * (4 - len(payload) % 4)  # Add padding
                decoded = json.loads(base64.urlsafe_b64decode(payload))
                role = decoded.get("role", "unknown")
                result["key_type"] = role
                
                if role != "service_role":
                    result["errors"].append(
                        f"Key appears to be '{role}' key, not 'service_role' key. "
                        "Service Role Key is required to bypass RLS policies. "
                        "Get it from Supabase Dashboard > Settings > API > service_role key (secret)"
                    )
        except Exception:
            # Can't decode, but that's okay - might still work
            pass
        
        # Try to access bucket
        try:
            supabase = create_client(supabase_url, supabase_key)
            bucket = supabase.storage.from_(BUCKET_NAME)
            
            # Try to list bucket (this will fail if bucket doesn't exist or RLS blocks it)
            try:
                bucket.list("")
                result["bucket_exists"] = True
                result["bucket_accessible"] = True
            except Exception as e:
                error_msg = str(e).lower()
                if "not found" in error_msg or "does not exist" in error_msg:
                    result["errors"].append(
                        f"Bucket '{BUCKET_NAME}' does not exist. "
                        f"Create it in Supabase Dashboard > Storage > New Bucket"
                    )
                elif "row-level security" in error_msg or "rls" in error_msg:
                    result["errors"].append(
                        "RLS policy error: Bucket exists but access is denied. "
                        "Make sure you're using Service Role Key (not anon key)."
                    )
                else:
                    result["errors"].append(f"Cannot access bucket: {e}")
        except Exception as e:
            result["errors"].append(f"Failed to create Supabase client: {e}")
    
    except Exception as e:
        result["errors"].append(f"Verification error: {e}")
    
    return result


def get_supabase_client() -> Client:
    """Get Supabase client for Storage operations.
    
    IMPORTANT: Must use Service Role Key (not anon key) to bypass RLS policies
    for Storage operations. Service Role Key has full access and bypasses RLS.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    # MUST use Service Role Key for Storage operations to bypass RLS
    # Anon key will fail with RLS policy errors
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL must be set in .env")
    
    if not supabase_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY (Service Role Key) must be set in .env. "
            "This key bypasses RLS policies and is required for Storage operations. "
            "Get it from Supabase Dashboard > Settings > API > service_role key (secret)"
        )
    
    return create_client(supabase_url, supabase_key)


def upload_file_to_storage(
    file_path: str,
    file_content: bytes,
    content_type: str = "text/csv",
    upsert: bool = True
) -> dict:
    """
    Upload file to Supabase Storage.
    
    Note: Folders are created automatically when uploading to a path like "folder/file.txt".
    The folder "folder" will be created automatically if it doesn't exist.
    
    Args:
        file_path: Path in bucket (e.g., "2025-01/etsy_statement_2025_1.csv")
        file_content: File content as bytes
        content_type: MIME type (default: text/csv)
        upsert: If True, overwrite existing file; if False, fail if exists
    
    Returns:
        dict with success status and file info
    """
    try:
        supabase = get_supabase_client()
        bucket = supabase.storage.from_(BUCKET_NAME)
        
        # Ensure file_path doesn't start with "/"
        file_path = file_path.lstrip("/")
        
        # Upload file
        # Note: upsert must be string "true", not boolean True
        file_opts = {
            "content-type": content_type
        }
        if upsert:
            file_opts["upsert"] = "true"  # Must be string, not boolean
        
        # Upload file - folder will be created automatically if path contains "/"
        response = bucket.upload(
            path=file_path,
            file=file_content,
            file_options=file_opts
        )
        
        # Check if upload was successful
        # Supabase upload() may return None or empty dict on success
        # If there's an error, it will raise an exception
        
        # Get public URL
        try:
            public_url = bucket.get_public_url(file_path)
        except:
            public_url = None
        
        print(f"Successfully uploaded {file_path} to Supabase Storage")
        
        return {
            "success": True,
            "path": file_path,
            "public_url": public_url,
            "response": response
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = str(e)
        
        # Provide helpful error messages
        if "row-level security" in error_msg.lower() or "rls" in error_msg.lower():
            error_msg = (
                f"RLS Policy Error: {error_msg}\n"
                "This usually means:\n"
                "1. You're not using Service Role Key (check SUPABASE_SERVICE_ROLE_KEY in .env)\n"
                "2. The bucket has RLS policies that need to be configured\n"
                "3. The bucket doesn't exist or isn't accessible\n"
                "Solution: Use Service Role Key (not anon key) to bypass RLS policies"
            )
        elif "bucket" in error_msg.lower() and ("not found" in error_msg.lower() or "does not exist" in error_msg.lower()):
            error_msg = (
                f"Bucket Error: {error_msg}\n"
                f"Make sure bucket '{BUCKET_NAME}' exists in your Supabase project.\n"
                "Create it in Supabase Dashboard > Storage > New Bucket"
            )
        
        print(f"Error uploading {file_path} to Supabase Storage: {error_msg}")
        print(error_trace)
        return {
            "success": False,
            "error": error_msg,
            "path": file_path,
            "traceback": error_trace
        }


def delete_file_from_storage(file_path: str) -> dict:
    """
    Delete file from Supabase Storage.
    
    Args:
        file_path: Path in bucket (e.g., "2025-01/etsy_statement_2025_1.csv")
    
    Returns:
        dict with success status
    """
    try:
        supabase = get_supabase_client()
        response = supabase.storage.from_(BUCKET_NAME).remove([file_path])
        
        return {
            "success": True,
            "path": file_path,
            "response": response
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "path": file_path
        }


def list_files_in_folder(folder_path: str) -> list:
    """
    List files in a folder in Supabase Storage.
    
    Args:
        folder_path: Folder path (e.g., "2025-01") or "" for root
    
    Returns:
        List of file info dicts
    """
    try:
        supabase = get_supabase_client()
        bucket = supabase.storage.from_(BUCKET_NAME)
        response = bucket.list(folder_path)
        
        return response if response else []
    except Exception as e:
        import traceback
        print(f"Error listing files in {folder_path}: {e}")
        print(traceback.format_exc())
        return []


def list_all_periods() -> list:
    """
    List all period folders (YYYY-MM) in the bucket.
    Since Supabase Storage doesn't have true folders, we maintain a periods.json file.
    
    Returns:
        List of period strings (e.g., ["2025-01", "2025-02"])
    """
    try:
        # Read periods list from periods.json in root
        periods_data = read_json_from_storage("periods.json")
        if periods_data and isinstance(periods_data, dict):
            periods_list = periods_data.get("periods", [])
            if isinstance(periods_list, list) and periods_list:
                return sorted(periods_list)
        
        # Fallback: try to find periods by listing root level
        # This is less reliable but works if periods.json doesn't exist yet
        supabase = get_supabase_client()
        bucket = supabase.storage.from_(BUCKET_NAME)
        periods_set = set()
        
        # Try to list root level
        root_items = bucket.list("")
        
        if root_items:
            import re
            for item in root_items:
                name = item.get("name", "")
                # If name matches YYYY-MM format exactly, it's a period folder
                if re.match(r"^\d{4}-\d{2}$", name):
                    periods_set.add(name)
        
        return sorted(list(periods_set))
    except Exception as e:
        import traceback
        print(f"Error listing periods: {e}")
        print(traceback.format_exc())
        return []


def save_periods_list(periods: list) -> bool:
    """
    Save list of periods to periods.json in bucket root.
    
    Args:
        periods: List of period strings (e.g., ["2025-01", "2025-02"])
    
    Returns:
        True if successful, False otherwise
    """
    try:
        data = {"periods": sorted(periods)}
        result = write_json_to_storage("periods.json", data)
        if not result:
            print(f"Failed to save periods list: {periods}")
        return result
    except Exception as e:
        import traceback
        print(f"Exception saving periods list: {e}")
        print(traceback.format_exc())
        return False


def add_period_to_list(period: str) -> bool:
    """
    Add a period to the periods list.
    
    Args:
        period: Period string (e.g., "2025-01")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        current_periods = list_all_periods()
        if period not in current_periods:
            current_periods.append(period)
            return save_periods_list(current_periods)
        return True
    except Exception:
        return False


def file_exists_in_storage(file_path: str) -> bool:
    """
    Check if file exists in Supabase Storage.
    
    Args:
        file_path: Path in bucket (e.g., "2025-01/manifest.json")
    
    Returns:
        True if file exists, False otherwise
    """
    try:
        supabase = get_supabase_client()
        bucket = supabase.storage.from_(BUCKET_NAME)
        
        # Extract folder and filename
        if "/" in file_path:
            folder_path = "/".join(file_path.split("/")[:-1])  # e.g., "2025-01"
            file_name = file_path.split("/")[-1]  # e.g., "manifest.json"
        else:
            folder_path = ""
            file_name = file_path
        
        # List files in the folder
        files = bucket.list(folder_path)
        
        if not files:
            return False
        
        # Check if file exists
        return any(f.get("name") == file_name for f in files)
    except Exception as e:
        # If error, assume file doesn't exist
        import traceback
        print(f"Error checking file existence for {file_path}: {e}")
        return False


def download_file_from_storage(file_path: str) -> Optional[bytes]:
    """
    Download file from Supabase Storage.
    
    Args:
        file_path: Path in bucket (e.g., "2025-01/etsy_statement_2025_1.csv")
    
    Returns:
        File content as bytes, or None if error
    """
    try:
        supabase = get_supabase_client()
        response = supabase.storage.from_(BUCKET_NAME).download(file_path)
        return response
    except Exception as e:
        return None


def read_json_from_storage(file_path: str) -> Optional[dict]:
    """
    Read JSON file from Supabase Storage.
    
    Args:
        file_path: Path in bucket (e.g., "2025-01/manifest.json")
    
    Returns:
        Parsed JSON as dict, or None if error or file doesn't exist
    """
    try:
        content = download_file_from_storage(file_path)
        if content is None:
            return None
        import json
        parsed = json.loads(content.decode('utf-8'))
        # Return None for empty dict to distinguish from "file doesn't exist"
        # But for manifest.json, we want to return {} even if empty
        return parsed
    except Exception:
        return None


def write_json_to_storage(file_path: str, data: dict) -> bool:
    """
    Write JSON file to Supabase Storage.
    
    Args:
        file_path: Path in bucket (e.g., "2025-01/manifest.json")
        data: Dictionary to serialize as JSON
    
    Returns:
        True if successful, False otherwise
    """
    try:
        import json
        json_content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        result = upload_file_to_storage(
            file_path=file_path,
            file_content=json_content,
            content_type="application/json",
            upsert=True
        )
        return result["success"]
    except Exception:
        return False
