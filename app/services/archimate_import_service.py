"""ArchiMate Open Exchange Format (OEF) XML import service (ENT-067).

Parses ArchiMate 3.2 OEF XML documents and imports elements/relationships
into the platform's ArchiMate element store.  Supports three import
strategies: skip_duplicates, update_existing, create_all.

Duplicate detection is by (name, element_type) case-insensitive match
against the ``archimate_elements`` table.
"""

from app.utils import safe_xml  # untrusted XML: entity-expansion safe
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
        # Implementation & Migration layer. DOGFOOD-002: the stored key must
        # be the one the Element Catalog counts and filters on
        # (``layer_order`` in app/modules/architecture/routes/archimate_routes.py
        # and the OEF exporter's map in app/services/archimate_oef_service.py
        # both use "Implementation"). Writing "Implementation & Migration"
        # here made 35 of customer zero's 168 elements land and vanish.
        "WorkPackage": "Implementation",
        "Deliverable": "Implementation",
        "ImplementationEvent": "Implementation",
        "Plateau": "Implementation",
        "Gap": "Implementation",
    }

    # Column widths on ``archimate_elements`` (app/models/archimate_core.py).
    # DOGFOOD-001: the parser checks these so preview reports what execute
    # will refuse, instead of one over-long name aborting the whole import
    # with a raw ``StringDataRightTruncation`` from the database.
    MAX_NAME_LENGTH = 100
    MAX_TYPE_LENGTH = 50

    # DOGFOOD-003 (relationship-validity authority audit): this class used to
    # carry its own `VALID_RELATIONSHIP_TYPES` flat set — a second opinion on
    # relationship validity with no element-type awareness, and unread by
    # anything (grepped: no external reference). Deleted. The authoritative
    # check is `RelationshipValidator.validate_relationship()`
    # (`app/modules/architecture/services/relationship_validator.py`), backed
    # by the element-type-keyed matrix in
    # `app/config/archimate_relationship_matrix.py` — see `_classify_relationships`
    # below, which is the only place this service classifies relationships.

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
                        "properties": {"status": "RULED", ...},
                        "invalid": "name_too_long (269 chars > 100)",  # only when present
                    }, ...
                ],
                "relationships": [
                    {
                        "identifier": "id-rel-1",
                        "type": "Serving",
                        "source": "id-elem-2",
                        "target": "id-elem-1",
                        "description": "..." | None,
                    }, ...
                ],
                "errors": [],
            }

        An element with ``invalid`` set is kept in the list so preview can
        show it, but ``execute_import`` refuses it (counted in ``failed``)
        rather than letting the database reject the whole batch.

        Raises ``ValueError`` on malformed XML.
        """
        if not xml_content or not xml_content.strip():
            raise ValueError("Empty XML content")

        try:
            root = safe_xml.fromstring(xml_content)
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

        # --- Property definitions (id -> name) ---
        # DOGFOOD-004: OEF stores properties indirectly — each <property> on
        # an element references a <propertyDefinition> by id, and the
        # human-readable key lives on the definition, not the property.
        property_defs: Dict[str, str] = {}
        propdefs_container = root.find(_tag("propertyDefinitions"))
        if propdefs_container is not None:
            for pd in propdefs_container.findall(_tag("propertyDefinition")):
                pd_id = pd.get("identifier", "")
                pd_name_el = pd.find(_tag("name"))
                pd_name = (
                    pd_name_el.text.strip()
                    if pd_name_el is not None and pd_name_el.text
                    else pd_id
                )
                if pd_id:
                    property_defs[pd_id] = pd_name

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

                # DOGFOOD-001: flag what the database would reject, per
                # element, so preview reports it and execute skips it.
                invalid = None
                if len(elem_name) > self.MAX_NAME_LENGTH:
                    invalid = (
                        f"name_too_long ({len(elem_name)} chars > {self.MAX_NAME_LENGTH})"
                    )
                    errors.append(
                        f"Element {identifier} '{elem_name[:40]}…' ({elem_type}) has a "
                        f"name of {len(elem_name)} characters; the limit is "
                        f"{self.MAX_NAME_LENGTH}. It will not be imported — shorten the "
                        f"name in the source model (the full text can go in its documentation)."
                    )
                elif len(elem_type) > self.MAX_TYPE_LENGTH:
                    invalid = (
                        f"type_too_long ({len(elem_type)} chars > {self.MAX_TYPE_LENGTH})"
                    )
                    errors.append(
                        f"Element {identifier} '{elem_name}' has a type of "
                        f"{len(elem_type)} characters; the limit is {self.MAX_TYPE_LENGTH}. "
                        f"It will not be imported."
                    )

                # --- Properties (DOGFOOD-004 minimal convention — see
                # docs/adr/0009-continuous-model-maintenance.md (Addendum)) ---
                properties: Dict[str, str] = {}
                props_container = elem.find(_tag("properties"))
                if props_container is not None:
                    for prop in props_container.findall(_tag("property")):
                        pd_ref = prop.get("propertyDefinitionRef", "")
                        value_el = prop.find(_tag("value"))
                        value = (
                            value_el.text.strip()
                            if value_el is not None and value_el.text
                            else ""
                        )
                        key = property_defs.get(pd_ref, pd_ref)
                        if key:
                            properties[key] = value

                entry: Dict[str, Any] = {
                    "identifier": identifier,
                    "name": elem_name,
                    "type": elem_type,
                    "layer": layer,
                    "description": description,
                    "properties": properties,
                }
                if invalid:
                    entry["invalid"] = invalid
                elements.append(entry)

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

                rel_doc_el = rel.find(_tag("documentation"))
                rel_description = (
                    rel_doc_el.text.strip()
                    if rel_doc_el is not None and rel_doc_el.text
                    else None
                )

                relationships.append({
                    "identifier": identifier,
                    "type": rel_type,
                    "source": source,
                    "target": target,
                    "description": rel_description,
                })

        return {
            "model_name": model_name,
            "elements": elements,
            "relationships": relationships,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Relationship classification — shared by preview and execute so the
    # two agree (DOGFOOD-003 acceptance criterion). The only validity
    # authority consulted is RelationshipValidator, backed by the
    # element-type-keyed matrix in app/config/archimate_relationship_matrix.py.
    # ------------------------------------------------------------------

    def _classify_relationships(
        self,
        relationships: List[Dict[str, Any]],
        type_by_identifier: Dict[str, str],
        id_map: Dict[str, int] = None,
    ) -> List[Dict[str, Any]]:
        """Validate each parsed relationship and annotate it with a status.

        ``type_by_identifier`` maps an OEF element identifier to its
        ArchiMate element type — used to resolve source/target types for
        the validator (identifiers, not names, because names may collide).

        ``id_map``, when given, additionally maps identifier to the
        already-persisted DB row id, so a valid entry also carries
        ``source_id``/``target_id`` ready for insert. Pass ``None`` for a
        type-only preview pass.

        Returns a list of dicts, each with ``identifier``, ``type``
        (normalized), ``source``, ``target``, ``status`` ("valid" |
        "invalid"), and — only when invalid — ``reason`` (human-readable,
        never a raw exception) and ``suggestions``.
        """
        from app.modules.architecture.routes.archimate_routes import _normalize_rel_type
        from app.modules.architecture.services.relationship_validator import (
            RelationshipValidator,
        )

        validator = RelationshipValidator()
        out: List[Dict[str, Any]] = []

        for rel in relationships:
            identifier = rel.get("identifier", "")
            rel_type_raw = rel.get("type", "")
            source_ref = rel.get("source", "")
            target_ref = rel.get("target", "")

            source_type = type_by_identifier.get(source_ref)
            target_type = type_by_identifier.get(target_ref)

            entry: Dict[str, Any] = {
                "identifier": identifier,
                "type": rel_type_raw,
                "source": source_ref,
                "target": target_ref,
                "description": rel.get("description"),
            }

            if source_type is None or target_type is None:
                entry["status"] = "invalid"
                entry["reason"] = (
                    "Source or target element was not imported "
                    "(missing, unnamed, or failed to parse)."
                )
                entry["suggestions"] = []
                out.append(entry)
                continue

            normalized_type = _normalize_rel_type(rel_type_raw)
            entry["type"] = normalized_type
            result = validator.validate_relationship(
                source_type, target_type, normalized_type
            )

            if not result.is_valid:
                entry["status"] = "invalid"
                entry["reason"] = (
                    "; ".join(result.errors)
                    if result.errors
                    else (
                        f"'{rel_type_raw}' is not a valid ArchiMate relationship "
                        f"between {source_type} and {target_type}."
                    )
                )
                entry["suggestions"] = result.suggestions
                out.append(entry)
                continue

            entry["status"] = "valid"
            if id_map is not None:
                entry["source_id"] = id_map.get(source_ref)
                entry["target_id"] = id_map.get(target_ref)
            out.append(entry)

        return out

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
                        "status": "new" | "exists" | "conflict" | "invalid",
                        "existing_id": int | None,
                        "diff": str | None,
                    }, ...
                ],
                "summary": {"new": N, "exists": N, "conflict": N, "invalid": N, "total": N, ...},
                "relationships": [...],
                "errors": [...],
            }

        ``invalid`` (DOGFOOD-001) counts the elements ``execute_import`` will
        refuse, so the number shown before the import matches what happens
        during it.
        """
        from app.models.archimate_core import ArchiMateElement

        elements = parsed_data.get("elements", [])
        preview_elements: List[Dict[str, Any]] = []
        counts = {"new": 0, "exists": 0, "conflict": 0, "invalid": 0}

        for elem in elements:
            if elem.get("invalid"):
                preview_elements.append({
                    **elem,
                    "status": "invalid",
                    "existing_id": None,
                    "diff": elem["invalid"],
                })
                counts["invalid"] += 1
                continue

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
                        f"Description differs: existing='{existing_desc[:120]}'"  # raw-html-ok: internal diff-conflict message field, never rendered as HTML/browser output
                    )
                    counts["conflict"] += 1

            preview_elements.append(entry)

        # Invalid elements will not be written, so relationships touching
        # them are unresolved in preview exactly as they will be in execute.
        type_by_identifier = {
            elem["identifier"]: elem["type"]
            for elem in elements
            if elem.get("identifier") and not elem.get("invalid")
        }
        relationships_preview = self._classify_relationships(
            parsed_data.get("relationships", []), type_by_identifier, id_map=None
        )
        relationships_valid = sum(1 for r in relationships_preview if r["status"] == "valid")
        relationships_invalid = len(relationships_preview) - relationships_valid

        return {
            "elements": preview_elements,
            "summary": {
                **counts,
                "total": len(elements),
                "relationships_valid": relationships_valid,
                "relationships_invalid": relationships_invalid,
                "relationships_total": len(relationships_preview),
            },
            "relationships": relationships_preview,
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

        Also writes relationships in a second pass (DOGFOOD-003) and
        ``<properties>`` into ``custom_properties`` (DOGFOOD-004, per the
        convention in ``docs/adr/0009-continuous-model-maintenance.md (Addendum)``).

        Returns::

            {
                "created": int,
                "updated": int,
                "skipped": int,
                "failed": int,
                "errors": [str, ...],
                "relationships_created": int,
                "relationships_skipped": int,
                "relationships_failed": [
                    {"identifier", "type", "source", "target", "reason"}, ...
                ],
            }

        DOGFOOD-001: every element is written inside its own savepoint
        (``db.session.begin_nested()``). An element the parser flagged as
        ``invalid``, or one the database refuses, is counted in ``failed``
        and named in ``errors`` in plain English; the rest of the model
        still lands. Nothing here ever aborts the whole batch.
        """
        from datetime import datetime, timezone

        from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship

        if strategy not in ("skip_duplicates", "update_existing", "create_all"):
            raise ValueError(f"Invalid strategy: {strategy}")

        elements = parsed_data.get("elements", [])
        created = 0
        updated = 0
        skipped = 0
        failed = 0
        errors: List[str] = list(parsed_data.get("errors", []))

        # OEF identifier -> {"db_id": int, "type": str}. Populated for every
        # element touched this run, including pre-existing ones matched by
        # name+type under skip_duplicates/update_existing — otherwise every
        # relationship touching a pre-existing element would fail to resolve.
        id_map: Dict[str, Dict[str, Any]] = {}

        def _write_properties(target_row, props: Dict[str, str], merge: bool) -> None:
            """Persist parsed <properties> onto custom_properties (DOGFOOD-004).

            Every property is a literal key, value as parsed — no renaming,
            no coercion. ``archie:imported_at`` is the one namespaced,
            reserved key, recording provenance for a future model-age
            measurement (ADR 0009 names no field of its own).
            """
            if not props:
                return
            base = dict(target_row.custom_properties or {}) if merge else {}
            base.update(props)
            base["archie:imported_at"] = datetime.now(timezone.utc).isoformat()
            target_row.custom_properties = base

        for elem in elements:
            name = elem["name"].strip()
            name_lower = name.lower()
            elem_type = elem["type"]
            layer = elem.get("layer", self.TYPE_TO_LAYER.get(elem_type, "Other"))
            description = elem.get("description")
            identifier = elem.get("identifier", "")
            props = elem.get("properties") or {}

            # DOGFOOD-001: the parser already flagged this element (name or
            # type wider than its column). Refuse it here, by name, and carry
            # on — the database never sees it, so nothing else is lost.
            if elem.get("invalid"):
                failed += 1
                errors.append(
                    f"Refused '{name[:40]}…' ({elem_type}, identifier={identifier or 'n/a'}): "
                    f"{elem['invalid']}."
                )
                continue

            try:
                # One savepoint per element. A failed INSERT/UPDATE rolls
                # back this element only; the outer transaction stays live
                # for every element after it, and the counters/id_map are
                # touched only after the flush succeeds, so they never
                # describe a row that does not exist.
                with db.session.begin_nested():
                    existing = None
                    if strategy != "create_all":
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
                        _write_properties(new_elem, props, merge=False)
                        db.session.flush()
                        if identifier:
                            id_map[identifier] = {"db_id": new_elem.id, "type": elem_type}
                        created += 1
                    elif strategy == "update_existing":
                        if description is not None:
                            existing.description = description
                        _write_properties(existing, props, merge=True)
                        db.session.flush()
                        if identifier:
                            id_map[identifier] = {"db_id": existing.id, "type": existing.type}
                        updated += 1
                    else:
                        # skip_duplicates — element itself is untouched, but it
                        # still needs an id-map entry so relationships that
                        # target it can resolve.
                        if identifier:
                            id_map[identifier] = {"db_id": existing.id, "type": existing.type}
                        skipped += 1

            except Exception as exc:
                logger.warning(
                    "Failed to import element '%s' (%s): %s",
                    name, elem_type, exc,
                )
                # M6: a raw exception string (e.g. a DB constraint message)
                # must never reach the client. The savepoint has already
                # been rolled back by the context manager, so the session
                # is usable for the next element.
                failed += 1
                errors.append(
                    f"Failed to import '{name[:40]}' ({elem_type}, identifier={identifier or 'n/a'}): "
                    "the database refused this element. It was skipped; the rest of the model "
                    "was still imported."
                )

        # --- Relationships (second pass, after every element has an id) ---
        type_by_identifier = {ident: info["type"] for ident, info in id_map.items()}
        classified = self._classify_relationships(
            parsed_data.get("relationships", []), type_by_identifier, id_map=None
        )
        # id_map carries db_id per identifier; attach it to the "valid" entries.
        db_id_by_identifier = {ident: info["db_id"] for ident, info in id_map.items()}

        relationships_created = 0
        relationships_skipped = 0
        relationships_failed: List[Dict[str, Any]] = []

        for rel in classified:
            if rel["status"] == "invalid":
                relationships_failed.append({
                    "identifier": rel["identifier"],
                    "type": rel["type"],
                    "source": rel["source"],
                    "target": rel["target"],
                    "reason": rel["reason"],
                    "suggestions": rel.get("suggestions", []),
                })
                continue

            source_db_id = db_id_by_identifier.get(rel["source"])
            target_db_id = db_id_by_identifier.get(rel["target"])
            if not source_db_id or not target_db_id:
                relationships_failed.append({
                    "identifier": rel["identifier"],
                    "type": rel["type"],
                    "source": rel["source"],
                    "target": rel["target"],
                    "reason": "Source or target element was not imported this run.",
                })
                continue

            try:
                # Same savepoint discipline as elements: one bad row never
                # takes the rest of the relationships (or the elements
                # already flushed) down with it.
                with db.session.begin_nested():
                    existing_rel = ArchiMateRelationship.query.filter_by(
                        source_id=source_db_id, target_id=target_db_id, type=rel["type"],
                    ).first()
                    if existing_rel is not None:
                        relationships_skipped += 1
                    else:
                        new_rel = ArchiMateRelationship(
                            type=rel["type"],
                            source_id=source_db_id,
                            target_id=target_db_id,
                            # <documentation> on the relationship (DOGFOOD-003):
                            # "ruling constrains offer" is the reason the edge
                            # exists, and it must survive the import.
                            description=rel.get("description"),
                        )
                        db.session.add(new_rel)
                        db.session.flush()
                        relationships_created += 1
            except Exception as exc:
                logger.warning(
                    "Failed to import relationship %s (%s -> %s): %s",
                    rel["identifier"], rel["source"], rel["target"], exc,
                )
                relationships_failed.append({
                    "identifier": rel["identifier"],
                    "type": rel["type"],
                    "source": rel["source"],
                    "target": rel["target"],
                    "reason": "Could not save this relationship due to an internal error.",
                })

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error("Import commit failed: %s", exc)
            return {
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "failed": len(elements),
                "errors": ["Database commit failed. No changes were saved."],
                "relationships_created": 0,
                "relationships_skipped": 0,
                "relationships_failed": [],
            }

        logger.info(
            "ArchiMate OEF import complete: %d created, %d updated, %d skipped, %d failed elements; "
            "%d created, %d skipped, %d failed relationships",
            created, updated, skipped, failed,
            relationships_created, relationships_skipped, len(relationships_failed),
        )

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "errors": errors,
            "relationships_created": relationships_created,
            "relationships_skipped": relationships_skipped,
            "relationships_failed": relationships_failed,
        }

    def import_with_ids(
        self,
        parsed_data: dict,
        strategy: str = "skip_duplicates",
    ) -> dict:
        """Import ArchiMate elements preserving their original source IDs.

        DOGFOOD-003 note: nothing calls this method — the route
        (``/solutions/import/archimate/execute``) calls ``execute_import``.
        Its docstring is also misleading: despite claiming ``source_id``
        matching it still matches existing rows by ``name/type/layer``
        (``.filter_by(name=name, type=elem_type, layer=layer)`` below), never
        by the OEF identifier. ``execute_import`` now builds its own
        identifier -> db-id map directly (id_map, above) rather than reusing
        this method, per the task brief's instruction not to build on it
        without fixing it first. Left in place, unfixed, as dead code — a
        follow-up should either repair or delete it rather than let a third
        near-duplicate importer accumulate.

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
