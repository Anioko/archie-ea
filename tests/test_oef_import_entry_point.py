"""DOGFOOD-005: the OEF importer must be reachable from the catalog.

Before this, ``POST /solutions/import/archimate/{preview,execute}`` existed and the panel partial
existed, but no page included the partial and nothing in the catalog linked to it. A user with a
``.archimate`` file had nowhere to put it.
"""
import os

import pytest

db_required = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set - page tests need PostgreSQL",
)


def test_import_page_route_is_registered(app):
    rules = {r.rule for r in app.url_map.iter_rules() if "GET" in (r.methods or ())}
    assert "/solutions/import/archimate" in rules


def test_import_page_and_catalog_templates_compile(app):
    """Jinja syntax errors surface at render time; catch them at load time instead."""
    for name in (
        "solutions/import_archimate.html",
        "solutions/partials/_import_preview.html",
        "architecture/elements.html",
    ):
        app.jinja_env.get_template(name)


def test_panel_reports_what_execute_will_refuse_and_relationship_counts(app):
    """The preview/execute contract from the round-trip fix is surfaced, not hidden."""
    source = app.jinja_env.loader.get_source(app.jinja_env, "solutions/partials/_import_preview.html")[0]
    for needle in (
        "preview.summary.invalid",
        "preview.relationship_summary",
        "importResult.failed",
        "importResult.relationships_created",
        "'invalid':",
    ):
        assert needle in source, needle


def test_catalog_links_to_the_import_page(app):
    source = app.jinja_env.loader.get_source(app.jinja_env, "architecture/elements.html")[0]
    assert source.count("/solutions/import/archimate") >= 2  # header action + empty state


@db_required
def test_import_page_renders_for_a_logged_in_user(app, client, db_session, login_as, make_org):
    from app.models import User

    org = make_org("oef-entry")
    user = User(email="oef-entry@example.com", is_active=True, organization_id=org.id)
    user.set_password("x")
    db_session.add(user)
    db_session.flush()

    login_as(client, user)
    resp = client.get("/solutions/import/archimate")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Import ArchiMate Model" in body
    assert "/solutions/import/archimate/preview" in body
