"""
Serialization Mixin for SQLAlchemy Models

Provides consistent to_dict() and to_summary_dict() methods across all models.
Handles datetime serialization, Decimal conversion, and relationship inclusion.

Usage:
    class MyModel(SerializationMixin, db.Model):
        __tablename__ = 'my_table'
        ...

    # Get full dict
    model.to_dict()

    # Get dict with specific fields
    model.to_dict(include=['id', 'name', 'related_items'])

    # Exclude sensitive fields
    model.to_dict(exclude=['password', 'api_key'])

    # Get minimal summary
    model.to_summary_dict()
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import inspect
from sqlalchemy.orm import RelationshipProperty


class SerializationMixin:
    """
    Mixin providing consistent serialization methods for SQLAlchemy models.

    Features:
    - Automatic column detection
    - Datetime serialization (ISO format)
    - Decimal conversion to float
    - Optional relationship inclusion
    - Field inclusion/exclusion support
    - JSON field parsing
    """

    # Default fields to exclude from serialization (can be overridden in subclasses)
    _serialization_exclude_fields: Set[str] = set()

    # Fields that contain JSON strings and should be parsed
    _json_fields: Set[str] = set()

    def to_dict(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        include_relationships: bool = False,
        max_depth: int = 1,
    ) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.

        Args:
            include: Optional list of fields to include. If provided, only these fields
                    are included (plus any explicitly included relationships).
            exclude: Optional list of fields to exclude from output.
            include_relationships: If True, includes related objects (shallow by default).
            max_depth: Maximum depth for relationship serialization (default 1).
                      Set to 0 to skip relationships entirely.

        Returns:
            Dictionary representation of the model.

        Example:
            >>> user.to_dict()
            {'id': 1, 'name': 'John', 'created_at': '2024 - 01 - 15T10:30:00'}

            >>> user.to_dict(include=['id', 'name'])
            {'id': 1, 'name': 'John'}

            >>> user.to_dict(exclude=['password'])
            {'id': 1, 'name': 'John', 'created_at': '2024 - 01 - 15T10:30:00'}
        """
        result = {}

        # Build exclude set
        exclude_set = set(exclude or [])
        exclude_set.update(self._serialization_exclude_fields)

        # Get model inspection
        mapper = inspect(self.__class__)

        # Process columns
        for column in mapper.columns:
            column_name = column.key

            # Skip if excluded
            if column_name in exclude_set:
                continue

            # Skip if include list provided and field not in it
            if include is not None and column_name not in include:
                continue

            value = getattr(self, column_name, None)
            result[column_name] = self._serialize_value(column_name, value)

        # Process relationships if requested
        if include_relationships and max_depth > 0:
            for rel in mapper.relationships:
                rel_name = rel.key

                # Skip if excluded
                if rel_name in exclude_set:
                    continue

                # Skip if include list provided and relationship not in it
                if include is not None and rel_name not in include:
                    continue

                result[rel_name] = self._serialize_relationship(rel, max_depth - 1)

        # Also check for explicit include of relationships
        if include:
            for field_name in include:
                if field_name not in result and hasattr(self, field_name):
                    # This might be a relationship not yet processed
                    value = getattr(self, field_name, None)
                    if value is not None:
                        if hasattr(value, "to_dict"):
                            result[field_name] = (
                                value.to_dict()
                                if max_depth > 0
                                else value.to_summary_dict()
                                if hasattr(value, "to_summary_dict")
                                else None
                            )
                        elif hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
                            # It's a collection
                            result[field_name] = [
                                item.to_summary_dict()
                                if hasattr(item, "to_summary_dict")
                                else str(item)
                                for item in value
                            ][
                                :10
                            ]  # Limit to first 10 items

        return result

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Return a minimal dictionary representation for list views and references.

        By default returns id, name (or title), and type fields if they exist.
        Override in subclasses for custom summary fields.

        Returns:
            Minimal dictionary with key identifying fields.

        Example:
            >>> product.to_summary_dict()
            {'id': 42, 'name': 'SAP S/4HANA', 'type': 'ERP'}
        """
        summary = {}

        # Always include id if present
        if hasattr(self, "id"):
            summary["id"] = self.id

        # Include name or title
        for name_field in ["name", "title", "display_name"]:
            if hasattr(self, name_field):
                value = getattr(self, name_field)
                if value is not None:
                    summary["name"] = value
                    break

        # Include type if present
        for type_field in ["type", "product_type", "vendor_type", "element_type"]:
            if hasattr(self, type_field):
                value = getattr(self, type_field)
                if value is not None:
                    summary["type"] = value
                    break

        return summary

    def _serialize_value(self, field_name: str, value: Any) -> Any:
        """
        Serialize a single value to JSON-compatible format.

        Handles:
        - None values
        - datetime/date objects (ISO format)
        - Decimal objects (float conversion)
        - JSON string fields (parsing)
        - Regular values (pass-through)
        """
        if value is None:
            return None

        # Handle datetime
        if isinstance(value, datetime):
            return value.isoformat()

        # Handle date
        if isinstance(value, date):
            return value.isoformat()

        # Handle Decimal
        if isinstance(value, Decimal):
            return float(value)

        # Handle JSON string fields
        if field_name in self._json_fields or field_name in getattr(self, "_json_fields", set()):
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value

        # Check for common JSON field patterns
        if isinstance(value, str) and field_name.endswith(
            ("_json", "_data", "_list", "_array", "_config")
        ):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        return value

    def _serialize_relationship(self, relationship: RelationshipProperty, depth: int) -> Any:
        """
        Serialize a relationship to JSON-compatible format.

        Args:
            relationship: SQLAlchemy relationship property
            depth: Remaining depth for nested serialization

        Returns:
            Serialized relationship data (dict, list of dicts, or None)
        """
        try:
            value = getattr(self, relationship.key, None)
        except Exception:
            # Relationship might not be loaded or accessible
            return None

        if value is None:
            return None

        # Handle single object relationships
        if not relationship.uselist:
            if hasattr(value, "to_summary_dict"):
                return value.to_summary_dict()
            elif hasattr(value, "to_dict"):
                return value.to_dict() if depth > 0 else {"id": getattr(value, "id", None)}
            else:
                return str(value)

        # Handle collection relationships
        try:
            items = list(value)[:10]  # Limit to first 10 items
        except Exception:
            return []

        result = []
        for item in items:
            if hasattr(item, "to_summary_dict"):
                result.append(item.to_summary_dict())
            elif hasattr(item, "to_dict"):
                result.append(item.to_dict() if depth > 0 else {"id": getattr(item, "id", None)})
            else:
                result.append(str(item))

        return result

    @classmethod
    def get_column_names(cls) -> List[str]:
        """
        Get list of all column names for this model.

        Returns:
            List of column name strings.
        """
        mapper = inspect(cls)
        return [column.key for column in mapper.columns]

    @classmethod
    def get_relationship_names(cls) -> List[str]:
        """
        Get list of all relationship names for this model.

        Returns:
            List of relationship name strings.
        """
        mapper = inspect(cls)
        return [rel.key for rel in mapper.relationships]
