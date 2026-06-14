"""
Base Database Seeder

Provides common functionality for all database seeders.
Implements idempotent seeding patterns and error handling.
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app import db

logger = logging.getLogger(__name__)


class BaseSeeder(ABC):
    """
    Abstract base class for all database seeders.

    Provides common functionality for:
    - Loading JSON seed data
    - Idempotent create/update operations
    - Two-pass relationship resolution
    - Comprehensive error handling and logging
    - Transaction management
    """

    def __init__(self, seed_data_path: str):
        """
        Initialize the seeder with seed data path.

        Args:
            seed_data_path: Path to the JSON seed data file (relative to app/seed_data/)
        """
        self.seed_data_path = Path("app/seed_data") / seed_data_path
        self.seed_data: List[Dict[str, Any]] = []
        self.created_count = 0
        self.updated_count = 0
        self.errors: List[str] = []

    def load_seed_data(self) -> bool:
        """
        Load seed data from JSON file.

        Returns:
            bool: True if data loaded successfully, False otherwise
        """
        try:
            if not self.seed_data_path.exists():
                error_msg = f"Seed data file not found: {self.seed_data_path}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                return False

            with open(self.seed_data_path, "r", encoding="utf-8") as f:
                self.seed_data = json.load(f)

            if not isinstance(self.seed_data, list):
                error_msg = f"Seed data must be a list, got {type(self.seed_data)}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                return False

            logger.info(f"Loaded {len(self.seed_data)} records from {self.seed_data_path}")
            return True

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in seed data file: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
        except Exception as e:
            error_msg = f"Error loading seed data: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False

    @abstractmethod
    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a single seed record.

        Args:
            record: The record to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    @abstractmethod
    def create_or_update_record(self, record: Dict[str, Any]) -> bool:
        """
        Create or update a single record.

        Args:
            record: The record data

        Returns:
            bool: True if successful, False otherwise
        """
        pass

    def seed(self) -> Dict[str, Any]:
        """
        Execute the seeding process.

        Returns:
            Dict containing seeding results
        """
        logger.info(f"Starting seeding for {self.__class__.__name__}")

        # Reset counters
        self.created_count = 0
        self.updated_count = 0
        self.errors = []

        # Load seed data
        if not self.load_seed_data():
            return {
                "success": False,
                "message": f"Failed to load seed data: {', '.join(self.errors)}",
                "data": {"created": 0, "updated": 0, "errors": self.errors},
            }

        if len(self.seed_data) == 0:
            logger.info("No seed data to process")
            return {
                "success": True,
                "message": "No seed data to process",
                "data": {"created": 0, "updated": 0, "errors": []},
            }

        # Process records in transaction
        try:
            with db.session.begin():
                for record in self.seed_data:
                    # Validate record
                    is_valid, error_msg = self.validate_record(record)
                    if not is_valid:
                        self.errors.append(f"Validation failed for record: {error_msg}")
                        continue

                    # Create or update record
                    if self.create_or_update_record(record):
                        # Counter updates are handled in the concrete implementation
                        pass
                    else:
                        self.errors.append(
                            f"Failed to create/update record: {record.get('name', 'Unknown')}"
                        )

            # Commit transaction
            db.session.commit()

            success = len(self.errors) == 0
            message = f"Seeded {self.created_count} created, {self.updated_count} updated"
            if self.errors:
                message += f", {len(self.errors)} errors"

            return {
                "success": success,
                "message": message,
                "data": {
                    "created": self.created_count,
                    "updated": self.updated_count,
                    "errors": self.errors,
                },
            }

        except Exception as e:
            db.session.rollback()
            error_msg = f"Seeding failed with exception: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "data": {
                    "created": self.created_count,
                    "updated": self.updated_count,
                    "errors": self.errors + [str(e)],
                },
            }

    def _create_result(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a standardized result dict for seeder operations."""
        return {
            "success": success,
            "message": message,
            "data": data or {"created": 0, "updated": 0, "errors": []},
        }

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of this seeder.

        Returns:
            Dict containing status information
        """
        return {
            "available": self.seed_data_path.exists(),
            "data_file": str(self.seed_data_path),
            "record_count": len(self.seed_data) if self.seed_data else 0,
        }
