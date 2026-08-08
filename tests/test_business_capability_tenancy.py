"""
Raw-SQL tenant scoping for the business-capability routes.

business_capability is a TenantMixin table, but the ORM's do_orm_execute listener
only rewrites ORM statements — a raw `text()` query goes straight to the database
unfiltered. Every query in business_capability_management_routes.py was written
with an empty placeholder and a comment asserting the opposite:

    _org_filter3 = ""
    _org_params3 = {}
    capabilities = db.session.execute(  # tenant-filtered
        text(f"... FROM business_capability {_org_filter3} ORDER BY name"),

so the code read as scoped while returning every organisation's capabilities.

The empty placeholders date from the initial open-source release, not from the
repair work — but these handlers previously raised NameError on the unbound result
variable and returned 500, so the leak was unreachable. Fixing the NameError is
what made it reachable, which is the uncomfortable part worth recording: repairing
a broken endpoint can expose a latent authorisation bug that the breakage was
hiding.

These tests assert the scoping at the SQL layer rather than through the HTTP
routes. The handlers wrap everything in `except Exception: flash(); redirect()`,
so a leak and a crash both render as a redirect and an endpoint test cannot tell
a scoped query from a swallowed one.
"""

import uuid

import pytest


@pytest.fixture(scope="module")
def app():
    from app import create_app

    application = create_app("testing")
    application.config["TESTING"] = True
    return application


@pytest.fixture
def two_orgs(app):
    """Two organisations, each owning one capability."""
    from app import db

    created = {}
    with app.test_request_context("/"):
        suffix = uuid.uuid4().hex[:8]
        ids = db.session.execute(
            db.text("SELECT id FROM organizations ORDER BY id LIMIT 2")
        ).scalars().all()
        if len(ids) < 2:
            pytest.skip("needs at least two organisations in the test database")
        org_a, org_b = ids[0], ids[1]
        cap_a = db.session.execute(
            db.text("INSERT INTO business_capability (name, level, organization_id) "
                    "VALUES (:n, 1, :o) RETURNING id"),
            {"n": f"OrgA Capability {suffix}", "o": org_a},
        ).scalar()
        cap_b = db.session.execute(
            db.text("INSERT INTO business_capability (name, level, organization_id) "
                    "VALUES (:n, 1, :o) RETURNING id"),
            {"n": f"OrgB Capability {suffix}", "o": org_b},
        ).scalar()
        db.session.commit()
        created = {"org_a": org_a, "org_b": org_b, "cap_a": cap_a, "cap_b": cap_b}

    yield created

    with app.test_request_context("/"):
        db.session.execute(
            db.text("DELETE FROM business_capability WHERE id IN (:a, :b)"),
            {"a": created["cap_a"], "b": created["cap_b"]},
        )
        db.session.commit()


def _run_scoped_list(app, org_id):
    """Exercise the helper exactly as the handlers do."""
    from flask import g

    from app import db
    from app.main.business_capability_management_routes import _org_scope

    with app.test_request_context("/"):
        g.current_org_id = org_id
        clause, params = _org_scope()
        rows = db.session.execute(
            db.text(f"SELECT id FROM business_capability {clause} ORDER BY name"), params
        ).scalars().all()
    return set(rows)


class TestListingIsScoped:
    def test_org_a_does_not_see_org_b(self, app, two_orgs):
        visible = _run_scoped_list(app, two_orgs["org_a"])
        assert two_orgs["cap_a"] in visible, "the owner must still see their own row"
        assert two_orgs["cap_b"] not in visible, (
            "SECURITY: another organisation's capability is visible. The raw-SQL "
            "queries in business_capability_management_routes.py are not scoped."
        )

    def test_org_b_does_not_see_org_a(self, app, two_orgs):
        visible = _run_scoped_list(app, two_orgs["org_b"])
        assert two_orgs["cap_b"] in visible
        assert two_orgs["cap_a"] not in visible

    def test_the_clause_is_actually_non_empty(self, app, two_orgs):
        """Guard against a regression to `_org_filter = ""`."""
        from flask import g

        from app.main.business_capability_management_routes import _org_scope

        with app.test_request_context("/"):
            g.current_org_id = two_orgs["org_a"]
            clause, params = _org_scope()
        assert "organization_id" in clause
        assert params.get("org") == two_orgs["org_a"]


class TestDetailIsScoped:
    def test_and_prefix_composes_with_an_existing_where(self, app, two_orgs):
        """The detail query already has WHERE id = :capability_id."""
        from flask import g

        from app import db
        from app.main.business_capability_management_routes import _org_scope

        with app.test_request_context("/"):
            g.current_org_id = two_orgs["org_a"]
            clause, params = _org_scope(prefix="AND")
            assert clause.startswith("AND"), "must not emit a second WHERE"
            # Org A asking for Org B's capability by id must get nothing.
            row = db.session.execute(
                db.text(f"SELECT id FROM business_capability "
                        f"WHERE id = :capability_id {clause}"),
                {"capability_id": two_orgs["cap_b"], **params},
            ).scalar()
        assert row is None, "SECURITY: direct id lookup crosses tenants"


class TestSystemContextMatchesTheOrm:
    def test_no_tenant_context_is_unfiltered_by_design(self, app):
        """CLI and system tasks have no g.current_org_id.

        The ORM listener returns early in that case rather than filtering, so raw
        SQL must behave the same. Inventing a stricter rule here would break
        seeders and commands while giving no security benefit — anything running
        without a request context already has full database access.
        """
        from app.main.business_capability_management_routes import _org_scope

        with app.app_context():
            clause, params = _org_scope()
        assert clause == "" and params == {}
