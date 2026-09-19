"""Founder-reported bug: "ArchiMate Composer" opened a blank canvas with a
template picker instead of the enterprise-wide Layered viewpoint (444
elements / 159 relationships across all layers).

Two parts fixed, verified here:

1. Nav plumbing (app/config/navigation_registry_v2.py,
   app/config/navigation_sections_v2.py) -- ``NavigationItemV2`` gained a
   ``query_params`` field threaded into ``url_for(endpoint, **query_params)``
   so the "ArchiMate Composer" link resolves to
   ``...composer?viewpoint=layered`` instead of the bare composer URL.

2. Backend scope (app/services/archimate_viewpoint_service.py) --
   ``get_viewpoint_data`` used to require a ``solution_id`` for every
   viewpoint, returning ``scope_required: True`` otherwise. ``'basic'`` and
   ``'layered'`` are now flagged ``enterprise_scope: True`` and, with no
   ``solution_id``, query ``ArchiMateElement.query`` directly (tenant-scoped
   by ``TenantMixin``'s ``do_orm_execute`` listener) instead of returning
   scope_required.

The cross-tenant test is the highest-stakes part of this bucket: the new
enterprise-wide path bypasses the solution-junction lookup entirely, so it
must be proven -- not assumed -- that it still only ever returns the calling
tenant's own rows.
"""


def test_composer_sidebar_link_carries_viewpoint_query_param(app, db_session, make_org, login_as):
    """The REAL, live sidebar (``app/utils/role_access.py::get_sidebar_zones``,
    rendered by ``app/templates/components/admin_sidebar.html``) is what a
    user actually clicks -- not the NavigationRegistryV2/navigation_sections_v2
    module, which turned out to be dead code: nothing in app/_bootstrap or any
    template imports it (``grep -rln 'get_navigation_sections\\|NavigationRegistryV2'
    app/templates/`` returns nothing), so the "changes already made" to that
    module in this bucket's brief never reached the rendered page. This test
    hits the real route and asserts the actual anchor href.
    """
    import uuid

    from app.models.user import User

    org = make_org("composer-sidebar")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"composer-sidebar-{suffix}@example.com",
        first_name="Composer",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    login_as(client, user)

    resp = client.get("/dashboard/overview")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert 'href="/archimate/composer?viewpoint=layered"' in html, (
        "the rendered sidebar's ArchiMate Composer link must carry "
        "?viewpoint=layered -- otherwise clicking it still lands on the "
        "blank canvas the founder reported. Sidebar HTML did not contain "
        "the expected href."
    )


def test_composer_nav_link_resolves_to_layered_viewpoint(app):
    """The sidebar "ArchiMate Composer" item must resolve to a URL carrying
    ``viewpoint=layered``, not the bare composer URL a blank canvas is
    served from.

    Exercises the real NavigationRegistryV2 resolution path (_resolve_url ->
    _safe_url_for -> url_for(endpoint, **query_params)), not just the
    presence of the right key in the section config dict.
    """
    from app.config.navigation_registry_v2 import NavigationRegistryV2
    from app.config.navigation_sections_v2 import ARCHITECTURE_TOOLS_SECTION

    registry = NavigationRegistryV2()
    registry.register_section(ARCHITECTURE_TOOLS_SECTION)

    composer_item = next(
        item for item in ARCHITECTURE_TOOLS_SECTION.items
        if item.label == "ArchiMate Composer"
    )
    assert composer_item.query_params == {"viewpoint": "layered"}, (
        "sanity check: the nav item itself must declare the query param "
        f"before resolution is even attempted, got {composer_item.query_params!r}"
    )

    with app.test_request_context("/"):
        resolved_url = registry._resolve_url(composer_item)

    assert "viewpoint=layered" in resolved_url, (
        f"composer nav link resolved to {resolved_url!r}, missing "
        "viewpoint=layered -- clicking it would land on the blank canvas "
        "the founder reported, not the layered viewpoint"
    )
    assert resolved_url.startswith("/archimate/composer"), resolved_url


# NOTE: NavigationRegistryV2.get_navigation_sections() -- the section-level
# entrypoint -- is not exercised here. It hits a third, separate pre-existing
# bug in this dead-code module: _is_visible() reads `config.disabled` but
# NavigationSectionV2 (unlike NavigationItemV2) declares no `disabled` field
# at all, so any get_navigation_sections() call raises AttributeError. Left
# undocumented as a known-issue rather than fixed here: this module is not
# imported by any template or app/_bootstrap file (confirmed by grep -rln
# 'get_navigation_sections\|NavigationRegistryV2' app/templates/ returning
# nothing), so it is not the code path the rendered sidebar actually uses --
# see test_composer_sidebar_link_carries_viewpoint_query_param above for the
# real, live mechanism. Fixing every bug in unexercised code is scope creep
# this bucket's brief did not ask for; the two bugs fixed above (regex= ->
# pattern=, and the disabled-item endpoint validator field-ordering bug) were
# fixed only because they blocked even importing the file the brief's diff
# touched.


def test_layered_viewpoint_returns_elements_without_solution_id(app, db_session, make_org, tenant_ctx):
    """'layered' declares enterprise_scope=True, so calling it with no
    solution_id (exactly what the composer nav link now does) must return
    real elements for the calling tenant, not scope_required: True.
    """
    from app.models.archimate_core import ArchiMateElement
    from app.services.archimate_viewpoint_service import get_viewpoint_data

    org = make_org("layered-vp")
    elements = [
        ArchiMateElement(name=f"Element {i}", type="ApplicationComponent",
                          layer="application", organization_id=org.id)
        for i in range(3)
    ]
    db_session.add_all(elements)
    db_session.flush()

    with tenant_ctx(org.id):
        result = get_viewpoint_data("layered", solution_id=None)

    assert result.get("scope_required") is not True, (
        f"'layered' with no solution_id still returned scope_required, "
        f"the composer would render 'Select a solution' again: {result}"
    )
    returned_ids = {e["id"] for e in result["elements"]}
    assert returned_ids == {e.id for e in elements}, (
        f"expected exactly this tenant's {len(elements)} elements, got {result['elements']}"
    )
    assert result["total"] == len(elements)


def test_layered_viewpoint_backend_failure_returns_explicit_error_not_fabricated_empty(
    app, db_session, make_org, tenant_ctx, monkeypatch
):
    """D4: a bare `except Exception: serialised = []` returned a 200 with
    elements: [] on ANY failure -- indistinguishable from a genuinely empty
    model, the fabrication class CLAUDE.md explicitly calls out. Force the
    enterprise-wide query to raise and assert the response carries an
    explicit error flag rather than silently looking like zero real data.
    """
    from app.models.archimate_core import ArchiMateElement
    from app.services.archimate_viewpoint_service import get_viewpoint_data

    org = make_org("layered-vp-failure")
    db_session.add(
        ArchiMateElement(name="Won't be reached", type="ApplicationComponent",
                          layer="application", organization_id=org.id)
    )
    db_session.commit()

    class _BoomQuery:
        def filter(self, *a, **k):
            return self

        def limit(self, *a, **k):
            raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(ArchiMateElement, "query", _BoomQuery())

    with tenant_ctx(org.id):
        result = get_viewpoint_data("layered", solution_id=None)

    assert result.get("error") is True, (
        f"a backend failure must set an explicit error flag, not silently "
        f"look like a real empty result: {result}"
    )
    assert result["elements"] == []
    assert result["relationships"] == [], (
        "relationships_out must be reset on failure too -- Invariant 4 "
        "forbids dangling relationships alongside an empty elements list"
    )


def test_basic_viewpoint_also_enterprise_scoped(app, db_session, make_org, tenant_ctx):
    """'basic' was flagged enterprise_scope alongside 'layered' -- confirm
    it also no longer requires solution_id, matching the brief's changes-
    already-made description of STANDARD_VIEWPOINTS.
    """
    from app.models.archimate_core import ArchiMateElement
    from app.services.archimate_viewpoint_service import get_viewpoint_data

    org = make_org("basic-vp")
    element = ArchiMateElement(name="Solo element", type="ApplicationComponent",
                                layer="application", organization_id=org.id)
    db_session.add(element)
    db_session.flush()

    with tenant_ctx(org.id):
        result = get_viewpoint_data("basic", solution_id=None)

    assert result.get("scope_required") is not True, result
    assert {e["id"] for e in result["elements"]} == {element.id}


def test_layered_viewpoint_cross_tenant_isolation(app, db_session, make_org, tenant_ctx):
    """The new enterprise-wide path bypasses the solution-junction lookup
    entirely and queries ArchiMateElement.query directly. Prove org A's call
    to the layered viewpoint never returns org B's elements -- the highest-
    stakes assertion in this bucket, per the brief.
    """
    from app.models.archimate_core import ArchiMateElement
    from app.services.archimate_viewpoint_service import get_viewpoint_data

    org_a = make_org("layered-a")
    org_b = make_org("layered-b")

    # Tenant B: a noisy neighbour with several elements that must never
    # leak into tenant A's enterprise-wide read.
    b_elements = [
        ArchiMateElement(name=f"B element {i}", type="ApplicationComponent",
                          layer="application", organization_id=org_b.id)
        for i in range(5)
    ]
    db_session.add_all(b_elements)

    # Tenant A: exactly one element of its own.
    a_element = ArchiMateElement(name="A element", type="ApplicationComponent",
                                  layer="application", organization_id=org_a.id)
    db_session.add(a_element)
    db_session.flush()

    with tenant_ctx(org_a.id):
        result = get_viewpoint_data("layered", solution_id=None)

    returned_ids = {e["id"] for e in result["elements"]}
    b_ids = {e.id for e in b_elements}

    assert returned_ids == {a_element.id}, (
        f"tenant A's layered viewpoint returned {returned_ids}, expected "
        f"only {{{a_element.id}}}"
    )
    assert not (returned_ids & b_ids), (
        "CROSS-TENANT LEAK: org A's enterprise-wide layered viewpoint "
        f"returned org B's element ids {returned_ids & b_ids}"
    )

    # Symmetric check: tenant B must see only its own 5 elements, not A's.
    with tenant_ctx(org_b.id):
        result_b = get_viewpoint_data("layered", solution_id=None)
    returned_ids_b = {e["id"] for e in result_b["elements"]}
    assert returned_ids_b == b_ids, returned_ids_b
    assert a_element.id not in returned_ids_b


def test_solution_scoped_viewpoint_still_requires_solution_id(app, db_session, make_org, tenant_ctx):
    """Regression guard: 'stakeholder' has no enterprise_scope flag (verified
    by reading STANDARD_VIEWPOINTS -- only 'basic' and 'layered' carry it),
    so it must still return scope_required: True with no solution_id. Proves
    the opt-in flag did not leak enterprise-wide behaviour into every other
    viewpoint.
    """
    from app.services.archimate_viewpoint_service import STANDARD_VIEWPOINTS, get_viewpoint_data

    assert not STANDARD_VIEWPOINTS["stakeholder"].get("enterprise_scope"), (
        "'stakeholder' must not carry enterprise_scope -- if it does, this "
        "test needs a different solution-scoped viewpoint picked instead"
    )

    # D6: assert the COMPLETE set of enterprise_scope viewpoints is exactly
    # {'basic', 'layered'} -- not just that 'stakeholder' individually lacks
    # the flag -- so a future viewpoint accidentally gaining it is caught.
    enterprise_scoped = {
        key for key, vp in STANDARD_VIEWPOINTS.items() if vp.get("enterprise_scope")
    }
    assert enterprise_scoped == {"basic", "layered"}, (
        f"expected exactly {{'basic', 'layered'}} to carry enterprise_scope, "
        f"got {enterprise_scoped}"
    )

    org = make_org("stakeholder-vp")
    with tenant_ctx(org.id):
        result = get_viewpoint_data("stakeholder", solution_id=None)

    assert result.get("scope_required") is True, (
        f"'stakeholder' (solution-scoped) must return scope_required: True "
        f"with no solution_id -- the enterprise_scope opt-in must not have "
        f"leaked into other viewpoints, got {result}"
    )
    assert result["elements"] == []


def test_layered_viewpoint_with_no_org_context_returns_scope_required(app, db_session, make_org):
    """D5: the enterprise-wide path relies on TenantMixin's do_orm_execute
    listener to scope ArchiMateElement.query -- but that listener is a
    documented NO-OP (not a deny) when g.current_org_id is unset
    (app/middleware/tenant_isolation.py). Before the fix flipped
    'no solution_id' from scope_required=True to running an unscoped query,
    the function was safe-by-default; after, it would return every tenant's
    rows if this path is ever reached with no org resolved. Assert the
    enterprise-wide branch fails closed (scope_required, zero rows) rather
    than falling through to an unscoped query, when no current org context
    is set at all.
    """
    from app.models.archimate_core import ArchiMateElement
    from app.services.archimate_viewpoint_service import get_viewpoint_data

    org_a = make_org("d5-no-context-a")
    db_session.add(
        ArchiMateElement(
            name="D5 leak probe",
            type="ApplicationComponent",
            layer="application",
            organization_id=org_a.id,
        )
    )
    db_session.commit()

    # A request context with g.current_org_id deliberately left unset --
    # mirrors any caller outside the normal @login_required request flow
    # (CLI, scheduler, a future non-authenticated caller).
    with app.test_request_context("/"):
        result = get_viewpoint_data("layered", solution_id=None)

    assert result.get("scope_required") is True, (
        f"with no current org context, the enterprise-wide 'layered' path "
        f"must fail closed (scope_required: True) rather than run an "
        f"unscoped query that would return every tenant's rows, got {result}"
    )
    assert result["elements"] == []
