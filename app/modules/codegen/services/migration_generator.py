"""MigrationGenerator -- produces non-destructive, reversible SQL migrations.

Key policies:
- Add column: ALTER TABLE ADD COLUMN (non-destructive)
- Remove column: NEVER auto-drops. Marks deprecated with COMMENT.
- Rename: ALTER TABLE RENAME COLUMN
- Always generates reverse script alongside forward
- Data backfill included when default provided
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Maps change field_type to SQL type
_SQL_TYPE_MAP = {
    "string": "VARCHAR(255)",
    "text": "TEXT",
    "integer": "INTEGER",
    "float": "FLOAT",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "enum": "VARCHAR(50)",
    "json": "JSONB",
    "decimal": "DECIMAL(12,2)",
}


def _to_table_name(entity: str) -> str:
    """Convert entity name to snake_case table name (simple pluralisation)."""
    import re
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", entity).lower()
    if not name.endswith("s"):
        name += "s"
    return name


class MigrationGenerator:
    """Generates non-destructive, reversible SQL for schema changes."""

    def generate_for_change(self, change_dict: Dict[str, Any]) -> Dict[str, str]:
        """Generate forward and reverse SQL for a single atomic change.

        Returns: {"forward": SQL, "reverse": SQL}
        """
        change_type = change_dict.get("type", "")
        handler = {
            "add_field": self._add_field,
            "remove_field": self._remove_field,
            "rename_field": self._rename_field,
            "add_entity": self._add_entity,
        }.get(change_type)

        if not handler:
            return {
                "forward": f"-- Unsupported change type: {change_type}",
                "reverse": f"-- Unsupported change type: {change_type}",
            }

        return handler(change_dict)

    def _add_field(self, change: Dict[str, Any]) -> Dict[str, str]:
        table = _to_table_name(change.get("entity", "unknown"))
        field = change.get("field_name", "new_field")
        sql_type = _SQL_TYPE_MAP.get(
            (change.get("field_type") or "string").lower(), "VARCHAR(255)"
        )
        default = change.get("default")

        forward_parts = [
            f"ALTER TABLE {table} ADD COLUMN {field} {sql_type};",
        ]

        if default is not None:
            forward_parts.append(
                f"-- backfill: UPDATE {table} SET {field} = '{default}' WHERE {field} IS NULL;"
            )

        reverse = f"ALTER TABLE {table} DROP COLUMN {field};"

        return {
            "forward": "\n".join(forward_parts),
            "reverse": reverse,
        }

    def _remove_field(self, change: Dict[str, Any]) -> Dict[str, str]:
        """NEVER auto-drops. Marks column as deprecated with 30-day notice."""
        table = _to_table_name(change.get("entity", "unknown"))
        field = change.get("field_name", "old_field")

        forward = (
            f"-- DEPRECATED: Column {field} marked for removal.\n"
            f"-- Policy: 30-day deprecation period. Do NOT auto-drop.\n"
            f"-- Requires explicit BA confirmation after deprecation period.\n"
            f"COMMENT ON COLUMN {table}.{field} IS "
            f"'DEPRECATED — scheduled for removal after 30-day deprecation period';"
        )
        reverse = (
            f"COMMENT ON COLUMN {table}.{field} IS NULL;"
        )

        return {"forward": forward, "reverse": reverse}

    def generate_batch(self, changes: list) -> Dict[str, Any]:
        """Generate combined migration SQL from a list of atomic changes.

        Returns: {
            "forward": combined forward SQL,
            "reverse": combined reverse SQL (in reverse order for correct undo),
            "per_change": [{change, forward, reverse}, ...]
        }
        """
        per_change = []
        forward_parts = []
        reverse_parts = []

        for change in changes:
            result = self.generate_for_change(change)
            per_change.append({
                "change": change,
                "forward": result["forward"],
                "reverse": result["reverse"],
            })
            forward_parts.append(result["forward"])
            reverse_parts.append(result["reverse"])

        # Reverse order for undo — last change undone first
        reverse_parts.reverse()

        return {
            "forward": "\n\n".join(forward_parts),
            "reverse": "\n\n".join(reverse_parts),
            "per_change": per_change,
        }

    def wrap_alembic(
        self,
        forward_sql: str,
        reverse_sql: str,
        revision_id: str = "0002",
        down_revision: str = "0001",
        description: str = "auto-generated migration",
    ) -> str:
        """Wrap raw SQL in an Alembic migration script.

        Produces a complete alembic/versions/<revision>_<description>.py file.
        """
        safe_desc = description.replace('"', '\\"')
        # Escape SQL for triple-quoted strings
        fwd = forward_sql.replace('"""', '\\"\\"\\"')
        rev = reverse_sql.replace('"""', '\\"\\"\\"')

        return f'''"""
{safe_desc}

Revision ID: {revision_id}
Revises: {down_revision}
"""
from alembic import op

revision = "{revision_id}"
down_revision = "{down_revision}"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
{fwd}
""")


def downgrade():
    op.execute("""
{rev}
""")
'''

    def _rename_field(self, change: Dict[str, Any]) -> Dict[str, str]:
        table = _to_table_name(change.get("entity", "unknown"))
        old_name = change.get("old_field_name", change.get("field_name", "old_field"))
        new_name = change.get("new_field_name", "new_field")

        forward = f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name};"
        reverse = f"ALTER TABLE {table} RENAME COLUMN {new_name} TO {old_name};"

        return {"forward": forward, "reverse": reverse}

    def _add_entity(self, change: Dict[str, Any]) -> Dict[str, str]:
        table = _to_table_name(change.get("entity", "unknown"))

        forward = (
            f"CREATE TABLE IF NOT EXISTS {table} (\n"
            f"    id SERIAL PRIMARY KEY,\n"
            f"    created_at TIMESTAMP DEFAULT NOW()\n"
            f");"
        )
        reverse = f"DROP TABLE IF EXISTS {table};"

        return {"forward": forward, "reverse": reverse}
