"""
Unified File Parser Service

Handles parsing of CSV, Excel, and JSON files for application import.
Consolidated from batch_import_service.py and unified_applications_import_routes.py.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pandas as pd
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)


@dataclass
class FileStats:
    """Statistics about a parsed file."""

    filename: str
    format: str
    total_rows: int
    columns: List[str]
    column_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "filename": self.filename,
            "format": self.format,
            "total_rows": self.total_rows,
            "columns": self.columns,
            "column_count": self.column_count,
        }


class FileParser:
    """
    Unified file parser for CSV, Excel, and JSON files.

    Supports both path-based and stream-based parsing.
    """

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}

    # Common column names for application name
    NAME_COLUMN_VARIANTS = [
        "name",
        "Name",
        "NAME",
        "application_name",
        "Application Name",
        "ApplicationName",
        "app_name",
        "App Name",
        "AppName",
        "title",
        "Title",
        "TITLE",
        "application",
        "Application",
        "APPLICATION",
    ]

    def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse file from path and return list of row dictionaries.

        Args:
            file_path: Path to the file to parse

        Returns:
            List of dictionaries, one per row

        Raises:
            ValueError: If file cannot be parsed
        """
        file_ext = os.path.splitext(file_path)[1].lower()

        try:
            if file_ext == ".csv":
                df = pd.read_csv(file_path)
            elif file_ext in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path)
            elif file_ext == ".json":
                df = pd.read_json(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

            # Convert NaN values to None for cleaner JSON serialization
            df = df.where(pd.notnull(df), None)

            return df.to_dict("records")

        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            raise ValueError(f"Failed to parse file: {str(e)}")

    def parse_file_stream(self, file: FileStorage) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse file from stream and return headers and rows.

        Args:
            file: FileStorage object from Flask request

        Returns:
            Tuple of (column_headers, row_dictionaries)

        Raises:
            ValueError: If file cannot be parsed
        """
        file_ext = os.path.splitext(file.filename)[1].lower()

        try:
            if file_ext == ".csv":
                df = pd.read_csv(file)
            elif file_ext in [".xlsx", ".xls"]:
                df = pd.read_excel(file)
            elif file_ext == ".json":
                df = pd.read_json(file)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

            # Reset file pointer for potential re-use
            file.seek(0)

            # Convert NaN to None
            df = df.where(pd.notnull(df), None)

            headers = list(df.columns)
            rows = df.to_dict("records")

            return headers, rows

        except Exception as e:
            logger.error(f"Error parsing file stream {file.filename}: {e}")
            raise ValueError(f"Failed to parse file: {str(e)}")

    def find_name_column(self, columns: List[str]) -> str:
        """
        Find the column containing application names.

        Args:
            columns: List of column names from the file

        Returns:
            Name of the column containing application names
        """
        columns_set = set(columns)
        for variant in self.NAME_COLUMN_VARIANTS:
            if variant in columns_set:
                return variant

        # Fallback to first column
        return columns[0] if columns else "name"
