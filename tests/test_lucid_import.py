"""Importing a Lucidchart diagram must keep the structure the author drew.

A nested box is how architects write "part of". Before this, the importer read
shapes and connectors and ignored containment entirely, so a diagram whose whole
meaning was its nesting - a product grouping, a layered reference model - arrived
as a flat list of unrelated elements. Colour had the same problem: a traffic-light
key is real information, and once the import dropped it the author could not get
it back.

These are pure unit tests. The transformer touches no database and no request
context, so they run in milliseconds and can afford to be exhaustive about the
geometry edge cases, which is where containment inference goes wrong.
"""

import pytest

from app.services.lucid_archimate_transformer import LucidArchiMateTransformer

pytestmark = pytest.mark.journey


def _shape(shape_id, lucid_class, name, box=None, **extra):
    shape = {
        "id": shape_id,
        "class": lucid_class,
        "textAreas": [{"label": "Text", "text": name}],
    }
    if box:
        x, y, w, h = box
        shape["boundingBox"] = {"x": x, "y": y, "w": w, "h": h}
    shape.update(extra)
    return shape


def _payload(shapes, lines=None, page_id="page-1"):
    return {
        "title": "Test Diagram",
        "pages": [{"id": page_id, "title": "Page 1",
                   "items": {"shapes": shapes, "lines": lines or []}}],
    }


def _rels(result, rel_type=None):
    rels = result["relationships"]
    if rel_type:
        rels = [r for r in rels if r["type"] == rel_type]
    return rels


def _pair(result, source_name, target_name):
    """Find a relationship by the NAMES of its endpoints, not their ids."""
    names = {e["id"]: e["name"] for e in result["elements"]}
    for rel in result["relationships"]:
        if (names.get(rel["source_id"]) == source_name
                and names.get(rel["target_id"]) == target_name):
            return rel
    return None


class TestNestingBecomesStructure:
    def test_a_nested_component_becomes_a_composition(self):
        """The core case: one box drawn inside another means part-of."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("outer", "ArchiMate3ComponentBoxBlock", "Platform", (0, 0, 400, 400)),
            _shape("inner", "ArchiMate3ComponentBoxBlock", "Module", (50, 50, 100, 100)),
        ]))

        rel = _pair(result, "Platform", "Module")
        assert rel is not None, (
            "containment produced no relationship, so the diagram's structure "
            "was lost: %r" % result["relationships"])
        assert rel["type"] == "composition"
        assert rel["derived_from"] == "nesting"

    def test_a_grouping_aggregates_rather_than_composes(self):
        """ArchiMate 3.2 §4.5 - a Grouping collects its members, it does not own them."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("g", "ArchiMate3GroupingBoxBlock", "ArchiCore", (0, 0, 800, 600)),
            _shape("c", "ArchiMate3ComponentBoxBlock", "Motivation Layer", (40, 40, 200, 120)),
        ]))

        rel = _pair(result, "ArchiCore", "Motivation Layer")
        assert rel is not None and rel["type"] == "aggregation", (
            "expected aggregation under a Grouping, got %r"
            % (rel and rel["type"]))

    def test_the_nearest_container_wins_not_the_outermost(self):
        """Three levels deep is where naive containment goes wrong.

        A shape sits geometrically inside its grandparent as well as its parent.
        Relating it to both produces a model that says the leaf is simultaneously
        part of two different wholes.
        """
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("a", "ArchiMate3ComponentBoxBlock", "Outer", (0, 0, 900, 900)),
            _shape("b", "ArchiMate3ComponentBoxBlock", "Middle", (100, 100, 400, 400)),
            _shape("c", "ArchiMate3ComponentBoxBlock", "Leaf", (150, 150, 80, 80)),
        ]))

        assert _pair(result, "Middle", "Leaf") is not None, "leaf lost its parent"
        assert _pair(result, "Outer", "Leaf") is None, (
            "the leaf was also related to its grandparent, so it is part of two "
            "wholes at once")
        assert _pair(result, "Outer", "Middle") is not None, "middle lost its parent"

    def test_shapes_on_different_pages_are_never_nested(self):
        """Coordinates repeat per page; treating them globally invents structure."""
        payload = {
            "title": "Two Pages",
            "pages": [
                {"id": "p1", "title": "One", "items": {"shapes": [
                    _shape("big", "ArchiMate3ComponentBoxBlock", "Big", (0, 0, 500, 500))], "lines": []}},
                {"id": "p2", "title": "Two", "items": {"shapes": [
                    _shape("small", "ArchiMate3ComponentBoxBlock", "Small", (10, 10, 50, 50))], "lines": []}},
            ],
        }
        result = LucidArchiMateTransformer().transform_document(payload)

        assert _pair(result, "Big", "Small") is None, (
            "shapes on different pages were nested because their coordinates "
            "happen to overlap")

    def test_an_explicit_connector_is_not_duplicated_by_nesting(self):
        """If the author drew the relationship, that statement wins."""
        result = LucidArchiMateTransformer().transform_document(_payload(
            shapes=[
                _shape("outer", "ArchiMate3ComponentBoxBlock", "Host", (0, 0, 400, 400)),
                _shape("inner", "ArchiMate3ComponentBoxBlock", "Guest", (50, 50, 100, 100)),
            ],
            lines=[{
                "id": "line-1",
                "textAreas": [{"label": "t0", "text": "triggers"}],
                "endpoint1": {"connectedTo": "outer"},
                "endpoint2": {"connectedTo": "inner"},
            }],
        ))

        between = [r for r in result["relationships"]
                   if {r["source_id"], r["target_id"]} == {"outer", "inner"}]
        assert len(between) == 1, (
            "expected the drawn connector only, got %d relationships: %r"
            % (len(between), [r["type"] for r in between]))
        assert between[0]["type"] == "triggering"

    def test_a_declared_parent_beats_geometry(self):
        """An export that names the container is more trustworthy than a bounding box."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("real", "ArchiMate3ComponentBoxBlock", "Real Parent", (0, 0, 900, 900)),
            _shape("decoy", "ArchiMate3ComponentBoxBlock", "Decoy", (100, 100, 400, 400)),
            _shape("child", "ArchiMate3ComponentBoxBlock", "Child", (150, 150, 80, 80),
                   parent="real"),
        ]))

        assert _pair(result, "Real Parent", "Child") is not None, (
            "the declared parent was ignored in favour of the enclosing box")
        assert _pair(result, "Decoy", "Child") is None

    def test_overlapping_but_not_enclosed_shapes_are_not_nested(self):
        """Partial overlap is a layout accident, not a statement of structure."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("a", "ArchiMate3ComponentBoxBlock", "A", (0, 0, 200, 200)),
            _shape("b", "ArchiMate3ComponentBoxBlock", "B", (150, 150, 200, 200)),
        ]))

        assert not _rels(result), (
            "overlapping shapes produced a relationship: %r" % result["relationships"])

    def test_nesting_is_flagged_for_review(self):
        """Nesting is ambiguous in ArchiMate; the guess must be visible."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("outer", "ArchiMate3ComponentBoxBlock", "Outer", (0, 0, 400, 400)),
            _shape("inner", "ArchiMate3ComponentBoxBlock", "Inner", (50, 50, 100, 100)),
        ]))

        assert any("nest" in w.lower() for w in result["warnings"]), (
            "the importer guessed a structural relationship and said nothing: %r"
            % result["warnings"])

    def test_no_geometry_means_no_invented_nesting(self):
        """Without coordinates there is nothing to infer from, and guessing is worse."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("a", "ArchiMate3ComponentBoxBlock", "A"),
            _shape("b", "ArchiMate3ComponentBoxBlock", "B"),
        ]))

        assert not _rels(result), (
            "relationships were invented for shapes with no geometry: %r"
            % result["relationships"])


class TestColourIsPreserved:
    def test_fill_colour_survives_the_import(self):
        """A traffic-light key is information the author cannot recover later."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("a", "ArchiMate3ComponentBoxBlock", "Ready Thing", (0, 0, 100, 100),
                   style={"fill": {"color": "#FF9900"}}),
        ]))

        props = result["elements"][0]["custom_properties"]
        assert props.get("lucid_fill_color") == "#FF9900", (
            "the shape's colour was dropped, so a RAG or readiness key is "
            "unrecoverable: %r" % props)

    @pytest.mark.parametrize("style,expected", [
        ({"fill": {"color": "#123456"}}, "#123456"),
        ({"fillColor": "#abcdef"}, "#abcdef"),
        ({"backgroundColor": "rgb(255,0,0)"}, "rgb(255,0,0)"),
    ])
    def test_the_colour_is_found_wherever_the_export_put_it(self, style, expected):
        """Lucid spells this differently per export flavour."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("a", "ArchiMate3ComponentBoxBlock", "Thing", (0, 0, 100, 100), style=style),
        ]))
        assert result["elements"][0]["custom_properties"].get("lucid_fill_color") == expected

    def test_no_colour_adds_no_property(self):
        """An absent colour must not become a null that looks deliberate."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("a", "ArchiMate3ComponentBoxBlock", "Thing", (0, 0, 100, 100)),
        ]))
        assert "lucid_fill_color" not in result["elements"][0]["custom_properties"]

    def test_the_parent_hint_does_not_leak_into_properties(self):
        """lucid_parent_id is plumbing - it becomes a relationship, not a property."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("p", "ArchiMate3ComponentBoxBlock", "Parent", (0, 0, 400, 400)),
            _shape("c", "ArchiMate3ComponentBoxBlock", "Child", (50, 50, 100, 100), parent="p"),
        ]))
        for element in result["elements"]:
            assert "lucid_parent_id" not in element["custom_properties"]


class TestTheShapeMapIsWiderThanTheCuratedList:
    """Lucid names its stencils after the concept, so the name can be read.

    Listing every stencil by hand covers whatever someone got round to adding.
    Deriving the type from the class name covers the whole set, and is safe
    because the result must match a real ArchiMate 3.2 type before it is used.
    """

    @pytest.mark.parametrize("lucid_class,expected", [
        ("ArchiMate3BusinessProcessBoxBlock", "BusinessProcess"),
        ("ArchiMate3CapabilityBoxBlock", "Capability"),
        ("ArchiMate3GoalBoxBlock", "Goal"),
        ("ArchiMate3DriverBoxBlock", "Driver"),
        ("ArchiMate3NodeBoxBlock", "Node"),
        ("ArchiMate3WorkPackageBoxBlock", "WorkPackage"),
        ("ArchiMate3BusinessActorBoxBlock", "BusinessActor"),
        ("ArchiMate3ValueStreamBoxBlock", "ValueStream"),
    ])
    def test_stencils_beyond_the_curated_map_now_import(self, lucid_class, expected):
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("a", lucid_class, "Thing", (0, 0, 100, 100)),
        ]))
        assert result["elements"], (
            "%s was skipped; the class name names a real ArchiMate type"
            % lucid_class)
        assert result["elements"][0]["type"] == expected

    def test_the_curated_map_still_wins_over_the_class_name(self):
        """Lucid's layer-agnostic names would be mistyped by a literal reading.

        'Object' is not an ArchiMate type and 'Component' is ambiguous; the
        curated map resolves both, and must not be overridden by pattern
        matching.
        """
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("o", "ArchiMate3ObjectBoxBlock", "Customer Record", (0, 0, 100, 100)),
            _shape("c", "ArchiMate3ComponentBoxBlock", "CRM", (200, 0, 100, 100)),
        ]))
        types = {e["name"]: e["type"] for e in result["elements"]}
        assert types == {"Customer Record": "DataObject", "CRM": "ApplicationComponent"}

    def test_an_invented_type_is_not_accepted(self):
        """Pattern matching must not manufacture types that do not exist."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("a", "ArchiMate3UnicornBoxBlock", "Sparkle", (0, 0, 100, 100)),
        ]))
        assert not result["elements"], (
            "invented an ArchiMate type from an unknown stencil: %r"
            % result["elements"])

    def test_a_stereotype_label_states_the_type(self):
        """«Capability» above the name is the author telling you the type."""
        shape = _shape("a", "GenericRectangle", "x", (0, 0, 100, 100))
        shape["textAreas"] = [{"label": "Text", "text": "«Capability»\nOrder Fulfilment"}]
        result = LucidArchiMateTransformer().transform_document(_payload([shape]))

        assert len(result["elements"]) == 1
        element = result["elements"][0]
        assert element["type"] == "Capability"
        assert element["name"] == "Order Fulfilment", (
            "the stereotype leaked into the element name: %r" % element["name"])
        assert element["custom_properties"]["lucid_type_source"] == "stereotype"

    def test_plain_rectangles_are_skipped_by_default(self):
        """Silence is the safe default: inventing a type for every box is fiction."""
        result = LucidArchiMateTransformer().transform_document(_payload([
            _shape("a", "GenericRectangle", "Some Product", (0, 0, 100, 100)),
        ]))
        assert not result["elements"]
        assert any("fallback" in w.lower() for w in result["warnings"]), (
            "skipped the shapes without telling the user how to import them: %r"
            % result["warnings"])

    def test_a_fallback_imports_plain_rectangles_with_their_structure(self):
        """The whole point: keep names, colour and nesting, guess only the type."""
        result = LucidArchiMateTransformer(
            fallback_element_type="ApplicationComponent"
        ).transform_document(_payload([
            _shape("outer", "GenericRectangle", "ArchiCore", (0, 0, 800, 600),
                   style={"fill": {"color": "#E8A33D"}}),
            _shape("inner", "GenericRectangle", "Service Catalogue", (40, 40, 200, 100)),
        ]))

        by_name = {e["name"]: e for e in result["elements"]}
        assert set(by_name) == {"ArchiCore", "Service Catalogue"}
        # A box drawn around other boxes is a grouping, whatever it was drawn with.
        assert by_name["ArchiCore"]["type"] == "Grouping"
        assert by_name["Service Catalogue"]["type"] == "ApplicationComponent"
        assert by_name["ArchiCore"]["custom_properties"]["lucid_fill_color"] == "#E8A33D"
        assert _pair(result, "ArchiCore", "Service Catalogue") is not None, (
            "nesting was lost for fallback-typed shapes")

    def test_a_guessed_type_is_marked_as_guessed(self):
        """A guess that looks like a fact is worse than no import at all."""
        result = LucidArchiMateTransformer(
            fallback_element_type="ApplicationComponent"
        ).transform_document(_payload([
            _shape("a", "GenericRectangle", "Thing", (0, 0, 100, 100)),
        ]))

        assert result["elements"][0]["custom_properties"]["lucid_type_source"] == "fallback"
        assert any("guess" in w.lower() for w in result["warnings"]), (
            "imported guessed types without saying so: %r" % result["warnings"])

    def test_a_fallback_type_must_be_a_real_archimate_type(self):
        with pytest.raises(ValueError, match="ArchiMate"):
            LucidArchiMateTransformer(fallback_element_type="NotTheRealThing")


class TestImageAnalysisNoLongerCrashes:
    """`await ...__doc__` sat on the live image path and raised TypeError.

    Every diagram-image upload failed before reaching the model. The bug was
    invisible in review because the line looks like prompt-building.
    """

    def test_the_awaited_docstring_is_gone(self):
        import inspect

        from app.services.archimate.document_analysis_service import DocumentAnalysisService

        source = inspect.getsource(DocumentAnalysisService._analyze_image)
        offending = [line.strip() for line in source.splitlines()
                     if "await" in line and "__doc__" in line and not line.strip().startswith("#")]
        assert not offending, (
            "awaiting a docstring raises TypeError before the image is ever "
            "sent: %r" % offending)

    def test_the_context_prompt_reaches_the_model(self):
        """The context-specific guidance was built and then thrown away."""
        import asyncio

        from app.services.archimate.document_analysis_service import DocumentAnalysisService

        captured = {}

        async def _fake_extract(image_path, provider, extra_instructions=""):
            captured["extra"] = extra_instructions
            return {"elements": []}, None

        service = DocumentAnalysisService.__new__(DocumentAnalysisService)
        service.multi_modal_service = type(
            "Stub", (), {"extract_archimate_from_diagram": staticmethod(_fake_extract)}
        )()

        data, _interaction = asyncio.run(
            service._analyze_image("/tmp/diagram.png", "claude", "application")
        )

        assert data == {"elements": []}
        assert "ApplicationComponent" in captured.get("extra", ""), (
            "the application-context prompt was not passed through: %r"
            % captured.get("extra"))
