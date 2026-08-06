"""Importing a Visio drawing, which is where these diagrams usually start.

60 of the 89 shapes in the production landscape diagram behind this work were
Lucid "FreehandBlock" - generic shapes carrying no ArchiMate type - because the
diagram had been imported into Lucid from Visio. Going to the Visio original
skips that lossy hop, and keeps the thing Lucid's JSON export throws away:
geometry. Geometry is the only thing that can say which application sits in
which data centre.

The fixtures here build .vsdx packages in memory. That is deliberate. A real
drawing was used to establish the format (and is exercised where relevant), but
a real drawing cannot be committed to a public repository, and it happened to
contain no connectors and no containment - the two paths most worth testing.
"""

import io
import zipfile

import pytest

from app.services.visio_archimate_transformer import VisioArchiMateTransformer

pytestmark = pytest.mark.journey

NS = 'xmlns="http://schemas.microsoft.com/office/visio/2012/main"'


def _shape(shape_id, text, x, y, w, h, fill=None, name=None):
    """A Visio shape. PinX/PinY is the CENTRE, which is the trap in this format."""
    attrs = 'ID="%d" Type="Shape"' % shape_id
    if name:
        attrs += ' NameU="%s"' % name
    fill_cell = '<Cell N="FillForegnd" V="%s"/>' % fill if fill else ""
    return (
        '<Shape {attrs}>'
        '<Cell N="PinX" V="{px}"/><Cell N="PinY" V="{py}"/>'
        '<Cell N="Width" V="{w}"/><Cell N="Height" V="{h}"/>'
        '<Cell N="LocPinX" V="{lx}"/><Cell N="LocPinY" V="{ly}"/>'
        '{fill}<Text>{text}</Text></Shape>'
    ).format(attrs=attrs, px=x + w / 2.0, py=y + h / 2.0, w=w, h=h,
             lx=w / 2.0, ly=h / 2.0, fill=fill_cell, text=text)


def _connector(shape_id, text="", pattern="1", end_arrow="1"):
    return (
        '<Shape ID="%d" Type="Shape">'
        '<Cell N="LinePattern" V="%s"/><Cell N="EndArrow" V="%s"/>'
        '<Cell N="BeginArrow" V="0"/><Text>%s</Text></Shape>'
        % (shape_id, pattern, end_arrow, text)
    )


def _vsdx(shapes, connects=""):
    page = ('<?xml version="1.0" encoding="utf-8"?>'
            '<PageContents %s><Shapes>%s</Shapes>%s</PageContents>'
            % (NS, "".join(shapes), connects))
    pages = ('<?xml version="1.0" encoding="utf-8"?>'
             '<Pages %s><Page ID="0" Name="Landscape"/></Pages>' % NS)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("visio/pages/pages.xml", pages)
        archive.writestr("visio/pages/page1.xml", page)
    return buffer.getvalue()


def _by_name(result):
    return {e["name"]: e for e in result["elements"]}


def _pair(result, source_name, target_name):
    names = {e["id"]: e["name"] for e in result["elements"]}
    for rel in result["relationships"]:
        if (names.get(rel["source_id"]) == source_name
                and names.get(rel["target_id"]) == target_name):
            return rel
    return None


class TestGeometry:
    def test_the_pin_is_the_centre_not_the_corner(self):
        """PinX/PinY locate the pin; LocPinX/LocPinY is its offset in the shape.

        Reading PinX as the left edge puts every box half a width out, and
        containment - the whole reason for preferring Visio - silently stops
        working.
        """
        raw = _vsdx([_shape(1, "Business Central", x=10, y=20, w=4, h=2)])
        element = _by_name(VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent").transform_document(raw))["Business Central"]

        # Inches × 100.
        assert (element["x"], element["y"]) == (1000, 2000), (
            "expected the left/bottom corner at (1000, 2000), got (%s, %s) - the "
            "pin was probably treated as the corner"
            % (element["x"], element["y"]))
        assert (element["w"], element["h"]) == (400, 200)

    def test_containment_comes_out_of_the_geometry(self):
        """The thing the Lucid JSON export cannot give you at all."""
        raw = _vsdx([
            _shape(1, "SG Azure Cloud", x=0, y=0, w=20, h=20),
            _shape(2, "Business Central", x=2, y=2, w=4, h=2),
            _shape(3, "MuleSoft", x=8, y=2, w=4, h=2),
        ])
        result = VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent").transform_document(raw)

        assert _pair(result, "SG Azure Cloud", "Business Central") is not None, (
            "the enclosing box produced no containment: %r" % result["relationships"])
        assert _pair(result, "SG Azure Cloud", "MuleSoft") is not None

    def test_a_flat_drawing_produces_no_containment(self):
        """Boxes side by side are not nested, and must not be invented.

        The real capability map used to develop this has 224 shapes and zero
        containment - a tiled grid. Reporting relationships there would be
        fabrication.
        """
        raw = _vsdx([
            _shape(1, "Order to Cash", x=0, y=0, w=4, h=2),
            _shape(2, "Demand to Supply", x=6, y=0, w=4, h=2),
        ])
        result = VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent").transform_document(raw)
        assert result["relationships"] == []


class TestTypesAndProperties:
    def test_the_master_name_gives_the_type(self):
        """A Visio ArchiMate stencil names its shape after the concept."""
        raw = _vsdx([_shape(1, "Order Handling", 0, 0, 4, 2, name="BusinessProcess")])
        element = _by_name(VisioArchiMateTransformer().transform_document(raw))["Order Handling"]
        assert element["type"] == "BusinessProcess"
        assert element["custom_properties"]["lucid_type_source"] == "master"

    def test_untyped_shapes_are_skipped_unless_a_fallback_is_given(self):
        raw = _vsdx([_shape(1, "Some Box", 0, 0, 4, 2)])
        assert VisioArchiMateTransformer().transform_document(raw)["elements"] == []

        with_fallback = VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent").transform_document(raw)
        assert with_fallback["elements"][0]["type"] == "ApplicationComponent"
        assert with_fallback["elements"][0]["custom_properties"]["lucid_type_source"] == "fallback"

    def test_fill_colour_and_qualifiers_survive(self):
        """Same treatment as the Lucid path - one importer's rules, not two."""
        raw = _vsdx([_shape(1, "Navitrans 365 (Phase 2)", 0, 0, 4, 2, fill="#2E75B6")])
        props = _by_name(VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent"
        ).transform_document(raw))["Navitrans 365 (Phase 2)"]["custom_properties"]

        assert props["lucid_fill_color"] == "#2E75B6"
        assert props["phase"] == "2", "qualifier was not lifted out of the name"


class TestConnectors:
    def test_a_connector_becomes_a_relationship(self):
        """Visio records one <Connect> per END, both naming the connector."""
        raw = _vsdx(
            [_shape(1, "Business Central", 0, 0, 4, 2),
             _shape(2, "MuleSoft", 10, 0, 4, 2),
             _connector(3)],
            connects='<Connects>'
                     '<Connect FromSheet="3" FromCell="BeginX" ToSheet="1"/>'
                     '<Connect FromSheet="3" FromCell="EndX" ToSheet="2"/>'
                     '</Connects>',
        )
        result = VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent").transform_document(raw)

        rel = _pair(result, "Business Central", "MuleSoft")
        assert rel is not None, "the connector produced no relationship"
        assert rel["type"] == "serving", "a solid arrow is serving"
        assert rel["derived_from"] == "notation"

    def test_a_dashed_connector_is_a_flow(self):
        """Solid versus dashed is how ArchiMate separates serving from flow."""
        raw = _vsdx(
            [_shape(1, "A", 0, 0, 4, 2), _shape(2, "B", 10, 0, 4, 2),
             _connector(3, pattern="2")],
            connects='<Connects>'
                     '<Connect FromSheet="3" FromCell="BeginX" ToSheet="1"/>'
                     '<Connect FromSheet="3" FromCell="EndX" ToSheet="2"/>'
                     '</Connects>',
        )
        result = VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent").transform_document(raw)
        assert _pair(result, "A", "B")["type"] == "flow"

    def test_a_written_label_beats_the_line_style(self):
        raw = _vsdx(
            [_shape(1, "A", 0, 0, 4, 2), _shape(2, "B", 10, 0, 4, 2),
             _connector(3, text="triggers")],
            connects='<Connects>'
                     '<Connect FromSheet="3" FromCell="BeginX" ToSheet="1"/>'
                     '<Connect FromSheet="3" FromCell="EndX" ToSheet="2"/>'
                     '</Connects>',
        )
        result = VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent").transform_document(raw)
        assert _pair(result, "A", "B")["type"] == "triggering"


class TestPackageHandling:
    def test_a_file_that_is_not_a_package_is_refused_clearly(self):
        with pytest.raises(ValueError, match="readable .vsdx"):
            VisioArchiMateTransformer().transform_document(b"this is not a zip")

    def test_a_package_with_no_pages_is_refused(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
        with pytest.raises(ValueError, match="no drawing pages"):
            VisioArchiMateTransformer().transform_document(buffer.getvalue())

    def test_the_payload_matches_the_lucid_importer_shape(self):
        """Everything downstream depends on one payload contract.

        The import service, preview, review queue and conformance report are all
        written against the Lucid transformer's output. A second shape here
        would mean a second set of everything.
        """
        raw = _vsdx([_shape(1, "A", 0, 0, 4, 2)])
        result = VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent").transform_document(raw)

        for key in ("model_name", "elements", "relationships", "layout_hints",
                    "warnings", "errors"):
            assert key in result, "payload is missing %r" % key
        element = result["elements"][0]
        for key in ("id", "identifier", "name", "type", "layer", "custom_properties"):
            assert key in element, "element is missing %r" % key


class TestUntrustedXml:
    """A .vsdx is a user upload, so its XML is hostile until proven otherwise.

    Entity expansion turns a few kilobytes into gigabytes during parsing. This
    deployment runs on a 3.8GB box that has already been OOM-killed once, so
    this is a denial of service, not a theoretical.
    """

    @staticmethod
    def _package_with(page_xml):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("visio/pages/page1.xml", page_xml)
        return buffer.getvalue()

    def test_an_entity_declaration_is_refused(self):
        bomb = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]>'
                '<PageContents %s><Shapes><Shape ID="1" Type="Shape">'
                '<Text>&lol;</Text></Shape></Shapes></PageContents>' % NS)
        result = VisioArchiMateTransformer(
            fallback_element_type="ApplicationComponent"
        ).transform_document(self._package_with(bomb))

        assert result["elements"] == [], (
            "a document carrying entity declarations was parsed anyway")

    def test_a_refusal_is_reported_rather_than_raised(self):
        """Refusing is right; 500ing at the user is not.

        safe_xml raises EntitiesForbidden, which is not an ET.ParseError - so a
        handler catching only parse errors lets it escape as a server error.
        """
        bomb = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]>'
                '<PageContents %s><Shapes/></PageContents>' % NS)
        result = VisioArchiMateTransformer().transform_document(
            self._package_with(bomb))

        assert any("refused by the XML parser" in w for w in result["warnings"]), (
            "the refusal was not reported to the uploader: %r" % result["warnings"])

    def test_parsing_does_not_use_elementtree_directly(self):
        """Every parse of uploaded bytes must go through safe_xml."""
        import inspect

        from app.services import visio_archimate_transformer as module

        source = inspect.getsource(module)
        assert "ET.fromstring" not in source, (
            "ElementTree parses uploaded XML directly, bypassing the "
            "entity-expansion guard")
        assert "safe_xml.fromstring" in source
