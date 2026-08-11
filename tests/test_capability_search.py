"""/capability-maturity/search — the page a business architect uses to find and
edit a capability, and the page the frameworks overview now sends them to.

It had never returned a result. Four independent defects, each fatal, each
hidden behind the previous one:

1. The SELECT list named ``capability_type``, a column that exists neither on
   ``BusinessCapability`` nor in the ``business_capability`` table. Every
   request raised ``UndefinedColumn``, was caught, and rendered the page's own
   error panel — "Error searching capabilities. Please try again."
2. The result count was produced by ``str.replace()`` against a differently
   whitespaced copy of the query string. Neither replacement matched, so
   ``.scalar()`` returned the first **id** in the result set, displayed as
   "Search Results (N capabilities)".
3. ``{{ getCategoryExplanation(cap.category) }}`` calls a JavaScript function
   defined in a ``<script>`` block at the bottom of the same template. Jinja
   cannot resolve it, so any result row carrying a category raised
   ``UndefinedError``.
4. ``{{ min(page * per_page, total_count) }}`` — ``min`` is a Python builtin,
   not a Jinja global, so the second page of results raised ``UndefinedError``.

And the three raw SQL statements ran against a ``TenantMixin`` table with no
``organization_id`` predicate, each carrying a ``# tenant-filtered`` comment.
``do_orm_execute`` cannot filter a textual statement: the search read every
organisation's capabilities, and defect 1 was the only thing hiding it.

Defects 3 and 4 are now also caught mechanically by the ``template-calls``
gate.
"""

from __future__ import annotations

import re
import uuid

import pytest


@pytest.fixture
def client(app):
    previous = app.config.get("LOGIN_DISABLED", False)
    app.config["LOGIN_DISABLED"] = True
    try:
        yield app.test_client()
    finally:
        app.config["LOGIN_DISABLED"] = previous


def _capability(db_session, name, **kw):
    from app.models.business_capabilities import BusinessCapability

    cap = BusinessCapability(name=name, **kw)
    db_session.add(cap)
    db_session.flush()
    return cap


def _rendered(app, client, url):
    """GET the page and return what the view handed the template."""
    from unittest.mock import patch

    from app.modules.capabilities.routes import maturity_routes as mod

    captured = {}

    def _fake_render(template_name, **context):
        captured["template"] = template_name
        captured.update(context)
        return ""

    with patch.object(mod, "render_template", _fake_render):
        resp = client.get(url)
    captured["status_code"] = resp.status_code
    return captured


def test_search_returns_capabilities_instead_of_an_error_panel(
    app, client, db_session, make_org, tenant_ctx
):
    org = make_org(f"search-{uuid.uuid4().hex[:6]}")
    with tenant_ctx(org.id):
        _capability(db_session, "Order Fulfilment", category="Operations", level=1)
        db_session.commit()

    ctx = _rendered(app, client, "/capability-maturity/search?q=Order Fulfilment")

    assert ctx["status_code"] == 200
    assert "load_error" not in ctx, (
        "the view fell into its exception branch — the SELECT named a column "
        "that does not exist, so the search never ran"
    )
    names = [c.name for c in ctx["capabilities"]]
    assert "Order Fulfilment" in names


def test_total_count_is_a_count_and_not_an_id(app, client, db_session, make_org, tenant_ctx):
    org = make_org(f"search-count-{uuid.uuid4().hex[:6]}")
    marker = f"Countable {uuid.uuid4().hex[:8]}"
    with tenant_ctx(org.id):
        for i in range(3):
            _capability(db_session, f"{marker} {i}", level=1)
        db_session.commit()

    ctx = _rendered(app, client, f"/capability-maturity/search?q={marker}")

    assert ctx["total_count"] == 3, (
        "the count was built by replacing a substring that did not occur in the "
        "query, so .scalar() returned the first id in the result set"
    )


def test_the_page_renders_with_a_categorised_result(app, client, db_session, make_org, tenant_ctx):
    """Really render it: this is the getCategoryExplanation regression."""
    org = make_org(f"search-render-{uuid.uuid4().hex[:6]}")
    marker = f"Categorised {uuid.uuid4().hex[:8]}"
    with tenant_ctx(org.id):
        _capability(db_session, marker, category="APO01", business_domain="IT", level=1)
        db_session.commit()

    resp = client.get(f"/capability-maturity/search?q={marker}")

    assert resp.status_code == 200
    assert b"Error searching capabilities" not in resp.data, (
        "a result row with a category made Jinja call a JavaScript function"
    )
    assert marker.encode() in resp.data


def test_the_domain_column_shows_the_domain(app, client, db_session, make_org, tenant_ctx):
    """The template read cap.domain; the column is business_domain.

    Every row therefore displayed "Unknown" whatever its domain was — a wrong
    value presented as a real one.
    """
    org = make_org(f"search-domain-{uuid.uuid4().hex[:6]}")
    marker = f"Domained {uuid.uuid4().hex[:8]}"
    with tenant_ctx(org.id):
        _capability(db_session, marker, business_domain="Supply Chain", level=1)
        db_session.commit()

    resp = client.get(f"/capability-maturity/search?q={marker}")

    assert resp.status_code == 200
    assert b"Supply Chain" in resp.data
    body = resp.data.decode("utf8", "replace")
    row = body[body.index(marker):][:2000]
    assert "Unknown" not in row


def test_pagination_renders_past_the_first_page(app, client, db_session, make_org, tenant_ctx):
    """The `min()` regression: it only fires once there are enough results."""
    org = make_org(f"search-page-{uuid.uuid4().hex[:6]}")
    marker = f"Paged {uuid.uuid4().hex[:8]}"
    with tenant_ctx(org.id):
        for i in range(25):  # per_page is 20
            _capability(db_session, f"{marker} {i:02d}", level=1)
        db_session.commit()

    resp = client.get(f"/capability-maturity/search?q={marker}&page=2")

    assert resp.status_code == 200
    assert b"Error searching capabilities" not in resp.data, (
        "min() is a Python builtin, not a Jinja global; the pagination summary "
        "raised UndefinedError as soon as a search had a second page"
    )
    assert re.search(rb"Showing\s+21\s+to\s+25\s+of\s+25\s+results", resp.data), (
        "the pagination summary did not render its real range"
    )


def test_search_does_not_read_another_organisations_capabilities(
    app, db_session, make_org, tenant_ctx
):
    """The raw SQL had no organization_id predicate and could not have had one.

    Logged in as a user of org B, org A's capability must not appear. The route
    goes through the ORM now, so do_orm_execute supplies the predicate.
    """
    from app.models.user import User

    org_a = make_org(f"search-iso-a-{uuid.uuid4().hex[:6]}")
    org_b = make_org(f"search-iso-b-{uuid.uuid4().hex[:6]}")
    secret = f"Secret Capability {uuid.uuid4().hex[:8]}"

    with tenant_ctx(org_a.id):
        _capability(db_session, secret, level=1)
        db_session.commit()

    with tenant_ctx(org_b.id):
        intruder = User(
            email=f"intruder-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Intruder",
            last_name="Tester",
            organization_id=org_b.id,
            confirmed=True,
            enterprise_role="business_architect",
        )
        db_session.add(intruder)
        db_session.commit()
        intruder_id = intruder.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(intruder_id)
        sess["_fresh"] = True

    # Flask-Login and the tenant middleware both cache on `g`, and pytest-flask
    # reuses one context across the test — a stale cache here would silently
    # run this request as org A and pass for the wrong reason.
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)

    # Assert on the result set, not on the page bytes: the search term is echoed
    # back into the query input, so `secret in resp.data` is true even when the
    # results are correctly empty.
    from unittest.mock import patch

    from app.modules.capabilities.routes import maturity_routes as mod

    captured = {}
    with patch.object(
        mod, "render_template", lambda t, **c: (captured.update(c), "")[1]
    ):
        resp = client.get(f"/capability-maturity/search?q={secret}")

    assert resp.status_code == 200
    names = [c.name for c in captured.get("capabilities", [])]
    assert secret not in names, (
        "org B's search returned org A's capability; the raw SQL this replaced "
        "selected FROM business_capability WHERE 1=1"
    )
    assert captured.get("total_count") == 0
