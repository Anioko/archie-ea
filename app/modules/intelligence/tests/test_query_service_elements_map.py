"""T-004a acceptance tests: the element identity map on the impact API and the
two derived-row fields the serialiser used to drop.

Maps to the T-004a brief's acceptance items (test ids in the build report):

    1  -> test_map_covers_every_row_and_chain_element_and_nothing_else,
          test_http_data_carries_elements_beside_rows_summary_reasons,
          test_map_is_empty_object_when_no_rows_and_on_early_return_branches
    2  -> test_every_map_entry_has_exactly_four_keys,
          test_forbidden_key_is_absent_from_every_map_entry[*],
          test_no_element_column_value_beyond_the_four_reaches_the_response
    3  -> test_map_is_one_batched_select_however_many_elements
    4  -> test_identity_resolution_runs_inside_the_latency_scope
    5  -> test_cross_tenant_element_is_absent_and_its_name_appears_nowhere_http,
          test_cross_tenant_element_is_absent_from_the_service_map,
          test_identity_lookup_is_tenant_correct_with_no_ambient_request_context,
          test_identity_lookup_holds_when_the_ambient_tenant_diverges
    6  -> test_deleted_and_nonexistent_elements_are_absent_not_500
    7  -> test_derived_row_carries_derived_id_and_engine_version_from_the_store,
          test_explicit_row_carries_null_for_the_derived_only_fields
    10 -> test_canonical_impact_endpoint_does_not_return_elements
    12 -> test_layer_is_plain_canonical_lower_case_or_null_and_type_may_be_null,
          test_a_null_named_element_is_absent_not_a_null_entry
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import time
import uuid

import pytest
from sqlalchemy import event

# Fixtures (app, db_session, make_org, tenant_ctx, client, login_as) come from
# app/modules/intelligence/tests/conftest.py's import of tests.conftest.

FOUR_KEYS = {"id", "name", "type", "layer"}

# The six names the brief requires be asserted absent individually, plus the
# real ArchiMateElement column names those concepts live under and a few more
# columns that would be a leak if the projection widened.
FORBIDDEN_KEYS = (
    "description",
    "scope",
    "tco",
    "criticality",
    "app_name",
    "estimated_financial_risk",
    "documentation",
    "properties",
    "tco_annual",
    "estimated_cost",
    "business_value_score",
    "organization_id",
    "deleted_at",
)


# --- fixtures / helpers ------------------------------------------------------


def _user(db_session, org_id):
    from app.models.user import User

    user = User(
        email=f"t004a-{uuid.uuid4().hex[:10]}@example.com",
        first_name="T004a",
        last_name="Tester",
        organization_id=org_id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _element(db_session, org_id, name, layer="application", type_="ApplicationComponent", **extra):
    from app.models import ArchiMateElement

    el = ArchiMateElement(name=name, type=type_, layer=layer, organization_id=org_id, **extra)
    db_session.add(el)
    db_session.flush()
    return el


def _relationship(db_session, org_id, source, target, type_="Serving"):
    from app.models import ArchiMateRelationship

    rel = ArchiMateRelationship(source_id=source.id, target_id=target.id, type=type_, organization_id=org_id)
    db_session.add(rel)
    db_session.flush()
    return rel


def _derived(
    db_session,
    org_id,
    source,
    target,
    *,
    chain_element_ids,
    rule_id="R-07",
    depth=2,
    confidence=1.0,
    engine_version="1.2.0",
    stale=False,
):
    from app.modules.intelligence.models.derived_relationship import DerivedRelationship

    row = DerivedRelationship(
        organization_id=org_id,
        source_element_id=source.id,
        target_element_id=target.id,
        derived_type="Serving",
        rule_id=rule_id,
        chain=list(range(1, depth + 1)),
        chain_element_ids=list(chain_element_ids),
        depth=depth,
        confidence=confidence,
        provenance="derivation",
        engine_version=engine_version,
        computed_at=_dt.datetime.utcnow(),
        stale=stale,
        stale_since=_dt.datetime.utcnow() if stale else None,
        stale_reason="element_deleted" if stale else None,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _impact(app, org_id, element_id, **kwargs):
    """``cross_layer_impact`` under a request context for ``org_id``."""
    from flask import g

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    with app.test_request_context("/"):
        g.current_org_id = org_id
        return IntelligenceQueryService.cross_layer_impact(element_id, **kwargs)


def _get(client, login_as, user, path):
    login_as(client, user)
    return client.get(path)


def _ids_named_by_rows(rows):
    ids = set()
    for row in rows:
        ids.add(row["element_id"])
        ids.update(row["relation"]["chain_elements"])
    return ids


class _ElementsStatementCounter:
    """Records every SELECT that reads ``archimate_elements``."""

    def __init__(self):
        self.statements = []

    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        if "FROM archimate_elements" in statement:
            self.statements.append(statement)

    @property
    def batched_lookups(self):
        """The identity map's select: an ``IN (...)`` over ``archimate_elements``.

        The service's root-existence check is ``WHERE id = :id`` (no IN), so it
        is not counted here; the total is asserted separately.
        """
        return [s for s in self.statements if " IN (" in s]


@pytest.fixture
def elements_counter(app):
    from app.extensions import db

    counter = _ElementsStatementCounter()
    event.listen(db.engine, "before_cursor_execute", counter)
    try:
        yield counter
    finally:
        event.remove(db.engine, "before_cursor_execute", counter)


# --- acceptance 1: presence and coverage ------------------------------------


def test_map_covers_every_row_and_chain_element_and_nothing_else(app, db_session, make_org):
    org = make_org("map-cover")
    a = _element(db_session, org.id, "Alpha", type_="ApplicationComponent", layer="application")
    b = _element(db_session, org.id, "Bravo", type_="BusinessProcess", layer="business")
    x = _element(db_session, org.id, "Xray", type_="Node", layer="technology")
    c = _element(db_session, org.id, "Charlie", type_="ApplicationService", layer="application")
    bystander = _element(db_session, org.id, "Bystander")  # in no row, no chain
    _relationship(db_session, org.id, a, b)
    # Derived a -> c walks THROUGH x, which is in no explicit row.
    _derived(db_session, org.id, a, c, chain_element_ids=[a.id, x.id, c.id])
    db_session.commit()

    with_derived = _impact(app, org.id, a.id, include_derived=True, max_depth=3, with_owner=False)
    ids = _ids_named_by_rows(with_derived["rows"])
    assert ids == {a.id, b.id, x.id, c.id}
    assert set(with_derived["elements"]) == {str(i) for i in ids}
    for key, entry in with_derived["elements"].items():
        assert isinstance(key, str)
        assert entry["id"] == int(key)
    assert with_derived["elements"][str(b.id)] == {
        "id": b.id,
        "name": "Bravo",
        "type": "BusinessProcess",
        "layer": "business",
    }
    assert str(bystander.id) not in with_derived["elements"]

    # Without derived rows, ids that only the derived chain names (x, c) drop
    # out of the map: it never carries an id that appears in neither place.
    explicit_only = _impact(app, org.id, a.id, include_derived=False, max_depth=3, with_owner=False)
    assert set(explicit_only["elements"]) == {str(a.id), str(b.id)}
    assert str(x.id) not in explicit_only["elements"]
    assert str(c.id) not in explicit_only["elements"]


def test_http_data_carries_elements_beside_rows_summary_reasons(app, db_session, make_org, client, login_as):
    org = make_org("map-http")
    user = _user(db_session, org.id)
    a = _element(db_session, org.id, "Alpha")
    b = _element(db_session, org.id, "Bravo")
    _relationship(db_session, org.id, a, b)
    db_session.commit()

    resp = _get(client, login_as, user, f"/api/v1/intelligence/impact/{a.id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    assert set(data.keys()) == {"rows", "summary", "reasons", "elements"}
    assert set(data["elements"]) == {str(a.id), str(b.id)}
    assert data["elements"][str(b.id)]["name"] == "Bravo"


def test_map_is_empty_object_when_no_rows_and_on_early_return_branches(app, db_session, make_org):
    from flask import g

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("map-empty")
    lonely = _element(db_session, org.id, "Lonely")
    db_session.commit()

    # An element with no relationships: rows [], but the key is still there.
    no_rows = _impact(app, org.id, lonely.id, include_derived=True, with_owner=False)
    assert no_rows["rows"] == []
    assert no_rows["elements"] == {}

    # element_not_found branch.
    missing = _impact(app, org.id, 2_000_000_000, with_owner=False)
    assert missing["reasons"] == ["element_not_found"]
    assert missing["elements"] == {}

    # no_tenant_context branch: no ambient tenant at all.
    with app.test_request_context("/"):
        g.current_org_id = None
        no_tenant = IntelligenceQueryService.cross_layer_impact(lonely.id, with_owner=False)
    assert no_tenant["reasons"] == ["no_tenant_context"]
    assert no_tenant["elements"] == {}


# --- acceptance 2: the four-key ceiling -------------------------------------


def _element_with_every_sensitive_column(db_session, org_id, name):
    return _element(
        db_session,
        org_id,
        name,
        description=f"SECRET-DESCRIPTION-{uuid.uuid4().hex}",
        documentation=f"SECRET-DOCUMENTATION-{uuid.uuid4().hex}",
        properties=f'{{"secret": "SECRET-PROPERTIES-{uuid.uuid4().hex}"}}',
        scope="cross-cutting",
        tco_annual=987654.25,
        estimated_cost=123456.5,
        business_value_score=71.5,
        reviewer_notes=f"SECRET-NOTES-{uuid.uuid4().hex}",
    )


def _ceiling_fixture(db_session, make_org):
    org = make_org("map-ceiling")
    a = _element_with_every_sensitive_column(db_session, org.id, "Alpha")
    b = _element_with_every_sensitive_column(db_session, org.id, "Bravo")
    c = _element_with_every_sensitive_column(db_session, org.id, "Charlie")
    _relationship(db_session, org.id, a, b)
    _derived(db_session, org.id, a, c, chain_element_ids=[a.id, b.id, c.id])
    db_session.commit()
    return org, a, b, c


def test_every_map_entry_has_exactly_four_keys(app, db_session, make_org):
    org, a, b, c = _ceiling_fixture(db_session, make_org)
    result = _impact(app, org.id, a.id, include_derived=True, with_owner=False)
    assert set(result["elements"]) == {str(a.id), str(b.id), str(c.id)}
    for entry in result["elements"].values():
        assert set(entry.keys()) == FOUR_KEYS


@pytest.mark.parametrize("forbidden", FORBIDDEN_KEYS)
def test_forbidden_key_is_absent_from_every_map_entry(app, db_session, make_org, client, login_as, forbidden):
    org, a, b, c = _ceiling_fixture(db_session, make_org)
    user = _user(db_session, org.id)
    db_session.commit()

    service_map = _impact(app, org.id, a.id, include_derived=True, with_owner=False)["elements"]
    assert service_map
    for entry in service_map.values():
        assert forbidden not in entry

    resp = _get(client, login_as, user, f"/api/v1/intelligence/impact/{a.id}?include_derived=true")
    assert resp.status_code == 200
    http_map = resp.get_json()["data"]["elements"]
    assert http_map
    for entry in http_map.values():
        assert forbidden not in entry


def test_no_element_column_value_beyond_the_four_reaches_the_response(app, db_session, make_org, client, login_as):
    """The values, not just the key names: none of the sensitive columns'
    content appears anywhere in the response body."""
    org, a, b, c = _ceiling_fixture(db_session, make_org)
    user = _user(db_session, org.id)
    db_session.commit()

    resp = _get(client, login_as, user, f"/api/v1/intelligence/impact/{a.id}?include_derived=true")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert '"elements"' in text
    for secret in ("SECRET-DESCRIPTION", "SECRET-DOCUMENTATION", "SECRET-PROPERTIES", "SECRET-NOTES", "987654", "123456.5"):
        assert secret not in text


def test_layer_is_plain_canonical_lower_case_or_null_and_type_may_be_null(app, db_session, make_org):
    org = make_org("map-layer")
    a = _element(db_session, org.id, "Alpha", layer="Business", type_="BusinessProcess")
    untyped = _element(db_session, org.id, "Untyped", layer=None, type_=None)
    _relationship(db_session, org.id, a, untyped)
    db_session.commit()

    result = _impact(app, org.id, a.id, with_owner=False)
    a_entry = result["elements"][str(a.id)]
    assert a_entry["layer"] == "business"
    assert type(a_entry["layer"]) is str  # not the case-insensitive str subclass
    untyped_entry = result["elements"][str(untyped.id)]
    assert untyped_entry == {"id": untyped.id, "name": "Untyped", "type": None, "layer": None}


def test_a_null_named_element_is_absent_not_a_null_entry(app, monkeypatch):
    """``name`` is NOT NULL on the model, so a null name should be
    unreachable through the database; if a row ever came back with one it is
    dropped rather than surfaced as ``{"name": null}`` (absence over a
    placeholder). The database cannot produce that row, so the result set is
    stubbed -- this pins the branch, it is not a reachable scenario.
    """
    from types import SimpleNamespace

    from app.modules.intelligence.services import query_service

    class _Result:
        def all(self):
            return [(1, None, "Node", "technology"), (2, "Real", "Node", "technology")]

    monkeypatch.setattr(
        query_service.db,
        "session",
        # ``remove`` because the app context's teardown calls it.
        SimpleNamespace(execute=lambda stmt: _Result(), remove=lambda *a, **k: None),
    )
    with app.app_context():
        got = query_service._resolve_elements_batch([1, 2], 7)

    assert set(got) == {"2"}
    assert got["2"] == {"id": 2, "name": "Real", "type": "Node", "layer": "technology"}


# --- acceptance 3: one query, not N -----------------------------------------


def _star(db_session, org, n):
    root = _element(db_session, org.id, "Root")
    leaves = [_element(db_session, org.id, f"Leaf-{i}") for i in range(n)]
    for leaf in leaves:
        _relationship(db_session, org.id, root, leaf)
    return root, leaves


def test_map_is_one_batched_select_however_many_elements(app, db_session, make_org, elements_counter):
    small_org = make_org("map-count-small")
    small_root, small_leaves = _star(db_session, small_org, 3)
    big_org = make_org("map-count-big")
    big_root, big_leaves = _star(db_session, big_org, 12)
    # Read every id BEFORE the commit expires the instances: touching an
    # expired attribute inside the counted window would itself issue a SELECT
    # on archimate_elements and inflate the count with the test's own reads.
    small_org_id, small_root_id = small_org.id, small_root.id
    big_org_id, big_root_id = big_org.id, big_root.id
    db_session.commit()

    elements_counter.statements.clear()
    small = _impact(app, small_org_id, small_root_id, max_depth=1, with_owner=False)
    small_lookups = len(elements_counter.batched_lookups)
    small_total = len(elements_counter.statements)

    elements_counter.statements.clear()
    big = _impact(app, big_org_id, big_root_id, max_depth=1, with_owner=False)
    big_lookups = len(elements_counter.batched_lookups)
    big_total = len(elements_counter.statements)

    assert len(small["elements"]) == 4  # root + 3 leaves
    assert len(big["elements"]) == 13  # root + 12 leaves: >= ten distinct elements
    assert len({row["element_id"] for row in big["rows"]}) == 12
    # One identity select, whether the result set names 4 elements or 13.
    assert small_lookups == 1, elements_counter.statements
    assert big_lookups == 1, elements_counter.statements
    # And the number of statements touching archimate_elements does not scale
    # with the number of elements (root-existence check + the one batch).
    assert small_total == big_total == 2, (small_total, big_total)


# --- acceptance 4: inside the latency scope ---------------------------------


def test_identity_resolution_runs_inside_the_latency_scope(app, db_session, make_org, monkeypatch):
    from app.modules.intelligence.services import query_service
    from app.services.prometheus_metrics import INTELLIGENCE_QUERY_DURATION, REGISTRY

    org = make_org("map-latency")
    a = _element(db_session, org.id, "Alpha")
    b = _element(db_session, org.id, "Bravo")
    _relationship(db_session, org.id, a, b)
    db_session.commit()

    labels = {"query": "cross_layer_impact", "depth": "3", "include_derived": "false"}
    INTELLIGENCE_QUERY_DURATION.labels(**labels)  # materialise the series
    count_before = REGISTRY.get_sample_value("archie_intelligence_query_seconds_count", labels) or 0.0
    sum_before = REGISTRY.get_sample_value("archie_intelligence_query_seconds_sum", labels) or 0.0

    state = {"inside": False, "seen_inside": None, "scopes": 0}
    real_scope = query_service.record_query_latency
    real_resolve = query_service._resolve_elements_batch

    @contextlib.contextmanager
    def spy_scope(name):
        with real_scope(name) as scope:
            state["scopes"] += 1
            state["inside"] = True
            try:
                yield scope
            finally:
                state["inside"] = False

    def slow_resolve(element_ids, org_id):
        state["seen_inside"] = state["inside"]
        time.sleep(0.08)  # a known cost the reported latency must include
        return real_resolve(element_ids, org_id)

    monkeypatch.setattr(query_service, "record_query_latency", spy_scope)
    monkeypatch.setattr(query_service, "_resolve_elements_batch", slow_resolve)

    result = _impact(app, org.id, a.id, include_derived=False, max_depth=3, with_owner=False)

    assert state["scopes"] == 1
    assert state["seen_inside"] is True  # called while the scope was open
    assert set(result["elements"]) == {str(a.id), str(b.id)}
    # summary.latency_ms covers the identity resolution ...
    assert result["summary"]["latency_ms"] >= 70
    # ... and the histogram observed it once, with the unchanged labels.
    count_after = REGISTRY.get_sample_value("archie_intelligence_query_seconds_count", labels)
    sum_after = REGISTRY.get_sample_value("archie_intelligence_query_seconds_sum", labels)
    assert count_after - count_before == 1
    assert sum_after - sum_before >= 0.07


# --- acceptance 5: cross-tenant absence -------------------------------------


FOREIGN_NAME = "ORGB-SECRET-ELEMENT-NAME"
FOREIGN_DESCRIPTION = "ORGB-SECRET-DESCRIPTION"


def _cross_tenant_fixture(db_session, make_org):
    """Org A's own rows REFERENCE an element that belongs to org B: an
    explicit relationship whose target is org B's element, and a derived fact
    whose chain runs through it. Nothing in org A's data is malformed except
    that dangling cross-tenant pointer -- the shape the fence exists for.
    """
    org_a = make_org("map-xt-a")
    org_b = make_org("map-xt-b")
    user_a = _user(db_session, org_a.id)
    a = _element(db_session, org_a.id, "Alpha")
    b = _element(db_session, org_a.id, "Bravo")
    foreign = _element(db_session, org_b.id, FOREIGN_NAME, description=FOREIGN_DESCRIPTION)
    _relationship(db_session, org_a.id, a, b)
    _relationship(db_session, org_a.id, a, foreign)
    _derived(db_session, org_a.id, a, foreign, chain_element_ids=[a.id, b.id, foreign.id], confidence=0.82)
    db_session.commit()
    return org_a, org_b, user_a, a, b, foreign


def test_cross_tenant_element_is_absent_and_its_name_appears_nowhere_http(
    app, db_session, make_org, client, login_as
):
    org_a, org_b, user_a, a, b, foreign = _cross_tenant_fixture(db_session, make_org)

    resp = _get(client, login_as, user_a, f"/api/v1/intelligence/impact/{a.id}?include_derived=true")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    data = resp.get_json()["data"]

    # The fixture really does put org B's id in org A's rows -- the assertion
    # below is not vacuous.
    assert foreign.id in _ids_named_by_rows(data["rows"])
    # Absent: no entry, no name, no placeholder.
    assert str(foreign.id) not in data["elements"]
    assert set(data["elements"]) == {str(a.id), str(b.id)}
    assert FOREIGN_NAME not in text
    assert FOREIGN_DESCRIPTION not in text
    # The derived row that runs through it has no sentence rather than a gap.
    derived = [r for r in data["rows"] if r["relation"]["kind"] == "derived"]
    assert derived and all(r["relation"]["plain_terms"] is None for r in derived)


def test_cross_tenant_element_is_absent_from_the_service_map(app, db_session, make_org):
    org_a, org_b, user_a, a, b, foreign = _cross_tenant_fixture(db_session, make_org)
    result = _impact(app, org_a.id, a.id, include_derived=True, with_owner=False)
    assert foreign.id in _ids_named_by_rows(result["rows"])
    assert str(foreign.id) not in result["elements"]
    assert FOREIGN_NAME not in str(result)
    assert FOREIGN_DESCRIPTION not in str(result)


def test_identity_lookup_is_tenant_correct_with_no_ambient_request_context(app, db_session, make_org):
    """The explicit ``organization_id`` predicate's own contract.

    With no ambient tenant (``g.current_org_id`` unset -- a job, a CLI command,
    a test looping tenants in one session) the ORM listener no-ops and the
    lookup is otherwise unfiltered. ``_resolve_elements_batch(ids, org_id)``
    must still name only ``org_id``'s elements.

    HONESTY: no shipped call path reaches this. ``cross_layer_impact`` reads
    ``org_id`` from the same ``g.current_org_id`` the listener uses, and
    returns before the lookup when it is ``None``. This is a direct call to
    the private function, pinning the guarantee for the caller shape
    ``derived_facts.list_derived_facts``'s docstring names; it is the only
    place the predicate is observable (see the build report's mutation proof).
    """
    from flask import g

    from app.modules.intelligence.services.query_service import _resolve_elements_batch

    org_a = make_org("map-noctx-a")
    org_b = make_org("map-noctx-b")
    mine = _element(db_session, org_a.id, "Mine")
    theirs = _element(db_session, org_b.id, FOREIGN_NAME)
    db_session.commit()

    with app.test_request_context("/"):
        g.current_org_id = None  # no ambient tenant: the listener is a no-op
        got = _resolve_elements_batch([mine.id, theirs.id], org_a.id)

    assert set(got) == {str(mine.id)}
    assert FOREIGN_NAME not in str(got)


def test_identity_lookup_holds_when_the_ambient_tenant_diverges(app, db_session, make_org):
    """Same contract, other divergence: the ambient tenant (what the listener
    filters by) is org B while the caller resolves on behalf of org A. Neither
    org's element may come back under the wrong tenant -- and org B's name in
    particular must not surface for a caller acting for org A.

    Same honesty as above: a direct call, not a scenario any shipped path
    produces (the SEC-09 owner test in ``test_query_service.py`` is the
    precedent for this shape).
    """
    from flask import g

    from app.modules.intelligence.services.query_service import _resolve_elements_batch

    org_a = make_org("map-diverge-a")
    org_b = make_org("map-diverge-b")
    mine = _element(db_session, org_a.id, "Mine")
    theirs = _element(db_session, org_b.id, FOREIGN_NAME)
    db_session.commit()

    with app.test_request_context("/"):
        g.current_org_id = org_b.id
        got = _resolve_elements_batch([mine.id, theirs.id], org_a.id)

    assert got == {}
    assert FOREIGN_NAME not in str(got)


# --- acceptance 6: deleted-element absence ----------------------------------


def test_deleted_and_nonexistent_elements_are_absent_not_500(app, db_session, make_org, client, login_as):
    org = make_org("map-deleted")
    user = _user(db_session, org.id)
    a = _element(db_session, org.id, "Alpha")
    gone = _element(db_session, org.id, "HardDeleted")
    soft = _element(db_session, org.id, "SoftDeleted")
    c = _element(db_session, org.id, "Charlie")
    gone_id = gone.id
    never_existed = 2_000_000_000
    db_session.delete(gone)
    soft.deleted_at = _dt.datetime.utcnow()
    db_session.flush()
    # Stored chains name the removed ids. Inserted AFTER the deletes so no
    # invalidation hook has marked the fact stale: this is the "id present in
    # a stored chain_elements array whose element no longer exists" case.
    _derived(
        db_session,
        org.id,
        a,
        c,
        depth=4,
        chain_element_ids=[a.id, gone_id, soft.id, never_existed, c.id],
    )
    db_session.commit()

    resp = _get(client, login_as, user, f"/api/v1/intelligence/impact/{a.id}?include_derived=true&max_depth=4")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    derived = [r for r in data["rows"] if r["relation"]["kind"] == "derived"]
    assert derived
    named = _ids_named_by_rows(data["rows"])
    assert {gone_id, soft.id, never_existed} <= named  # they ARE named by the stored chain
    for removed in (gone_id, soft.id, never_existed):
        assert str(removed) not in data["elements"]  # ... and absent from the map
    assert set(data["elements"]) == {str(a.id), str(c.id)}
    assert "HardDeleted" not in resp.get_data(as_text=True)
    assert "SoftDeleted" not in resp.get_data(as_text=True)
    assert all(r["relation"]["plain_terms"] is not None for r in derived)  # endpoints a and c resolve


# --- acceptance 7: the two restored fields ----------------------------------


def test_derived_row_carries_derived_id_and_engine_version_from_the_store(app, db_session, make_org):
    org = make_org("map-restored")
    a = _element(db_session, org.id, "Alpha")
    m = _element(db_session, org.id, "Mid")
    c = _element(db_session, org.id, "Charlie")
    fact = _derived(db_session, org.id, a, c, chain_element_ids=[a.id, m.id, c.id], engine_version="1.2.0")
    db_session.commit()

    result = _impact(app, org.id, a.id, include_derived=True, with_owner=False)
    derived = [r for r in result["rows"] if r["relation"]["kind"] == "derived"]
    assert len(derived) == 1
    relation = derived[0]["relation"]
    assert relation["derived_id"] == fact.id
    assert relation["engine_version"] == "1.2.0"
    # Both come from the store's own values, not from a literal.
    from app.modules.intelligence.services.derived_facts import list_derived_facts

    with app.test_request_context("/"):
        from flask import g

        g.current_org_id = org.id
        stored = list_derived_facts(org.id, include_stale=True)
    assert [f["id"] for f in stored] == [relation["derived_id"]]
    assert [f["engine_version"] for f in stored] == [relation["engine_version"]]


def test_explicit_row_carries_null_for_the_derived_only_fields(app, db_session, make_org):
    org = make_org("map-explicit-null")
    a = _element(db_session, org.id, "Alpha")
    b = _element(db_session, org.id, "Bravo")
    _relationship(db_session, org.id, a, b)
    db_session.commit()

    result = _impact(app, org.id, a.id, include_derived=True, with_owner=False)
    explicit = [r for r in result["rows"] if r["relation"]["kind"] == "explicit"]
    assert explicit
    for row in explicit:
        relation = row["relation"]
        for key in ("derived_id", "engine_version", "plain_terms"):
            assert key in relation  # present ...
            assert relation[key] is None  # ... and null, never a placeholder


# --- acceptance 10: canonical endpoint does not return the map --------------


def test_canonical_impact_endpoint_does_not_return_elements(app, db_session, make_org, client, login_as):
    org = make_org("map-canonical")
    user = _user(db_session, org.id)
    a = _element(db_session, org.id, "Alpha")
    b = _element(db_session, org.id, "Bravo")
    c = _element(db_session, org.id, "Charlie")
    _relationship(db_session, org.id, a, b)
    _derived(db_session, org.id, a, c, chain_element_ids=[a.id, b.id, c.id])
    db_session.commit()

    login_as(client, user)
    resp = client.post(
        "/api/v1/impact/analyze",
        json={"element_id": a.id, "scenario": "modification", "include_derived": True},
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "elements" not in data
    # SEC-02: the canonical projection is still the narrow one.
    for element in data["affected_elements"]:
        assert set(element.keys()) == {"id", "name", "type", "level"}
