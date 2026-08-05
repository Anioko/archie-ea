"""Turn a Visio .vsdx package into the same canonical payload the Lucid importer emits.

Why this exists: 60 of the 89 shapes in the production landscape diagram that
drove this work were Lucid "FreehandBlock" - generic shapes, no ArchiMate type -
because the diagram had been imported into Lucid from Visio. Going to the Visio
original skips that lossy hop. More importantly it keeps GEOMETRY, which Lucid's
JSON export discards, and geometry is the only thing that can tell you which
application sits in which data centre.

The output is deliberately identical in shape to LucidArchiMateTransformer's, so
everything downstream already works: nesting derivation, the import service,
preview, the review queue, conformance reporting.

Format notes, all confirmed against a real .vsdx rather than assumed:

  * A .vsdx is an OPC (ZIP) package. Pages live at visio/pages/pageN.xml.
  * The namespace is http://schemas.microsoft.com/office/visio/2012/main.
  * Geometry is in <Cell N="PinX"/> etc, in INCHES, and PinX/PinY is the pin
    position while LocPinX/LocPinY is the pin's offset inside the shape - so
    the left edge is PinX - LocPinX, not PinX.
  * Visio's Y axis points up. That is left alone: containment is unaffected by
    which way Y runs, as long as every box uses the same convention.
  * <Shapes> nests inside <Shape> for groups, giving containment outright.
    Where a diagram has no groups - the common case - geometry supplies it.
  * <Connects> gives connectivity: two <Connect> rows per connector, one for
    each end, joined by FromSheet.
"""
from __future__ import annotations

import io
import re
import zipfile
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from app.services.lucid_archimate_transformer import LucidArchiMateTransformer

VISIO_NS = "http://schemas.microsoft.com/office/visio/2012/main"
NS = {"v": VISIO_NS}

# Visio works in inches; the canonical payload wants integers. 100 units per
# inch keeps sub-millimetre detail without floats.
UNITS_PER_INCH = 100


class VisioArchiMateTransformer:
    """Read a .vsdx and emit canonical ArchiMate elements and relationships."""

    # Visio connectors carry their meaning in line styling much as Lucid does.
    # BeginArrow/EndArrow are numeric codes; 0 means no arrowhead.
    ARROW_NONE = {"0", "", None}

    def __init__(self, fallback_element_type: Optional[str] = None,
                 event_element_type: str = "BusinessEvent"):
        # Reuse the Lucid transformer for everything that is not Visio-specific:
        # type resolution, qualifier lifting, legend detection, nesting rules.
        # Two importers that disagree about what "(Phase 2)" means would be a
        # bug waiting to happen.
        self._shared = LucidArchiMateTransformer(
            event_element_type=event_element_type,
            fallback_element_type=fallback_element_type,
        )
        self.fallback_element_type = fallback_element_type

    # -- package ----------------------------------------------------------

    @staticmethod
    def _pages(archive: zipfile.ZipFile) -> List[str]:
        """Page parts, in document order. pages.xml itself is metadata, not a page."""
        parts = [n for n in archive.namelist()
                 if re.match(r"visio/pages/page\d+\.xml$", n, re.I)]

        def _index(name):
            match = re.search(r"page(\d+)\.xml$", name, re.I)
            return int(match.group(1)) if match else 0

        return sorted(parts, key=_index)

    @staticmethod
    def _page_names(archive: zipfile.ZipFile) -> Dict[int, str]:
        """Page display names from pages.xml, keyed by 1-based position."""
        try:
            root = ET.fromstring(archive.read("visio/pages/pages.xml"))
        except (KeyError, ET.ParseError):
            return {}
        names = {}
        for index, page in enumerate(root.findall("v:Page", NS), start=1):
            names[index] = page.get("Name") or page.get("NameU") or "Page %d" % index
        return names

    # -- shapes -----------------------------------------------------------

    @staticmethod
    def _cell(shape: ET.Element, name: str) -> Optional[str]:
        cell = shape.find("v:Cell[@N='%s']" % name, NS)
        return cell.get("V") if cell is not None else None

    @classmethod
    def _number(cls, shape: ET.Element, name: str) -> Optional[float]:
        raw = cls._cell(shape, name)
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _geometry(cls, shape: ET.Element) -> Dict[str, int]:
        """{x, y, w, h} in hundredths of an inch, or {} when the shape has none.

        PinX/PinY locate the pin, LocPinX/LocPinY say where the pin sits inside
        the shape. Treating PinX as the left edge puts every box half a width
        out and quietly ruins containment.
        """
        width, height = cls._number(shape, "Width"), cls._number(shape, "Height")
        pin_x, pin_y = cls._number(shape, "PinX"), cls._number(shape, "PinY")
        if None in (width, height, pin_x, pin_y) or width <= 0 or height <= 0:
            return {}
        loc_x = cls._number(shape, "LocPinX")
        loc_y = cls._number(shape, "LocPinY")
        loc_x = width / 2 if loc_x is None else loc_x
        loc_y = height / 2 if loc_y is None else loc_y
        return {
            "x": int(round((pin_x - loc_x) * UNITS_PER_INCH)),
            "y": int(round((pin_y - loc_y) * UNITS_PER_INCH)),
            "w": int(round(width * UNITS_PER_INCH)),
            "h": int(round(height * UNITS_PER_INCH)),
        }

    @staticmethod
    def _text(shape: ET.Element) -> str:
        """All text in the shape, including runs split across <cp>/<pp> children."""
        node = shape.find("v:Text", NS)
        if node is None:
            return ""
        return " ".join("".join(node.itertext()).split()).strip()

    def _type_for(self, shape: ET.Element, text: str) -> tuple:
        """(element type, how it was decided) or (None, None).

        Visio names a shape after its master - "Application Component" for an
        ArchiMate stencil - so the master name is the strongest signal, then a
        stereotype label, then the caller's fallback.
        """
        for attr in ("NameU", "Name", "Master", "MasterShape"):
            value = shape.get(attr)
            if not value:
                continue
            resolved = self._shared._type_from_token(re.sub(r"[.\d]+$", "", value))
            if resolved:
                return resolved, "master"

        stereotype = self._shared._element_type_from_stereotype(
            {"textAreas": [{"label": "Text", "text": text}]})
        if stereotype:
            return stereotype, "stereotype"
        return None, None

    # -- the transform ----------------------------------------------------

    def transform_document(self, raw: bytes) -> Dict[str, Any]:
        """Canonical payload from .vsdx bytes."""
        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as exc:
            raise ValueError("Not a readable .vsdx package: %s" % exc) from exc

        pages = self._pages(archive)
        if not pages:
            raise ValueError("This .vsdx contains no drawing pages.")
        page_names = self._page_names(archive)

        warnings: List[str] = []
        elements: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        by_shape_key: Dict[str, Dict[str, Any]] = {}
        annotations = legend = fallback_used = untyped = 0

        for position, part in enumerate(pages, start=1):
            try:
                root = ET.fromstring(archive.read(part))
            except ET.ParseError as exc:
                warnings.append("Page %s could not be parsed: %s" % (part, exc))
                continue

            page_id = "page-%d" % position
            page_name = page_names.get(position, "Page %d" % position)

            shapes = root.findall(".//v:Shape", NS)
            connected = self._connected_ids(root, page_id)

            for shape in shapes:
                shape_id = shape.get("ID")
                if not shape_id:
                    continue
                key = "%s-%s" % (page_id, shape_id)
                text = self._text(shape)
                if not text:
                    continue  # a shape with no label carries no name

                if len(text) > self._shared.ANNOTATION_TEXT_LENGTH:
                    annotations += 1
                    continue
                if self._shared._is_legend_swatch(text, key, connected):
                    legend += 1
                    continue

                element_type, source = self._type_for(shape, text)
                if not element_type and self.fallback_element_type:
                    element_type = self.fallback_element_type
                    source = "fallback"
                    fallback_used += 1
                if not element_type:
                    untyped += 1
                    continue

                name = self._shared._extract_shape_name(
                    {"textAreas": [{"label": "Text", "text": text}]}) or text

                element = {
                    "id": key,
                    "identifier": key,
                    "name": name,
                    "type": element_type,
                    "layer": self._shared.ELEMENT_TYPE_TO_LAYER.get(element_type, "other"),
                    "description": None,
                    "rendering_mode": None,
                    "custom_properties": {
                        "visio_shape_id": shape_id,
                        "visio_page_id": page_id,
                        "visio_page_name": page_name,
                        "lucid_page_id": page_id,      # nesting derivation keys on this
                        "lucid_page_name": page_name,
                        "lucid_type_source": source,
                    },
                }
                element["custom_properties"].update(
                    self._shared._extract_qualifiers(name))

                fill = self._cell(shape, "FillForegnd")
                if fill and fill.startswith("#"):
                    element["custom_properties"]["lucid_fill_color"] = fill

                geometry = self._geometry(shape)
                if geometry:
                    element.update(geometry)

                elements.append(element)
                by_shape_key[key] = element

            # Explicit group containment, where the drawing uses groups.
            for container in root.findall(".//v:Shape", NS):
                container_id = container.get("ID")
                child_shapes = container.findall("v:Shapes/v:Shape", NS)
                if not container_id or not child_shapes:
                    continue
                parent_key = "%s-%s" % (page_id, container_id)
                if parent_key not in by_shape_key:
                    continue
                for child in child_shapes:
                    child_key = "%s-%s" % (page_id, child.get("ID"))
                    child_element = by_shape_key.get(child_key)
                    if child_element is not None:
                        child_element["custom_properties"]["lucid_parent_id"] = parent_key

            relationships.extend(self._connectors(root, page_id, by_shape_key))

        existing_pairs = {(r.get("source_id"), r.get("target_id")) for r in relationships}
        relationships.extend(
            self._shared._derive_nesting_relationships(elements, existing_pairs, warnings))
        for element in elements:
            element.get("custom_properties", {}).pop("lucid_parent_id", None)

        if annotations:
            warnings.append(
                "Skipped %d shape(s) holding more than %d characters of text - "
                "commentary rather than architecture."
                % (annotations, self._shared.ANNOTATION_TEXT_LENGTH))
        if legend:
            warnings.append(
                "Skipped %d legend swatch(es) - shapes labelled with an ArchiMate "
                "concept name and connected to nothing." % legend)
        if untyped:
            warnings.append(
                "Skipped %d shape(s) with no ArchiMate type. Visio names a shape "
                "after its master, so a drawing built from generic rectangles "
                "carries none. Set a fallback element type to import them as a "
                "starting point." % untyped)
        if fallback_used:
            warnings.append(
                "%d shape(s) had no type of their own and were imported as '%s'. "
                "Their names, geometry and colours are real; the TYPE is a guess."
                % (fallback_used, self.fallback_element_type))

        return {
            "model_name": "Visio import",
            "source_product": "visio",
            "elements": elements,
            "relationships": relationships,
            "layout_hints": {},
            "warnings": warnings,
            "errors": [],
        }

    # -- connectors -------------------------------------------------------

    @staticmethod
    def _connected_ids(root: ET.Element, page_id: str) -> set:
        connected = set()
        for connect in root.findall(".//v:Connect", NS):
            target = connect.get("ToSheet")
            if target:
                connected.add("%s-%s" % (page_id, target))
        return connected

    def _connectors(self, root: ET.Element, page_id: str,
                    by_shape_key: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Relationships from <Connects>.

        Visio records one <Connect> per END of a connector, both naming the
        connector in FromSheet. Pairing them by FromSheet reconstructs the edge;
        BeginX/EndX in FromCell says which end is which.
        """
        ends: Dict[str, Dict[str, str]] = {}
        for connect in root.findall(".//v:Connect", NS):
            connector = connect.get("FromSheet")
            shape = connect.get("ToSheet")
            if not connector or not shape:
                continue
            which = "begin" if (connect.get("FromCell") or "").lower().startswith("begin") else "end"
            ends.setdefault(connector, {})[which] = shape

        shapes_by_id = {s.get("ID"): s for s in root.findall(".//v:Shape", NS)}
        built = []
        for connector_id, pair in ends.items():
            source_key = "%s-%s" % (page_id, pair.get("begin"))
            target_key = "%s-%s" % (page_id, pair.get("end"))
            if source_key not in by_shape_key or target_key not in by_shape_key:
                continue

            connector = shapes_by_id.get(connector_id)
            label = self._text(connector) if connector is not None else ""
            rel_type, provenance = self._relationship_for(connector, label)

            built.append({
                "id": "%s-conn-%s" % (page_id, connector_id),
                "identifier": "%s-conn-%s" % (page_id, connector_id),
                "type": rel_type,
                "source_id": source_key,
                "target_id": target_key,
                "source": source_key,
                "target": target_key,
                "access_mode": None,
                "flow_label": label if rel_type == "flow" else None,
                "custom_label": label or None,
                "description": None,
                "connection_spec": None,
                "derived_from": provenance,
            })
        return built

    def _relationship_for(self, connector: Optional[ET.Element], label: str) -> tuple:
        """(relationship type, provenance) for a Visio connector.

        A written label wins, exactly as on the Lucid path. Otherwise the line
        pattern is read: Visio's LinePattern 1 is solid, anything above it is
        some form of dash, and ArchiMate distinguishes serving from flow by
        precisely that.
        """
        if label:
            for token, mapped in self._shared.RELATIONSHIP_LABEL_MAP.items():
                if token in label.lower():
                    return mapped, "label"

        if connector is None:
            return "association", None

        pattern = self._cell(connector, "LinePattern")
        end_arrow = self._cell(connector, "EndArrow")
        begin_arrow = self._cell(connector, "BeginArrow")

        has_arrow = (end_arrow not in self.ARROW_NONE) or (begin_arrow not in self.ARROW_NONE)
        if not has_arrow:
            return "association", "notation"
        if pattern and pattern not in ("0", "1"):
            # Dashed or dotted with an arrowhead. Visio does not distinguish the
            # two finely enough to separate flow from access reliably, and flow
            # is overwhelmingly the commoner intent on an application landscape.
            return "flow", "notation"
        return "serving", "notation"
