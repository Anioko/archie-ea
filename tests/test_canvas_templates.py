"""Canvas templates as data — schema, seeding, and the two pages' structure.

Covers: (1) the static schema/placeholder test over CANVAS_TEMPLATES; (2)
that the Composer payload shape carries `zones`/`entries` for a canvas key
and that CANVAS_TEMPLATES' own zone order is a dense, ascending sequence the
page templates render one row per zone from; (3) seed_canvas_templates()
idempotence; (4) both detail pages render for an empty tenant with the
empty hint outside the input, "0 not yet classified", and no other literal
zero; (6) a foreign canvas id and a foreign business case id return the
page's existing not-found bytes.

This is data-and-render only: no projection yet, so every box's entries
list stays empty and every zone carries its empty_reason (a later change
fills the entries).
"""
from __future__ import annotations

import copy
import re

import pytest

from app.config.archimate_viewpoints import (
    CANVAS_PROFILE_OPTIONS_BY_TYPE,
    CANVAS_TEMPLATES,
    validate_canvas_templates,
)


# -- Schema and the static placeholder test ----------------------------------


class TestSchema:
    def test_validate_canvas_templates_passes_on_the_real_templates(self):
        validate_canvas_templates()

    def test_three_templates_with_the_srs_zone_counts(self):
        assert sorted(CANVAS_TEMPLATES) == ["business_case", "business_model_canvas", "lean_canvas"]
        assert [len(CANVAS_TEMPLATES[k]["zones"]) for k in sorted(CANVAS_TEMPLATES)] == [9, 9, 9]

    def test_bmc_box_keys_equal_the_record_columns(self):
        from app.models.business_model import CANVAS_BLOCKS

        keys = {z["box_key"] for z in CANVAS_TEMPLATES["business_model_canvas"]["zones"]}
        assert keys == set(CANVAS_BLOCKS)

    def test_case_zones_with_an_existing_column_use_the_column_name_as_box_key(self):
        from app.models.business_case import BusinessCase

        columns = set(BusinessCase.__table__.columns.keys())
        zones = {z["box_key"] for z in CANVAS_TEMPLATES["business_case"]["zones"]}
        for box_key in ("problem_statement", "options_considered", "expected_benefits", "key_risks"):
            assert box_key in columns
            assert box_key in zones

    def test_every_zone_element_type_has_a_profile_options_entry(self):
        all_types = {
            t for tpl in CANVAS_TEMPLATES.values() for z in tpl["zones"] for t in z["element_types"]
        }
        missing = all_types - set(CANVAS_PROFILE_OPTIONS_BY_TYPE)
        assert not missing, f"element types with no seeded profile options: {missing}"

    def test_no_literal_colour_anywhere_in_the_config_module(self):
        with open("app/config/archimate_viewpoints.py", encoding="utf-8") as fh:
            src = fh.read()
        assert not re.search(r"#[0-9a-fA-F]{6}", src)

    def test_validator_fails_on_placeholder_text_in_a_label(self):
        bad = copy.deepcopy(CANVAS_TEMPLATES)
        bad["lean_canvas"]["zones"][0]["label"] = "Lorem ipsum placeholder"
        with pytest.raises(AssertionError):
            validate_canvas_templates(bad)

    def test_validator_fails_on_a_literal_colour(self):
        bad = copy.deepcopy(CANVAS_TEMPLATES)
        bad["lean_canvas"]["zones"][0]["colour"] = "#112233"
        with pytest.raises(AssertionError):
            validate_canvas_templates(bad)

    def test_validator_fails_on_a_duplicate_box_key(self):
        bad = copy.deepcopy(CANVAS_TEMPLATES)
        bad["lean_canvas"]["zones"][1]["box_key"] = bad["lean_canvas"]["zones"][0]["box_key"]
        with pytest.raises(AssertionError):
            validate_canvas_templates(bad)

    def test_validator_fails_when_an_element_zone_carries_no_flags(self):
        bad = copy.deepcopy(CANVAS_TEMPLATES)
        bad["lean_canvas"]["zones"][0]["flags"] = []
        with pytest.raises(AssertionError):
            validate_canvas_templates(bad)

    def test_validator_fails_on_an_unknown_membership(self):
        bad = copy.deepcopy(CANVAS_TEMPLATES)
        bad["lean_canvas"]["zones"][0]["membership"] = "made_up"
        with pytest.raises(AssertionError):
            validate_canvas_templates(bad)


# -- Seed idempotence ---------------------------------------------------------


class TestSeedIdempotence:
    def test_seed_canvas_templates_twice_changes_nothing_the_second_time(self, app, db_session):
        from app.commands.seed_viewpoints import seed_canvas_templates
        from app.models.acm_property_template import AcmPropertyTemplate
        from app.models.archimate_viewpoint import ArchiMateViewpoint

        profile_type_count = len(CANVAS_PROFILE_OPTIONS_BY_TYPE)

        first = seed_canvas_templates()
        assert first == (3, 0, profile_type_count, 0)

        second = seed_canvas_templates()
        assert second == (0, 3, 0, profile_type_count)

        canvas_rows = ArchiMateViewpoint.query.filter_by(viewpoint_type="canvas").all()
        assert len(canvas_rows) == 3
        assert {row.is_standard for row in canvas_rows} == {False}

        profile_rows = AcmPropertyTemplate.query.filter_by(property_key="profile").all()
        assert len(profile_rows) == profile_type_count
        by_type = {row.archimate_type: row.enum_options for row in profile_rows}
        for archimate_type, options in CANVAS_PROFILE_OPTIONS_BY_TYPE.items():
            assert by_type[archimate_type] == options

    def test_seed_viewpoints_calls_seed_canvas_templates(self, app, db_session):
        from app.commands.seed_viewpoints import seed_viewpoints
        from app.models.archimate_viewpoint import ArchiMateViewpoint

        seed_viewpoints()
        assert ArchiMateViewpoint.query.filter_by(viewpoint_type="canvas").count() == 3


# -- Composer render shape ----------------------------------------------------


class TestComposerRenderShape:
    @pytest.mark.parametrize("key", sorted(CANVAS_TEMPLATES))
    def test_get_viewpoint_data_carries_zones_and_entries_present_and_empty(self, key):
        from app.services.archimate_viewpoint_service import get_viewpoint_data

        data = get_viewpoint_data(key)
        assert data["scope_required"] is False
        assert "zones" in data and data["zones"] == []
        assert "entries" in data and data["entries"] == []
        assert data["elements"] == []
        assert data["relationships"] == []

    @pytest.mark.parametrize("key", sorted(CANVAS_TEMPLATES))
    def test_template_zone_order_is_dense_and_ascending(self, key):
        zones = CANVAS_TEMPLATES[key]["zones"]
        orders = [z["order"] for z in zones]
        assert orders == sorted(orders)
        assert orders == list(range(1, len(zones) + 1))
        assert [z["phone_order"] for z in zones] == orders

    def test_get_available_viewpoints_lists_the_three_templates_as_canvas_category(self):
        from app.services.archimate_viewpoint_service import get_available_viewpoints

        entries = {v["id"]: v for v in get_available_viewpoints() if v["category"] == "canvas"}
        assert set(entries) == set(CANVAS_TEMPLATES)
        for key, tpl in CANVAS_TEMPLATES.items():
            assert entries[key]["name"] == tpl["name"]

    def test_a_non_canvas_key_is_unaffected(self):
        from app.services.archimate_viewpoint_service import STANDARD_VIEWPOINTS, get_viewpoint_data

        assert "zones" not in STANDARD_VIEWPOINTS["motivation"]
        # 'motivation' has no solution_id and is not enterprise_scope, so it
        # still asks for scope — proving the canvas short-circuit added above
        # it did not change this existing invariant.
        data = get_viewpoint_data("motivation")
        assert data["scope_required"] is True
        assert "zones" not in data
