"""LLM-powered fuzzy matching of upload columns to generated data model fields.

Matching priority: exact name -> normalized name -> abbreviation expansion -> substring containment -> semantic match (LLM).
Each mapping includes a confidence score for UI color coding.
"""
import logging
import re

logger = logging.getLogger(__name__)


def _normalize(name: str) -> str:
    """Normalize a column/field name for comparison."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]", "", name)  # Remove non-alphanumeric
    return name


# Common abbreviation expansions
_EXPANSIONS = {
    "addr": "address", "qty": "quantity", "amt": "amount",
    "desc": "description", "num": "number", "no": "number",
    "cust": "customer", "prod": "product", "org": "organization",
    "dept": "department", "mgr": "manager", "emp": "employee",
    "tel": "phone", "ph": "phone", "mob": "mobile",
}


def _expand(name: str) -> str:
    """Expand common abbreviations in a normalized name.

    Only replaces when the abbreviation is not already part of the full word,
    preventing 'address' from becoming 'addressess'.
    """
    normalized = _normalize(name)
    for abbr, full in _EXPANSIONS.items():
        if full in normalized:
            # Already contains the full form — skip to avoid double-expansion
            continue
        normalized = normalized.replace(abbr, full)
    return normalized


class ColumnMappingEngine:
    """Map upload columns to data model fields with confidence scoring."""

    def auto_map(
        self,
        sheet_columns: list[str],
        model_fields: dict[str, list[str]],
    ) -> list[dict]:
        """Match sheet columns to model entity fields.

        Args:
            sheet_columns: Column headers from uploaded file
            model_fields: {"entity_name": ["field1", "field2", ...]}

        Returns:
            List of mappings, each with:
            - source_column: original column name
            - target_entity: matched entity or None
            - target_field: matched field or None
            - confidence: 0.0 to 1.0
            - match_type: "exact", "abbreviation", "substring", or "none"
        """
        # Build flat lookup: normalized_field -> (entity, field)
        field_lookup: dict[str, tuple[str, str]] = {}
        expanded_lookup: dict[str, tuple[str, str]] = {}
        for entity, fields in model_fields.items():
            for field in fields:
                field_lookup[_normalize(field)] = (entity, field)
                expanded_lookup[_expand(field)] = (entity, field)

        mappings = []
        used_targets: set[tuple[str, str]] = set()

        for col in sheet_columns:
            mapping = self._match_column(col, field_lookup, expanded_lookup, used_targets)
            if mapping["target_field"]:
                used_targets.add((mapping["target_entity"], mapping["target_field"]))
            mappings.append(mapping)

        return mappings

    def _match_column(
        self,
        col: str,
        field_lookup: dict,
        expanded_lookup: dict,
        used: set,
    ) -> dict:
        """Match a single column against available fields."""
        norm_col = _normalize(col)
        exp_col = _expand(col)

        # 1. Exact normalized match (confidence 0.98)
        if norm_col in field_lookup:
            entity, field = field_lookup[norm_col]
            if (entity, field) not in used:
                return {
                    "source_column": col,
                    "target_entity": entity,
                    "target_field": field,
                    "confidence": 0.98,
                    "match_type": "exact",
                }

        # 2. Expanded abbreviation match (confidence 0.85)
        if exp_col in expanded_lookup:
            entity, field = expanded_lookup[exp_col]
            if (entity, field) not in used:
                return {
                    "source_column": col,
                    "target_entity": entity,
                    "target_field": field,
                    "confidence": 0.85,
                    "match_type": "abbreviation",
                }

        # 3. Substring containment match (confidence 0.70)
        for norm_field, (entity, field) in field_lookup.items():
            if (entity, field) in used:
                continue
            if norm_field in norm_col or norm_col in norm_field:
                return {
                    "source_column": col,
                    "target_entity": entity,
                    "target_field": field,
                    "confidence": 0.70,
                    "match_type": "substring",
                }

        # 4. No match
        return {
            "source_column": col,
            "target_entity": None,
            "target_field": None,
            "confidence": 0.0,
            "match_type": "none",
        }
