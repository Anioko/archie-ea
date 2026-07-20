"""Tests for the Organization module: enterprise org chart + enterprise RACI
matrix (Business-Architect signature artifacts).

Covers:
- EnterpriseRaciAssignment model import + column shape + unique constraint,
  mirroring tests/test_business_model.py's approach.
- The module's register(app) + service helpers import cleanly.
- The blueprint registers on a bare Flask app (no full create_app() boot —
  this module is self-contained and doesn't need the whole ORM graph) and
  organization.* routes resolve.
- service.build_org_tree() assembles a tree from seeded BusinessActors
  linked by Composition ArchiMateRelationships, using the app's test
  fixture + db.create_all() (mirrors tests/test_motivation_bridge.py).
"""

import uuid

import pytest


class TestEnterpriseRaciAssignmentModel:
    def test_model_importable(self):
        from app.models.organization_model import (
            RACI_VALUES,
            STAKEHOLDER_TYPES,
            EnterpriseRaciAssignment,
        )

        assert EnterpriseRaciAssignment is not None
        assert RACI_VALUES == ("R", "A", "C", "I")
        assert STAKEHOLDER_TYPES == ("actor", "role", "user")

    def test_table_name(self):
        from app.models.organization_model import EnterpriseRaciAssignment

        assert EnterpriseRaciAssignment.__tablename__ == "enterprise_raci_assignments"

    def test_has_expected_columns(self):
        from app.models.organization_model import EnterpriseRaciAssignment

        columns = set(EnterpriseRaciAssignment.__table__.columns.keys())
        for col in (
            "id",
            "organization_id",
            "stakeholder_type",
            "stakeholder_id",
            "stakeholder_name",
            "capability_id",
            "raci",
            "notes",
            "created_at",
            "updated_at",
        ):
            assert col in columns

    def test_has_unique_constraint(self):
        from app.models.organization_model import EnterpriseRaciAssignment

        constraint_names = {
            getattr(c, "name", None) for c in EnterpriseRaciAssignment.__table__.constraints
        }
        assert "uq_enterprise_raci_stakeholder_capability" in constraint_names

    def test_all_new_columns_are_nullable(self):
        """Only organization_id (TenantMixin, defaulted via _default_org_id) may be
        NOT NULL — every column this module adds must be nullable so create_all()
        never conflicts with the reconcile-schema drift-repair step."""
        from app.models.organization_model import EnterpriseRaciAssignment

        table = EnterpriseRaciAssignment.__table__
        for col_name in (
            "stakeholder_type",
            "stakeholder_id",
            "stakeholder_name",
            "capability_id",
            "raci",
            "notes",
            "created_at",
            "updated_at",
        ):
            assert table.columns[col_name].nullable is True, f"{col_name} must be nullable"

    def test_to_dict_round_trip(self):
        from app.models.organization_model import EnterpriseRaciAssignment

        assignment = EnterpriseRaciAssignment(
            stakeholder_type="actor",
            stakeholder_id=1,
            stakeholder_name="Manufacturing Quality Department",
            capability_id=1,
            raci="A",
        )
        data = assignment.to_dict()
        assert data["stakeholder_type"] == "actor"
        assert data["stakeholder_name"] == "Manufacturing Quality Department"
        assert data["raci"] == "A"


class TestOrganizationModule:
    def test_module_register_function_importable(self):
        from app.modules.organization import organization_bp, register

        assert callable(register)
        assert organization_bp.name == "organization"
        assert organization_bp.url_prefix == "/organization"

    def test_service_importable(self):
        from app.modules.organization import service

        assert hasattr(service, "build_org_tree")
        assert hasattr(service, "search_stakeholders")
        assert hasattr(service, "list_matrix_capabilities")
        assert hasattr(service, "list_raci_assignments")
        assert hasattr(service, "upsert_raci_cell")
        assert hasattr(service, "delete_raci_cell")


class TestOrganizationBlueprintRoutes:
    """Register the blueprint on a bare Flask app (no full create_app() boot)
    to verify routing without paying for the whole ORM/app-factory import."""

    @pytest.fixture(scope="module")
    def bare_app(self):
        from flask import Flask

        from app.modules.organization.routes import organization_bp

        flask_app = Flask(__name__)
        flask_app.register_blueprint(organization_bp)
        return flask_app

    def test_index_endpoint_resolves(self, bare_app):
        with bare_app.test_request_context():
            from flask import url_for

            assert url_for("organization.index") == "/organization/"

    def test_chart_endpoints_resolve(self, bare_app):
        with bare_app.test_request_context():
            from flask import url_for

            assert url_for("organization.chart") == "/organization/chart"
            assert url_for("organization.chart_data") == "/organization/chart/api/data"

    def test_raci_endpoints_resolve(self, bare_app):
        with bare_app.test_request_context():
            from flask import url_for

            assert url_for("organization.raci") == "/organization/raci"
            assert url_for("organization.raci_data") == "/organization/raci/api/data"

    def test_raci_cell_endpoint_registered_with_post_and_delete(self, bare_app):
        methods = set()
        found = False
        for r in bare_app.url_map.iter_rules():
            if r.endpoint == "organization.raci_cell_save":
                found = True
                methods |= set(r.methods or [])
        assert found, "organization/raci/api/cell (save) route not registered"
        assert "POST" in methods

        methods = set()
        found = False
        for r in bare_app.url_map.iter_rules():
            if r.endpoint == "organization.raci_cell_delete":
                found = True
                methods |= set(r.methods or [])
        assert found, "organization/raci/api/cell (delete) route not registered"
        assert "DELETE" in methods

    def test_stakeholder_search_endpoint_resolves(self, bare_app):
        with bare_app.test_request_context():
            from flask import url_for

            assert url_for("organization.stakeholder_search") == "/organization/api/stakeholders/search"


@pytest.fixture(scope="module")
def app():
    from app import create_app, db

    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    # New table (enterprise_raci_assignments) — create_all() only creates
    # missing tables, never touches existing ones, so this is safe against
    # the shared test database's pre-existing schema.
    with app.app_context():
        db.create_all()

    return app


def _make_org_hierarchy(db, suffix):
    """Seed a small org hierarchy: HoldCo (parent) composed of two
    sub-departments, plus one orphan actor with no relationships at all.
    Returns (holdco, dept_a, dept_b, orphan)."""
    from app.models.archimate_core import ArchiMateRelationship
    from app.models.business_layer import BusinessActor
    from app.models.organization import Organization

    org = Organization(name=f"Org Chart Test Org {suffix}", slug=f"org-chart-test-{suffix}")
    db.session.add(org)
    db.session.flush()

    holdco = BusinessActor(
        name=f"HoldCo {suffix}", actor_type="Business Unit", organization_id=org.id
    )
    dept_a = BusinessActor(
        name=f"Dept A {suffix}", actor_type="Department", organization_id=org.id
    )
    dept_b = BusinessActor(
        name=f"Dept B {suffix}", actor_type="Department", organization_id=org.id
    )
    orphan = BusinessActor(
        name=f"Orphan Team {suffix}", actor_type="Team", organization_id=org.id
    )
    db.session.add_all([holdco, dept_a, dept_b, orphan])
    db.session.flush()  # assigns archimate_element_id via the before_insert listener

    rel_a = ArchiMateRelationship(
        type="Composition",
        source_id=holdco.archimate_element_id,
        target_id=dept_a.archimate_element_id,
    )
    rel_b = ArchiMateRelationship(
        type="Composition",
        source_id=holdco.archimate_element_id,
        target_id=dept_b.archimate_element_id,
    )
    db.session.add_all([rel_a, rel_b])
    db.session.commit()

    return org, holdco, dept_a, dept_b, orphan


def _cleanup_org_hierarchy(db, org, actors):
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.business_layer import BusinessActor
    from app.models.organization import Organization

    try:
        element_ids = [a.archimate_element_id for a in actors if a.archimate_element_id]
        if element_ids:
            ArchiMateRelationship.query.filter(
                ArchiMateRelationship.source_id.in_(element_ids)
            ).delete(synchronize_session=False)
        for a in actors:
            BusinessActor.query.filter_by(id=a.id).delete()
        if element_ids:
            ArchiMateElement.query.filter(ArchiMateElement.id.in_(element_ids)).delete(
                synchronize_session=False
            )
        Organization.query.filter_by(id=org.id).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()


class TestBuildOrgTree:
    def test_builds_tree_from_composition_relationships(self, app):
        from app import db
        from app.modules.organization import service

        suffix = uuid.uuid4().hex[:8]

        with app.app_context():
            org, holdco, dept_a, dept_b, orphan = _make_org_hierarchy(db, suffix)
            try:
                tree = service.build_org_tree()

                assert tree["fallback"] is False
                assert tree["relationship_count"] >= 2

                root_names = {r["name"] for r in tree["roots"]}
                assert holdco.name in root_names
                # Orphan actors (no relationships at all) surface as their
                # own roots rather than being dropped.
                assert orphan.name in root_names

                holdco_node = next(r for r in tree["roots"] if r["name"] == holdco.name)
                child_names = {c["name"] for c in holdco_node["children"]}
                assert dept_a.name in child_names
                assert dept_b.name in child_names
            finally:
                _cleanup_org_hierarchy(db, org, [holdco, dept_a, dept_b, orphan])

    def test_orphan_actor_surfaces_without_relationships(self, app):
        """An actor with zero composition/aggregation relationships must
        still show up somewhere in the org data — either as its own root
        (tree mode) or inside its actor_type group (flat fallback mode).
        This is deliberately agnostic to which mode is active, since that
        depends on whether *any* BusinessActor in the shared test database
        has a composition/aggregation relationship — see
        test_builds_tree_from_composition_relationships for the strict,
        self-contained assertion that tree mode activates correctly."""
        from app import db
        from app.models.business_layer import BusinessActor
        from app.models.organization import Organization
        from app.modules.organization import service

        suffix = uuid.uuid4().hex[:8]

        with app.app_context():
            org = Organization(
                name=f"Flat Fallback Test Org {suffix}", slug=f"flat-fallback-test-{suffix}"
            )
            db.session.add(org)
            db.session.flush()

            actor = BusinessActor(
                name=f"Standalone Dept {suffix}", actor_type="Department", organization_id=org.id
            )
            db.session.add(actor)
            db.session.commit()

            try:
                tree = service.build_org_tree()
                if tree["fallback"]:
                    names_in_groups = {
                        a["name"] for g in tree["groups"] for a in g["actors"]
                    }
                    assert actor.name in names_in_groups
                else:
                    def _collect_names(node):
                        names = {node["name"]}
                        for child in node["children"]:
                            names |= _collect_names(child)
                        return names

                    all_names = set()
                    for root in tree["roots"]:
                        all_names |= _collect_names(root)
                    assert actor.name in all_names
            finally:
                _cleanup_org_hierarchy(db, org, [actor])
