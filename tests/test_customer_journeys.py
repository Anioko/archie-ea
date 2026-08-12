"""
Tests for the BIZBOK customer journey map.

Written against the SHARED fixtures in tests/conftest.py (``app``,
``db_session``, ``make_org``, ``tenant_ctx``) rather than a hand-rolled
module-scoped ``app``: ``db_session`` runs every test inside a transaction that
is always rolled back, so nothing here can leave residue in the shared test
database even if it fails partway.

Covers:
- the models import, map, and carry the tenancy the design requires;
- the ``code`` uniqueness is per organisation, not global — two organisations
  can both use ONBOARD;
- rows do not leak between organisations;
- the service builds journeys, stages, capability links and the grid, reaching
  real ``BusinessCapability`` rows and the applications behind them;
- an unrated stage stores NULL, never 0;
- a journey gets an ArchiMate mirror on the lower-case ``business`` layer;
- every page and JSON endpoint answers 200 through a real test client.
"""

from __future__ import annotations

import uuid

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def journey_org(make_org):
    """An organisation to hang journeys off."""
    return make_org("journey")


def _login(client, user_id):
    """Switch *client* to *user_id*, and make the switch actually take.

    Setting the session cookie is the standard Flask-Login test pattern and is
    not sufficient here. ``db_session`` holds one app context open for the whole
    test, and ``client.get()`` reuses it rather than pushing its own — so
    Flask-Login's ``g._login_user`` survives between requests and is answered
    from cache without the cookie ever being consulted. Left uncleared it
    resolves to AnonymousUser once and every subsequent request 302s to the
    login page while the session plainly holds a user id. The same note in
    ``tests/test_ba_tenant_and_authz.py::_login`` records this costing a whole
    session once already.

    The tenant keys are cleared for the same reason: stale org state would make
    an isolation assertion pass for the wrong reason.
    """
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    def test_models_importable(self):
        from app.models.customer_journey import (
            SENTIMENT_SCALE,
            CustomerJourney,
            CustomerJourneyStage,
            CustomerJourneyStageCapability,
        )

        assert CustomerJourney is not None
        assert CustomerJourneyStage is not None
        assert CustomerJourneyStageCapability is not None
        assert SENTIMENT_SCALE["neutral"] == 0

    def test_every_model_is_tenant_scoped(self):
        """Without TenantMixin these rows leak across organisations silently."""
        from app.models.customer_journey import (
            CustomerJourney,
            CustomerJourneyStage,
            CustomerJourneyStageCapability,
        )
        from app.models.mixins import TenantMixin

        for model in (
            CustomerJourney,
            CustomerJourneyStage,
            CustomerJourneyStageCapability,
        ):
            assert issubclass(model, TenantMixin), f"{model.__name__} is not tenant-scoped"
            assert "organization_id" in model.__table__.c

    def test_code_is_unique_per_organisation_not_globally(self):
        """`unique=True` on `code` would make ONBOARD first-come-first-served."""
        from app.models.customer_journey import CustomerJourney

        code_column = CustomerJourney.__table__.c.code
        assert code_column.unique is not True

        constraints = {
            tuple(col.name for col in constraint.columns)
            for constraint in CustomerJourney.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert ("organization_id", "code") in constraints

    def test_nullable_columns_survive_reconcile_schema(self):
        """reconcile-schema only ADDs nullable columns; a NOT NULL one breaks
        every existing database. Only the identity/ownership columns may be
        NOT NULL."""
        from app.models.customer_journey import (
            CustomerJourney,
            CustomerJourneyStage,
            CustomerJourneyStageCapability,
        )

        allowed_not_null = {
            "id",
            "organization_id",
            "name",
            "journey_id",
            "stage_id",
            "capability_id",
            "stage_order",
        }
        for model in (
            CustomerJourney,
            CustomerJourneyStage,
            CustomerJourneyStageCapability,
        ):
            for column in model.__table__.c:
                if not column.nullable:
                    assert column.name in allowed_not_null, (
                        f"{model.__tablename__}.{column.name} is NOT NULL and is not "
                        "an identity/ownership column"
                    )

    def test_mappers_configure_without_error(self, app):
        from sqlalchemy.orm import configure_mappers

        with app.app_context():
            configure_mappers()

    def test_back_populates_pairs_match(self, app):
        from app.models.customer_journey import (
            CustomerJourney,
            CustomerJourneyStage,
            CustomerJourneyStageCapability,
        )

        with app.app_context():
            assert CustomerJourney.stages.property.back_populates == "journey"
            assert CustomerJourneyStage.journey.property.back_populates == "stages"
            assert (
                CustomerJourneyStage.capability_links.property.back_populates == "stage"
            )
            assert (
                CustomerJourneyStageCapability.stage.property.back_populates
                == "capability_links"
            )
            assert (
                CustomerJourneyStageCapability.journey.property.back_populates
                == "capability_links"
            )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TestJourneyService:
    def test_create_journey_makes_an_archimate_element_on_the_business_layer(
        self, db_session, tenant_ctx, journey_org
    ):
        from app.models.customer_journey import CustomerJourney
        from app.models.models import ArchiMateElement
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            journey = svc.create_journey(
                {
                    "name": f"Onboarding {_suffix()}",
                    "code": f"ONB-{_suffix()}",
                    "persona_name": "First-time claimant",
                    "journey_type": "onboarding",
                }
            )

            assert journey.id is not None
            assert journey.organization_id == journey_org.id
            assert journey.archimate_element_id is not None

            element = db_session.get(ArchiMateElement, journey.archimate_element_id)
            assert element is not None
            assert element.type == "BusinessProcess"
            # Lower case: the element browser and the layer APIs key on it.
            assert str(element.layer).lower() == "business"

            assert (
                db_session.get(CustomerJourney, journey.id).name == journey.name
            )

    def test_an_unrecognised_journey_type_is_dropped_not_stored(
        self, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            journey = svc.create_journey(
                {"name": f"Journey {_suffix()}", "journey_type": "nonsense"}
            )
            assert journey.journey_type is None

    def test_create_journey_requires_a_name(self, db_session, tenant_ctx, journey_org):
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            with pytest.raises(ValueError):
                svc.create_journey({"name": "   "})

    def test_stages_are_ordered_and_auto_numbered(
        self, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            journey = svc.create_journey({"name": f"Journey {_suffix()}"})
            first = svc.create_stage(journey.id, {"name": "Aware"})
            second = svc.create_stage(journey.id, {"name": "Compare"})
            third = svc.create_stage(journey.id, {"name": "Buy", "stage_order": "9"})

            assert (first.stage_order, second.stage_order, third.stage_order) == (1, 2, 9)

            data = svc.get_journey_with_stages(journey.id)
            assert [stage["name"] for stage in data["stages"]] == [
                "Aware",
                "Compare",
                "Buy",
            ]

    def test_an_unrated_stage_stores_null_not_zero(
        self, db_session, tenant_ctx, journey_org
    ):
        """A stored 0 is indistinguishable from a measured neutral."""
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            journey = svc.create_journey({"name": f"Journey {_suffix()}"})
            unrated = svc.create_stage(journey.id, {"name": "Aware"})
            assert unrated.sentiment is None
            assert unrated.sentiment_score is None

            junk = svc.create_stage(journey.id, {"name": "Compare", "sentiment": "meh"})
            assert junk.sentiment is None
            assert junk.sentiment_score is None

            rated = svc.create_stage(
                journey.id, {"name": "Buy", "sentiment": "frustrated"}
            )
            assert rated.sentiment == "frustrated"
            assert rated.sentiment_score == -1

            # A measured neutral IS 0 and must be stored as 0, not dropped.
            neutral = svc.create_stage(
                journey.id, {"name": "Renew", "sentiment": "neutral"}
            )
            assert neutral.sentiment_score == 0

    def test_touchpoints_and_pain_points_split_into_lists(
        self, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            journey = svc.create_journey({"name": f"Journey {_suffix()}"})
            svc.create_stage(
                journey.id,
                {
                    "name": "Compare",
                    "touchpoints": "Pricing page\n\nLive chat\n",
                    "pain_points": "Quote takes 3 days",
                    "channel": "web",
                },
            )
            stage = svc.get_journey_with_stages(journey.id)["stages"][0]
            assert stage["touchpoints"] == ["Pricing page", "Live chat"]
            assert stage["pain_points"] == ["Quote takes 3 days"]
            assert stage["channel"] == "web"

    def test_missing_journey_yields_the_documented_empty_grid(self, app):
        from app.modules.capabilities.services import customer_journey_service as svc

        with app.app_context():
            assert svc.build_capability_grid(-1) == {
                "journey": None,
                "stages": [],
                "capabilities": [],
                "cells": {},
            }

    def test_get_journey_with_stages_returns_none_when_absent(self, app):
        from app.modules.capabilities.services import customer_journey_service as svc

        with app.app_context():
            assert svc.get_journey_with_stages(-1) is None


class TestCapabilityLinks:
    """The link that makes a journey architecture rather than a drawing."""

    def _capability(self, db_session, name):
        from app.models.business_capabilities import BusinessCapability

        capability = BusinessCapability(name=name, code=f"CJ-{_suffix()}", level=2)
        db_session.add(capability)
        db_session.flush()
        return capability

    def test_link_reaches_a_real_business_capability(
        self, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            capability = self._capability(db_session, f"Customer Onboarding {_suffix()}")
            journey = svc.create_journey({"name": f"Journey {_suffix()}"})
            stage = svc.create_stage(journey.id, {"name": "Apply"})

            link = svc.upsert_capability_link(
                stage.id, capability.id, {"support_level": 4, "support_type": "primary"}
            )
            assert link.journey_id == journey.id
            assert link.capability_id == capability.id
            assert link.support_level == 4
            assert link.support_type == "primary"

            grid = svc.build_capability_grid(journey.id)
            assert grid["journey"]["id"] == journey.id
            assert [row["id"] for row in grid["capabilities"]] == [capability.id]
            cell = grid["cells"][f"{capability.id}:{stage.id}"]
            assert cell["support_level"] == 4

            # And the stage view carries the capability's real name.
            stages = svc.get_journey_with_stages(journey.id)["stages"]
            assert stages[0]["capabilities"][0]["capability_name"] == capability.name

    def test_upsert_updates_rather_than_duplicating(
        self, db_session, tenant_ctx, journey_org
    ):
        from app.models.customer_journey import CustomerJourneyStageCapability
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            capability = self._capability(db_session, f"Billing {_suffix()}")
            journey = svc.create_journey({"name": f"Journey {_suffix()}"})
            stage = svc.create_stage(journey.id, {"name": "Pay"})

            svc.upsert_capability_link(stage.id, capability.id, {"support_level": 2})
            svc.upsert_capability_link(stage.id, capability.id, {"support_level": 5})

            rows = CustomerJourneyStageCapability.query.filter_by(
                stage_id=stage.id, capability_id=capability.id
            ).all()
            assert len(rows) == 1
            assert rows[0].support_level == 5

            assert svc.delete_capability_link(stage.id, capability.id) is True
            assert svc.delete_capability_link(stage.id, capability.id) is False

    def test_support_level_is_null_when_not_assessed(
        self, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            capability = self._capability(db_session, f"Servicing {_suffix()}")
            journey = svc.create_journey({"name": f"Journey {_suffix()}"})
            stage = svc.create_stage(journey.id, {"name": "Call"})

            link = svc.upsert_capability_link(stage.id, capability.id, {})
            assert link.support_level is None
            assert link.support_type is None

    def test_link_to_a_nonexistent_capability_raises(
        self, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            journey = svc.create_journey({"name": f"Journey {_suffix()}"})
            stage = svc.create_stage(journey.id, {"name": "Apply"})
            with pytest.raises(ValueError):
                svc.upsert_capability_link(stage.id, -1, {})

    def test_grid_row_carries_the_applications_behind_the_capability(
        self, db_session, tenant_ctx, journey_org
    ):
        """Stage -> capability -> application, which is the whole point."""
        from app.models.application_capability import ApplicationCapabilityMapping
        from app.models.application_portfolio import ApplicationComponent
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            capability = self._capability(db_session, f"Claims Handling {_suffix()}")
            application = ApplicationComponent(name=f"Guidewire {_suffix()}")
            db_session.add(application)
            db_session.flush()
            db_session.add(
                ApplicationCapabilityMapping(
                    organization_id=journey_org.id,
                    application_component_id=application.id,
                    business_capability_id=capability.id,
                )
            )
            db_session.flush()

            journey = svc.create_journey({"name": f"Journey {_suffix()}"})
            stage = svc.create_stage(journey.id, {"name": "Claim"})
            svc.upsert_capability_link(stage.id, capability.id, {"support_level": 5})

            grid = svc.build_capability_grid(journey.id)
            row = grid["capabilities"][0]
            assert [app["id"] for app in row["applications"]] == [application.id]
            assert row["applications"][0]["name"] == application.name

    def test_capability_picker_excludes_already_linked_capabilities(
        self, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        with tenant_ctx(journey_org.id):
            marker = _suffix()
            linked = self._capability(db_session, f"Linked {marker}")
            free = self._capability(db_session, f"Free {marker}")
            journey = svc.create_journey({"name": f"Journey {marker}"})
            stage = svc.create_stage(journey.id, {"name": "Apply"})
            svc.upsert_capability_link(stage.id, linked.id, {})

            found = svc.list_linkable_capabilities(journey.id, search=marker)
            ids = {row["id"] for row in found}
            assert free.id in ids
            assert linked.id not in ids


class TestTenantIsolation:
    def test_two_organisations_can_hold_the_same_journey_code(
        self, db_session, tenant_ctx, make_org
    ):
        """The whole point of scoping `code` per organisation."""
        from app.modules.capabilities.services import customer_journey_service as svc

        # Ids are read out first: expunge_all() below detaches the Organization
        # rows, and touching org_b.id afterwards would raise
        # DetachedInstanceError rather than test anything about tenancy.
        org_a_id = make_org("cj-a").id
        org_b_id = make_org("cj-b").id
        code = f"ONB-{_suffix()}"

        with tenant_ctx(org_a_id):
            svc.create_journey({"name": "Onboarding", "code": code})
        db_session.expunge_all()
        with tenant_ctx(org_b_id):
            second = svc.create_journey({"name": "Onboarding", "code": code})
            assert second.id is not None
            assert second.organization_id == org_b_id

    def test_journeys_do_not_leak_between_organisations(
        self, db_session, tenant_ctx, make_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        org_a_id = make_org("cj-x").id
        org_b_id = make_org("cj-y").id
        marker = _suffix()

        with tenant_ctx(org_a_id):
            svc.create_journey({"name": f"Private {marker}"})

        # Expunge first: `.get()` and the identity map answer from cache without
        # emitting SQL, so the tenant filter would never run and the test would
        # pass for the wrong reason. Ids were read before this line for the same
        # reason the assertion below cannot touch a detached Organization.
        db_session.expunge_all()
        with tenant_ctx(org_b_id):
            names = {journey["name"] for journey in svc.list_journeys()}
        assert f"Private {marker}" not in names


# ---------------------------------------------------------------------------
# Blueprint and HTTP surface
# ---------------------------------------------------------------------------


class TestBlueprint:
    def test_blueprint_registered(self, app):
        assert "customer_journey" in app.blueprints

    def test_endpoints_resolve(self, app):
        from flask import url_for

        with app.test_request_context():
            assert url_for("customer_journey.index") == "/customer-journeys/"
            assert url_for("customer_journey.detail", journey_id=1) == "/customer-journeys/1"
            assert (
                url_for("customer_journey.api_grid", journey_id=1)
                == "/customer-journeys/1/grid"
            )
            assert (
                url_for("customer_journey.api_capabilities", journey_id=1)
                == "/customer-journeys/1/api/capabilities"
            )

    def test_capability_link_api_carries_both_methods(self, app):
        methods = set()
        found = False
        for rule in app.url_map.iter_rules():
            if (
                rule.endpoint.startswith("customer_journey.")
                and rule.rule == "/customer-journeys/api/capability-link"
            ):
                found = True
                methods |= set(rule.methods or [])
        assert found, "/customer-journeys/api/capability-link is not registered"
        assert {"POST", "PUT", "DELETE"} <= methods


class TestPagesRender:
    """Every page answers 200 through a real client, not just 'the route exists'."""

    @pytest.fixture
    def logged_in_client(self, app, db_session, journey_org):
        from app.models.user import User

        user = User(
            email=f"cj-{_suffix()}@example.com",
            first_name="Journey",
            last_name="Architect",
            organization_id=journey_org.id,
            enterprise_role="business_architect",
            # An unconfirmed user is bounced to account.unconfirmed by a
            # before_app_request hook, so every assertion below would read 302
            # and say nothing about these routes.
            confirmed=True,
        )
        user.password_hash = "x"  # never used: the session is set directly
        db_session.add(user)
        db_session.flush()

        client = app.test_client()
        _login(client, user.id)
        return client, user

    def test_index_returns_200(self, logged_in_client):
        client, _ = logged_in_client
        response = client.get("/customer-journeys/")
        assert response.status_code == 200
        assert b"Customer Journeys" in response.data

    def test_detail_returns_200_and_shows_the_stage(
        self, logged_in_client, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        client, _ = logged_in_client
        with tenant_ctx(journey_org.id):
            journey = svc.create_journey(
                {"name": f"Renewal {_suffix()}", "persona_name": "Existing customer"}
            )
            svc.create_stage(
                journey.id,
                {
                    "name": "Receive reminder",
                    "channel": "email",
                    "sentiment": "frustrated",
                    "touchpoints": "Renewal email",
                    "pain_points": "Arrives too late",
                },
            )

        response = client.get(f"/customer-journeys/{journey.id}")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert "Receive reminder" in body
        assert "Existing customer" in body
        assert "Renewal email" in body

    def test_detail_of_a_missing_journey_is_404_not_500(self, logged_in_client):
        client, _ = logged_in_client
        response = client.get("/customer-journeys/999999999")
        assert response.status_code == 404

    def test_grid_endpoint_returns_200_json(
        self, logged_in_client, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        client, _ = logged_in_client
        with tenant_ctx(journey_org.id):
            journey = svc.create_journey({"name": f"Journey {_suffix()}"})
            svc.create_stage(journey.id, {"name": "Apply"})

        response = client.get(f"/customer-journeys/{journey.id}/grid")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["journey"]["id"] == journey.id
        assert [stage["name"] for stage in payload["stages"]] == ["Apply"]

    def test_grid_of_a_missing_journey_is_404_with_an_error(self, logged_in_client):
        client, _ = logged_in_client
        response = client.get("/customer-journeys/999999999/grid")
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_capability_picker_endpoint_returns_200_json(
        self, logged_in_client, db_session, tenant_ctx, journey_org
    ):
        from app.modules.capabilities.services import customer_journey_service as svc

        client, _ = logged_in_client
        with tenant_ctx(journey_org.id):
            journey = svc.create_journey({"name": f"Journey {_suffix()}"})

        response = client.get(
            f"/customer-journeys/{journey.id}/api/capabilities?q=nothing-matches-{_suffix()}"
        )
        assert response.status_code == 200
        assert response.get_json()["capabilities"] == []

    def test_capability_link_api_rejects_non_integer_ids_with_400(
        self, logged_in_client
    ):
        client, _ = logged_in_client
        response = client.post(
            "/customer-journeys/api/capability-link",
            json={"stage_id": "not-an-int", "capability_id": 1},
        )
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_the_whole_write_path_works_over_http(
        self, logged_in_client, db_session, journey_org
    ):
        """Create a journey, add a stage, link a capability — as a user would.

        A route that only ever answers GET has not been shown to work; the write
        path is where require_roles, the tenant default and the ArchiMate mirror
        all actually run.
        """
        from app.models.business_capabilities import BusinessCapability
        from app.models.customer_journey import CustomerJourney

        client, _ = logged_in_client
        marker = _suffix()

        created = client.post(
            "/customer-journeys/create",
            data={
                "name": f"Claim {marker}",
                "code": f"CLM-{marker}",
                "persona_name": "First-time claimant",
                "journey_type": "service",
            },
        )
        assert created.status_code == 302
        journey_id = int(created.headers["Location"].rstrip("/").rsplit("/", 1)[-1])

        journey = db_session.get(CustomerJourney, journey_id)
        assert journey.organization_id == journey_org.id
        assert journey.archimate_element_id is not None

        staged = client.post(
            f"/customer-journeys/{journey_id}/stages",
            data={
                "name": "Report the claim",
                "channel": "call_centre",
                "sentiment": "angry",
                "touchpoints": "Claims line\nSMS confirmation",
                "pain_points": "Twenty minutes on hold",
            },
        )
        assert staged.status_code == 302

        grid = client.get(f"/customer-journeys/{journey_id}/grid").get_json()
        assert [stage["name"] for stage in grid["stages"]] == ["Report the claim"]
        assert grid["stages"][0]["sentiment_score"] == -2
        stage_id = grid["stages"][0]["id"]

        capability = BusinessCapability(
            name=f"Claims Intake {marker}", code=f"CI-{marker}", level=2
        )
        db_session.add(capability)
        db_session.flush()

        linked = client.post(
            "/customer-journeys/api/capability-link",
            json={
                "stage_id": stage_id,
                "capability_id": capability.id,
                "support_level": 5,
                "support_type": "primary",
            },
        )
        assert linked.status_code == 200
        assert linked.get_json()["link"]["support_level"] == 5

        grid = client.get(f"/customer-journeys/{journey_id}/grid").get_json()
        assert [row["id"] for row in grid["capabilities"]] == [capability.id]
        assert grid["cells"][f"{capability.id}:{stage_id}"]["support_level"] == 5

        cleared = client.delete(
            "/customer-journeys/api/capability-link",
            json={"stage_id": stage_id, "capability_id": capability.id},
        )
        assert cleared.status_code == 200
        assert cleared.get_json()["deleted"] is True

    def test_a_reader_cannot_write(self, app, db_session, journey_org):
        """require_roles must actually keep a non-architect out of the writes."""
        from app.models.user import User

        reader = User(
            email=f"cj-reader-{_suffix()}@example.com",
            organization_id=journey_org.id,
            enterprise_role="portfolio_manager",
            confirmed=True,
        )
        reader.password_hash = "x"
        db_session.add(reader)
        db_session.flush()

        client = app.test_client()
        _login(client, reader.id)

        assert client.get("/customer-journeys/").status_code == 200
        response = client.post(
            "/customer-journeys/create", data={"name": f"Nope {_suffix()}"}
        )
        assert response.status_code == 403
