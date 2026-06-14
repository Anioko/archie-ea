"""ArchiMate Open Exchange Format (OEF) import/export service.

Implements XML-based interchange compatible with ArchiMate 3.0 OEF specification.
"""

import xml.etree.ElementTree as ET
from datetime import datetime  # dead-code-ok

from app import db
from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship, ArchitectureModel


class ArchiMateOEFService:
    """Service for ArchiMate Open Exchange Format XML import/export."""

    ARCHIMATE_NS = "http://www.opengroup.org/xsd/archimate/3.0/"
    XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
    DC_NS = "http://purl.org/dc/elements/1.1/"

    # Maps OEF xsi:type to (layer, element_type)
    _TYPE_MAP: dict[str, tuple[str, str]] = {
        # Business layer
        "BusinessActor": ("Business", "BusinessActor"),
        "BusinessRole": ("Business", "BusinessRole"),
        "BusinessProcess": ("Business", "BusinessProcess"),
        "BusinessFunction": ("Business", "BusinessFunction"),
        "BusinessService": ("Business", "BusinessService"),
        "BusinessObject": ("Business", "BusinessObject"),
        "BusinessInterface": ("Business", "BusinessInterface"),
        "BusinessEvent": ("Business", "BusinessEvent"),
        "BusinessInteraction": ("Business", "BusinessInteraction"),
        "BusinessCollaboration": ("Business", "BusinessCollaboration"),
        "Contract": ("Business", "Contract"),
        "Representation": ("Business", "Representation"),
        # Application layer
        "ApplicationComponent": ("Application", "ApplicationComponent"),
        "ApplicationInterface": ("Application", "ApplicationInterface"),
        "ApplicationService": ("Application", "ApplicationService"),
        "ApplicationFunction": ("Application", "ApplicationFunction"),
        "ApplicationProcess": ("Application", "ApplicationProcess"),
        "DataObject": ("Application", "DataObject"),
        # Technology layer
        "Node": ("Technology", "Node"),
        "Device": ("Technology", "Device"),
        "SystemSoftware": ("Technology", "SystemSoftware"),
        "TechnologyService": ("Technology", "TechnologyService"),
        "TechnologyInterface": ("Technology", "TechnologyInterface"),
        "Path": ("Technology", "Path"),
        "CommunicationNetwork": ("Technology", "CommunicationNetwork"),
        "Artifact": ("Technology", "Artifact"),
        # Strategy layer
        "Resource": ("Strategy", "Resource"),
        "Capability": ("Strategy", "Capability"),
        "CourseOfAction": ("Strategy", "CourseOfAction"),
        "ValueStream": ("Strategy", "ValueStream"),
        # Motivation layer
        "Driver": ("Motivation", "Driver"),
        "Assessment": ("Motivation", "Assessment"),
        "Goal": ("Motivation", "Goal"),
        "Outcome": ("Motivation", "Outcome"),
        "Principle": ("Motivation", "Principle"),
        "Requirement": ("Motivation", "Requirement"),
        "Constraint": ("Motivation", "Constraint"),
        "Stakeholder": ("Motivation", "Stakeholder"),
        "Value": ("Motivation", "Value"),
        "Meaning": ("Motivation", "Meaning"),
        # Implementation & Migration layer
        "WorkPackage": ("Implementation", "WorkPackage"),
        "Deliverable": ("Implementation", "Deliverable"),
        "ImplementationEvent": ("Implementation", "ImplementationEvent"),
        "Plateau": ("Implementation", "Plateau"),
        "Gap": ("Implementation", "Gap"),
    }

    def export_model(self, model_id: int | None = None) -> str:
        """Export elements (and optionally a specific model) to OEF XML string."""
        ET.register_namespace("", self.ARCHIMATE_NS)
        ET.register_namespace("xsi", self.XSI_NS)
        ET.register_namespace("dc", self.DC_NS)

        # Determine model metadata
        model = None
        if model_id is not None:
            model = db.session.get(ArchitectureModel, model_id)

        model_name = model.name if model else "ArchiMate Model"
        model_identifier = f"id-model-{model_id}" if model_id else "id-model-export"

        root = ET.Element(
            f"{{{self.ARCHIMATE_NS}}}model",
            attrib={
                f"{{{self.XSI_NS}}}schemaLocation": (
                    f"{self.ARCHIMATE_NS} "
                    "http://www.opengroup.org/xsd/archimate/3.1/archimate3_Diagram.xsd"
                ),
                "identifier": model_identifier,
                "version": "3.0",
            },
        )

        name_el = ET.SubElement(root, f"{{{self.ARCHIMATE_NS}}}name")
        name_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        name_el.text = model_name

        # Query elements
        query = ArchiMateElement.query
        if model_id is not None:
            query = query.filter_by(architecture_id=model_id)
        elements = query.all()

        # Query relationships
        rel_query = ArchiMateRelationship.query
        if model_id is not None:
            rel_query = rel_query.filter_by(architecture_id=model_id)
        relationships = rel_query.all()

        # <elements>
        elements_el = ET.SubElement(root, f"{{{self.ARCHIMATE_NS}}}elements")
        for elem in elements:
            el_type = elem.type or "ApplicationComponent"
            el_attrib = {
                "identifier": f"id-{elem.id}",
                f"{{{self.XSI_NS}}}type": el_type,
            }
            el_node = ET.SubElement(elements_el, f"{{{self.ARCHIMATE_NS}}}element", el_attrib)
            el_name = ET.SubElement(el_node, f"{{{self.ARCHIMATE_NS}}}name")
            el_name.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
            el_name.text = elem.name or ""
            if elem.description:
                doc_el = ET.SubElement(el_node, f"{{{self.ARCHIMATE_NS}}}documentation")
                doc_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                doc_el.text = elem.description

        # <relationships>
        relationships_el = ET.SubElement(root, f"{{{self.ARCHIMATE_NS}}}relationships")
        for rel in relationships:
            if rel.source_id is None or rel.target_id is None:
                continue
            rel_type = rel.type or "Association"
            rel_attrib = {
                "identifier": f"id-rel-{rel.id}",
                f"{{{self.XSI_NS}}}type": rel_type,
                "source": f"id-{rel.source_id}",
                "target": f"id-{rel.target_id}",
            }
            ET.SubElement(relationships_el, f"{{{self.ARCHIMATE_NS}}}relationship", rel_attrib)

        return ET.tostring(root, encoding="unicode", xml_declaration=False)

    def import_model(self, xml_string: str) -> dict:
        """Parse OEF XML and upsert elements/relationships.

        Returns a summary dict with counts of created/updated items and errors.
        """
        result = {
            "elements_created": 0,
            "elements_updated": 0,
            "relationships_created": 0,
            "relationships_updated": 0,
            "errors": [],
        }

        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as exc:
            result["errors"].append(f"XML parse error: {exc}")
            return result

        ns = {"a": self.ARCHIMATE_NS, "xsi": self.XSI_NS}

        # Resolve default namespace from root tag if present
        def _ns_tag(tag: str) -> str:
            """Return tag with archimate namespace prefix."""
            return f"{{{self.ARCHIMATE_NS}}}{tag}"

        # Map OEF identifiers → DB ids for relationship wiring
        identifier_to_db_id: dict[str, int] = {}

        # --- Elements ---
        elements_container = root.find(_ns_tag("elements"))
        if elements_container is not None:
            for el_node in elements_container.findall(_ns_tag("element")):
                try:
                    identifier = el_node.get("identifier", "")
                    xsi_type = el_node.get(f"{{{self.XSI_NS}}}type") or el_node.get("type") or ""
                    layer, elem_type = self._element_type_to_archimate(xsi_type)

                    name_node = el_node.find(_ns_tag("name"))
                    name = (name_node.text or "").strip() if name_node is not None else xsi_type

                    doc_node = el_node.find(_ns_tag("documentation"))
                    description = (doc_node.text or "").strip() if doc_node is not None else None

                    # Try to match existing element by identifier suffix (e.g. "id-42" → id=42)
                    existing = None
                    if identifier.startswith("id-") and not identifier.startswith("id-rel-"):
                        id_part = identifier[3:]
                        if id_part.isdigit():
                            existing = db.session.get(ArchiMateElement, int(id_part))

                    if existing:
                        existing.name = name
                        existing.type = elem_type
                        existing.layer = layer
                        if description:
                            existing.description = description
                        identifier_to_db_id[identifier] = existing.id
                        result["elements_updated"] += 1
                    else:
                        new_el = ArchiMateElement(
                            name=name,
                            type=elem_type,
                            layer=layer,
                            description=description,
                        )
                        db.session.add(new_el)
                        db.session.flush()  # get id
                        identifier_to_db_id[identifier] = new_el.id
                        result["elements_created"] += 1

                except Exception as exc:  # noqa: BLE001
                    result["errors"].append(f"Element '{el_node.get('identifier', '?')}': {exc}")

        # --- Relationships ---
        rels_container = root.find(_ns_tag("relationships"))
        if rels_container is not None:
            for rel_node in rels_container.findall(_ns_tag("relationship")):
                try:
                    rel_identifier = rel_node.get("identifier", "")
                    xsi_type = (
                        rel_node.get(f"{{{self.XSI_NS}}}type") or rel_node.get("type") or "Association"
                    )
                    source_ref = rel_node.get("source", "")
                    target_ref = rel_node.get("target", "")

                    source_db_id = identifier_to_db_id.get(source_ref)
                    target_db_id = identifier_to_db_id.get(target_ref)

                    # Fallback: parse numeric id from source/target ref
                    if source_db_id is None and source_ref.startswith("id-"):
                        part = source_ref[3:]
                        if part.isdigit():
                            source_db_id = int(part)
                    if target_db_id is None and target_ref.startswith("id-"):
                        part = target_ref[3:]
                        if part.isdigit():
                            target_db_id = int(part)

                    if source_db_id is None or target_db_id is None:
                        result["errors"].append(
                            f"Relationship '{rel_identifier}': could not resolve "
                            f"source='{source_ref}' or target='{target_ref}'"
                        )
                        continue

                    # Try to match existing
                    existing_rel = None
                    if rel_identifier.startswith("id-rel-"):
                        id_part = rel_identifier[7:]
                        if id_part.isdigit():
                            existing_rel = db.session.get(ArchiMateRelationship, int(id_part))

                    if existing_rel:
                        existing_rel.type = xsi_type
                        existing_rel.source_id = source_db_id
                        existing_rel.target_id = target_db_id
                        result["relationships_updated"] += 1
                    else:
                        new_rel = ArchiMateRelationship(
                            type=xsi_type,
                            source_id=source_db_id,
                            target_id=target_db_id,
                        )
                        db.session.add(new_rel)
                        result["relationships_created"] += 1

                except Exception as exc:  # noqa: BLE001
                    result["errors"].append(
                        f"Relationship '{rel_node.get('identifier', '?')}': {exc}"
                    )

        try:
            db.session.commit()
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            result["errors"].append(f"Database commit error: {exc}")

        return result

    def _element_type_to_archimate(self, xsi_type: str) -> tuple[str, str]:
        """Convert OEF xsi:type like 'BusinessProcess' to (layer, element_type)."""
        # Strip namespace prefix if present (e.g. "archimate3:BusinessProcess")
        if ":" in xsi_type:
            xsi_type = xsi_type.split(":")[-1]
        return self._TYPE_MAP.get(xsi_type, ("Application", xsi_type or "ApplicationComponent"))
