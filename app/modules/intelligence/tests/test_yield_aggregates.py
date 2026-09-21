"""The aggregate reads behind the yield answer: counts, staleness, freshness,
engine versions, and the tenant's explicit relationship count.

Each is a SQL aggregate for one tenant, takes the organisation explicitly, and
is correct with no request context. Two properties matter to the screen that
reads them: another tenant's rows are never counted, and after a fresh
recompute the aggregates and the recompute's own answer are the same numbers.

Fixtures (app, db_session, make_org) come from this directory's conftest.
"""

from __future__ import annotations

from app.modules.intelligence.services.derivation_runner import ENGINE_VERSION

import datetime
import inspect
import re
import uuid

import pytest


def _element(db_session, org_id, name):
    from app.models import ArchiMateElement

    row = ArchiMateElement(name=name, type="ApplicationComponent", layer="application", organization_id=org_id)
    db_session.add(row)
    db_session.flush()
    return row


def _relationship(db_session, org_id, source, target, type_="Serving"):
    from app.models import ArchiMateRelationship

    row = ArchiMateRelationship(source_id=source.id, target_id=target.id, type=type_, organization_id=org_id)
    db_session.add(row)
    db_session.flush()
    return row


def _derived(db_session, org_id, source, target, *, stale=False, engine_version=ENGINE_VERSION, computed_at=None):
    from app.modules.intelligence.models.derived_relationship import DerivedRelationship

    row = DerivedRelationship(
        organization_id=org_id,
        source_element_id=source.id,
        target_element_id=target.id,
        derived_type="Association",
        rule_id="fallback:Test:%s" % uuid.uuid4().hex[:6],
        chain=[999],
        chain_element_ids=[source.id, target.id],
        depth=1,
        confidence="1.00",
        provenance="derivation",
        engine_version=engine_version,
        computed_at=computed_at or datetime.datetime.utcnow(),
        stale=stale,
        stale_since=datetime.datetime.utcnow() if stale else None,
        stale_reason="derivation_stale" if stale else None,
    )
    db_session.add(row)
    db_session.flush()
    return row


# --- the derived-fact aggregates ---------------------------------------------


def test_the_total_is_every_stored_row_and_stale_is_part_of_it(app, db_session, make_org):
    from app.modules.intelligence.services.derived_facts import derived_fact_aggregates

    org = make_org("agg-total")
    a, b, c, d = (_element(db_session, org.id, n) for n in "abcd")
    _derived(db_session, org.id, a, b)
    _derived(db_session, org.id, b, c)
    _derived(db_session, org.id, c, d, stale=True)
    db_session.commit()
    org_id = org.id

    with app.app_context():
        agg = derived_fact_aggregates(org_id)

    assert agg["current_count"] == 2, "the rows that are not stale"
    assert agg["stale_count"] == 1
    assert agg["total_count"] == 3
    assert agg["total_count"] == agg["current_count"] + agg["stale_count"]
    assert "derived_count" not in agg, "one name per meaning: the payload's derived_count is the total"


def test_most_recent_computed_at_and_distinct_engine_versions_are_the_stores_own(app, db_session, make_org):
    from app.modules.intelligence.services.derived_facts import derived_fact_aggregates

    org = make_org("agg-fresh")
    a, b, c = (_element(db_session, org.id, n) for n in "abc")
    older = datetime.datetime(2026, 1, 2, 3, 4, 5)
    newer = datetime.datetime(2026, 6, 7, 8, 9, 10)
    _derived(db_session, org.id, a, b, engine_version="0.9.0", computed_at=older)
    _derived(db_session, org.id, b, c, engine_version="1.0.0", computed_at=newer)
    db_session.commit()
    org_id = org.id

    with app.app_context():
        agg = derived_fact_aggregates(org_id)

    assert agg["computed_at"] == newer
    assert agg["engine_versions"] == ["0.9.0", "1.0.0"]


def test_a_tenant_with_nothing_stored_has_zero_counts_and_no_time_or_version(app, db_session, make_org):
    from app.modules.intelligence.services.derived_facts import derived_fact_aggregates

    org = make_org("agg-empty")
    db_session.commit()
    org_id = org.id

    with app.app_context():
        agg = derived_fact_aggregates(org_id)

    assert agg["total_count"] == 0
    assert agg["computed_at"] is None
    assert agg["engine_versions"] == []


def test_another_tenants_rows_are_never_counted(app, db_session, make_org):
    from app.modules.intelligence.services.derived_facts import (
        derived_fact_aggregates,
        explicit_relationship_count,
    )

    mine = make_org("agg-mine")
    theirs = make_org("agg-theirs")
    a, b = _element(db_session, mine.id, "a"), _element(db_session, mine.id, "b")
    x, y = _element(db_session, theirs.id, "x"), _element(db_session, theirs.id, "y")
    _derived(db_session, mine.id, a, b)
    for _ in range(4):
        _derived(db_session, theirs.id, x, y, stale=True)
        _relationship(db_session, theirs.id, x, y)
    _relationship(db_session, mine.id, a, b)
    db_session.commit()
    mine_id, theirs_id = mine.id, theirs.id

    with app.app_context():
        mine_agg = derived_fact_aggregates(mine_id)
        theirs_agg = derived_fact_aggregates(theirs_id)
        mine_explicit = explicit_relationship_count(mine_id)
        theirs_explicit = explicit_relationship_count(theirs_id)

    assert (mine_agg["total_count"], mine_agg["stale_count"], mine_explicit) == (1, 0, 1)
    assert (theirs_agg["total_count"], theirs_agg["stale_count"], theirs_explicit) == (4, 4, 4)


def test_the_aggregates_take_the_organisation_explicitly_and_carry_the_predicate():
    """Static: each aggregate is given the organisation and filters on it, so it is
    correct when there is no request for the tenant listener to read."""
    from app.modules.intelligence.services import derived_facts

    for function in (
        derived_facts.derived_fact_aggregates,
        derived_facts.explicit_relationship_count,
        derived_facts.active_element_count,
    ):
        assert list(inspect.signature(function).parameters) == ["organization_id"]
        source = inspect.getsource(function)
        assert "organization_id ==" in source.replace("\r", "")
        assert "select(" in source, "an aggregate is a select, not a loop over loaded rows"
        assert "len(" not in re.sub(r'""".*?"""', "", source, flags=re.S)


def test_the_aggregates_run_with_no_request_context(app, db_session, make_org):
    """No ``g.current_org_id`` and no request: the explicit predicate alone fences it."""
    from flask import g, has_request_context

    from app.modules.intelligence.services.derived_facts import (
        derived_fact_aggregates,
        explicit_relationship_count,
    )

    org = make_org("agg-no-context")
    other = make_org("agg-no-context-other")
    a, b = _element(db_session, org.id, "a"), _element(db_session, org.id, "b")
    x, y = _element(db_session, other.id, "x"), _element(db_session, other.id, "y")
    _relationship(db_session, org.id, a, b)
    _relationship(db_session, other.id, x, y)
    _relationship(db_session, other.id, y, x)
    db_session.commit()
    org_id = org.id

    with app.app_context():
        assert not has_request_context()
        assert getattr(g, "current_org_id", None) is None
        assert explicit_relationship_count(org_id) == 1
        assert derived_fact_aggregates(org_id)["total_count"] == 0


def test_the_aggregates_are_a_few_statements_however_many_rows_there_are(app, db_session, make_org):
    from sqlalchemy import event

    from app.extensions import db
    from app.modules.intelligence.services.derived_facts import (
        derived_fact_aggregates,
        explicit_relationship_count,
    )

    org = make_org("agg-bounded")
    a, b = _element(db_session, org.id, "a"), _element(db_session, org.id, "b")
    for _ in range(25):
        _derived(db_session, org.id, a, b)
        _relationship(db_session, org.id, a, b)
    db_session.commit()
    org_id = org.id

    statements = []

    def _count(*args, **kwargs):
        statements.append(args[2] if len(args) > 2 else "")

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", _count)
        try:
            derived_fact_aggregates(org_id)
            explicit_relationship_count(org_id)
        finally:
            event.remove(db.engine, "before_cursor_execute", _count)

    assert len(statements) <= 8, statements


# --- the aggregates agree with a fresh recompute -------------------------------


def test_after_a_fresh_recompute_the_aggregates_and_the_recompute_agree(app, db_session, make_org):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner
    from app.modules.intelligence.services.derived_facts import (
        derived_fact_aggregates,
        explicit_relationship_count,
    )

    org = make_org("agg-fresh-recompute")
    a, b, c, d = (_element(db_session, org.id, n) for n in "abcd")
    _relationship(db_session, org.id, a, b, "Composition")
    _relationship(db_session, org.id, b, c, "Serving")
    _relationship(db_session, org.id, c, d, "Serving")
    db_session.commit()
    org_id = org.id

    with app.app_context():
        result = DerivationRunner().run_and_persist(org_id, trigger="on_demand")
        agg = derived_fact_aggregates(org_id)
        explicit = explicit_relationship_count(org_id)

    assert explicit == result.explicit_count == 3
    assert agg["total_count"] == result.derived_count
    assert agg["stale_count"] == 0
    assert agg["current_count"] == result.derived_count
    assert result.derived_count >= 1, "the fixture must derive something for this to mean anything"


def test_a_partial_recompute_reports_what_the_store_holds_not_what_the_run_returned(app, db_session, make_org):
    """A store that holds more or fewer rows than the last run returned (a run cut
    short, a row written since) is described by the store, which is what a reader of
    the store sees."""
    from app.modules.intelligence.services.derivation_runner import DerivationRunner
    from app.modules.intelligence.services.derived_facts import derived_fact_aggregates

    org = make_org("agg-partial")
    a, b, c = (_element(db_session, org.id, n) for n in "abc")
    _relationship(db_session, org.id, a, b, "Composition")
    _relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()
    org_id = org.id
    with app.app_context():
        result = DerivationRunner().run_and_persist(org_id, trigger="on_demand")
    _derived(db_session, org.id, a, c)
    db_session.commit()

    with app.app_context():
        agg = derived_fact_aggregates(org_id)

    assert agg["total_count"] == result.derived_count + 1
    assert agg["total_count"] != result.derived_count


def test_the_explicit_count_is_every_relationship_row_matching_what_the_runner_counts(app, db_session, make_org):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner
    from app.modules.intelligence.services.derived_facts import explicit_relationship_count

    org = make_org("agg-explicit-runner")
    a, b, c = (_element(db_session, org.id, n) for n in "abc")
    for kind in ("Composition", "Serving", "Association", "Flow", "Triggering"):
        _relationship(db_session, org.id, a, b, kind)
    _relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()
    org_id = org.id

    with app.app_context():
        counted = explicit_relationship_count(org_id)
        run = DerivationRunner().run(org_id)

    assert counted == run.explicit_count == 6


def test_the_aggregates_refuse_to_guess_the_tenant():
    from app.modules.intelligence.services.derived_facts import (
        active_element_count,
        derived_fact_aggregates,
        explicit_relationship_count,
    )

    for function in (derived_fact_aggregates, explicit_relationship_count, active_element_count):
        with pytest.raises(TypeError):
            function()  # type: ignore[call-arg]


# --- the element count the model check measures ---------------------------------


def test_the_element_count_leaves_out_other_tenants_and_deleted_elements(app, db_session, make_org):
    from app.modules.intelligence.services.derived_facts import active_element_count

    mine = make_org("elements-mine")
    theirs = make_org("elements-theirs")
    for name in "abc":
        _element(db_session, mine.id, name)
    gone = _element(db_session, mine.id, "gone")
    gone.deleted_at = datetime.datetime.utcnow()
    for name in "wxyz":
        _element(db_session, theirs.id, name)
    db_session.commit()
    mine_id, theirs_id = mine.id, theirs.id

    with app.app_context():
        assert active_element_count(mine_id) == 3, "a deleted element and another tenant's are not counted"
        assert active_element_count(theirs_id) == 4
        assert active_element_count(theirs_id + 10_000) == 0, "an unknown tenant has none, not an error"


def test_the_element_count_is_the_number_of_elements_the_detector_loads(app, db_session, make_org, monkeypatch):
    """The guard measures the thing that drives the detector's cost: the detector is
    handed exactly as many elements as the count reports, deleted ones left out."""
    from app.modules.genome.services import drift_detector
    from app.modules.intelligence.services.derived_facts import active_element_count

    org = make_org("elements-detector")
    other = make_org("elements-detector-other")
    for name in ("alpha", "bravo", "charlie", "delta"):
        _element(db_session, org.id, name)
    gone = _element(db_session, org.id, "echo")
    gone.deleted_at = datetime.datetime.utcnow()
    _element(db_session, other.id, "foxtrot")
    db_session.commit()
    org_id = org.id

    loaded = []
    real = drift_detector._detect_near_duplicates

    def _spy(elements):
        loaded.append(len(elements))
        return real(elements)

    monkeypatch.setattr(drift_detector, "_detect_near_duplicates", _spy)

    with app.app_context():
        drift_detector.detect_model_drift(org_id)
        counted = active_element_count(org_id)

    assert loaded == [4]
    assert counted == loaded[0]


def test_the_element_count_runs_with_no_request_context_in_one_statement(app, db_session, make_org):
    from flask import g, has_request_context
    from sqlalchemy import event

    from app.extensions import db
    from app.modules.intelligence.services.derived_facts import active_element_count

    org = make_org("elements-no-context")
    other = make_org("elements-no-context-other")
    _element(db_session, org.id, "a")
    _element(db_session, org.id, "b")
    _element(db_session, other.id, "x")
    db_session.commit()
    org_id = org.id

    statements = []

    def _count(*args, **kwargs):
        statements.append(args[2] if len(args) > 2 else "")

    with app.app_context():
        assert not has_request_context()
        assert getattr(g, "current_org_id", None) is None
        event.listen(db.engine, "before_cursor_execute", _count)
        try:
            counted = active_element_count(org_id)
        finally:
            event.remove(db.engine, "before_cursor_execute", _count)

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert counted == 2
    assert len(selects) == 1, statements
    assert "count(" in selects[0].lower()


@pytest.mark.parametrize("versions, physical, expected_current", [
    ([ENGINE_VERSION], [False], 1),
    (["1.0.0"], [False], 0),
    ([ENGINE_VERSION, "1.0.0", "9.0.0", ""], [False] * 4, 1),
    ([ENGINE_VERSION, ENGINE_VERSION], [False, True], 1),
])
def test_effective_currentness_agrees_across_lists_details_and_sql_counts(
    app, db_session, make_org, versions, physical, expected_current
):
    from app.modules.intelligence.services.derived_facts import (
        derived_fact_aggregates, get_derived_fact, list_derived_facts,
    )
    org_id = make_org("fact-currentness").id
    foreign_id = make_org("fact-currentness-foreign").id
    a, b = _element(db_session, org_id, "a"), _element(db_session, org_id, "b")
    rows = [_derived(db_session, org_id, a, b, engine_version=v, stale=s)
            for v, s in zip(versions, physical)]
    stored = [(r.id, r.engine_version, r.computed_at, r.stale, r.stale_since, r.stale_reason) for r in rows]
    db_session.commit()
    current = list_derived_facts(org_id)
    all_facts = list_derived_facts(org_id, include_stale=True)
    assert len(current) == expected_current
    assert len(all_facts) == len(versions)
    for row_id, version, computed, stale, since, reason in stored:
        effective_stale = stale or version != ENGINE_VERSION
        fact = get_derived_fact(org_id, row_id)
        assert fact == next(f for f in all_facts if f["id"] == row_id)
        assert fact["stale"] is effective_stale
        assert fact.get("reason") == ("derivation_stale" if effective_stale else None)
        assert fact["engine_version"] == version
        assert fact["computed_at"] == computed.isoformat()
        assert get_derived_fact(org_id, row_id, include_stale=False) == (None if effective_stale else fact)
        assert get_derived_fact(foreign_id, row_id) is None
    agg = derived_fact_aggregates(org_id)
    assert agg["total_count"] == len(versions)
    assert agg["current_count"] == expected_current
    assert agg["stale_count"] == len(versions) - expected_current
    assert agg["engine_versions"] == sorted(set(versions))
    assert agg["computed_at"] == max(r[2] for r in stored)
    db_session.expire_all()
    assert [(r.id, r.engine_version, r.computed_at, r.stale, r.stale_since, r.stale_reason)
            for r in rows] == stored, "reads must not write flags, versions or timestamps"


def test_null_legacy_version_is_stale_without_weakening_the_fact_schema(app, db_session):
    from types import SimpleNamespace
    from sqlalchemy import literal, select
    from app.extensions import db
    from app.modules.intelligence.services.derived_facts import _effective_current, _serialize

    row = SimpleNamespace(id=1, organization_id=1, source_element_id=2, target_element_id=3,
                          derived_type="Association", rule_id="fallback:access:access", chain=[4, 5],
                          chain_element_ids=[2, 6, 3], depth=2, confidence=1, provenance="derivation",
                          engine_version=None, computed_at=None, stale=False)
    payload = _serialize(row)
    assert payload["stale"] is True and payload["reason"] == "derivation_stale"
    assert payload["engine_version"] is None and payload["computed_at"] is None
    # Normal facts forbid NULL versions. Exercise null-safe SQL as scalar
    # values rather than altering schema constraints or inventing a valid row.
    model = SimpleNamespace(stale=literal(False), engine_version=literal(None))
    assert db.session.execute(select(_effective_current(model))).scalar_one() is False
    assert db.session.execute(select(~_effective_current(model))).scalar_one() is True
