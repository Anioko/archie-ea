"""T-003 / task 03 acceptance criteria 3, 4, 7, 8."""

from __future__ import annotations

import uuid



def _make_user(db_session, org, *, email=None):
    from app.models.user import Role, User

    admin_role = Role.query.filter_by(name="Administrator").first()
    if admin_role is None:
        Role.insert_roles()
        admin_role = Role.query.filter_by(name="Administrator").first()

    user = User(
        email=email or f"t003-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Test",
        last_name="User",
        organization_id=org.id,
        role=admin_role,
        is_org_admin=True,
        confirmed=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_element(db_session, org_id, name_hint, type_="ApplicationComponent"):
    from app.models import ArchiMateElement

    row = ArchiMateElement(
        name=f"E-{name_hint}", type=type_, layer="application", organization_id=org_id
    )
    db_session.add(row)
    db_session.flush()
    return row


def _make_relationship(db_session, org_id, source, target, type_):
    from app.models import ArchiMateRelationship

    row = ArchiMateRelationship(
        source_id=source.id, target_id=target.id, type=type_, organization_id=org_id
    )
    db_session.add(row)
    db_session.flush()
    return row


def _insert_derived_row(db_session, org_id, source, target, **overrides):
    import datetime as _dt

    from app.modules.intelligence.models.derived_relationship import DerivedRelationship

    params = dict(
        organization_id=org_id,
        source_element_id=source.id,
        target_element_id=target.id,
        derived_type="Association",
        rule_id="fallback:X:X",
        chain=[],
        chain_element_ids=[source.id, target.id],
        depth=1,
        confidence="1.00",
        provenance="derivation",
        engine_version="1.0.0",
        computed_at=_dt.datetime.utcnow(),
        stale=False,
        stale_since=None,
        stale_reason=None,
    )
    params.update(overrides)
    row = DerivedRelationship(**params)
    db_session.add(row)
    db_session.flush()
    return row


# --- Acceptance item 3 (brief 10): auth + CSRF on the recompute endpoint ----


def test_recompute_endpoint_requires_login(client):
    resp = client.post("/api/v1/intelligence/derivation/recompute", json={"scope": "tenant"})
    assert resp.status_code in (302, 401)


def test_recompute_endpoint_rejects_post_without_csrf_token(app, db_session, make_org, client):
    """CSRF is normally disabled under TESTING; assert it explicitly here by
    re-enabling WTF_CSRF_ENABLED for the duration of this one test."""
    org = make_org("api-csrf")
    user = _make_user(db_session, org)
    db_session.commit()

    from tests._session_test_helpers import mint_test_sid

    sid = mint_test_sid(user.id, organization_id=org.id)
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
        sess["_sid"] = sid

    app.config["WTF_CSRF_ENABLED"] = True
    try:
        resp = client.post(
            "/api/v1/intelligence/derivation/recompute",
            json={"scope": "tenant"},
        )
        assert resp.status_code == 400
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_recompute_endpoint_succeeds_and_returns_derivation_result(
    app, db_session, make_org, client, login_as
):
    org = make_org("api-recompute-ok")
    user = _make_user(db_session, org)
    a = _make_element(db_session, org.id, "a")
    b = _make_element(db_session, org.id, "b")
    c = _make_element(db_session, org.id, "c")
    _make_relationship(db_session, org.id, a, b, "Composition")
    _make_relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()

    login_as(client, user)
    resp = client.post(
        "/api/v1/intelligence/derivation/recompute",
        json={"scope": "tenant"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["success"] is True
    assert "derived_count" in body["data"]


def test_recompute_endpoint_rejects_non_tenant_scope(app, db_session, make_org, client, login_as):
    org = make_org("api-scope-reject")
    user = _make_user(db_session, org)
    db_session.commit()

    login_as(client, user)
    resp = client.post(
        "/api/v1/intelligence/derivation/recompute",
        json={"scope": "estate"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_recompute_endpoint_reports_lock_held_not_500(app, db_session, make_org, client, login_as):
    from app.jobs.tenant_safe_job import job_lock
    from app.modules.intelligence.services.recompute_job import per_tenant_lock_name

    org = make_org("api-recompute-locked")
    user = _make_user(db_session, org)
    db_session.commit()
    org_id = org.id

    login_as(client, user)

    with app.app_context():
        with job_lock(per_tenant_lock_name(org_id), required=True):
            resp = client.post(
                "/api/v1/intelligence/derivation/recompute",
                json={"scope": "tenant"},
            )

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "RECOMPUTE_LOCKED"


# --- Acceptance item 8: request session survives the harness call ----------


def test_on_demand_endpoint_leaves_request_session_and_org_context_intact(
    app, db_session, make_org, client, login_as
):
    org = make_org("api-session-survives")
    user = _make_user(db_session, org)
    db_session.commit()

    login_as(client, user)
    resp = client.post(
        "/api/v1/intelligence/derivation/recompute",
        json={"scope": "tenant"},
    )
    assert resp.status_code == 200

    # A second request on the same client, same session, must still resolve
    # to the same user/org -- proving login state and g.current_org_id were
    # not corrupted by the harness's db.session.remove() calls inside the
    # first request.
    resp2 = client.get("/api/v1/intelligence/derived/999999")
    assert resp2.status_code == 404  # tenant-scoped 404, not a 401/redirect


# --- Acceptance item 4 (brief 3, API-2): provenance expansion --------------


def test_provenance_expansion_resolves_chain_to_source_target(
    app, db_session, make_org, client, login_as
):
    org = make_org("api-provenance")
    user = _make_user(db_session, org)
    a = _make_element(db_session, org.id, "a")
    b = _make_element(db_session, org.id, "b")
    c = _make_element(db_session, org.id, "c")
    r1 = _make_relationship(db_session, org.id, a, b, "Composition")
    r2 = _make_relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()

    r1_id, r2_id = r1.id, r2.id  # captured before any request detaches these

    row = _insert_derived_row(
        db_session, org.id, a, c, chain=[r1_id, r2_id], depth=2, derived_type="Serving"
    )
    db_session.commit()
    row_id = row.id

    login_as(client, user)
    resp = client.get(f"/api/v1/intelligence/derived/{row_id}")
    assert resp.status_code == 200
    body = resp.get_json()["data"]
    assert body["id"] == row_id
    expanded = body["expanded_chain"]
    assert [e["id"] for e in expanded] == [r1_id, r2_id]
    for e in expanded:
        assert e["derived_from"] == row_id
        assert "source_id" in e and "target_id" in e


def test_provenance_expansion_cross_tenant_id_is_404_not_leak(
    app, db_session, make_org, client, login_as
):
    org_a = make_org("api-prov-a")
    org_b = make_org("api-prov-b")
    user_b = _make_user(db_session, org_b)

    a1 = _make_element(db_session, org_a.id, "a1")
    a2 = _make_element(db_session, org_a.id, "a2")
    db_session.commit()

    row_a = _insert_derived_row(db_session, org_a.id, a1, a2, chain=[], depth=1)
    db_session.commit()
    row_a_id = row_a.id

    login_as(client, user_b)
    resp = client.get(f"/api/v1/intelligence/derived/{row_a_id}")
    assert resp.status_code == 404


# --- Round-1 refuter finding D4: read path must not use tenant_scope() -----


def test_get_derived_fact_does_not_corrupt_request_globals(app, db_session, make_org):
    """``tenant_scope()`` is a background-job harness: its ``finally`` clause
    sets ``g.current_org = None`` and only restores ``g.current_org_id``,
    never ``g.current_org``. Using it inside a live request's read path
    clobbers whatever the normal request lifecycle had cached there. Proves
    the read path (used by GET /api/v1/intelligence/derived/<id>) leaves a
    pre-existing g.current_org untouched."""
    from flask import g

    from app.modules.intelligence.services.derived_facts import get_derived_fact

    org = make_org("d4-no-tenant-scope")
    a = _make_element(db_session, org.id, "a")
    b = _make_element(db_session, org.id, "b")
    db_session.commit()
    row = _insert_derived_row(db_session, org.id, a, b, chain=[], depth=1)
    db_session.commit()
    row_id, org_id = row.id, org.id

    with app.test_request_context():
        g.current_org_id = org_id
        sentinel = object()  # stands in for the real ORM object a request caches
        g.current_org = sentinel

        result = get_derived_fact(org_id, row_id)

        assert result is not None
        assert g.current_org_id == org_id
        assert g.current_org is sentinel, (
            "the read path must not clobber g.current_org -- tenant_scope() "
            "would silently set it to None as a side effect of being used "
            "outside its intended background-job lifecycle"
        )


# --- Round-1 refuter finding D6: an unresolved chain link must not vanish ---


def test_expanded_chain_marks_an_unresolved_link_instead_of_dropping_it(
    app, db_session, make_org, client, login_as
):
    """A chain id with no matching ArchiMateRelationship (e.g. deleted after
    the derived row was computed) must appear as an explicit unresolved
    marker, not silently vanish -- a shorter-but-complete-looking array reads
    as a complete derivation chain when it is not."""
    org = make_org("d6-unresolved-chain")
    user = _make_user(db_session, org)
    a = _make_element(db_session, org.id, "a")
    b = _make_element(db_session, org.id, "b")
    r1 = _make_relationship(db_session, org.id, a, b, "Composition")
    db_session.commit()
    r1_id = r1.id

    missing_rel_id = r1_id + 999_999  # never a real relationship id

    row = _insert_derived_row(
        db_session, org.id, a, b, chain=[r1_id, missing_rel_id], depth=2, derived_type="Serving"
    )
    db_session.commit()
    row_id = row.id

    login_as(client, user)
    resp = client.get(f"/api/v1/intelligence/derived/{row_id}")
    assert resp.status_code == 200
    expanded = resp.get_json()["data"]["expanded_chain"]

    assert len(expanded) == 2, "an unresolved link must not shorten the array"
    assert expanded[0]["id"] == r1_id
    assert "source_id" in expanded[0]

    assert expanded[1]["id"] == missing_rel_id
    assert expanded[1].get("unresolved") is True
    assert "source_id" not in expanded[1]


# --- Acceptance item 7 (brief 14): exactly two routes, NFR-8 ---------------


def test_module_registers_exactly_three_routes(app):
    """T-004 adds the US-1 impact route (API-1) to this existing blueprint --
    see docs/buckets/t004-us1-impact-endpoint/tasks/00-verification-notes.md
    defect D1. Still exactly one blueprint, now three routes on it.
    """
    rules = [
        rule for rule in app.url_map.iter_rules() if rule.endpoint.startswith("intelligence_api.")
    ]
    endpoints = {rule.endpoint for rule in rules}
    assert endpoints == {
        "intelligence_api.recompute_derivation",
        "intelligence_api.get_derived_fact_provenance",
        "intelligence_api.cross_layer_impact",
    }



# --- T-004a: the restored derived_id addresses the provenance endpoint --------


def test_impact_row_derived_id_addresses_the_provenance_endpoint(
    app, db_session, make_org, client, login_as
):
    """The reason ``relation.derived_id`` exists: a caller looking at a derived
    row on the impact API can open ``GET /derived/<derived_id>`` for exactly
    that fact, and both report the same ``engine_version``."""
    org = make_org("api-derived-id-roundtrip")
    user = _make_user(db_session, org)
    a = _make_element(db_session, org.id, "a")
    b = _make_element(db_session, org.id, "b")
    c = _make_element(db_session, org.id, "c")
    r1 = _make_relationship(db_session, org.id, a, b, "Composition")
    r2 = _make_relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()
    r1_id, r2_id = r1.id, r2.id

    row = _insert_derived_row(
        db_session,
        org.id,
        a,
        c,
        chain=[r1_id, r2_id],
        chain_element_ids=[a.id, b.id, c.id],
        depth=2,
        derived_type="Serving",
        engine_version="1.2.0",
    )
    db_session.commit()
    row_id = row.id

    login_as(client, user)
    impact = client.get(f"/api/v1/intelligence/impact/{a.id}?include_derived=true")
    assert impact.status_code == 200
    derived_rows = [
        r for r in impact.get_json()["data"]["rows"] if r["relation"]["kind"] == "derived"
    ]
    assert len(derived_rows) == 1
    relation = derived_rows[0]["relation"]
    assert relation["derived_id"] == row_id
    assert relation["engine_version"] == "1.2.0"

    login_as(client, user)
    provenance = client.get(f"/api/v1/intelligence/derived/{relation['derived_id']}")
    assert provenance.status_code == 200
    fact = provenance.get_json()["data"]
    assert fact["id"] == relation["derived_id"]
    assert fact["engine_version"] == relation["engine_version"]
