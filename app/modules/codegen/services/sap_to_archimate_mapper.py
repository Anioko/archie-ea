"""SAP → ArchiMate 3.2 mapping service.

Converts structured SAP metadata (output of sap_metadata_reader.py) into
ArchiMate element and relationship dicts ready for database insertion.

No Flask or SQLAlchemy imports — this is pure Python so it can be unit-tested
in isolation and reused from CLI tooling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Display names for SAP modules
# ---------------------------------------------------------------------------

MODULE_DISPLAY_NAMES: dict[str, str] = {
    "MM": "SAP Materials Management (MM)",
    "SD": "SAP Sales & Distribution (SD)",
    "FI": "SAP Financial Accounting (FI)",
    "CO": "SAP Controlling (CO)",
    "HR": "SAP Human Resources (HR)",
    "PP": "SAP Production Planning (PP)",
    "PS": "SAP Project System (PS)",
    "WM": "SAP Warehouse Management (WM)",
    "QM": "SAP Quality Management (QM)",
    "PM": "SAP Plant Maintenance (PM)",
    "BASIS": "SAP Basis / Technical",
}

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

_SCOPE = "enterprise"
_BUILDING_BLOCK_TYPE = "SBB"


@dataclass
class SapImportResult:
    """Holds everything produced by :class:`SapToArchiMateMapper.map_all`."""

    elements: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------


class SapToArchiMateMapper:
    """Map SAP metadata to ArchiMate 3.2 elements and relationships.

    Each element dict carries a ``_temp_id`` key (e.g. ``"element_MM_TABLE_MARA"``)
    that is unique within a single import batch.  Relationship dicts use
    ``source_ref`` / ``target_ref`` instead of ``source_id`` / ``target_id``; the
    caller (``sap_importer.py``) resolves these refs to real DB IDs after INSERT.

    Args:
        architecture_id: ID of the ``ArchitectureModel`` that will own every
            element and relationship produced by this mapper.
    """

    def __init__(self, architecture_id: int) -> None:
        self._architecture_id = architecture_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map_all(
        self,
        tables: list[dict[str, Any]],
        transactions: list[dict[str, Any]],
        roles: list[dict[str, Any]],
    ) -> SapImportResult:
        """Map all SAP metadata to ArchiMate elements + relationships.

        Args:
            tables: List of SAP table dicts (from sap_metadata_reader).
            transactions: List of SAP transaction dicts.
            roles: List of SAP PFCG role dicts.

        Returns:
            :class:`SapImportResult` with elements, relationships, stats and
            any non-fatal errors.
        """
        result = SapImportResult()

        table_elements = self.map_tables(tables)
        function_elements = self.map_transactions(transactions)
        module_elements = self.map_modules(tables, transactions)
        role_elements = self.map_roles(roles)

        all_elements = module_elements + table_elements + function_elements + role_elements

        relationships = self.build_relationships(
            module_elements=module_elements,
            table_elements=table_elements,
            function_elements=function_elements,
            role_elements=role_elements,
            roles_raw=roles,
        )

        result.elements = all_elements
        result.relationships = relationships
        result.stats = {
            "tables": len(table_elements),
            "transactions": len(function_elements),
            "roles": len(role_elements),
            "components": len(module_elements),
            "relationships": len(relationships),
        }

        logger.info(
            "SAP→ArchiMate mapping complete: %d elements, %d relationships",
            len(all_elements),
            len(relationships),
        )
        return result

    # ------------------------------------------------------------------
    # Element mappers
    # ------------------------------------------------------------------

    def map_tables(self, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map SAP tables → ``data_object`` ArchiMate elements.

        Duplicates (same ``table_name``) are silently collapsed to one element.
        """
        seen: set[str] = set()
        elements: list[dict[str, Any]] = []

        for table in tables:
            table_name: str = (table.get("table_name") or "").strip().upper()
            if not table_name:
                logger.warning("Skipping table row with no table_name: %s", table)
                continue
            if table_name in seen:
                continue
            seen.add(table_name)

            description: str = (table.get("description") or "").strip()
            module: str = (table.get("module") or table.get("sap_module") or "").strip().upper()
            field_count: int = int(table.get("field_count") or 0)

            display_name = description if description else table_name
            full_description = (
                f"SAP {module} table {table_name}: {description}"
                if description
                else f"SAP {module} table {table_name}"
            )

            elements.append(
                self._base_element(
                    temp_id=f"element_{module}_TABLE_{table_name}",
                    name=display_name,
                    elem_type="data_object",
                    layer="application",
                    description=full_description,
                    acm_domain=module or None,
                    custom_properties={
                        "sap_table": table_name,
                        "field_count": field_count,
                        "sap_module": module,
                    },
                )
            )

        return elements

    def map_transactions(self, transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map SAP transactions → ``application_function`` ArchiMate elements.

        Duplicates (same ``tcode``) are silently collapsed to one element.
        """
        seen: set[str] = set()
        elements: list[dict[str, Any]] = []

        for txn in transactions:
            tcode: str = (txn.get("tcode") or txn.get("transaction_code") or "").strip().upper()
            if not tcode:
                logger.warning("Skipping transaction row with no tcode: %s", txn)
                continue
            if tcode in seen:
                continue
            seen.add(tcode)

            description: str = (txn.get("description") or txn.get("tcode_description") or "").strip()
            module: str = (txn.get("module") or txn.get("sap_module") or "").strip().upper()
            program: str = (txn.get("program") or txn.get("program_name") or "").strip()

            display_name = description if description else tcode

            elements.append(
                self._base_element(
                    temp_id=f"element_{module}_TCODE_{tcode}",
                    name=display_name,
                    elem_type="application_function",
                    layer="application",
                    description=f"SAP transaction {tcode}: {description}" if description else f"SAP transaction {tcode}",
                    acm_domain=module or None,
                    custom_properties={
                        "sap_tcode": tcode,
                        "program": program,
                        "sap_module": module,
                    },
                )
            )

        return elements

    def map_modules(
        self,
        tables: list[dict[str, Any]],
        transactions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Derive unique SAP modules and create ``application_component`` elements.

        Counts tables and transactions per module from the input data.
        """
        module_tables: dict[str, set[str]] = {}
        module_tcodes: dict[str, set[str]] = {}

        for table in tables:
            module = (table.get("module") or table.get("sap_module") or "").strip().upper()
            table_name = (table.get("table_name") or "").strip().upper()
            if module and table_name:
                module_tables.setdefault(module, set()).add(table_name)

        for txn in transactions:
            module = (txn.get("module") or txn.get("sap_module") or "").strip().upper()
            tcode = (txn.get("tcode") or txn.get("transaction_code") or "").strip().upper()
            if module and tcode:
                module_tcodes.setdefault(module, set()).add(tcode)

        all_modules = set(module_tables) | set(module_tcodes)
        elements: list[dict[str, Any]] = []

        for module in sorted(all_modules):
            display_name = MODULE_DISPLAY_NAMES.get(module, f"SAP {module}")
            table_count = len(module_tables.get(module, set()))
            tcode_count = len(module_tcodes.get(module, set()))

            elements.append(
                self._base_element(
                    temp_id=f"element_MODULE_{module}",
                    name=display_name,
                    elem_type="application_component",
                    layer="application",
                    description=f"SAP module {module} — {table_count} tables, {tcode_count} transactions",
                    acm_domain=module,
                    custom_properties={
                        "sap_module": module,
                        "table_count": table_count,
                        "tcode_count": tcode_count,
                    },
                )
            )

        return elements

    def map_roles(self, roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map SAP PFCG roles → ``business_role`` ArchiMate elements."""
        seen: set[str] = set()
        elements: list[dict[str, Any]] = []

        for role in roles:
            role_name: str = (role.get("role_name") or role.get("name") or "").strip()
            if not role_name:
                logger.warning("Skipping role row with no role_name: %s", role)
                continue
            if role_name in seen:
                continue
            seen.add(role_name)

            description: str = (role.get("description") or role.get("role_description") or "").strip()
            assigned_tcodes: list[str] = role.get("assigned_tcodes") or []
            tcode_count = len(assigned_tcodes)

            display_name = description if description else role_name

            elements.append(
                self._base_element(
                    temp_id=f"element_ROLE_{_sanitise_key(role_name)}",
                    name=display_name,
                    elem_type="business_role",
                    layer="business",
                    description=f"SAP PFCG role {role_name}: {description}" if description else f"SAP PFCG role {role_name}",
                    acm_domain=None,
                    custom_properties={
                        "sap_role": role_name,
                        "tcode_count": tcode_count,
                    },
                )
            )

        return elements

    # ------------------------------------------------------------------
    # Relationship builder
    # ------------------------------------------------------------------

    def build_relationships(
        self,
        module_elements: list[dict[str, Any]],
        table_elements: list[dict[str, Any]],
        function_elements: list[dict[str, Any]],
        role_elements: list[dict[str, Any]],
        roles_raw: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build all ArchiMate relationships between mapped elements.

        Three relationship patterns are generated:

        1. ``data_object`` --[composition]--> ``application_component``
           (each SAP table belongs to its module component)
        2. ``application_function`` --[composition]--> ``application_component``
           (each SAP transaction belongs to its module component)
        3. ``business_role`` --[assignment]--> ``application_function``
           (each role assignment to a transaction, one relationship per pair)

        Relationships use ``source_ref`` / ``target_ref`` referencing the
        ``_temp_id`` values on element dicts; the caller resolves to real IDs.
        """
        relationships: list[dict[str, Any]] = []

        # Index module elements by their module code for fast lookup.
        module_by_code: dict[str, str] = {}
        for elem in module_elements:
            module_code: str = (elem.get("custom_properties") or {}).get("sap_module", "")
            if module_code:
                module_by_code[module_code] = elem["_temp_id"]

        # 1. data_object → application_component (composition)
        for elem in table_elements:
            module_code = (elem.get("custom_properties") or {}).get("sap_module", "")
            component_ref = module_by_code.get(module_code)
            if not component_ref:
                continue
            relationships.append(
                self._relationship(
                    rel_type="composition",
                    source_ref=elem["_temp_id"],
                    target_ref=component_ref,
                    description=f"Table {elem['custom_properties']['sap_table']} is part of {module_code} module",
                )
            )

        # 2. application_function → application_component (composition)
        for elem in function_elements:
            module_code = (elem.get("custom_properties") or {}).get("sap_module", "")
            component_ref = module_by_code.get(module_code)
            if not component_ref:
                continue
            relationships.append(
                self._relationship(
                    rel_type="composition",
                    source_ref=elem["_temp_id"],
                    target_ref=component_ref,
                    description=f"Transaction {elem['custom_properties']['sap_tcode']} is part of {module_code} module",
                )
            )

        # 3. business_role → application_function (assignment) — one per (role, tcode) pair
        # Build lookup: tcode → function element _temp_id
        function_by_tcode: dict[str, str] = {}
        for elem in function_elements:
            tcode: str = (elem.get("custom_properties") or {}).get("sap_tcode", "")
            if tcode:
                function_by_tcode[tcode.upper()] = elem["_temp_id"]

        # Build lookup: role_name → role element _temp_id
        role_by_name: dict[str, str] = {}
        for elem in role_elements:
            sap_role: str = (elem.get("custom_properties") or {}).get("sap_role", "")
            if sap_role:
                role_by_name[sap_role] = elem["_temp_id"]

        seen_assignments: set[tuple[str, str]] = set()
        for role in roles_raw:
            role_name = (role.get("role_name") or role.get("name") or "").strip()
            role_ref = role_by_name.get(role_name)
            if not role_ref:
                continue

            assigned_tcodes: list[str] = role.get("assigned_tcodes") or []
            for tcode in assigned_tcodes:
                tcode_upper = tcode.strip().upper()
                function_ref = function_by_tcode.get(tcode_upper)
                if not function_ref:
                    continue
                pair = (role_ref, function_ref)
                if pair in seen_assignments:
                    continue
                seen_assignments.add(pair)
                relationships.append(
                    self._relationship(
                        rel_type="assignment",
                        source_ref=role_ref,
                        target_ref=function_ref,
                        description=f"Role {role_name} is assigned transaction {tcode_upper}",
                    )
                )

        return relationships

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _base_element(
        self,
        *,
        temp_id: str,
        name: str,
        elem_type: str,
        layer: str,
        description: str,
        acm_domain: str | None,
        custom_properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a dict matching ArchiMateElement column names plus ``_temp_id``."""
        return {
            "_temp_id": temp_id,
            "name": name,
            "type": elem_type,
            "layer": layer,
            "description": description,
            "scope": _SCOPE,
            "building_block_type": _BUILDING_BLOCK_TYPE,
            "acm_domain": acm_domain,
            "architecture_id": self._architecture_id,
            "custom_properties": custom_properties,
        }

    def _relationship(
        self,
        *,
        rel_type: str,
        source_ref: str,
        target_ref: str,
        description: str,
    ) -> dict[str, Any]:
        """Return a relationship dict using ref placeholders instead of DB IDs."""
        return {
            "type": rel_type,
            "source_ref": source_ref,
            "target_ref": target_ref,
            "description": description,
            "architecture_id": self._architecture_id,
        }


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _sanitise_key(value: str) -> str:
    """Replace characters that would break a temp-id with underscores."""
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in value)
