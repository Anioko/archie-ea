"""Business information model — the BIZBOK information map.

Covers:

* the declaration invariants that no runtime behaviour reveals — the new table
  is ``TenantMixin``, and ``business_objects.code`` is unique *per organisation*
  rather than globally;
* the service end to end against real rows: domains, objects, the capability x
  object CRUD matrix, object-to-object relationships written into the ArchiMate
  layer, and application mastering;
* that a created business object reaches the ArchiMate business layer with a
  **lower-case** ``layer``, because the element browser and every layer API key
  on the lower-case token and a capitalised one is invisible to all of them;
* tenant isolation, since a leak here would expose another organisation's data
  dictionary;
* blueprint registration and endpoint resolution.

Written against the shared fixtures in tests/conftest.py: ``db_session`` runs
each test inside a transaction that is always rolled back, so nothing here can
leave residue in the shared test database.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _make_domain(db_session, org_id, name=None):
    from app.models.process_data import DataDomain

    row = DataDomain(
        name=name or f"Domain {_suffix()}",
        code=f"D{_suffix()[:6]}",
        organization_id=org_id,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _make_object(db_session, org_id, name=None, domain_id=None, code=None):
    from app.models.business_layer import BusinessObject

    row = BusinessObject(
        name=name or f"Object {_suffix()}",
        code=code or f"O{_suffix()[:6]}",
        data_domain_id=domain_id,
        organization_id=org_id,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _make_capability(db_session, org_id, name=None):
    from app.models.business_capabilities import BusinessCapability

    row = BusinessCapability(
        name=name or f"Capability {_suffix()}",
        code=f"C{_suffix()[:6]}",
        level=1,
        organization_id=org_id,
    )
    db_session.add(row)
    db_session.flush()
    return row


# --------------------------------------------------------------- declarations


class TestDeclarations:
    def test_models_importable(self):
        from app.models.business_layer import BusinessObject
        from app.models.information_model import CapabilityObjectCrud
        from app.models.process_data import DataDomain
        from app.models.relationship_tables import DataObjectStorage

        assert CapabilityObjectCrud is not None
        assert BusinessObject is not None
        assert DataDomain is not None
        assert DataObjectStorage is not None

    def test_crud_table_is_tenant_scoped(self):
        """Omitting TenantMixin would silently leak every CRUD statement across
        organisations, and nothing at a call site would show it."""
        from app.models.information_model import CapabilityObjectCrud
        from app.models.mixins import TenantMixin

        assert issubclass(CapabilityObjectCrud, TenantMixin)
        assert "organization_id" in CapabilityObjectCrud.__table__.c

    def test_business_object_code_is_unique_per_organisation(self):
        """`unique=True` on an authored code makes it first-come-first-served
        across every tenant — the second organisation to use "ORD" is refused.
        Enforced globally by scripts/check_tenant_unique.py; pinned here for
        this column specifically."""
        from sqlalchemy import UniqueConstraint

        from app.models.business_layer import BusinessObject

        table = BusinessObject.__table__
        assert not table.c.code.unique, "business_objects.code must not be globally unique"

        scoped = [
            c
            for c in table.constraints
            if isinstance(c, UniqueConstraint)
            and {col.name for col in c.columns} == {"organization_id", "code"}
        ]
        assert scoped, "expected UNIQUE (organization_id, code) on business_objects"

    def test_new_columns_are_nullable(self):
        """reconcile-schema only adds nullable columns; a NOT NULL addition
        breaks every existing database on the next boot."""
        from app.models.business_layer import BusinessObject
        from app.models.relationship_tables import DataObjectStorage

        assert BusinessObject.__table__.c.code.nullable
        assert DataObjectStorage.__table__.c.application_id.nullable
        assert DataObjectStorage.__table__.c.system_role.nullable

    def test_mappers_configure(self, app):
        from sqlalchemy.orm import configure_mappers

        with app.app_context():
            configure_mappers()


# --------------------------------------------------------------- ArchiMate


class TestArchiMateMirror:
    def test_created_object_reaches_the_business_layer_in_lower_case(
        self, db_session, make_org, tenant_ctx
    ):
        from app.models.archimate_core import ArchiMateElement
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("archimate")
        with tenant_ctx(org.id):
            obj = im_service.create_object(
                {"name": f"Customer Order {_suffix()}", "code": "ORD", "description": "An order."}
            )
            assert obj.archimate_element_id, (
                "a business object with no ArchiMate element is invisible to the "
                "element browser and to the AI assistant, which reads that layer"
            )
            element = db_session.get(ArchiMateElement, obj.archimate_element_id)

        assert element is not None
        assert element.type == "BusinessObject"
        assert element.layer == "business", (
            f"layer must be lower case; got {element.layer!r}. A capitalised layer "
            "is invisible to the element browser and every layer API."
        )


# --------------------------------------------------------------- the map


class TestInformationMap:
    def test_map_groups_objects_by_domain_and_shows_the_unfiled(
        self, db_session, make_org, tenant_ctx
    ):
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("map")
        domain = _make_domain(db_session, org.id, name=f"Customer {_suffix()}")
        filed = _make_object(db_session, org.id, domain_id=domain.id)
        unfiled = _make_object(db_session, org.id, domain_id=None)

        with tenant_ctx(org.id):
            info_map = im_service.build_information_map()

        domains = {d["id"]: d for d in info_map["domains"]}
        assert domain.id in domains
        assert [o["id"] for o in domains[domain.id]["objects"]] == [filed.id]
        assert domains[domain.id]["object_count"] == 1
        assert unfiled.id in {o["id"] for o in info_map["unfiled"]}
        assert info_map["object_count"] == 2

    def test_domain_delete_keeps_its_objects(self, db_session, make_org, tenant_ctx):
        """The objects are the record; the domain is a grouping. Cascading would
        destroy the data dictionary because somebody tidied a folder."""
        from app.models.business_layer import BusinessObject
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("domdel")
        domain = _make_domain(db_session, org.id)
        obj = _make_object(db_session, org.id, domain_id=domain.id)

        with tenant_ctx(org.id):
            assert im_service.delete_domain(domain.id) is True
            survivor = BusinessObject.query.filter(BusinessObject.id == obj.id).first()

        assert survivor is not None
        assert survivor.data_domain_id is None


# --------------------------------------------------------------- CRUD matrix


class TestCrudMatrix:
    def test_matrix_shape_when_there_is_nothing_to_show(self, db_session, make_org, tenant_ctx):
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("emptymatrix")
        with tenant_ctx(org.id):
            matrix = im_service.build_crud_matrix()

        assert matrix["objects"] == []
        assert matrix["capabilities"] == []
        assert matrix["cells"] == {}

    def test_upsert_updates_rather_than_duplicates(self, db_session, make_org, tenant_ctx):
        from app.models.information_model import CapabilityObjectCrud
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("crud")
        capability = _make_capability(db_session, org.id)
        obj = _make_object(db_session, org.id)

        with tenant_ctx(org.id):
            first = im_service.upsert_crud_cell(
                capability.id, obj.id, {"creates": True, "reads": True}
            )
            assert first.crud_letters == "CR"

            im_service.upsert_crud_cell(
                capability.id,
                obj.id,
                {"creates": True, "reads": True, "updates": True, "deletes": True},
            )
            rows = CapabilityObjectCrud.query.filter(
                CapabilityObjectCrud.capability_id == capability.id,
                CapabilityObjectCrud.business_object_id == obj.id,
            ).all()

            assert len(rows) == 1
            assert rows[0].crud_letters == "CRUD"

            matrix = im_service.build_crud_matrix()
            key = f"{capability.id}:{obj.id}"
            assert key in matrix["cells"]
            assert matrix["cells"][key]["letters"] == "CRUD"
            assert [c["id"] for c in matrix["capabilities"]] == [capability.id]

            assert im_service.delete_crud_cell(capability.id, obj.id) is True
            assert im_service.delete_crud_cell(capability.id, obj.id) is False

    def test_no_operations_reads_as_none_not_zero(self, db_session, make_org, tenant_ctx):
        """A cell with nothing claimed must render as an em dash, not as a word
        or a zero that reads like a measurement."""
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("crudnone")
        capability = _make_capability(db_session, org.id)
        obj = _make_object(db_session, org.id)

        with tenant_ctx(org.id):
            row = im_service.upsert_crud_cell(capability.id, obj.id, {"reads": False})

        assert row.crud_letters is None

    def test_upsert_rejects_a_missing_reference(self, db_session, make_org, tenant_ctx):
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("crudbad")
        obj = _make_object(db_session, org.id)

        with tenant_ctx(org.id):
            with pytest.raises(ValueError):
                im_service.upsert_crud_cell(-1, obj.id, {"reads": True})


# --------------------------------------------------------------- relationships


class TestObjectRelationships:
    def test_relationship_is_written_to_the_archimate_layer(
        self, db_session, make_org, tenant_ctx
    ):
        from app.models.archimate_core import ArchiMateRelationship
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("rel")
        with tenant_ctx(org.id):
            order = im_service.create_object({"name": f"Order {_suffix()}"})
            line = im_service.create_object({"name": f"Order Line {_suffix()}"})

            rel = im_service.create_object_relationship(
                order.id, line.id, "composition", "An order is made of order lines."
            )

            stored = db_session.get(ArchiMateRelationship, rel.id)
            assert stored.type == "composition"
            assert stored.source_id == order.archimate_element_id
            assert stored.target_id == line.archimate_element_id

            listed = im_service.list_object_relationships(order.id)
            assert [r["object_id"] for r in listed["outgoing"]] == [line.id]
            assert listed["incoming"] == []

            reverse = im_service.list_object_relationships(line.id)
            assert [r["object_id"] for r in reverse["incoming"]] == [order.id]

            # Re-stating the same relationship must not create a second row.
            again = im_service.create_object_relationship(order.id, line.id, "composition")
            assert again.id == rel.id

            assert im_service.delete_object_relationship(rel.id) is True
            assert im_service.list_object_relationships(order.id)["outgoing"] == []

    def test_a_bad_relationship_type_is_refused(self, db_session, make_org, tenant_ctx):
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("relbad")
        with tenant_ctx(org.id):
            a = im_service.create_object({"name": f"A {_suffix()}"})
            b = im_service.create_object({"name": f"B {_suffix()}"})

            with pytest.raises(ValueError):
                im_service.create_object_relationship(a.id, b.id, "sends-things-to")
            with pytest.raises(ValueError):
                im_service.create_object_relationship(a.id, a.id, "composition")


# --------------------------------------------------------------- applications


class TestApplicationMastering:
    def _make_application(self, db_session, org_id):
        from app.models.application_portfolio import ApplicationComponent

        row = ApplicationComponent(name=f"App {_suffix()}", organization_id=org_id)
        db_session.add(row)
        db_session.flush()
        return row

    def test_system_of_record_is_recorded_and_readable(
        self, db_session, make_org, tenant_ctx
    ):
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("apps")
        application = self._make_application(db_session, org.id)

        with tenant_ctx(org.id):
            obj = im_service.create_object({"name": f"Customer {_suffix()}"})
            link = im_service.set_object_application(
                obj.id, application.id, {"system_role": "system_of_record"}
            )
            assert link.application_id == application.id
            assert link.is_master_source is True
            # The legacy column keeps pointing at the ArchiMate element, so the
            # existing archimate_relationship_sync listener still fires.
            assert link.application_component_id == application.archimate_element_id

            detail = im_service.get_object_detail(obj.id)

        assert detail["system_of_record"] == application.name
        assert detail["applications"][0]["system_role_label"] == "System of Record"

    def test_an_unstated_role_stays_unstated(self, db_session, make_org, tenant_ctx):
        """NULL means nobody has said. Defaulting it to "consumer" would invent
        a fact about the portfolio."""
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("approle")
        application = self._make_application(db_session, org.id)

        with tenant_ctx(org.id):
            obj = im_service.create_object({"name": f"Product {_suffix()}"})
            im_service.set_object_application(obj.id, application.id, {})
            detail = im_service.get_object_detail(obj.id)

        assert detail["applications"][0]["system_role"] is None
        assert detail["applications"][0]["system_role_label"] is None
        assert detail["system_of_record"] is None

    def test_a_bad_role_is_refused(self, db_session, make_org, tenant_ctx):
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org = make_org("approlebad")
        application = self._make_application(db_session, org.id)

        with tenant_ctx(org.id):
            obj = im_service.create_object({"name": f"Contract {_suffix()}"})
            with pytest.raises(ValueError):
                im_service.set_object_application(
                    obj.id, application.id, {"system_role": "golden_source"}
                )


# --------------------------------------------------------------- tenancy


class TestTenantIsolation:
    def test_one_organisation_cannot_see_anothers_information_model(
        self, db_session, make_org, tenant_ctx
    ):
        from app.modules.information_model.services import (
            information_model_service as im_service,
        )

        org_a, org_b = make_org("ima"), make_org("imb")
        domain_a = _make_domain(db_session, org_a.id)
        object_a = _make_object(db_session, org_a.id, domain_id=domain_a.id)

        # `.get()` and the identity map are per-session; clear it so the query
        # below actually reaches the database and the tenant filter applies.
        db_session.expunge_all()

        with tenant_ctx(org_b.id):
            info_map = im_service.build_information_map()
            visible_domains = {d["id"] for d in info_map["domains"]}
            visible_objects = {o["id"] for o in info_map["unfiled"]}
            for domain in info_map["domains"]:
                visible_objects |= {o["id"] for o in domain["objects"]}

        assert domain_a.id not in visible_domains, "TENANT LEAK: org B saw org A's data domain"
        assert object_a.id not in visible_objects, "TENANT LEAK: org B saw org A's business object"

    def test_two_organisations_can_use_the_same_object_code(
        self, db_session, make_org, tenant_ctx
    ):
        """The point of UNIQUE (organization_id, code): both tenants call it ORD."""
        org_a, org_b = make_org("codea"), make_org("codeb")
        _make_object(db_session, org_a.id, code="ORD")
        _make_object(db_session, org_b.id, code="ORD")
        db_session.flush()  # raises IntegrityError if the constraint is global


# --------------------------------------------------------------- blueprint


class TestBlueprint:
    def test_blueprint_registered(self, app):
        assert "information_model" in app.blueprints

    def test_page_endpoints_resolve(self, app):
        from flask import url_for

        with app.test_request_context():
            assert url_for("information_model.index") == "/information-model/"
            assert (
                url_for("information_model.object_detail", object_id=7)
                == "/information-model/objects/7"
            )
            assert (
                url_for("information_model.crud_matrix") == "/information-model/crud-matrix"
            )

    def test_crud_api_carries_both_write_verbs(self, app):
        """POST/PUT and DELETE live on separate view functions sharing one path,
        so methods must be aggregated across every rule for that path."""
        methods = set()
        found = False
        for rule in app.url_map.iter_rules():
            if (
                rule.endpoint.startswith("information_model.")
                and rule.rule == "/information-model/api/crud"
            ):
                found = True
                methods |= set(rule.methods or [])
        assert found, "/information-model/api/crud is not registered"
        assert {"POST", "PUT", "DELETE"} <= methods

    def test_writes_are_not_reachable_without_a_session(self, app):
        """Every write is behind ``@login_required`` + ``@require_roles``.

        Driven as real requests, so it tests the decorator chain that is
        actually installed rather than re-asserting the source. An anonymous
        caller must be turned away (401 from ``require_roles``, or a 302 to the
        login page from ``login_required``) — never carried through to the
        handler.

        This establishes the guards are live. It does **not** establish that a
        logged-in user lacking ``business_architect`` is refused; that needs a
        seeded user and is covered by the CI authorisation matrix in
        tests/smoke/.
        """
        app.config["WTF_CSRF_ENABLED"] = False
        client = app.test_client()

        writes = [
            ("/information-model/objects", {}),
            ("/information-model/domains", {}),
        ]
        for path, payload in writes:
            resp = client.post(path, data=payload)
            assert resp.status_code in (302, 401, 403), (
                f"anonymous POST {path} returned {resp.status_code}; the write is unguarded"
            )

        json_writes = [
            "/information-model/api/crud",
            "/information-model/api/relationships",
            "/information-model/api/applications",
        ]
        for path in json_writes:
            resp = client.post(path, json={})
            assert resp.status_code in (302, 401, 403), (
                f"anonymous POST {path} returned {resp.status_code}; the write is unguarded"
            )

    def test_reads_require_a_session(self, app):
        client = app.test_client()
        for path in ("/information-model/", "/information-model/crud-matrix"):
            resp = client.get(path)
            assert resp.status_code in (302, 401), (
                f"anonymous GET {path} returned {resp.status_code}; the page is unguarded"
            )
