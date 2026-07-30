"""
Tests for Value Stream mapping + the BIZBOK capability x value-stream grid.

Covers:
- Model import and relationship wiring (UnifiedCapability <-> CapabilityValueStreamMapping
  <-> ValueStream / ValueStreamStage) resolves without SQLAlchemy mapper errors.
- value_stream_service builds a well-formed BIZBOK grid structure from seeded objects.
- The value_stream blueprint registers on the Flask app and `value_stream.index` resolves.
"""

import uuid

import pytest


@pytest.fixture(scope="module")
def app():
    from app import create_app

    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


class TestModelRelationships:
    """Model import + relationship wiring."""

    def test_models_importable(self):
        from app.models.unified_capability import (
            CapabilityValueStreamMapping,
            UnifiedCapability,
            ValueStream,
            ValueStreamStage,
        )

        assert CapabilityValueStreamMapping is not None
        assert UnifiedCapability is not None
        assert ValueStream is not None
        assert ValueStreamStage is not None

    def test_relationships_are_wired(self):
        """The value-stream relationships must no longer be commented out."""
        from app.models.unified_capability import (
            CapabilityValueStreamMapping,
            UnifiedCapability,
            ValueStream,
            ValueStreamStage,
        )

        assert hasattr(UnifiedCapability, "value_stream_mappings")
        assert hasattr(CapabilityValueStreamMapping, "capability")
        assert hasattr(CapabilityValueStreamMapping, "value_stream")
        assert hasattr(CapabilityValueStreamMapping, "value_stream_stage")
        assert hasattr(ValueStream, "capability_mappings")
        assert hasattr(ValueStreamStage, "capability_mappings")

    def test_mappers_configure_without_error(self, app):
        """SQLAlchemy lazily resolves relationship strings (back_populates targets,
        class names) the first time mappers are configured. This fails loudly if a
        back_populates pair is mismatched or a target class name is misspelled.
        """
        from sqlalchemy.orm import configure_mappers

        with app.app_context():
            configure_mappers()  # raises InvalidRequestError on a broken mapping

    def test_back_populates_pairs_match(self, app):
        from app.models.unified_capability import (
            CapabilityValueStreamMapping,
            UnifiedCapability,
            ValueStream,
            ValueStreamStage,
        )

        with app.app_context():
            assert (
                UnifiedCapability.value_stream_mappings.property.back_populates
                == "capability"
            )
            assert (
                CapabilityValueStreamMapping.capability.property.back_populates
                == "value_stream_mappings"
            )
            assert (
                CapabilityValueStreamMapping.value_stream.property.back_populates
                == "capability_mappings"
            )
            assert (
                ValueStream.capability_mappings.property.back_populates
                == "value_stream"
            )
            assert (
                CapabilityValueStreamMapping.value_stream_stage.property.back_populates
                == "capability_mappings"
            )
            assert (
                ValueStreamStage.capability_mappings.property.back_populates
                == "value_stream_stage"
            )


class TestValueStreamServiceImports:
    def test_service_importable(self):
        from app.modules.capabilities.services import value_stream_service

        assert hasattr(value_stream_service, "list_value_streams")
        assert hasattr(value_stream_service, "get_value_stream_with_stages")
        assert hasattr(value_stream_service, "build_bizbok_grid")
        assert hasattr(value_stream_service, "upsert_mapping_cell")
        assert hasattr(value_stream_service, "delete_mapping_cell")

    def test_grid_shape_for_missing_value_stream(self, app):
        """A nonexistent value stream must yield the documented empty shape, never raise."""
        from app.modules.capabilities.services import value_stream_service as vs_service

        with app.app_context():
            grid = vs_service.build_bizbok_grid(-1)

        assert grid == {
            "value_stream": None,
            "stages": [],
            "capabilities": [],
            "cells": {},
        }


class TestBizbokGridWithSeededData:
    """Build the grid end-to-end against real seeded rows in the test DB."""

    def test_grid_reflects_seeded_mapping(self, app):
        from app import db
        from app.models.unified_capability import (
            CapabilityValueStreamMapping,
            UnifiedCapability,
            ValueStream,
            ValueStreamStage,
        )
        from app.modules.capabilities.services import value_stream_service as vs_service

        suffix = uuid.uuid4().hex[:8]
        with app.app_context():
            # Created via the service (Core-level insert) rather than
            # db.session.add(ValueStream(...)) directly: a pre-existing
            # after_insert event on ValueStream in app/models/strategy_layer.py
            # references a column that does not exist on this DB's
            # `value_streams` table, so an ORM-level insert raises AttributeError.
            # ValueStream is tenant-scoped (TenantMixin) as of 2026-07-30, so
            # organization_id is NOT NULL. _default_org_id() deliberately
            # refuses to guess when several organizations exist, so seeding
            # outside a request would insert NULL and fail. Supply the tenant
            # explicitly via a request context, exactly as a real request does.
            from flask import g as _g

            from app.models.organization import Organization

            _org = Organization.query.order_by(Organization.id.asc()).first()
            if _org is None:
                _org = Organization(name=f"VS Test Org {suffix}")
                db.session.add(_org)
                db.session.commit()

            with app.test_request_context():
                _g.current_org_id = _org.id
                vs = vs_service.create_value_stream(
                    {"name": f"Test Value Stream {suffix}", "code": f"TVS-{suffix}"}
                )

            stage1 = ValueStreamStage(
                name="Identify", value_stream_id=vs.id, stage_order=1
            )
            stage2 = ValueStreamStage(
                name="Fulfill", value_stream_id=vs.id, stage_order=2
            )
            db.session.add_all([stage1, stage2])

            capability = UnifiedCapability(
                name=f"Test Capability {suffix}", code=f"TCAP-{suffix}", level=2
            )
            db.session.add(capability)
            db.session.flush()

            mapping = CapabilityValueStreamMapping(
                capability_id=capability.id,
                value_stream_id=vs.id,
                value_stream_stage_id=stage1.id,
                support_type="primary",
                support_level=4,
                capability_contribution=75,
            )
            db.session.add(mapping)
            db.session.commit()

            vs_id, cap_id, stage1_id, stage2_id = vs.id, capability.id, stage1.id, stage2.id

            try:
                grid = vs_service.build_bizbok_grid(vs_id)

                assert grid["value_stream"]["id"] == vs_id
                assert [s["id"] for s in grid["stages"]] == [stage1_id, stage2_id]
                assert [c["id"] for c in grid["capabilities"]] == [cap_id]

                cell_key = f"{cap_id}:{stage1_id}"
                assert cell_key in grid["cells"]
                assert grid["cells"][cell_key]["support_level"] == 4
                assert grid["cells"][cell_key]["capability_contribution"] == 75

                empty_cell_key = f"{cap_id}:{stage2_id}"
                assert empty_cell_key not in grid["cells"]

                # Relationship access round-trips both directions.
                assert capability.value_stream_mappings.count() == 1
                assert mapping.capability_id == cap_id
                assert mapping.value_stream.id == vs_id
                assert mapping.value_stream_stage.id == stage1_id

                # upsert_mapping_cell updates the existing row rather than duplicating it.
                vs_service.upsert_mapping_cell(
                    cap_id, vs_id, stage1_id, {"support_level": 2, "capability_contribution": 30}
                )
                refreshed = CapabilityValueStreamMapping.query.filter_by(
                    capability_id=cap_id, value_stream_id=vs_id, value_stream_stage_id=stage1_id
                ).all()
                assert len(refreshed) == 1
                assert refreshed[0].support_level == 2

                # delete_mapping_cell removes it.
                deleted = vs_service.delete_mapping_cell(cap_id, vs_id, stage1_id)
                assert deleted is True
                assert (
                    CapabilityValueStreamMapping.query.filter_by(
                        capability_id=cap_id,
                        value_stream_id=vs_id,
                        value_stream_stage_id=stage1_id,
                    ).first()
                    is None
                )
            finally:
                CapabilityValueStreamMapping.query.filter_by(value_stream_id=vs_id).delete()
                ValueStreamStage.query.filter_by(value_stream_id=vs_id).delete()
                UnifiedCapability.query.filter_by(id=cap_id).delete()
                ValueStream.query.filter_by(id=vs_id).delete()
                db.session.commit()


class TestValueStreamBlueprint:
    def test_blueprint_registered(self, app):
        assert "value_stream" in app.blueprints

    def test_index_endpoint_resolves(self, app):
        with app.test_request_context():
            from flask import url_for

            assert url_for("value_stream.index") == "/value-streams/"

    def test_detail_and_grid_endpoints_resolve(self, app):
        with app.test_request_context():
            from flask import url_for

            assert url_for("value_stream.detail", value_stream_id=1) == "/value-streams/1"
            assert url_for("value_stream.api_grid", value_stream_id=1) == "/value-streams/1/grid"

    def test_mapping_api_route_registered(self, app):
        # The mapping API is exposed on one path via more than one view function
        # (POST/PUT on one, DELETE on another), so aggregate methods across every
        # rule that shares the path rather than collapsing them into a dict.
        methods = set()
        found = False
        for r in app.url_map.iter_rules():
            if r.endpoint.startswith("value_stream.") and r.rule == "/value-streams/api/mapping":
                found = True
                methods |= set(r.methods or [])
        assert found, "/value-streams/api/mapping not registered"
        assert "POST" in methods
        assert "DELETE" in methods
