"""
Unified Duplicate Detector Service

Handles in-file and database duplicate detection for application imports.
Consolidated from batch_import_service.py and unified_applications_import_routes.py.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func

logger = logging.getLogger(__name__)


@dataclass
class DuplicateInfo:
    """Information about a duplicate entry."""

    row: int
    name: str
    existing_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"row": self.row, "name": self.name}
        if self.existing_id is not None:
            result["existing_id"] = self.existing_id
        return result


@dataclass
class DuplicateAnalysisResult:
    """Results of duplicate analysis."""

    # Counts
    in_file_count: int = 0
    database_count: int = 0
    missing_names_count: int = 0

    # Details (first N for display)
    in_file_duplicates: List[DuplicateInfo] = field(default_factory=list)
    database_duplicates: List[DuplicateInfo] = field(default_factory=list)

    # Calculated values
    unique_names: Set[str] = field(default_factory=set)
    will_create: int = 0
    will_update: int = 0
    will_skip: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "in_file_duplicates": self.in_file_count,
            "in_file_duplicate_details": [d.to_dict() for d in self.in_file_duplicates[:10]],
            "database_duplicates": self.database_count,
            "database_duplicate_details": [d.to_dict() for d in self.database_duplicates[:10]],
            "missing_names": self.missing_names_count,
            "will_create": self.will_create,
            "will_update": self.will_update,
            "will_skip": self.will_skip,
            "unique_count": len(self.unique_names),
        }


class DuplicateDetector:
    """
    Unified duplicate detector for application imports.

    Checks for:
    - In-file duplicates (same name appearing multiple times)
    - Database duplicates (names already in ApplicationComponent table)
    """

    def __init__(self, name_column: str = "name"):
        """
        Initialize detector.

        Args:
            name_column: Column name containing application names
        """
        self.name_column = name_column

    def analyze_duplicates(
        self,
        rows: List[Dict[str, Any]],
        name_column: Optional[str] = None,
        check_database: bool = True,
        max_details: int = 10,
    ) -> DuplicateAnalysisResult:
        """
        Analyze rows for duplicate application names.

        Args:
            rows: List of row dictionaries from parsed file
            name_column: Column containing app names (overrides instance default)
            check_database: Whether to check for database duplicates
            max_details: Maximum number of duplicate details to return

        Returns:
            DuplicateAnalysisResult with counts and details
        """
        name_col = name_column or self.name_column
        result = DuplicateAnalysisResult()

        seen_names: Dict[str, int] = {}  # name_lower -> first_row
        in_file_dups: List[DuplicateInfo] = []
        missing_count = 0

        # Scan for in-file duplicates
        for idx, row in enumerate(rows, start=1):
            raw_name = row.get(name_col, "")
            if raw_name is None:
                raw_name = ""
            name = str(raw_name).strip()

            if not name:
                missing_count += 1
                continue

            name_lower = name.lower()

            if name_lower in seen_names:
                in_file_dups.append(DuplicateInfo(row=idx, name=name))
            else:
                seen_names[name_lower] = idx
                result.unique_names.add(name_lower)

        result.in_file_count = len(in_file_dups)
        result.in_file_duplicates = in_file_dups[:max_details]
        result.missing_names_count = missing_count

        # Check database duplicates
        db_dups: List[DuplicateInfo] = []
        if check_database and result.unique_names:
            db_dups = self._check_database_duplicates(result.unique_names, seen_names, max_details)

        result.database_count = len(db_dups)
        result.database_duplicates = db_dups[:max_details]

        # Calculate summary
        total_rows = len(rows)
        unique_count = len(result.unique_names)
        result.will_update = result.database_count
        result.will_create = unique_count - result.database_count
        result.will_skip = result.in_file_count + result.missing_names_count

        return result

    def _check_database_duplicates(
        self,
        unique_names: Set[str],
        name_to_row: Dict[str, int],
        max_details: int,
    ) -> List[DuplicateInfo]:
        """
        Check for duplicates in the database.

        Args:
            unique_names: Set of unique lowercase names from file
            name_to_row: Mapping of lowercase name to row number
            max_details: Maximum details to return

        Returns:
            List of DuplicateInfo for names found in database
        """
        try:
            from app.models.application_portfolio import ApplicationComponent

            # Query for existing applications (case-insensitive)
            existing_apps = ApplicationComponent.query.filter(
                func.lower(ApplicationComponent.name).in_(unique_names)
            ).all()

            duplicates = []
            for app in existing_apps:
                name_lower = app.name.lower()
                row_num = name_to_row.get(name_lower, 0)
                duplicates.append(DuplicateInfo(row=row_num, name=app.name, existing_id=app.id))

            return duplicates[:max_details]

        except Exception as e:
            logger.error(f"Error checking database duplicates: {e}")
            return []

    def check_single_name(self, name: str) -> Optional[int]:
        """
        Check if a single application name exists in database.

        Args:
            name: Application name to check

        Returns:
            Application ID if exists, None otherwise
        """
        try:
            from app.models.application_portfolio import ApplicationComponent

            existing = ApplicationComponent.query.filter(
                func.lower(ApplicationComponent.name) == name.lower()
            ).first()

            return existing.id if existing else None

        except Exception as e:
            logger.error(f"Error checking name '{name}': {e}")
            return None

    @staticmethod
    def preload_existing_apps() -> Dict[str, Any]:
        """
        Pre-load all existing applications into lookup dicts for O(1) matching.

        Returns dict with:
            by_name: {lowercase_name: {"id": int, "name": str}}
            by_code: {application_code: int}  (only entries with codes)
        """
        from app.models.application_portfolio import ApplicationComponent

        by_name = {}
        by_code = {}
        for row in (  # model-safety-ok: single preload query, not N+1
            ApplicationComponent.query
            .with_entities(
                ApplicationComponent.id,
                ApplicationComponent.name,
                ApplicationComponent.application_code,
            )
            .all()
        ):
            by_name[row.name.lower()] = {"id": row.id, "name": row.name}
            if row.application_code:
                by_code[row.application_code] = row.id

        logger.debug(
            "Preloaded %d apps by name, %d by code",
            len(by_name), len(by_code),
        )
        return {"by_name": by_name, "by_code": by_code}

    @staticmethod
    def find_existing_app(
        name: str,
        lookup: Dict[str, Any],
        app_code: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find an existing application using preloaded lookup dicts.

        Case-insensitive name match, with optional application_code fallback.

        Args:
            name: Application name to search for
            lookup: Dict from preload_existing_apps()
            app_code: Optional application code for secondary lookup

        Returns:
            {"id": int, "name": str} if found, None otherwise
        """
        # Primary: case-insensitive name match
        match = lookup["by_name"].get(name.lower())
        if match:
            return match

        # Fallback: application_code match
        if app_code and app_code in lookup["by_code"]:
            app_id = lookup["by_code"][app_code]
            # Resolve the name from the by_name dict
            for info in lookup["by_name"].values():
                if info["id"] == app_id:
                    return info
            return {"id": app_id, "name": name}

        return None
