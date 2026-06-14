"""
UX Enrichment Service — read-only.

Auto-infers UX configuration from live database metadata:
  - navigation tab ordering (by ArchiMate relationship density)
  - field control types (enum pickers, date pickers, relation pickers)
  - data volume tiers per entity table
  - design system defaults

Imported by:
  - uml_enrichment_service.py (Task 4)
  - codegen route handlers (Task 2)
"""

import logging
import re
from typing import Optional

from sqlalchemy import text

from app import db

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# Ordered candidates for "display field" detection (most preferred first)
_DISPLAY_FIELD_CANDIDATES = [
    "name",
    "title",
    "label",
    "display_name",
    "full_name",
    "subject",
    "code",
    "reference",
    "identifier",
]


# ---------------------------------------------------------------------------
# Pure helpers (no DB)
# ---------------------------------------------------------------------------

def _infer_volume_tier(row_count: int) -> str:
    """Map a row count to a volume tier string."""
    if row_count < 500:
        return "small"
    if row_count < 10_000:
        return "medium"
    return "large"


def _sanitise_enum_value(value) -> Optional[str]:
    """Return a cleaned enum string or None if invalid."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if len(s) > 100:
        return None
    return s


def _detect_display_field(column_names: list) -> Optional[str]:
    """Return the first column matching a preferred display-field candidate.

    Matching is case-insensitive; the *original* column name is returned.
    """
    lower_to_original = {col.lower(): col for col in column_names}
    for candidate in _DISPLAY_FIELD_CANDIDATES:
        if candidate in lower_to_original:
            return lower_to_original[candidate]
    return None


def _resolve_table_for_entity(entity_name: str, elements: list) -> Optional[str]:
    """Find the DB table name for a named entity from the element list."""
    for el in elements:
        if el.element_name == entity_name and el.element_table:
            return el.element_table
    return None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _query_enum_values(table_name: str, field_name: str) -> list:
    """Return sorted distinct non-null values for a field (max 30).

    Table and field names come from ORM metadata — NOT user input — so
    f-string interpolation is safe here.  Only the LIMIT is parameterised.
    """
    if not _SAFE_IDENTIFIER.match(table_name) or not _SAFE_IDENTIFIER.match(field_name):
        logger.warning("Unsafe identifier rejected: %s.%s", table_name, field_name)
        return []
    try:
        sql = text(
            f"SELECT DISTINCT {field_name} FROM {table_name}"
            f" WHERE {field_name} IS NOT NULL LIMIT :limit"
        )
        rows = db.session.execute(sql, {"limit": 30}).fetchall()
        values = []
        for (raw,) in rows:
            cleaned = _sanitise_enum_value(raw)
            if cleaned is not None:
                values.append(cleaned)
        return sorted(values)
    except Exception:
        logger.debug(
            "Could not query enum values for %s.%s", table_name, field_name, exc_info=True
        )
        return []


def _query_row_count(table_name: str) -> int:
    """Return the pg_class estimated row count for a table (fast, approximate)."""
    try:
        sql = text(
            "SELECT reltuples::bigint FROM pg_class WHERE relname = :tname"
        )
        count = db.session.execute(sql, {"tname": table_name}).scalar()
        return max(0, int(count or 0))
    except Exception:
        logger.debug("Could not query row count for %s", table_name, exc_info=True)
        return 0


def _get_table_columns(table_name: str) -> list:
    """Return ordered list of column names for a table via information_schema."""
    try:
        sql = text(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = :tname ORDER BY ordinal_position"
        )
        rows = db.session.execute(sql, {"tname": table_name}).fetchall()
        return [row[0] for row in rows]
    except Exception:
        logger.debug("Could not get columns for %s", table_name, exc_info=True)
        return []


def _rank_entities_for_navigation(solution_id: int) -> list:
    """Return entity names ordered by ArchiMate relationship count DESC."""
    try:
        sql = text(
            """
            SELECT
                COALESCE(ae.name, sae.element_name) AS entity_name,
                COUNT(ar.id) AS rel_count
            FROM solution_archimate_elements sae
            LEFT JOIN archimate_elements ae ON ae.id = sae.element_id
            LEFT JOIN archimate_relationships ar
                ON ar.source_id = sae.element_id
                OR ar.target_id = sae.element_id
            WHERE sae.solution_id = :sid
            GROUP BY COALESCE(ae.name, sae.element_name)
            ORDER BY rel_count DESC, COALESCE(ae.name, sae.element_name)
            LIMIT 10
            """
        )
        rows = db.session.execute(sql, {"sid": solution_id}).fetchall()
        return [row[0] for row in rows]
    except Exception:
        logger.debug(
            "Could not rank entities for solution %s", solution_id, exc_info=True
        )
        return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_ux_enrichment(solution_id: int) -> dict:
    """Build a UX enrichment dict for a solution.

    Loads SolutionArchiMateElement records lazily (inside this function to
    avoid circular imports) and infers field controls, data volumes, and
    navigation ordering from live DB metadata.

    Returns an empty-structure dict on any loading error so callers can
    always merge safely.
    """
    _empty = {
        "navigation": {"suggested_tabs": []},
        "field_controls": {},
        "data_volumes": {},
        "design_system": {"primary_color": "#6366f1", "icon_library": "ionicons"},
    }

    # Lazy import to break potential circular dependencies
    from app.models.solution_archimate_element import SolutionArchiMateElement  # noqa: PLC0415

    try:
        elements = SolutionArchiMateElement.query.filter_by(solution_id=solution_id).all()
    except Exception:
        logger.warning(
            "build_ux_enrichment: failed to load elements for solution %s",
            solution_id,
            exc_info=True,
        )
        return _empty

    # Navigation tabs
    ranked = _rank_entities_for_navigation(solution_id)
    suggested_tabs = [{"entity": name} for name in ranked]

    # Per-entity field controls + data volumes
    field_controls: dict = {}
    data_volumes: dict = {}

    for el in elements:
        entity_name = el.element_name or ""
        table_name = el.element_table or ""
        spec_data = el.spec_data or {}
        fields = spec_data.get("fields", []) if isinstance(spec_data, dict) else []

        # Data volume
        if table_name:
            count = _query_row_count(table_name)
            data_volumes[entity_name] = {
                "row_count": count,
                "tier": _infer_volume_tier(count),
            }

        # Field controls
        entity_controls: dict = {}
        for field in fields:
            if not isinstance(field, dict):
                continue
            fname = field.get("name") or field.get("field_name")
            if not fname:
                continue
            ftype = field.get("type", "")
            fk = field.get("foreign_key")

            if ftype == "enum":
                if table_name:
                    detected = _query_enum_values(table_name, fname)
                else:
                    detected = []
                entity_controls[fname] = {"type": "enum", "detected_values": detected}

            elif ftype in ("datetime", "date"):
                entity_controls[fname] = {"type": "date_picker"}

            elif fk:
                # fk looks like "EntityName.id"
                parts = str(fk).split(".", 1)
                ref_entity = parts[0] if parts else ""
                ref_table = _resolve_table_for_entity(ref_entity, elements)
                if ref_table:
                    cols = _get_table_columns(ref_table)
                    display_field = _detect_display_field(cols) or "name"
                else:
                    display_field = "name"
                entity_controls[fname] = {
                    "type": "relation_picker",
                    "referenced_entity": ref_entity,
                    "display_field": display_field,
                }

        if entity_controls:
            field_controls[entity_name] = entity_controls

    return {
        "navigation": {"suggested_tabs": suggested_tabs},
        "field_controls": field_controls,
        "data_volumes": data_volumes,
        "design_system": {"primary_color": "#6366f1", "icon_library": "ionicons"},
    }
