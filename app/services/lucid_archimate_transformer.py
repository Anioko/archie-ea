"""Lucidchart payload transformer for ArchiMate composer imports."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class LucidArchiMateTransformer:
    """Transform Lucidchart document contents into canonical ArchiMate payloads."""

    LUCID_CLASS_TO_ELEMENT_TYPE: Dict[str, str] = {
        "ArchiMate3ServiceBoxBlock": "ApplicationService",
        "ArchiMate3ComponentBoxBlock": "ApplicationComponent",
        "ArchiMate3InterfaceBoxBlock": "ApplicationInterface",
        "ArchiMate3LocationBoxBlock": "Location",
        "ArchiMate3CommunicationNetworkBoxBlock": "CommunicationNetwork",
        "ArchiMate3ObjectBoxBlock": "DataObject",
        "ArchiMate3GroupingBoxBlock": "Grouping",
    }

    LUCID_CLASS_TO_RENDERING_MODE: Dict[str, str] = {
        "ArchiMate3ServiceBoxBlock": "lucid_white_box",
        "ArchiMate3ComponentBoxBlock": "lucid_black_box",
        "ArchiMate3InterfaceBoxBlock": "lucid_white_box",
        "ArchiMate3EventBoxBlock": "lucid_white_box",
        "ArchiMate3LocationBoxBlock": "lucid_white_box",
        "ArchiMate3CommunicationNetworkBoxBlock": "lucid_white_box",
        "ArchiMate3ObjectBoxBlock": "lucid_white_box",
        "ArchiMate3GroupingBoxBlock": "lucid_white_box",
    }

    APPLICATION_CONTEXT_CLASSES = {
        "ArchiMate3ServiceBoxBlock",
        "ArchiMate3ComponentBoxBlock",
        "ArchiMate3InterfaceBoxBlock",
        "ArchiMate3ObjectBoxBlock",
    }

    KNOWN_STEREOTYPES = {
        "SERVICE",
        "INTERFACE",
        "EVENT",
        "DATA OBJECT",
    }

    ELEMENT_TYPE_TO_LAYER: Dict[str, str] = {
        "ApplicationService": "application",
        "ApplicationComponent": "application",
        "ApplicationInterface": "application",
        "ApplicationEvent": "application",
        "BusinessEvent": "business",
        "Location": "physical",
        "CommunicationNetwork": "technology",
        "DataObject": "application",
        "Grouping": "other",
    }

    # Lucid line-endpoint arrowhead styles → canonical ArchiMate relationship type.
    ENDPOINT_STYLE_TO_RELATIONSHIP: Dict[str, str] = {
        "Generalization": "specialization",
    }

    CONNECTION_SPEC_KEY_MAP: Dict[str, str] = {
        "data": "data_name",
        "transfer strategy": "transfer_strategy",
        "interface type": "interface_type",
        "iam": "iam_method",
        "file format": "file_format",
        "file name": "file_name_pattern",
        "protocol": "protocol",
        "direction": "direction",
    }

    RELATIONSHIP_LABEL_MAP: Dict[str, str] = {
        "triggers": "triggering",
        "flow": "flow",
        "assigned": "assignment",
        "accesses": "access",
    }

    GEOMETRY_KEYS = {
        "x",
        "y",
        "width",
        "height",
        "position",
        "geometry",
        "bounds",
        "boundingBox",
        "vertices",
        "waypoints",
    }

    def __init__(self, event_element_type: str = "BusinessEvent"):
        if event_element_type not in {"BusinessEvent", "ApplicationEvent"}:
            raise ValueError(
                "event_element_type must be 'BusinessEvent' or 'ApplicationEvent'"
            )
        self.event_element_type = event_element_type

    def transform_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return canonical elements, relationships, and import warnings."""
        if not isinstance(payload, dict):
            raise ValueError("Lucidchart payload must be a dictionary")

        payload = self._normalize_payload(payload)
        pages = payload.get("pages") or []
        if not isinstance(pages, list) or not pages:
            raise ValueError("Lucidchart payload must include at least one page")

        warnings: List[str] = []
        elements: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        imported_shape_ids: Dict[str, Dict[str, Any]] = {}
        skipped_connector_count = 0
        skipped_relationship_count = 0
        total_shapes_seen = 0
        inferred_event_type = self._infer_event_element_type(pages)

        geometry_present = self._payload_has_geometry(payload)
        if not geometry_present:
            warnings.append(
                "Lucidchart payload does not include geometry data; layout_hints are omitted to avoid fabricated coordinates."
            )

        for page_index, page in enumerate(pages):
            items = page.get("items") or {}
            page_id = page.get("id") or f"page-{page_index}"
            page_name = page.get("title") or page_id

            for shape in items.get("shapes") or []:
                total_shapes_seen += 1
                lucid_class = (shape.get("class") or "").strip()
                if lucid_class == "ConnectorBlock":
                    skipped_connector_count += 1
                    continue

                element_type = self._element_type_for_class(
                    lucid_class,
                    inferred_event_type=inferred_event_type,
                )
                if not element_type:
                    warnings.append(
                        f"Unsupported Lucidchart shape class '{lucid_class}' skipped."
                    )
                    continue

                identifier = shape.get("id")
                if not identifier:
                    warnings.append("Encountered Lucidchart shape without an id; skipped.")
                    continue

                name = self._extract_shape_name(shape)
                if not name:
                    warnings.append(
                        f"Lucidchart shape '{identifier}' has no importable name; skipped."
                    )
                    continue

                lucid_stereotype = self._extract_shape_stereotype(shape)
                geometry = self._shape_geometry(shape)

                element = {
                    "id": identifier,
                    "identifier": identifier,
                    "name": name,
                    "type": element_type,
                    "layer": self.ELEMENT_TYPE_TO_LAYER.get(element_type, "other"),
                    # No rendering_mode: imported elements adopt the composer's
                    # native ArchiMate styling (layer colours, icons, shape per
                    # type) — they should look like natively-created elements, not
                    # carry a Lucid-specific box style. The original Lucid class is
                    # kept below purely as provenance metadata.
                    "rendering_mode": None,
                    "description": None,
                    "custom_properties": {
                        "lucid_class": lucid_class,
                        "lucid_page_id": page_id,
                        "lucid_page_name": page_name,
                    },
                }
                if lucid_stereotype:
                    element["custom_properties"]["lucid_stereotype"] = lucid_stereotype
                if geometry:
                    # Source layout available (e.g. Standard Import boundingBox or
                    # an ARCHIE round-trip export) — preserve it so the composer
                    # places elements exactly where they were, no auto-arrange.
                    element.update(geometry)
                elements.append(element)
                imported_shape_ids[identifier] = element

            for line in items.get("lines") or []:
                relationship = self._transform_line(line, imported_shape_ids)
                if relationship is None:
                    skipped_relationship_count += 1
                    continue
                relationships.append(relationship)

        if not elements and total_shapes_seen:
            distinct = sorted({
                (shape.get("class") or "").strip()
                for page in pages
                for shape in (page.get("items") or {}).get("shapes") or []
                if (shape.get("class") or "").strip()
            })
            shown = ", ".join(distinct)[:300] or "(none)"
            warnings.append(
                f"No ArchiMate shapes were recognized in this export "
                f"({total_shapes_seen} shape(s) found). The importer maps Lucid's "
                f"ArchiMate shape library (the 'ArchiMate3…' shapes). Shape types in "
                f"this export: {shown}."
            )

        if skipped_connector_count:
            warnings.append(
                f"Skipped {skipped_connector_count} Lucid ConnectorBlock scaffolding shapes because they do not represent canonical ArchiMate elements."
            )
            warnings.append(
                "This Lucid export uses anonymous connector anchors for some relationships. Without source geometry or owner metadata, those edges cannot be attached to the correct ArchiMate element automatically."
            )
        if skipped_relationship_count:
            warnings.append(
                f"Skipped {skipped_relationship_count} Lucid relationships whose endpoints were unsupported or non-importable."
            )

        return {
            "model_name": payload.get("title") or "Lucidchart Import",
            "source_product": payload.get("product"),
            "elements": elements,
            "relationships": relationships,
            "layout_hints": {},
            "warnings": self._unique(warnings),
            "errors": [],
        }

    def _transform_line(
        self,
        line: Dict[str, Any],
        imported_shape_ids: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        line_id = line.get("id")
        source_id, target_id = self._resolve_line_endpoints(line)
        if not source_id or not target_id:
            return None
        if source_id not in imported_shape_ids or target_id not in imported_shape_ids:
            return None

        label = self._extract_line_label(line)
        connection_spec = self._parse_connection_spec(line)
        relationship_type = self._infer_relationship_type(label, connection_spec)
        # When the label/spec don't pin a type, fall back to the arrowhead style
        # (e.g. a Generalization arrowhead → ArchiMate specialization).
        endpoint_style = self._endpoint_style(line)
        if relationship_type == "association":
            relationship_type = (
                self.ENDPOINT_STYLE_TO_RELATIONSHIP.get(endpoint_style)
                or relationship_type
            )
        access_mode = self._infer_access_mode(relationship_type, label)
        flow_label = connection_spec.get("data_name") if relationship_type == "flow" else None
        # Preserve a meaningful edge label: an explicit line label, else the
        # arrowhead style (keeps ERD cardinality like "One Or More" visible).
        custom_label = None
        if label and not connection_spec:
            custom_label = label
        elif relationship_type == "association" and endpoint_style:
            custom_label = self._pretty_endpoint_style(endpoint_style)

        return {
            "id": line_id,
            "identifier": line_id,
            "type": relationship_type,
            "source_id": source_id,
            "target_id": target_id,
            "source": source_id,
            "target": target_id,
            "access_mode": access_mode,
            "flow_label": flow_label,
            "custom_label": custom_label,
            "description": None,
            "connection_spec": connection_spec or None,
        }

    @classmethod
    def _normalize_payload(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Accept both Lucid payload conventions.

        - REST ``documents/{id}/contents``: ``pages[].items.shapes`` where a shape
          carries ``class`` + ``textAreas`` (what the OAuth path delivers).
        - Standard Import / native ``.lucid`` ``document.json``: ``pages[].shapes``
          where a shape carries ``type`` + ``text``.

        Returns a payload in the ``items``/``class``/``textAreas`` convention the rest
        of the transformer expects. Non-destructive for payloads already in that
        convention.
        """
        if not isinstance(payload, dict):
            return payload
        pages = payload.get("pages")
        if not isinstance(pages, list):
            return payload

        for page in pages:
            if not isinstance(page, dict):
                continue
            items = page.get("items")
            items = dict(items) if isinstance(items, dict) else {}
            shapes = items.get("shapes")
            if shapes is None:
                shapes = page.get("shapes") or []
            lines = items.get("lines")
            if lines is None:
                lines = page.get("lines") or []
            items["shapes"] = [cls._normalize_shape(s) for s in shapes if isinstance(s, dict)]
            items["lines"] = [cls._normalize_line(line) for line in lines if isinstance(line, dict)]
            page["items"] = items
        return payload

    @staticmethod
    def _normalize_shape(shape: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(shape)
        if not normalized.get("class") and normalized.get("type"):
            normalized["class"] = normalized.get("type")
        if not normalized.get("textAreas"):
            text = normalized.get("text")
            if isinstance(text, dict):
                text = text.get("text")
            if isinstance(text, str) and text.strip():
                normalized["textAreas"] = [{"label": "Text", "text": text}]
        return normalized

    @staticmethod
    def _normalize_line(line: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(line)
        if not normalized.get("textAreas"):
            text = normalized.get("text")
            if isinstance(text, dict):
                text = text.get("text")
            if isinstance(text, str) and text.strip():
                normalized["textAreas"] = [{"label": "t0", "text": text}]
        for key in ("endpoint1", "endpoint2"):
            endpoint = normalized.get(key)
            if isinstance(endpoint, dict) and not endpoint.get("connectedTo"):
                ref = (
                    endpoint.get("id")
                    or endpoint.get("shapeId")
                    or endpoint.get("shape")
                    or endpoint.get("endpoint")
                )
                if ref:
                    endpoint = dict(endpoint)
                    endpoint["connectedTo"] = ref
                    normalized[key] = endpoint
        return normalized

    def _element_type_for_class(
        self,
        lucid_class: str,
        inferred_event_type: Optional[str] = None,
    ) -> Optional[str]:
        if lucid_class == "ArchiMate3EventBoxBlock":
            return inferred_event_type or self.event_element_type
        return self.LUCID_CLASS_TO_ELEMENT_TYPE.get(lucid_class)

    def _infer_event_element_type(self, pages: List[Dict[str, Any]]) -> str:
        if self.event_element_type != "BusinessEvent":
            return self.event_element_type

        shape_classes = {
            (shape.get("class") or "").strip()
            for page in pages
            for shape in (page.get("items") or {}).get("shapes") or []
        }
        if shape_classes & self.APPLICATION_CONTEXT_CLASSES:
            return "ApplicationEvent"
        return self.event_element_type

    def _rendering_mode_for_class(self, lucid_class: str) -> str:
        return self.LUCID_CLASS_TO_RENDERING_MODE.get(lucid_class, "black_box")

    def _extract_shape_name(self, shape: Dict[str, Any]) -> str:
        text = self._extract_text(shape.get("textAreas") or [])
        if not text:
            return ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) >= 2 and lines[0].upper() in self.KNOWN_STEREOTYPES:
            return " ".join(lines[1:]).strip()
        return " ".join(lines).strip()

    def _extract_shape_stereotype(self, shape: Dict[str, Any]) -> Optional[str]:
        text = self._extract_text(shape.get("textAreas") or [])
        if not text:
            return None
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return None
        stereotype = lines[0].upper()
        if stereotype in self.KNOWN_STEREOTYPES:
            return stereotype
        return None

    def _extract_line_label(self, line: Dict[str, Any]) -> str:
        return self._extract_text(line.get("textAreas") or [])

    def _extract_text(self, text_areas: List[Dict[str, Any]]) -> str:
        texts = [str(area.get("text") or "").strip() for area in text_areas]
        texts = [text for text in texts if text]
        return "\n".join(texts).strip()

    def _parse_connection_spec(self, line: Dict[str, Any]) -> Dict[str, str]:
        spec: Dict[str, str] = {}

        for item in line.get("customData") or []:
            raw_key = str(item.get("key") or "").strip().lower()
            raw_value = str(item.get("value") or "").strip()
            canonical_key = self.CONNECTION_SPEC_KEY_MAP.get(raw_key)
            if canonical_key and raw_value:
                spec[canonical_key] = raw_value

        if spec:
            return spec

        label = self._extract_line_label(line)
        for raw_line in label.splitlines():
            if " - " not in raw_line:
                continue
            key, value = raw_line.split(" - ", 1)
            canonical_key = self.CONNECTION_SPEC_KEY_MAP.get(key.strip().lower())
            if canonical_key and value.strip():
                spec[canonical_key] = value.strip()

        return spec

    def _infer_relationship_type(
        self,
        label: str,
        connection_spec: Dict[str, str],
    ) -> str:
        lowered = label.strip().lower()
        if connection_spec:
            return "flow"
        if lowered == "creates":
            return "access"
        return self.RELATIONSHIP_LABEL_MAP.get(lowered, "association")

    def _infer_access_mode(self, relationship_type: str, label: str) -> Optional[str]:
        if relationship_type != "access":
            return None
        lowered = label.strip().lower()
        if lowered == "creates":
            return "write"
        return "read"

    @staticmethod
    def _shape_geometry(shape: Dict[str, Any]) -> Dict[str, int]:
        """Extract {x, y, w, h} from a shape when the export carries layout.

        Sources, in order: ``boundingBox`` (Lucid Standard Import / ARCHIE
        round-trip exports, keys x/y/w/h or x/y/width/height), then top-level
        x/y(+width/height). Returns {} when no usable position exists — never
        fabricates coordinates.
        """
        def _num(value: Any) -> Optional[float]:
            return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

        box = shape.get("boundingBox")
        if isinstance(box, dict):
            x, y = _num(box.get("x")), _num(box.get("y"))
            if x is not None and y is not None:
                w = _num(box.get("w")) or _num(box.get("width"))
                h = _num(box.get("h")) or _num(box.get("height"))
                geom = {"x": int(x), "y": int(y)}
                if w:
                    geom["w"] = int(w)
                if h:
                    geom["h"] = int(h)
                return geom

        x, y = _num(shape.get("x")), _num(shape.get("y"))
        if x is not None and y is not None:
            geom = {"x": int(x), "y": int(y)}
            w, h = _num(shape.get("width")), _num(shape.get("height"))
            if w:
                geom["w"] = int(w)
            if h:
                geom["h"] = int(h)
            return geom
        return {}

    @staticmethod
    def _pretty_endpoint_style(style: str) -> str:
        """Readable edge label from a Lucid arrowhead style — e.g.
        'CFN ERD Zero Or More Arrow' → 'Zero Or More'."""
        s = style.strip()
        for prefix in ("CFN ERD ", "ERD "):
            if s.startswith(prefix):
                s = s[len(prefix):]
        if s.endswith(" Arrow"):
            s = s[: -len(" Arrow")]
        return s.strip() or style.strip()

    @staticmethod
    def _endpoint_style(line: Dict[str, Any]) -> str:
        """The meaningful arrowhead style on a line (prefer the target end)."""
        for key in ("endpoint2", "endpoint1"):
            style = str((line.get(key) or {}).get("style") or "").strip()
            if style and style.lower() != "none":
                return style
        return ""

    def _resolve_line_endpoints(self, line: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        endpoint1 = line.get("endpoint1") or {}
        endpoint2 = line.get("endpoint2") or {}
        source_id = endpoint1.get("connectedTo")
        target_id = endpoint2.get("connectedTo")

        style1 = str(endpoint1.get("style") or "").strip()
        style2 = str(endpoint2.get("style") or "").strip()
        if style1 == "Arrow" and style2 != "Arrow":
            return target_id, source_id

        return source_id, target_id

    def _payload_has_geometry(self, payload: Dict[str, Any]) -> bool:
        pages = payload.get("pages") or []
        for page in pages:
            items = page.get("items") or {}
            for collection_name in ("shapes", "lines", "groups", "layers"):
                for item in items.get(collection_name) or []:
                    if self._contains_geometry(item):
                        return True
        return False

    def _contains_geometry(self, value: Any) -> bool:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in self.GEOMETRY_KEYS:
                    return True
                if self._contains_geometry(nested):
                    return True
            return False
        if isinstance(value, list):
            return any(self._contains_geometry(item) for item in value)
        return False

    def _unique(self, items: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered
