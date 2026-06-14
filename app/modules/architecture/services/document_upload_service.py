"""
Document Upload Service for ArchiMate Engine

Handles file uploads and storage for multi-modal architecture generation.
Supports PDF, images, Office documents, and text files.
"""

import hashlib
import mimetypes
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app import db
from app.models import User

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "md": "text/markdown",
    "html": "text/html",
    "csv": "text/csv",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


class DocumentUploadService:
    """
    Service for handling document uploads for ArchiMate generation
    """

    # Expose constants on the class so callers can inspect allowed types
    ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS
    MAX_FILE_SIZE = MAX_FILE_SIZE

    def __init__(self, upload_folder: str):
        """
        Initialize upload service

        Args:
            upload_folder: Base directory for file uploads
        """
        self.upload_folder = upload_folder
        self._ensure_upload_directory()

    def _ensure_upload_directory(self):
        """Create upload directory if it doesn't exist"""
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder, exist_ok=True)

        # Create subdirectories by type
        for subdir in ["documents", "images", "spreadsheets", "temp"]:
            subdir_path = os.path.join(self.upload_folder, subdir)
            if not os.path.exists(subdir_path):
                os.makedirs(subdir_path, exist_ok=True)

    def is_allowed_file(self, filename: str) -> bool:
        """
        Check if file extension is allowed

        Args:
            filename: Name of the file

        Returns:
            True if file type is allowed, False otherwise
        """
        if "." not in filename:
            return False
        ext = filename.rsplit(".", 1)[1].lower()
        return ext in self.ALLOWED_EXTENSIONS

    def get_file_type(self, filename: str) -> Optional[str]:
        """
        Get file type category

        Args:
            filename: Name of the file

        Returns:
            'image', 'document', 'text', 'spreadsheet', or None if unknown
        """
        if "." not in filename:
            return None

        ext = filename.rsplit(".", 1)[1].lower()

        if ext in ["png", "jpg", "jpeg", "gif", "svg"]:
            return "image"
        elif ext in ["pdf", "doc", "docx", "ppt", "pptx"]:
            return "document"
        elif ext in ["txt", "md", "html"]:
            return "text"
        elif ext in ["csv", "xls", "xlsx"]:
            return "spreadsheet"
        return None

    def validate_file(self, file: FileStorage) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file

        Args:
            file: Werkzeug FileStorage object

        Returns:
            (is_valid, error_message)
        """
        # Check if file exists
        if not file or not file.filename:
            return False, "No file provided"

        # Check filename
        if file.filename == "":
            return False, "Empty filename"

        # Check file extension
        if not self.is_allowed_file(file.filename):
            return False, (
                "File type not allowed. Allowed types: "
                f"{', '.join(self.ALLOWED_EXTENSIONS.keys())}"
            )

        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        if file_size > self.MAX_FILE_SIZE:
            return False, ("File too large. Maximum size: " f"{self.MAX_FILE_SIZE / 1024 / 1024}MB")

        if file_size == 0:
            return False, "File is empty"

        return True, None

    def save_file(self, file: FileStorage, user_id: int) -> Dict:
        """
        Save uploaded file to disk

        Args:
            file: Werkzeug FileStorage object
            user_id: ID of user uploading the file

        Returns:
            Dictionary with file info: {
                'filename': str,
                'original_filename': str,
                'file_path': str,
                'file_type': str,
                'file_size': int,
                'mime_type': str,
                'hash': str
            }

        Raises:
            ValueError: If file validation fails
        """
        # Validate file
        is_valid, error_msg = self.validate_file(file)
        if not is_valid:
            raise ValueError(error_msg)

        # Get file type
        file_type = self.get_file_type(file.filename)
        if not file_type:
            raise ValueError("Unknown file type")

        # Generate unique filename
        original_filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{user_id}_{timestamp}_{original_filename}"

        # Determine subdirectory
        if file_type == "image":
            subdir = "images"
        elif file_type == "spreadsheet":
            subdir = "spreadsheets"
        else:
            subdir = "documents"
        file_path = os.path.join(self.upload_folder, subdir, filename)

        # Calculate file hash for deduplication
        file.seek(0)
        file_hash = hashlib.sha256(file.read()).hexdigest()
        file.seek(0)

        # Save file
        file.save(file_path)

        # Get file size
        file_size = os.path.getsize(file_path)

        # Get MIME type
        ext = original_filename.rsplit(".", 1)[1].lower()
        mime_type = self.ALLOWED_EXTENSIONS.get(ext, "application/octet-stream")

        return {
            "filename": filename,
            "original_filename": original_filename,
            "file_path": file_path,
            "file_type": file_type,
            "file_size": file_size,
            "mime_type": mime_type,
            "hash": file_hash,
        }

    def delete_file(self, file_path: str) -> bool:
        """
        Delete file from disk

        Args:
            file_path: Path to file

        Returns:
            True if deleted, False if file doesn't exist
        """
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

    def get_file_info(self, file_path: str) -> Optional[Dict]:
        """
        Get information about a file

        Args:
            file_path: Path to file

        Returns:
            Dictionary with file info or None if file doesn't exist
        """
        if not os.path.exists(file_path):
            return None

        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)

        return {
            "file_path": file_path,
            "file_size": file_size,
            "mime_type": mime_type,
            "exists": True,
            "modified_at": datetime.fromtimestamp(os.path.getmtime(file_path)),
        }
