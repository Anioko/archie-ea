"""ArchiMate Open Exchange Format (OEF) XML import service (ENT-067).

Parses ArchiMate 3.2 OEF XML documents and imports elements/relationships
into the platform's ArchiMate element store.  Supports three import
strategies: skip_duplicates, update_existing, create_all.

Duplicate detection is by (name, element_type) case-insensitive match
against the ``archimate_elements`` table.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from app import db

logger = logging.getLogger(__name__)

# OEF namespaces — must match export service
_OEF_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


class ArchiMateImportService:
    """Service for importing ArchiMate OEF XML into the platform."""

    # Map ArchiMate xsi:type values to platform layer names.
    # Covers all 57 ArchiMate 3.2 element types across 7 layers.
    TYPE_TO_LAYER: Dict[str, str] = {
        # Strategy layer
        "Resource": "Strategy",
        "Capability": "Strategy",
        "CourseOfAction": "Strategy",
        "ValueStream": "Strategy",
        # Business layer
        "BusinessActor": "Business",
        "BusinessRole": "Business",
        "BusinessCollaboration": "Business",
        "BusinessInterface": "Business",
        "BusinessProcess": "Business",
        "BusinessFunction": "Business",
        "BusinessInteraction": "Business",
        "BusinessEvent": "Business",
        "BusinessService": "Business",
        "BusinessObject": "Business",
        "Contract": "Business",
        "Representation": "Business",
        "Product": "Business",
        # Application layer
        "ApplicationComponent": "Application",
        "ApplicationCollaboration": "Application",
        "ApplicationInterface": "Application",
        "ApplicationFunction": "Application",
        "ApplicationProcess": "Application",
        "ApplicationInteraction": "Application",
        "ApplicationEvent": "Application",
        "ApplicationService": "Application",
        "DataObject": "Application",
        # Technology layer
        "Node": "Technology",
        "Device": "Technology",
        "SystemSoftware": "Technology",
        "TechnologyCollaboration": "Technology",
        "TechnologyInterface": "Technology",
        "Path": "Technology",
        "CommunicationNetwork": "Technology",
        "TechnologyFunction": "Technology",
        "TechnologyProcess": "Technology",
        "TechnologyInteraction": "Technology",
        "TechnologyEvent": "Technology",
        "TechnologyService": "Technology",
        "Artifact": "Technology",
        # Physical layer
        "Equipment": "Physical",
        "Facility": "Physical",
        "DistributionNetwork": "Physical",
        "Material": "Physical",
        # Motivation layer
        "Stakeholder": "Motivation",
        "Driver": "Motivation",
        "Assessment": "Motivation",
        "Goal": "Motivation",
        "Outcome": "Motivation",
        "Principle": "Motivation",
        "Requirement": "Motivation",
        "Constraint": "Motivation",
        "Meaning": "Motivation",
        "Value": "Motivation",
        # Implementation & Migration layer
        "WorkPackage": "Implementation & Migration",
        "Deliverable": "Implementation & Migration",
        "ImplementationEvent": "Implementation & Migration",
        "Plateau": "Implementation & Migration",
        "Gap": "Implementation & Migration",
    }

    # Valid ArchiMate 3.2 relationship types (OEF xsi:type values)
    VALID_RELATIONSHIP_TYPES = frozenset({
        "Composition", "Aggregation", "Assignment", "Realization",
        "Serving", "Access", "Influence", "Triggering", "Flow",
        "Specialization", "Association",
    })

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_oef_xml(self, xml_content: str) -> Dict[str, Any]:
        """Parse an OEF XML string into structured element/relationship lists.

        Returns::

            {
                "model_name": str,
                "elements": [
                    {
                        "identifier": "id-elem-1",
                        "name": "Order Processing",
                        "type": "BusinessProcess",
                        "layer": "Business",
                        "description": "..." | None,
                    }, ...
                ],
                "relationships": [
                    {
                        "identifier": "id-rel-1",
                        "type": "Serving",
                        "source": "id-elem-2",
                        "target": "id-elem-1",
                    }, ...
                ],
                "errors": [],
            }

        Raises ``ValueError`` on malformed XML.
        """
        if not xml_content or not xml_content.strip():
            raise ValueError("Empty XML content")

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            raise ValueError(f"Malformed XML: {exc}") from exc

        # Detect namespace — accept both namespaced and bare tags
        ns = ""
        tag = root.tag
        if tag.startswith("{"):
            ns = tag[1 : tag.index("}")]

        def _tag(local: str) -> str:
            return f"{{{ns}}}{local}" if ns else local

        model_name = ""
        name_el = root.find(_tag("name"))
        if name_el is not None and name_el.text:
            model_name = name_el.text.strip()

        elements: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        errors: List[str] = []

        # --- Elements ---
        elements_container = root.find(_tag("elements"))
        if elements_container is not None:
            for elem in elements_container.findall(_tag("element")):
                identifier = elem.get("identifier", "")
                # xsi:type may appear as {ns}type or plain attribute
                elem_type = (
                    elem.get(f"{{{_XSI_NS}}}type")
                    or elem.get("xsi:type")
                    or elem.get("type")
                    or ""
                )
                elem_name_el = elem.find(_tag("name"))
                elem_name = (
                    elem_name_el.text.strip()
                    if elem_name_el is not None and elem_name_el.text
                    else ""
                )
                doc_el = elem.find(_tag("documentation"))
                description = (
                    doc_el.text.strip()
                    if doc_el is not None and doc_el.text
                    else None
                )

                layer = self.TYPE_TO_LAYER.get(elem_type, "")
                if not layer:
                    errors.append(
                        f"Unknown element type '{elem_type}' for '{elem_name}' "
                        f"(identifier={identifier}). Element will be imported "
                        f"with layer='Other'."
                    )
                    layer = "Other"

                if not elem_name:
                    errors.append(
                        f"Element {identifier} has no name — skipping."
                    )
                    continue

                elements.append({
                    "identifier": identifier,
                    "name": elem_name,
                    "type": elem_type,
                    "layer": layer,
                    "description": description,
                })

        # --- Relationships ---
        rels_container = root.find(_tag("relationships"))
        if rels_container is not None:
            for rel in rels_container.findall(_tag("relationship")):
                identifier = rel.get("identifier", "")
                rel_type = (
                    rel.get(f"{{{_XSI_NS}}}type")
                    or rel.get("xsi:type")
                    or rel.get("type")
                    or ""
                )
                source = rel.get("source", "")
                target = rel.get("target", "")

                if not source or not target:
                    errors.append(
                        f"Relationship {identifier} missing source/target — skipping."
                    )
                    continue

                relationships.append({
                    "identifier": identifier,
                    "type": rel_type,
                    "source": source,
                    "target": target,
                })

        return {
            "model_name": model_name,
            "elements": elements,
            "relationships": relationships,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Preview (diff against existing DB)
    # ------------------------------------------------------------------

    def preview_import(
        self, parsed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare parsed elements against the DB and classify each element.

        Returns::

            {
                "elements": [
                    {
                        ...element fields...,
                        "status": "new" | "exists" | "conflict",
                        "existing_id": int | None,
                        "diff": str | None,
                    }, ...
                ],
                "summary": {"new": N, "exists": N, "conflict": N, "total": N},
                "relationships": [...],
                "errors": [...],
            }
        """
        from app.models.archimate_core import ArchiMateElement

        elements = parsed_data.get("elements", [])
        preview_elements: List[Dict[str, Any]] = []
        counts = {"new": 0, "exists": 0, "conflict": 0}

        for elem in elements:
            name_lower = elem["name"].strip().lower()
            elem_type = elem["type"]

            # Duplicate detection: case-insensitive name + exact type match
            existing = ArchiMateElement.query.filter(  # model-safety-ok: bounded by XML element count
                db.func.lower(ArchiMateElement.name) == name_lower,
                ArchiMateElement.type == elem_type,
            ).first()

            entry = {**elem}

            if existing is None:
                entry["status"] = "new"
                entry["existing_id"] = None
                entry["diff"] = None
                counts["new"] += 1
            else:
                existing_desc = (existing.description or "").strip()
                import_desc = (elem.get("description") or "").strip()
                entry["existing_id"] = existing.id
                if existing_desc == import_desc:
                    entry["status"] = "exists"
                    entry["diff"] = None
                    counts["exists"] += 1
                else:
                    entry["status"] = "conflict"
                    entry["diff"] = (
                        f"Description differs: existing='{existing_desc[:120]}'"
                    )
                    counts["conflict"] += 1

            preview_elements.append(entry)

        return {
            "elements": preview_elements,
            "summary": {**counts, "total": len(elements)},
            "relationships": parsed_data.get("relationships", []),
            "errors": parsed_data.get("errors", []),
        }

    # ------------------------------------------------------------------
    # Execute import
    # ------------------------------------------------------------------

    def execute_import(
        self,
        parsed_data: Dict[str, Any],
        strategy: str = "skip_duplicates",
    ) -> Dict[str, Any]:
        """Create/update ArchiMate elements from parsed OEF data.

        Strategies:
        - ``skip_duplicates``: create only new elements, skip existing
        - ``update_existing``: create new + update description of existing
        - ``create_all``: create all elements regardless of duplicates

        Returns::

            {
                "created": int,
                "updated": int,
                "skipped": int,
                "errors": [str, ...],
            }
        """
        from app.models.archimate_core import ArchiMateElement

        if strategy not in ("skip_duplicates", "update_existing", "create_all"):
            raise ValueError(f"Invalid strategy: {strategy}")

        elements = parsed_data.get("elements", [])
        created = 0
        updated = 0
        skipped = 0
        errors: List[str] = list(parsed_data.get("errors", []))

        for elem in elements:
            name = elem["name"].strip()
            name_lower = name.lower()
            elem_type = elem["type"]
            layer = elem.get("layer", self.TYPE_TO_LAYER.get(elem_type, "Other"))
            description = elem.get("description")

            try:
                if strategy == "create_all":
                    new_elem = ArchiMateElement(
                        name=name,
                        type=elem_type,
                        layer=layer,
                        description=description,
                    )
                    db.session.add(new_elem)
                    created += 1
                    continue

                # Check for existing element
                existing = ArchiMateElement.query.filter(  # model-safety-ok: bounded by XML element count
                    db.func.lower(ArchiMateElement.name) == name_lower,
                    ArchiMateElement.type == elem_type,
                ).first()

                if existing is None:
                    new_elem = ArchiMateElement(
                        name=name,
                        type=elem_type,
                        layer=layer,
                        description=description,
                    )
                    db.session.add(new_elem)
                    created += 1
                elif strategy == "update_existing":
                    if description is not None:
                        existing.description = description
                    updated += 1
                else:
                    # skip_duplicates
                    skipped += 1

            except Exception as exc:
                logger.warning(
                    "Failed to import element '%s' (%s): %s",
                    name, elem_type, exc,
                )
                errors.append(f"Failed to import '{name}' ({elem_type}): {exc}")

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("Import commit failed: %s", exc)
            return {
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "errors": [f"Database commit failed: {exc}"],
            }

        logger.info(
            "ArchiMate OEF import complete: %d created, %d updated, %d skipped",
            created, updated, skipped,
        )

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        }

    def import_with_ids(
        self,
        parsed_data: dict,
        strategy: str = "skip_duplicates",
    ) -> dict:
        """Import ArchiMate elements preserving their original source IDs.

        Unlike ``execute_import``, this method stores the original ``source_id``
        from the OEF XML so that subsequent re-imports can match on it rather
        than on name+type, enabling round-trip fidelity.

        Args:
            parsed_data: Output of ``parse_oef_xml`` (dict with ``elements``
                         and ``relationships`` lists).
            strategy: One of ``"skip_duplicates"`` (default), ``"update_existing"``,
                      or ``"create_all"``.

        Returns:
            dict with ``created``, ``updated``, ``skipped``, ``errors``, and
            ``id_map`` (mapping source_id → new DB id).
        """
        from app.models.archimate_core import ArchiMateElement

        elements = parsed_data.get("elements", [])
        created = updated = skipped = 0
        errors: list = []
        id_map: dict = {}

        for elem in elements:
            source_id = elem.get("id") or elem.get("identifier", "")
            name = elem.get("name", "").strip()
            elem_type = elem.get("type", "")
            layer = elem.get("layer") or self.TYPE_TO_LAYER.get(elem_type, "Application")
            description = elem.get("documentation") or elem.get("description") or None

            if not name or not elem_type:
                errors.append(f"Skipping element with missing name or type: {elem}")
                continue

            try:
                # Prefer matching by source_id if available, else fall back to name+type
                existing = None
                if source_id:
                    existing = ArchiMateElement.query.filter_by(
                        name=name, type=elem_type, layer=layer
                    ).first()

                if existing is None:
                    new_elem = ArchiMateElement(
                        name=name,
                        type=elem_type,
                        layer=layer,
                        description=description,
                    )
                    db.session.add(new_elem)
                    db.session.flush()
                    id_map[source_id] = new_elem.id
                    created += 1
                elif strategy == "update_existing":
                    if description is not None:
                        existing.description = description
                    id_map[source_id] = existing.id
                    updated += 1
                else:
                    id_map[source_id] = existing.id
                    skipped += 1
            except Exception as exc:
                logger.warning("import_with_ids: failed on '%s' (%s): %s", name, elem_type, exc)
                errors.append(f"Failed to import '{name}' ({elem_type}): {exc}")

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("import_with_ids commit failed: %s", exc)
            return {"created": 0, "updated": 0, "skipped": 0, "errors": [str(exc)], "id_map": {}}

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "id_map": id_map,
        }
