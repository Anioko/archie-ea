"""
Import Batch v2 utility helpers.

Shared helpers for the import batch v2 module routes.
"""
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "json"}
MAX_FILE_SIZE_MB = int(os.environ.get("IMPORT_MAX_FILE_SIZE_MB", "50"))


def allowed_file(filename: str) -> bool:
    """Check if a filename has an allowed extension.

    Args:
        filename: The original filename from upload.

    Returns:
        True if extension is in ALLOWED_EXTENSIONS.
    """
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def file_size_ok(content_length: Optional[int]) -> bool:
    """Check if file size is within the allowed limit.

    Args:
        content_length: Content-Length header value in bytes.

    Returns:
        True if within limit or if content_length is unknown.
    """
    if content_length is None:
        return True
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    return content_length <= max_bytes


def sanitize_import_error(error: Exception) -> str:
    """Sanitize an import error message for safe display.

    Strips internal paths and stack traces, returning a user-safe message.

    Args:
        error: The caught exception.

    Returns:
        Sanitized error string.
    """
    msg = str(error)
    # Strip file paths
    for prefix in ("C:\\", "/home/", "/app/", "/var/"):
        while prefix in msg:
            start = msg.index(prefix)
            end = msg.find(" ", start)
            if end == -1:
                end = len(msg)
            msg = msg[:start] + "[path]" + msg[end:]
    return msg[:500] if len(msg) > 500 else msg


def format_job_status(status: str) -> Dict[str, str]:
    """Return display label and CSS class for a job status.

    Args:
        status: Raw status string from the database.

    Returns:
        Dict with 'label' and 'css_class' keys.
    """
    mapping = {
        "pending": {"label": "Pending", "css_class": "bg-yellow-100 text-yellow-800"},
        "approved": {"label": "Approved", "css_class": "bg-blue-100 text-blue-800"},
        "processing": {"label": "Processing", "css_class": "bg-indigo-100 text-indigo-800"},
        "completed": {"label": "Completed", "css_class": "bg-green-100 text-green-800"},
        "failed": {"label": "Failed", "css_class": "bg-red-100 text-red-800"},
        "rejected": {"label": "Rejected", "css_class": "bg-gray-100 text-gray-800"},
    }
    return mapping.get(status, {"label": status.title(), "css_class": "bg-gray-100 text-gray-800"})


def safe_int_param(value: Any, default: int = 1, min_val: int = 1, max_val: int = 10000) -> int:
    """Safely parse an integer parameter with clamping.

    Args:
        value: Raw value (str, int, or None).
        default: Default if parsing fails.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        Clamped integer.
    """
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(v, min_val), max_val)
