"""
Schema Inference Service

Accepts SQL DDL or OpenAPI JSON/YAML and infers ArchiMate DataObject elements.
Creates them in the element catalog via the existing create_archimate_element pathway.

Supported input formats:
  - SQL DDL: CREATE TABLE statements (PostgreSQL / MySQL / generic SQL)
  - OpenAPI 3.x JSON/YAML: schemas section, components/schemas

Output: list of inferred DataObject elements (name, description, attributes) ready
for creation via ToolExecutor._tool_create_archimate_element.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Matches the CREATE TABLE header up to the opening paren; the body is then
# extracted by balanced-paren scanning (a regex would truncate at the first ')'
# inside types like DECIMAL(10,2)).
_DDL_TABLE_HEADER_RE = re.compile(
    r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\w+\.)?[`"\[]?(\w+)[`"\]]?\s*\(',
    re.IGNORECASE,
)
_DDL_COLUMN_RE = re.compile(
    r'^\s*[`"\[]?(\w+)[`"\]]?\s+([\w\(\),\s]+?)(?:\s+(?:NOT\s+NULL|DEFAULT|PRIMARY|UNIQUE|REFERENCES|CHECK|CONSTRAINT).*)?\s*$',
    re.IGNORECASE | re.MULTILINE,
)
_SKIP_COL_KEYWORDS = {
    "PRIMARY", "KEY", "UNIQUE", "INDEX", "CONSTRAINT", "CHECK", "FOREIGN",
}


@dataclass
class InferredDataObject:
    name: str
    description: str
    layer: str = "application"
    element_type: str = "DataObject"
    attributes: List[Dict[str, str]] = field(default_factory=list)
    source: str = ""  # 'ddl' | 'openapi'

    def to_create_args(self) -> dict:
        desc = self.description
        if self.attributes:
            attr_lines = "; ".join(
                f"{a['name']} ({a['type']})" for a in self.attributes[:10]
            )
            desc = f"{desc}\nFields: {attr_lines}"
        # Keys match the create_archimate_element tool schema exactly ('type', not 'element_type')
        return {
            "name": self.name,
            "description": desc,
            "layer": self.layer,
            "type": self.element_type,
        }


class SchemaInferenceService:
    """Parse DDL/OpenAPI text and return InferredDataObject list."""

    @classmethod
    def infer_from_ddl(cls, ddl_text: str) -> dict:
        """
        Parse SQL DDL and return inferred DataObjects.

        Returns: {"success": True, "inferred": [...], "table_count": N}
        """
        try:
            objects = []
            for match in _DDL_TABLE_HEADER_RE.finditer(ddl_text):
                table_name = match.group(1)
                body = cls._extract_balanced_body(ddl_text, match.end())
                columns = cls._parse_ddl_columns(body)
                obj = InferredDataObject(
                    name=cls._humanize(table_name),
                    description=f"DataObject inferred from DDL table '{table_name}'.",
                    attributes=columns,
                    source="ddl",
                )
                objects.append(obj)

            return {
                "success": True,
                "inferred": [o.__dict__ for o in objects],
                "table_count": len(objects),
                "create_args": [o.to_create_args() for o in objects],
            }
        except Exception as e:
            logger.exception("SchemaInferenceService.infer_from_ddl failed")
            return {"success": False, "error": str(e)}

    @classmethod
    def infer_from_openapi(cls, openapi_text: str) -> dict:
        """
        Parse OpenAPI 3.x JSON/YAML and return inferred DataObjects from components/schemas.

        Returns: {"success": True, "inferred": [...], "schema_count": N}
        """
        try:
            spec = cls._parse_openapi_text(openapi_text)
            schemas = (
                spec.get("components", {}).get("schemas", {})
                or spec.get("definitions", {})  # OpenAPI 2.x fallback
            )
            if not schemas:
                return {
                    "success": True,
                    "inferred": [],
                    "schema_count": 0,
                    "message": "No schemas found in components/schemas or definitions.",
                }

            objects = []
            for schema_name, schema_def in schemas.items():
                if not isinstance(schema_def, dict):
                    continue
                columns = cls._parse_openapi_properties(schema_def)
                desc = schema_def.get("description") or f"DataObject inferred from OpenAPI schema '{schema_name}'."
                obj = InferredDataObject(
                    name=cls._humanize(schema_name),
                    description=desc,
                    attributes=columns,
                    source="openapi",
                )
                objects.append(obj)

            return {
                "success": True,
                "inferred": [o.__dict__ for o in objects],
                "schema_count": len(objects),
                "create_args": [o.to_create_args() for o in objects],
            }
        except Exception as e:
            logger.exception("SchemaInferenceService.infer_from_openapi failed")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_balanced_body(text: str, start: int) -> str:
        """Return the text from `start` (just after the opening paren) up to the
        matching closing paren, honouring nested parens like DECIMAL(10,2)."""
        depth = 1
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return text[start:i]
        return text[start:]  # unbalanced input — take the rest

    @staticmethod
    def _split_top_level_commas(body: str) -> List[str]:
        """Split a CREATE TABLE body on commas at paren-depth zero, so single-line
        DDL and types like DECIMAL(10,2) parse correctly."""
        parts, depth, current = [], 0, []
        for ch in body:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append("".join(current))
        return parts

    @classmethod
    def _parse_ddl_columns(cls, body: str) -> List[Dict[str, str]]:
        cols = []
        for segment in cls._split_top_level_commas(body):
            line = segment.strip()
            if not line:
                continue
            first_token = line.split()[0].strip('`"[]').upper() if line.split() else ""
            if first_token in _SKIP_COL_KEYWORDS:
                continue
            m = _DDL_COLUMN_RE.match(line)
            if m:
                col_name = m.group(1)
                col_type = m.group(2).strip().split()[0]  # take first token of type
                if col_name.upper() not in _SKIP_COL_KEYWORDS:
                    cols.append({"name": col_name, "type": col_type})
        return cols[:30]  # cap at 30 columns per table

    @staticmethod
    def _parse_openapi_properties(schema_def: dict) -> List[Dict[str, str]]:
        props = schema_def.get("properties") or {}
        cols = []
        for prop_name, prop_def in props.items():
            if not isinstance(prop_def, dict):
                continue
            prop_type = prop_def.get("type") or prop_def.get("$ref", "").split("/")[-1] or "any"
            cols.append({"name": prop_name, "type": prop_type})
        return cols[:30]

    @staticmethod
    def _parse_openapi_text(text: str) -> dict:
        """Try JSON, then YAML-lite (key: value)."""
        text = text.strip()
        if text.startswith("{"):
            return json.loads(text)
        # Minimal YAML→dict via PyYAML if available
        try:
            import yaml  # type: ignore
            return yaml.safe_load(text) or {}
        except ImportError:
            pass
        # Fallback: best-effort JSON after stripping YAML markers
        cleaned = re.sub(r'^---\s*', '', text, flags=re.MULTILINE)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _humanize(identifier: str) -> str:
        """Convert snake_case or CamelCase to Title Case."""
        # Split on underscores and camel humps
        parts = re.sub(r'([a-z])([A-Z])', r'\1 \2', identifier)
        parts = re.sub(r'[_-]', ' ', parts)
        return parts.strip().title()
