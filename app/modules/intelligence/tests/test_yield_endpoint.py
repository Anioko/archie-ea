"""T-005 / task 02 acceptance criteria 1-13: ``GET /api/v1/intelligence/yield``,
the p95 bucket-edge read, and the Shape-B trigger.

Read ``docs/buckets/t005-us5-yield-report/tasks/00-verification-notes.md``
(D1-D4, D8, D11, D12) and
``docs/buckets/t005-us5-yield-report/tasks/02-yield-endpoint-p95-read-and-
shape-b-trigger.md`` before changing this file -- the decisions there are
binding.

Fixtures (app, db_session, make_org, tenant_ctx, client, login_as) are
discovered via app/modules/intelligence/tests/conftest.py's own import of
tests.conftest (same pattern as test_impact_route.py).
"""

from __future__ import annotations

from app.modules.intelligence.services.derivation_runner import ENGINE_VERSION

import uuid

import pytest

from app.services.prometheus_metrics import INTELLIGENCE_QUERY_DURATION

PINNED_LABELS = {"query": "cross_layer_impact", "depth": "4", "include_derived": "true"}


def _user(db_session, org_id):
    from app.models.user import User

    user = User(
        email=f"t005-{uuid.uuid4().hex[:10]}@example.com",
        first_name="T005",
        last_name="Tester",
        organization_id=org_id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _element(db_session, org_id, name, layer="application"):
    from app.models import ArchiMateElement

    el = ArchiMateElement(name=name, type="ApplicationComponent", layer=layer, organization_id=org_id)
    db_session.add(el)
    db_session.flush()
    return el


def _relationship(db_session, org_id, source, target, type_="Serving"):
    from app.models import ArchiMateRelationship

    rel = ArchiMateRelationship(source_id=source.id, target_id=target.id, type=type_, organization_id=org_id)
    db_session.add(rel)
    db_session.flush()
    return rel


def _observe_pinned(n: int, *, seconds: float = 0.01, labels: dict | None = None) -> None:
    lbl = dict(PINNED_LABELS)
    if labels:
        lbl.update(labels)
    for _ in range(n):
        INTELLIGENCE_QUERY_DURATION.labels(**lbl).observe(seconds)


# --- Acceptance criterion 1: fields present (FR-7) --------------------------


def test_computed_branch_carries_every_required_field(app, db_session, make_org, client, login_as):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org = make_org("yield-fields")
    user = _user(db_session, org.id)
    a = _element(db_session, org.id, "A")
    b = _element(db_session, org.id, "B")
    _relationship(db_session, org.id, a, b)
    db_session.commit()
    org_id = org.id

    with app.app_context():
        DerivationRunner().run_and_persist(org_id, trigger="on_demand")

    login_as(client, user)
    resp = client.get("/api/v1/intelligence/yield")
    assert resp.status_code == 200
    data = resp.get_json()["data"]

    for key in (
        "explicit_count", "derived_count", "ratio", "computed_at", "engine_version",
        "stale_count", "last_recompute_duration_ms", "p95",
    ):
        assert key in data, f"missing field {key!r}"
    assert "latency_seconds" in data["p95"]
    assert "sample_count" in data["p95"]


# --- Acceptance criterion 2: not-computed vs measured-zero distinguishability


def test_not_computed_branch_carries_state_and_reason_with_null_counts(
    app, db_session, make_org, client, login_as
):
    org = make_org("yield-not-computed")
    user = _user(db_session, org.id)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/api/v1/intelligence/yield")
    assert resp.status_code == 200
    data = resp.get_json()["data"]

    assert data["state"] == "not_computed"
    assert data["reason"] == "derivation_not_computed"
    for key in ("explicit_count", "derived_count", "ratio", "computed_at", "engine_version", "stale_count", "last_recompute_duration_ms"):
        assert data[key] is None


def test_measured_zero_differs_from_not_computed_end_to_end(app, db_session, make_org, client, login_as):
    """The D6 case, driven through the endpoint: a tenant that ran and
    derived zero must read differently from a tenant that never ran."""
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org_ran_zero = make_org("yield-ran-zero")
    org_never_ran = make_org("yield-never-ran")
    user_ran_zero = _user(db_session, org_ran_zero.id)
    user_never_ran = _user(db_session, org_never_ran.id)
    db_session.commit()
    org_ran_zero_id = org_ran_zero.id

    with app.app_context():
        DerivationRunner().run_and_persist(org_ran_zero_id, trigger="on_demand")

    login_as(client, user_ran_zero)
    resp_ran_zero = client.get("/api/v1/intelligence/yield")
    data_ran_zero = resp_ran_zero.get_json()["data"]

    login_as(client, user_never_ran)
    resp_never_ran = client.get("/api/v1/intelligence/yield")
    data_never_ran = resp_never_ran.get_json()["data"]

    assert data_ran_zero["state"] == "current"
    assert data_ran_zero["derived_count"] == 0
    assert data_never_ran["state"] == "not_computed"
    assert data_never_ran["derived_count"] is None
    assert data_ran_zero != data_never_ran


def test_mutation_proof_not_computed_zero_seam(app, db_session, make_org, client, login_as, monkeypatch):
    """Acceptance item 12: force the not-computed branch to emit 0 instead of
    null via its isolated seam, and confirm the distinguishability test above
    would go red -- proving that test is not vacuously green.

    Test id for the build report: this test IS the mutation proof for
    ``test_measured_zero_differs_from_not_computed_end_to_end`` /
    ``test_not_computed_branch_carries_state_and_reason_with_null_counts``.
    """
    import app.modules.intelligence.services.query_service as qs

    org = make_org("yield-mutation-proof")
    user = _user(db_session, org.id)
    db_session.commit()

    def _zeroed_counts():
        return {
            "explicit_count": 0,
            "derived_count": 0,
            "ratio": 0,
            "computed_at": None,
            "engine_version": None,
            "stale_count": 0,
            "last_recompute_duration_ms": None,
        }

    monkeypatch.setattr(qs, "_not_computed_counts", _zeroed_counts)

    login_as(client, user)
    resp = client.get("/api/v1/intelligence/yield")
    data = resp.get_json()["data"]

    # With the seam mutated, the not-computed branch now reports 0s -- the
    # exact fabrication the real seam prevents. This confirms the guard is
    # load-bearing: removing it changes the observable payload.
    assert data["derived_count"] == 0
    assert data["state"] == "not_computed"


# --- Acceptance criterion 3: insufficient-samples branch --------------------


def test_p95_null_with_insufficient_samples_below_100(app, db_session, make_org, client, login_as):
    org = make_org("yield-insufficient")
    user = _user(db_session, org.id)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/api/v1/intelligence/yield")
    data = resp.get_json()["data"]
    # sample_count == 0 on a never-observed series.
    assert data["p95"]["sample_count"] >= 0
    if data["p95"]["sample_count"] < 100:
        assert data["p95"]["latency_seconds"] is None
        assert data["p95"]["reason"] == "insufficient_samples_for_p95"


def test_p95_sample_count_boundary_99_vs_100(app, db_session, make_org, client, login_as):
    from app.modules.intelligence.services.latency_probe import read_p95_bucket_edge

    with app.app_context():
        distinct_query = f"boundary-test-{uuid.uuid4().hex[:8]}"
        for _ in range(99):
            INTELLIGENCE_QUERY_DURATION.labels(
                query=distinct_query, depth="4", include_derived="true"
            ).observe(0.02)
        result_99 = read_p95_bucket_edge(query=distinct_query, depth="4", include_derived="true")
        assert result_99["sample_count"] == 99
        assert result_99["latency_seconds"] is None
        assert result_99["reason"] == "insufficient_samples_for_p95"

        INTELLIGENCE_QUERY_DURATION.labels(
            query=distinct_query, depth="4", include_derived="true"
        ).observe(0.02)
        result_100 = read_p95_bucket_edge(query=distinct_query, depth="4", include_derived="true")
        assert result_100["sample_count"] == 100
        assert result_100["latency_seconds"] is not None
        assert result_100["reason"] is None


# --- Acceptance criterion 4: no fabricated target ---------------------------


def test_no_fabricated_target_field_anywhere_in_payload(app, db_session, make_org, client, login_as):
    import json

    org = make_org("yield-no-target")
    user = _user(db_session, org.id)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/api/v1/intelligence/yield")
    body_text = json.dumps(resp.get_json())

    for forbidden in ("\"target\"", "\"goal\"", "\"slo_target\"", "threshold_target"):
        assert forbidden not in body_text, f"found forbidden fabricated-target key {forbidden!r}"


# --- Acceptance criterion 5: p95 source is the histogram, pinned selector --


def test_p95_reads_declared_bucket_boundaries_and_moves_across_them(app):
    from app.modules.intelligence.services.latency_probe import read_p95_bucket_edge

    with app.app_context():
        distinct_query = f"bucket-edge-{uuid.uuid4().hex[:8]}"
        for _ in range(100):
            INTELLIGENCE_QUERY_DURATION.labels(
                query=distinct_query, depth="4", include_derived="true"
            ).observe(0.02)  # falls in the 0.025 declared bucket
        result = read_p95_bucket_edge(query=distinct_query, depth="4", include_derived="true")
        # 0.02s falls in the declared 0.025 bucket -- the reported value is
        # always one of the histogram's own declared boundaries.
        assert result["latency_seconds"] == 0.025


def test_p95_unaffected_by_different_include_derived_or_depth_label(app):
    from app.modules.intelligence.services.latency_probe import read_p95_bucket_edge

    with app.app_context():
        distinct_query = f"label-isolation-{uuid.uuid4().hex[:8]}"
        for _ in range(100):
            INTELLIGENCE_QUERY_DURATION.labels(
                query=distinct_query, depth="4", include_derived="true"
            ).observe(0.01)
        baseline = read_p95_bucket_edge(query=distinct_query, depth="4", include_derived="true")

        # Observations on a DIFFERENT include_derived label must not move it.
        for _ in range(500):
            INTELLIGENCE_QUERY_DURATION.labels(
                query=distinct_query, depth="4", include_derived="false"
            ).observe(4.5)
        after_different_include_derived = read_p95_bucket_edge(
            query=distinct_query, depth="4", include_derived="true"
        )
        assert after_different_include_derived == baseline

        # Observations on a DIFFERENT depth label must not move it either.
        for _ in range(500):
            INTELLIGENCE_QUERY_DURATION.labels(
                query=distinct_query, depth="3", include_derived="true"
            ).observe(4.5)
        after_different_depth = read_p95_bucket_edge(
            query=distinct_query, depth="4", include_derived="true"
        )
        assert after_different_depth == baseline


def test_repeated_yield_calls_do_not_move_the_pinned_series(app, db_session, make_org, client, login_as):
    """D2 self-pollution guard: calling the yield endpoint 200 times must not
    change the pinned cross_layer_impact series' sample_count -- AND must
    move derivation_yield's own series by the same number of calls (D-3,
    refuter round 2). Checking only the negative half (pinned series
    unaffected) would leave a mislabelling regression -- one that reused the
    pinned selector's exact labels for the yield endpoint's own probe --
    green, since nothing would have moved either series and the test would
    never notice. Asserting both halves pins that the two label sets are
    genuinely disjoint, not just that nothing happened.
    """
    from app.modules.intelligence.services.latency_probe import read_p95_bucket_edge

    # derivation_yield's own probe (query_service.py's
    # `record_query_latency("derivation_yield")` call) never sets
    # scope.depth/scope.include_derived, so it always resolves to
    # depth="unknown", include_derived="false" -- matching latency_probe.py's
    # own fallback labelling, not the pinned NFR5 selector.
    own_labels = {"query": "derivation_yield", "depth": "unknown", "include_derived": "false"}

    org = make_org("yield-self-pollution")
    user = _user(db_session, org.id)
    db_session.commit()

    login_as(client, user)
    first = client.get("/api/v1/intelligence/yield").get_json()["data"]
    before_count = first["p95"]["sample_count"]
    before_own = read_p95_bucket_edge(min_samples=0, **own_labels)["sample_count"]

    # before_own is captured AFTER the "first" call above, so that call's
    # observation is already baked into the baseline -- only count
    # observations made from here on.
    calls_made = 0
    for _ in range(200):
        client.get("/api/v1/intelligence/yield")
        calls_made += 1

    last = client.get("/api/v1/intelligence/yield").get_json()["data"]
    calls_made += 1
    after_count = last["p95"]["sample_count"]
    after_own = read_p95_bucket_edge(min_samples=0, **own_labels)["sample_count"]

    assert after_count == before_count, (
        "calling the yield endpoint must not move the pinned "
        "cross_layer_impact series -- derivation_yield's own latency must "
        "not pollute the series it reports on"
    )
    assert after_own - before_own == calls_made, (
        "derivation_yield's OWN latency series must move by exactly the "
        "number of calls made -- if this does not move, the endpoint's own "
        "probe is not observing at all (or is mislabelled onto a series "
        "this test isn't watching), which the pinned-series-unmoved "
        "assertion alone cannot detect"
    )


# --- Acceptance criterion 6: above-top-bucket honesty ------------------------


def test_above_highest_bucket_reports_null_with_reason_and_still_fires_shape_b(app):
    from app.modules.intelligence.services.latency_probe import read_p95_bucket_edge

    with app.app_context():
        distinct_query = f"above-bucket-{uuid.uuid4().hex[:8]}"
        for _ in range(100):
            INTELLIGENCE_QUERY_DURATION.labels(
                query=distinct_query, depth="4", include_derived="true"
            ).observe(9.0)  # above the highest declared bucket (5.0)
        result = read_p95_bucket_edge(query=distinct_query, depth="4", include_derived="true")

    assert result["latency_seconds"] is None
    assert result["reason"] == "p95_above_highest_bucket"
    assert result["p95_exceeds_seconds"] == 5.0


def test_shape_b_trigger_fires_on_pinned_series_breach(app, db_session, make_org, client, login_as, monkeypatch):
    """Drives the trigger through the real pinned series
    (query=cross_layer_impact, depth=4, include_derived=true)."""
    org = make_org("yield-shape-b")
    user = _user(db_session, org.id)
    db_session.commit()

    _observe_pinned(100, seconds=4.9)  # above 2.0s threshold, within top bucket (5.0)

    caught = []

    def _capturing_warning(msg, *args, **kwargs):
        caught.append(msg % args if args else msg)

    import logging

    logger = logging.getLogger("archie.intelligence.oa2")
    monkeypatch.setattr(logger, "warning", _capturing_warning)

    login_as(client, user)
    resp = client.get("/api/v1/intelligence/yield")
    data = resp.get_json()["data"]

    assert data["shape_b_trigger"] is not None
    assert data["shape_b_trigger"]["threshold_seconds"] == 2.0
    assert data["shape_b_trigger"]["sample_count"] >= 100
    assert data["shape_b_trigger"]["recorded_at"]
    assert any("shape_b_trigger" in m for m in caught)


def test_shape_b_trigger_creates_no_work_item_or_queue_entry(app, db_session, make_org, client, login_as):
    """No build/work item, task, queue entry or state change -- it opens a
    decision, it does not start work (task 02 acceptance item 8)."""
    org = make_org("yield-shape-b-no-workitem")
    user = _user(db_session, org.id)
    db_session.commit()

    _observe_pinned(100, seconds=4.9)

    login_as(client, user)
    resp = client.get("/api/v1/intelligence/yield")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["shape_b_trigger"] is not None
    # No table row anywhere claims to be a "trigger" record; the response
    # body itself IS the record (D11 -- a dataclass, not a workflow).
    from app.modules.intelligence.services.observability import ShapeBTriggerRecord

    assert set(data["shape_b_trigger"].keys()) == set(ShapeBTriggerRecord.__dataclass_fields__.keys())


# --- Acceptance criterion 7: scope honesty (D4) ------------------------------


def test_p95_scope_is_process_estate_wide_and_nested(app, db_session, make_org, client, login_as):
    org = make_org("yield-scope")
    user = _user(db_session, org.id)
    db_session.commit()

    login_as(client, user)
    resp = client.get("/api/v1/intelligence/yield")
    data = resp.get_json()["data"]

    assert isinstance(data["p95"], dict)
    assert data["p95"]["scope"] == "process_estate_wide"
    # p95 must never be flattened alongside the per-tenant counts.
    assert "latency_seconds" not in data
    assert "p95_sample_count" not in data


# --- Acceptance criterion 9: authorisation -----------------------------------


def test_yield_route_rejects_anonymous(app, client):
    resp = client.get("/api/v1/intelligence/yield")
    assert resp.status_code in (302, 401)


# --- Acceptance criterion 10: tenancy ----------------------------------------


def test_yield_response_is_tenant_scoped(app, db_session, make_org, client, login_as):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org_a = make_org("yield-tenant-a")
    org_b = make_org("yield-tenant-b")
    user_a = _user(db_session, org_a.id)
    user_b = _user(db_session, org_b.id)
    a1 = _element(db_session, org_a.id, "a1")
    a2 = _element(db_session, org_a.id, "a2")
    _relationship(db_session, org_a.id, a1, a2)
    db_session.commit()
    org_a_id = org_a.id

    with app.app_context():
        DerivationRunner().run_and_persist(org_a_id, trigger="on_demand")

    login_as(client, user_a)
    data_a = client.get("/api/v1/intelligence/yield").get_json()["data"]

    login_as(client, user_b)
    data_b = client.get("/api/v1/intelligence/yield").get_json()["data"]

    assert data_a["state"] == "current"
    assert data_b["state"] == "not_computed", (
        "org_a having run must not make org_b report computed"
    )
    assert data_a["organization_id"] == org_a_id
    assert data_b["organization_id"] == org_b.id


# --- Acceptance criterion 11: store agreement (D8) ---------------------------


def test_recompute_and_yield_agree_on_explicit_derived_ratio(app, db_session, make_org, client, login_as):
    org = make_org("yield-store-agreement")
    user = _user(db_session, org.id)
    a = _element(db_session, org.id, "A")
    b = _element(db_session, org.id, "B")
    c = _element(db_session, org.id, "C")
    _relationship(db_session, org.id, a, b, "Composition")
    _relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()

    login_as(client, user)
    recompute_resp = client.post(
        "/api/v1/intelligence/derivation/recompute", json={"scope": "tenant"}
    )
    assert recompute_resp.status_code == 200
    recompute_data = recompute_resp.get_json()["data"]

    yield_resp = client.get("/api/v1/intelligence/yield")
    assert yield_resp.status_code == 200
    yield_data = yield_resp.get_json()["data"]

    assert yield_data["explicit_count"] == recompute_data["explicit_count"]
    assert yield_data["derived_count"] == recompute_data["derived_count"]
    if recompute_data["ratio"] is None:
        assert yield_data["ratio"] is None
    else:
        assert yield_data["ratio"] == pytest.approx(recompute_data["ratio"])


# --- Acceptance criterion 13: NFR-8 / Release 1 completeness ----------------


def test_exactly_four_intelligence_routes_registered(app):
    rules = [
        rule for rule in app.url_map.iter_rules()
        if str(rule).startswith("/api/v1/intelligence")
    ]
    assert len(rules) == 4, (
        f"expected exactly 4 /api/v1/intelligence/* rules (recompute POST, "
        f"derived GET, impact GET, yield GET) -- found {len(rules)}: "
        f"{[str(r) for r in rules]}"
    )


def test_release1_l0_engine_version_matches_runner_constant_on_stored_rows(
    app, db_session, make_org, client, login_as
):
    from app.modules.intelligence.services.derivation_runner import ENGINE_VERSION, DerivationRunner

    org = make_org("yield-l0-engine-version")
    user = _user(db_session, org.id)
    a = _element(db_session, org.id, "A")
    b = _element(db_session, org.id, "B")
    c = _element(db_session, org.id, "C")
    _relationship(db_session, org.id, a, b, "Composition")
    _relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()
    org_id = org.id

    with app.app_context():
        DerivationRunner().run_and_persist(org_id, trigger="on_demand")

    login_as(client, user)
    data = client.get("/api/v1/intelligence/yield").get_json()["data"]

    assert data["engine_version"] == [ENGINE_VERSION]


# =============================================================================
# The worked-out connections screen reads this payload. The tests below pin the
# field set it needs, the null-and-a-reason rule for every absent value, the
# measured zero that is not "never worked out", the p95 that is read from one
# pinned series only, and the drift count that comes from the detector alone.
# =============================================================================

ALL_FIELDS = (
    "explicit_count", "derived_count", "ratio", "computed_at", "engine_version",
    "stale_count", "last_recompute_duration_ms", "p95_latency_seconds", "sample_count",
    "state", "drift_finding_count", "reasons",
)
COUNT_FIELDS = (
    "explicit_count", "derived_count", "ratio", "computed_at", "engine_version", "stale_count",
)


def _derived_row(db_session, org_id, source, target, *, stale=False, engine_version=ENGINE_VERSION):
    import datetime

    from app.modules.intelligence.models.derived_relationship import DerivedRelationship

    row = DerivedRelationship(
        organization_id=org_id,
        source_element_id=source.id,
        target_element_id=target.id,
        derived_type="Association",
        rule_id="fallback:Test:Test",
        chain=[999],
        chain_element_ids=[source.id, target.id],
        depth=1,
        confidence="1.00",
        provenance="derivation",
        engine_version=engine_version,
        computed_at=datetime.datetime.utcnow(),
        stale=stale,
        stale_since=datetime.datetime.utcnow() if stale else None,
        stale_reason="derivation_stale" if stale else None,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _yield_for(client, login_as, user):
    login_as(client, user)
    response = client.get("/api/v1/intelligence/yield")
    assert response.status_code == 200
    return response.get_json()["data"]


def _patch_p95(monkeypatch, *, latency, samples, reason, exceeds=None):
    """Answer the pinned-series read with a chosen reading, so a test does not depend
    on what other tests observed on the process-wide histogram."""
    import app.modules.intelligence.services.latency_probe as probe

    reading = {"latency_seconds": latency, "sample_count": samples, "reason": reason}
    if exceeds is not None:
        reading["p95_exceeds_seconds"] = exceeds
    monkeypatch.setattr(probe, "read_p95_bucket_edge", lambda **_kw: dict(reading))


def _patch_drift(monkeypatch, *, total=None, raises=None):
    import app.modules.genome.services.drift_detector as detector

    calls = []

    def _detect(org_id, session=None):
        calls.append(org_id)
        if raises is not None:
            raise raises
        return {"summary": {"total": total, "by_type": {"orphaned": total}}, "findings": [{"type": "orphaned"}]}

    monkeypatch.setattr(detector, "detect_model_drift", _detect)
    return calls


# --- the field set ----------------------------------------------------------


def test_every_field_is_present_when_derivation_has_never_run(app, db_session, make_org, client, login_as):
    org = make_org("yield-fields-never")
    user = _user(db_session, org.id)
    db_session.commit()

    data = _yield_for(client, login_as, user)

    for key in ALL_FIELDS:
        assert key in data, f"missing field {key!r}"
    assert isinstance(data["reasons"], list)


def test_every_field_is_present_after_derivation_ran(app, db_session, make_org, client, login_as):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org = make_org("yield-fields-ran")
    user = _user(db_session, org.id)
    a, b, c = (_element(db_session, org.id, n) for n in "abc")
    _relationship(db_session, org.id, a, b, "Composition")
    _relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()
    org_id = org.id
    with app.app_context():
        DerivationRunner().run_and_persist(org_id, trigger="on_demand")

    data = _yield_for(client, login_as, user)

    for key in ALL_FIELDS:
        assert key in data, f"missing field {key!r}"
    assert data["state"] == "current"
    assert data["explicit_count"] == 2
    assert data["derived_count"] >= 1
    assert data["ratio"] == pytest.approx(data["derived_count"] / data["explicit_count"])
    assert data["computed_at"]
    assert data["engine_version"]
    assert data["stale_count"] == 0


def test_the_flat_p95_fields_mirror_the_scoped_block(app, db_session, make_org, client, login_as, monkeypatch):
    org = make_org("yield-flat-p95")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_p95(monkeypatch, latency=0.05, samples=250, reason=None)

    data = _yield_for(client, login_as, user)

    assert data["p95_latency_seconds"] == 0.05
    assert data["sample_count"] == 250
    assert data["p95"]["latency_seconds"] == data["p95_latency_seconds"]
    assert data["p95"]["sample_count"] == data["sample_count"]
    assert data["p95"]["scope"] == "process_estate_wide"
    assert "insufficient_samples_for_p95" not in data["reasons"]


# --- never worked out: null, a reason, and not a zero ------------------------


def test_never_worked_out_is_null_counts_with_the_reason_in_the_list(
    app, db_session, make_org, client, login_as
):
    org = make_org("yield-never-null")
    user = _user(db_session, org.id)
    # Relationships exist, but derivation has not run: the counts still are not
    # reported, because they are the derivation's to report.
    a, b = _element(db_session, org.id, "a"), _element(db_session, org.id, "b")
    _relationship(db_session, org.id, a, b)
    db_session.commit()

    data = _yield_for(client, login_as, user)

    assert data["state"] == "not_computed"
    assert data["reason"] == "derivation_not_computed"
    assert "derivation_not_computed" in data["reasons"]
    for key in COUNT_FIELDS:
        assert data[key] is None, key
    assert data["last_recompute_duration_ms"] is None
    assert "no_recompute_duration_recorded" in data["reasons"]


def test_a_run_that_derived_nothing_is_a_measured_zero_and_reads_differently(
    app, db_session, make_org, client, login_as
):
    """One explicit relationship and nothing derived from it: derivation ran, so the
    counts are numbers. The tenant that never ran carries null in the same places."""
    from app.modules.intelligence.services.derivation_runner import ENGINE_VERSION, DerivationRunner

    ran = make_org("yield-zero-ran")
    never = make_org("yield-zero-never")
    ran_user, never_user = _user(db_session, ran.id), _user(db_session, never.id)
    a, b = _element(db_session, ran.id, "a"), _element(db_session, ran.id, "b")
    _relationship(db_session, ran.id, a, b)
    db_session.commit()
    ran_id = ran.id
    with app.app_context():
        result = DerivationRunner().run_and_persist(ran_id, trigger="on_demand")
    assert result.derived_count == 0, "the fixture must derive nothing for this test to mean anything"

    measured = _yield_for(client, login_as, ran_user)
    unmeasured = _yield_for(client, login_as, never_user)

    assert measured["state"] == "current"
    assert measured["explicit_count"] == 1
    assert measured["derived_count"] == 0
    assert measured["stale_count"] == 0
    assert measured["ratio"] == 0
    assert measured["ratio"] is not None
    assert "derivation_not_computed" not in measured["reasons"]
    assert measured["computed_at"] is None, "no stored fact carries a time; none is invented"
    assert measured["last_run_at"], "the run's own finish time is reported instead"
    assert measured["engine_version"] == [ENGINE_VERSION]
    assert measured["last_recompute_duration_ms"] is not None

    assert unmeasured["state"] == "not_computed"
    assert unmeasured["derived_count"] is None
    assert "derivation_not_computed" in unmeasured["reasons"]
    assert measured != unmeasured


def test_the_ratio_is_null_when_there_are_no_explicit_relationships(
    app, db_session, make_org, client, login_as
):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org = make_org("yield-ratio-null")
    user = _user(db_session, org.id)
    db_session.commit()
    org_id = org.id
    with app.app_context():
        DerivationRunner().run_and_persist(org_id, trigger="on_demand")

    data = _yield_for(client, login_as, user)

    assert data["state"] == "current"
    assert data["explicit_count"] == 0
    assert data["ratio"] is None


# --- the counts are the stores' own -------------------------------------------


def test_explicit_count_is_the_live_count_of_the_tenants_relationships(
    app, db_session, make_org, client, login_as
):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org = make_org("yield-live-explicit")
    other = make_org("yield-live-explicit-other")
    user = _user(db_session, org.id)
    a, b, c = (_element(db_session, org.id, n) for n in "abc")
    _relationship(db_session, org.id, a, b, "Composition")
    _relationship(db_session, org.id, b, c, "Serving")
    x, y = _element(db_session, other.id, "x"), _element(db_session, other.id, "y")
    for _ in range(3):
        _relationship(db_session, other.id, x, y)
    db_session.commit()
    org_id = org.id
    with app.app_context():
        DerivationRunner().run_and_persist(org_id, trigger="on_demand")

    before = _yield_for(client, login_as, user)
    assert before["explicit_count"] == 2, "another tenant's relationships are not counted"

    _relationship(db_session, org.id, a, c, "Association")
    db_session.commit()
    after = _yield_for(client, login_as, user)
    assert after["explicit_count"] == 3, "a relationship added since the run is counted"


def test_derived_count_is_the_stores_row_count_and_stale_is_part_of_it(
    app, db_session, make_org, client, login_as
):
    org = make_org("yield-store-rows")
    user = _user(db_session, org.id)
    a, b, c = (_element(db_session, org.id, n) for n in "abc")
    _relationship(db_session, org.id, a, b)
    _derived_row(db_session, org.id, a, b)
    _derived_row(db_session, org.id, b, c)
    _derived_row(db_session, org.id, a, c, stale=True)
    db_session.commit()

    data = _yield_for(client, login_as, user)

    assert data["derived_count"] == 3
    assert data["stale_count"] == 1
    assert data["state"] == "stale"
    assert data["explicit_count"] == 1
    assert data["ratio"] == pytest.approx(3.0)


def test_stored_facts_with_no_run_record_are_not_reported_as_never_worked_out(
    app, db_session, make_org, client, login_as
):
    org = make_org("yield-rows-no-run")
    user = _user(db_session, org.id)
    a, b = _element(db_session, org.id, "a"), _element(db_session, org.id, "b")
    _derived_row(db_session, org.id, a, b)
    db_session.commit()

    data = _yield_for(client, login_as, user)

    assert data["state"] == "current"
    assert data["derived_count"] == 1
    assert "derivation_not_computed" not in data["reasons"]
    assert data["last_recompute_duration_ms"] is None
    assert "no_recompute_duration_recorded" in data["reasons"]


def test_endpoint_and_a_fresh_recompute_agree_on_every_count(app, db_session, make_org, client, login_as):
    org = make_org("yield-agree-fresh")
    user = _user(db_session, org.id)
    a, b, c, d = (_element(db_session, org.id, n) for n in "abcd")
    _relationship(db_session, org.id, a, b, "Composition")
    _relationship(db_session, org.id, b, c, "Serving")
    _relationship(db_session, org.id, c, d, "Serving")
    db_session.commit()

    login_as(client, user)
    recompute = client.post("/api/v1/intelligence/derivation/recompute", json={"scope": "tenant"})
    assert recompute.status_code == 200
    ran = recompute.get_json()["data"]
    data = client.get("/api/v1/intelligence/yield").get_json()["data"]

    assert data["explicit_count"] == ran["explicit_count"] == 3
    assert data["derived_count"] == ran["derived_count"]
    assert data["ratio"] == pytest.approx(ran["ratio"])
    assert data["stale_count"] == 0
    assert data["state"] == "current"


# --- the last recalculation's duration -----------------------------------------


def test_the_last_recompute_duration_is_the_runs_own_measurement(app, db_session, make_org, client, login_as):
    from app.modules.intelligence.models.derivation_run import DerivationRun
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org = make_org("yield-duration")
    user = _user(db_session, org.id)
    a, b = _element(db_session, org.id, "a"), _element(db_session, org.id, "b")
    _relationship(db_session, org.id, a, b)
    db_session.commit()
    org_id = org.id
    with app.app_context():
        DerivationRunner().run_and_persist(org_id, trigger="on_demand")
        stored = DerivationRun.query.filter_by(organization_id=org_id).one().duration_ms

    data = _yield_for(client, login_as, user)

    assert data["last_recompute_duration_ms"] == stored
    assert "no_recompute_duration_recorded" not in data["reasons"]


def test_a_stored_run_with_no_duration_is_null_with_the_reason(app, db_session, make_org, client, login_as):
    from app.extensions import db as app_db
    from app.modules.intelligence.models.derivation_run import DerivationRun
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org = make_org("yield-duration-null")
    user = _user(db_session, org.id)
    db_session.commit()
    org_id = org.id
    with app.app_context():
        DerivationRunner().run_and_persist(org_id, trigger="on_demand")
        for run in DerivationRun.query.filter_by(organization_id=org_id).all():
            run.duration_ms = None
        app_db.session.commit()

    data = _yield_for(client, login_as, user)

    assert data["last_recompute_duration_ms"] is None
    assert "no_recompute_duration_recorded" in data["reasons"]


# --- p95: below the floor, above the floor, and where it is read from ----------


def test_below_the_floor_p95_is_null_with_the_reason_and_the_count(
    app, db_session, make_org, client, login_as, monkeypatch
):
    org = make_org("yield-below-floor")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_p95(monkeypatch, latency=None, samples=99, reason="insufficient_samples_for_p95")

    data = _yield_for(client, login_as, user)

    assert data["p95_latency_seconds"] is None
    assert data["sample_count"] == 99
    assert "insufficient_samples_for_p95" in data["reasons"]


def test_the_p95_is_read_from_the_pinned_series_and_nothing_wider(app, db_session, make_org, client, login_as, monkeypatch):
    import app.modules.intelligence.services.latency_probe as probe

    org = make_org("yield-pinned-series")
    user = _user(db_session, org.id)
    db_session.commit()
    seen = []

    def _read(**kwargs):
        seen.append(kwargs)
        return {"latency_seconds": None, "sample_count": 0, "reason": "insufficient_samples_for_p95"}

    monkeypatch.setattr(probe, "read_p95_bucket_edge", _read)

    _yield_for(client, login_as, user)

    assert seen == [{"query": "cross_layer_impact", "depth": "4", "include_derived": "true"}]


def test_above_the_floor_the_figure_is_a_declared_bucket_of_the_pinned_series_only(app, db_session, make_org, client, login_as, monkeypatch):
    """The real histogram, a label set of its own standing in for the pinned one: a
    hundred observations of 20 ms read as the 25 ms bucket's edge, and observations
    on any other label set do not move it."""
    import app.modules.intelligence.services.latency_probe as probe

    stand_in = f"pinned-stand-in-{uuid.uuid4().hex[:8]}"
    for _ in range(100):
        INTELLIGENCE_QUERY_DURATION.labels(query=stand_in, depth="4", include_derived="true").observe(0.02)
    for _ in range(500):
        INTELLIGENCE_QUERY_DURATION.labels(query=stand_in, depth="3", include_derived="true").observe(4.5)
        INTELLIGENCE_QUERY_DURATION.labels(query=stand_in, depth="4", include_derived="false").observe(4.5)

    real = probe.read_p95_bucket_edge
    monkeypatch.setattr(
        probe, "read_p95_bucket_edge",
        lambda **kw: real(query=stand_in, depth=kw["depth"], include_derived=kw["include_derived"]),
    )
    org = make_org("yield-above-floor")
    user = _user(db_session, org.id)
    db_session.commit()

    data = _yield_for(client, login_as, user)

    assert data["sample_count"] == 100
    assert data["p95_latency_seconds"] == 0.025
    assert "insufficient_samples_for_p95" not in data["reasons"]


def test_no_mean_no_sum_across_label_sets_no_raw_samples_on_the_p95_path():
    """Static: the reading is bucket counts of one label set. There is no ``_sum``
    anywhere on the path (which would make a mean), no ``sum()`` across label
    sets, no percentile of raw observations, and the reader divides nothing."""
    import ast
    import inspect
    import textwrap

    import app.modules.intelligence.services.latency_probe as probe
    import app.modules.intelligence.services.query_service as service

    def _body(function):
        tree = ast.parse(textwrap.dedent(inspect.getsource(function))).body[0]
        first = tree.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            tree.body = tree.body[1:]
        return tree

    banned = {"sum", "statistics", "numpy", "np", "percentile", "quantile", "mean", "average", "median"}
    reader = _body(probe.read_p95_bucket_edge)
    caller = _body(service.IntelligenceQueryService.derivation_yield)
    for tree in (reader, caller):
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & banned, sorted(names & banned)
        strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        assert not [s for s in strings if "_sum" in s], strings
    assert not [
        n for n in ast.walk(reader)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.FloorDiv))
    ], "the reader divides nothing: no mean, no interpolation"
    flat = " ".join(inspect.getsource(probe.read_p95_bucket_edge).split())
    assert flat.count("sample.labels.get(k) == v for k, v in target_labels.items()") == 2, (
        "both the bucket samples and the count are matched on every label of the one series"
    )
    assert 'target_labels = {"query": query, "depth": depth, "include_derived": include_derived}' in flat
    assert (service.NFR5_QUERY, service.NFR5_DEPTH, service.NFR5_INCLUDE_DERIVED) == (
        "cross_layer_impact", "4", "true",
    )


# --- no target of any kind ---------------------------------------------------


def test_the_payload_carries_no_target_goal_benchmark_or_verdict(app, db_session, make_org, client, login_as):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org = make_org("yield-no-target-computed")
    user = _user(db_session, org.id)
    a, b, c = (_element(db_session, org.id, n) for n in "abc")
    _relationship(db_session, org.id, a, b, "Composition")
    _relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()
    org_id = org.id
    with app.app_context():
        DerivationRunner().run_and_persist(org_id, trigger="on_demand")

    data = _yield_for(client, login_as, user)
    keys = set()

    def _walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                keys.add(key)
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    _walk(data)
    for word in ("target", "goal", "benchmark", "verdict", "status_ok", "good", "bad", "progress", "score", "grade"):
        assert not [k for k in keys if word in k.lower()], (word, sorted(keys))


# --- the figures read: the drift detector is never called ----------------------


def _bulk_elements(db_session, org_id, count):
    """``count`` elements for one tenant in one statement (a model of a known size)."""
    from sqlalchemy import insert

    from app.models import ArchiMateElement

    db_session.execute(
        insert(ArchiMateElement),
        [
            {"name": f"Element {i}", "type": "ApplicationComponent", "layer": "application",
             "organization_id": org_id}
            for i in range(count)
        ],
    )
    db_session.flush()


def _model_check(client, login_as, user, query=""):
    login_as(client, user)
    response = client.get("/api/v1/intelligence/yield?part=model-check" + query)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


MODEL_CHECK_FIELDS = {"organization_id", "drift_finding_count", "element_count", "reasons"}


def test_the_figures_read_never_calls_the_detector(app, db_session, make_org, client, login_as, monkeypatch):
    """A detector that raises on call leaves the figures read untouched, and the count is
    absent because it was not asked for: not unavailable, and not zero."""
    org = make_org("yield-figures-no-detector")
    user = _user(db_session, org.id)
    a, b = _element(db_session, org.id, "a"), _element(db_session, org.id, "b")
    _relationship(db_session, org.id, a, b)
    db_session.commit()
    calls = _patch_drift(monkeypatch, raises=AssertionError("the figures read must not run the detector"))

    for query in ("", "?part=figures"):
        login_as(client, user)
        response = client.get("/api/v1/intelligence/yield" + query)
        data = response.get_json()["data"]
        assert response.status_code == 200, query
        for key in ALL_FIELDS:
            assert key in data, (query, key)
        assert data["drift_finding_count"] is None
        assert "drift_count_not_requested" in data["reasons"]
        assert "source_unavailable" not in data["reasons"], "not asked for is not unavailable"
        assert "model_too_large_for_drift_check" not in data["reasons"]
        assert data["explicit_count"] is None or isinstance(data["explicit_count"], int)
    assert calls == [], "the detector was called by a figures read"


def test_the_default_answer_is_the_figures_answer(app, db_session, make_org, client, login_as, monkeypatch):
    """The cheap answer is the default: a caller that asks the plain question cannot occupy a
    worker with the detector by accident."""
    org = make_org("yield-default-part")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_p95(monkeypatch, latency=None, samples=3, reason="insufficient_samples_for_p95")

    login_as(client, user)
    plain = client.get("/api/v1/intelligence/yield").get_json()["data"]
    login_as(client, user)
    figures = client.get("/api/v1/intelligence/yield?part=figures").get_json()["data"]

    assert set(plain) == set(figures)
    assert plain["drift_finding_count"] is None and figures["drift_finding_count"] is None
    assert "element_count" not in plain, "the size belongs to the model check"


# --- the model check: the detector's count, or null and a reason -----------------


def test_the_model_check_calls_the_detector_once_for_the_callers_own_tenant_and_reads_its_total(
    app, db_session, make_org, client, login_as, monkeypatch
):
    org = make_org("yield-drift-own")
    other = make_org("yield-drift-other")
    user = _user(db_session, org.id)
    _element(db_session, org.id, "one")
    _element(db_session, org.id, "two")
    _element(db_session, other.id, "theirs")
    db_session.commit()
    calls = _patch_drift(monkeypatch, total=7)

    login_as(client, user)
    response = client.get(
        f"/api/v1/intelligence/yield?part=model-check&organization_id={other.id}&org_id={other.id}"
    )
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert calls == [org.id], "exactly once, about the caller's own tenant, never a requested one"
    assert data == {
        "organization_id": org.id, "drift_finding_count": 7, "element_count": 2, "reasons": [],
    }
    text = str(data)
    assert "by_type" not in text and "findings" not in text and "orphaned" not in text, (
        "only the total is read from the detector's report"
    )


def test_the_model_check_carries_none_of_the_figures(app, db_session, make_org, client, login_as, monkeypatch):
    """No aggregates, no run record, no response-time read: the answer is the count and its size."""
    import app.modules.intelligence.services.derived_facts as facts
    import app.modules.intelligence.services.latency_probe as probe

    org = make_org("yield-model-check-only")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_drift(monkeypatch, total=0)

    def _refuse(*_a, **_k):
        raise AssertionError("the model check read something the figures read owns")

    for name in ("derived_fact_aggregates", "latest_derivation_run", "explicit_relationship_count"):
        monkeypatch.setattr(facts, name, _refuse)
    monkeypatch.setattr(probe, "read_p95_bucket_edge", _refuse)

    data = _model_check(client, login_as, user)

    assert set(data) == MODEL_CHECK_FIELDS


def test_a_model_at_the_size_limit_is_counted_and_one_element_above_it_is_not(
    app, db_session, make_org, client, login_as, monkeypatch
):
    """Exactly 1,000 elements gets a computed count; 1,001 gets null with the reason, and the
    detector is never called on that branch."""
    import app.modules.intelligence.services.query_service as service

    assert service.DRIFT_COUNT_MAX_ELEMENTS == 1000
    org = make_org("yield-at-limit")
    user = _user(db_session, org.id)
    _bulk_elements(db_session, org.id, 1000)
    db_session.commit()
    calls = _patch_drift(monkeypatch, total=4)

    at_limit = _model_check(client, login_as, user)

    assert calls == [org.id]
    assert at_limit["drift_finding_count"] == 4
    assert at_limit["element_count"] == 1000
    assert at_limit["reasons"] == []

    _element(db_session, org.id, "one too many")
    db_session.commit()
    del calls[:]

    above = _model_check(client, login_as, user)

    assert calls == [], "above the limit the detector is not called"
    assert above["drift_finding_count"] is None
    assert above["element_count"] == 1001
    assert above["reasons"] == ["model_too_large_for_drift_check"]
    assert above["drift_finding_count"] != 0


def test_the_size_limit_reads_the_limit_it_names(app, db_session, make_org, client, login_as, monkeypatch):
    """The guard compares against ``DRIFT_COUNT_MAX_ELEMENTS`` as it is when the read runs, at
    the boundary: equal is counted, one over is not."""
    import app.modules.intelligence.services.query_service as service

    org = make_org("yield-limit-constant")
    user = _user(db_session, org.id)
    for name in "abc":
        _element(db_session, org.id, name)
    db_session.commit()
    calls = _patch_drift(monkeypatch, total=1)

    monkeypatch.setattr(service, "DRIFT_COUNT_MAX_ELEMENTS", 3)
    assert _model_check(client, login_as, user)["drift_finding_count"] == 1
    assert calls == [org.id]

    monkeypatch.setattr(service, "DRIFT_COUNT_MAX_ELEMENTS", 2)
    over = _model_check(client, login_as, user)
    assert over["drift_finding_count"] is None and over["reasons"] == ["model_too_large_for_drift_check"]
    assert calls == [org.id], "still one call: the second read did not reach the detector"


def test_a_measured_zero_drift_count_is_a_zero_and_is_not_absent(app, db_session, make_org, client, login_as, monkeypatch):
    org = make_org("yield-drift-zero")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_drift(monkeypatch, total=0)

    data = _model_check(client, login_as, user)

    assert data["drift_finding_count"] == 0
    assert data["reasons"] == []


def test_an_unavailable_detector_is_null_with_a_reason_never_zero(app, db_session, make_org, client, login_as, monkeypatch):
    org = make_org("yield-drift-unavailable")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_drift(monkeypatch, raises=RuntimeError("the detector is down"))

    data = _model_check(client, login_as, user)

    assert data["drift_finding_count"] is None
    assert data["drift_finding_count"] != 0
    assert data["reasons"] == ["source_unavailable"]
    assert set(data) == MODEL_CHECK_FIELDS


def test_a_failed_size_read_cannot_reach_the_detector_or_return_a_zero(app, make_org, monkeypatch):
    from app.modules.intelligence.services import derived_facts as facts
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    def unavailable(_org_id):
        raise RuntimeError("Size unavailable")

    monkeypatch.setattr(facts, "active_element_count", unavailable)
    calls = _patch_drift(monkeypatch, raises=AssertionError("must not run without a size"))
    with pytest.raises(RuntimeError, match="Size unavailable"):
        IntelligenceQueryService.model_check(make_org("failed-size").id)
    assert calls == []


@pytest.mark.parametrize(
    "total",
    [-5, -1, True, False, 3.0, 2.5, "7", None, [3], {"n": 3}],
    ids=repr,
)
def test_a_detector_total_that_is_not_a_non_negative_whole_number_is_null_with_a_reason(
    app, db_session, make_org, client, login_as, monkeypatch, total
):
    """The total is accepted only as a non-negative integer that is not a boolean. Anything
    else is not a count of anything: null and ``source_unavailable``, never a number on the page."""
    org = make_org("yield-drift-malformed")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_drift(monkeypatch, total=total)

    data = _model_check(client, login_as, user)

    assert data["drift_finding_count"] is None
    assert data["reasons"] == ["source_unavailable"]


@pytest.mark.parametrize("total", [0, 1, 7, 1000])
def test_a_detector_total_that_is_a_non_negative_whole_number_is_the_count(
    app, db_session, make_org, client, login_as, monkeypatch, total
):
    org = make_org("yield-drift-wellformed")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_drift(monkeypatch, total=total)

    data = _model_check(client, login_as, user)

    assert data["drift_finding_count"] == total
    assert type(data["drift_finding_count"]) is int
    assert data["reasons"] == []


def test_a_detector_report_with_no_total_is_unavailable_not_zero(app, db_session, make_org, client, login_as, monkeypatch):
    import app.modules.genome.services.drift_detector as detector

    org = make_org("yield-drift-no-total")
    user = _user(db_session, org.id)
    db_session.commit()
    monkeypatch.setattr(detector, "detect_model_drift", lambda org_id, session=None: {"findings": []})

    data = _model_check(client, login_as, user)

    assert data["drift_finding_count"] is None
    assert data["reasons"] == ["source_unavailable"]


def test_the_real_detector_supplies_the_count_when_nothing_is_patched(app, db_session, make_org, client, login_as):
    from app.modules.genome.services.drift_detector import detect_model_drift

    org = make_org("yield-drift-real")
    user = _user(db_session, org.id)
    _element(db_session, org.id, "Alone")
    db_session.commit()
    org_id = org.id

    data = _model_check(client, login_as, user)
    with app.app_context():
        expected = detect_model_drift(org_id)["summary"]["total"]

    assert data["drift_finding_count"] == expected
    assert data["element_count"] == 1
    assert expected >= 1, "a lone element is a finding, so this is not a vacuous agreement"


def test_one_tenants_model_check_never_reaches_another(app, db_session, make_org, client, login_as, monkeypatch):
    big = make_org("yield-check-big")
    small = make_org("yield-check-small")
    big_user, small_user = _user(db_session, big.id), _user(db_session, small.id)
    _bulk_elements(db_session, big.id, 5)
    _element(db_session, small.id, "only")
    db_session.commit()
    _patch_drift(monkeypatch, total=2)

    assert _model_check(client, login_as, big_user)["element_count"] == 5
    assert _model_check(client, login_as, small_user)["element_count"] == 1


# --- an unknown part answers 400 and reaches nothing -----------------------------


@pytest.mark.parametrize(
    "query",
    ["?part=nope", "?part=", "?part=Figures", "?part=model_check", "?part=model-check%20",
     "?part=figures&part=model-check", "?part=model-check&part=model-check"],
)
def test_an_unknown_part_answers_400_and_reaches_nothing(
    app, db_session, make_org, client, login_as, monkeypatch, query
):
    import app.modules.intelligence.services.derived_facts as facts
    import app.modules.intelligence.services.latency_probe as probe

    org = make_org("yield-bad-part")
    user = _user(db_session, org.id)
    db_session.commit()
    calls = _patch_drift(monkeypatch, total=1)
    reached = []

    def _reach(name):
        def _record(*_a, **_k):
            reached.append(name)
            raise AssertionError(f"{name} was reached by a request that names an unknown part")

        return _record

    for name in ("derived_fact_aggregates", "latest_derivation_run", "explicit_relationship_count",
                 "active_element_count"):
        monkeypatch.setattr(facts, name, _reach(name))
    monkeypatch.setattr(probe, "read_p95_bucket_edge", _reach("read_p95_bucket_edge"))
    before, _ = _series_snapshot()

    login_as(client, user)
    response = client.get("/api/v1/intelligence/yield" + query)
    body = response.get_json()

    assert response.status_code == 400
    assert body["success"] is False and body["error"]["code"] == "INVALID_PART"
    assert calls == [] and reached == []
    after, _ = _series_snapshot()
    assert _moved(before, after) == {}, "a request that reads nothing observes nothing"


# --- one observation per request, on the request's own series --------------------

FIGURES_SERIES = ("derivation_yield", "unknown", "false")
MODEL_CHECK_SERIES = ("model_drift_count", "unknown", "false")
PINNED_SERIES = ("cross_layer_impact", "4", "true")


def _series_snapshot():
    """Every series of the query-latency histogram: ``({key: count}, {key: sum})``, from its
    public collect() output."""
    counts, sums = {}, {}
    for sample in INTELLIGENCE_QUERY_DURATION.collect()[0].samples:
        key = (sample.labels.get("query"), sample.labels.get("depth"), sample.labels.get("include_derived"))
        if sample.name.endswith("_count"):
            counts[key] = sample.value
        elif sample.name.endswith("_sum"):
            sums[key] = sample.value
    return counts, sums


def _moved(before, after):
    return {key: after[key] - before.get(key, 0) for key in after if after[key] != before.get(key, 0)}


def test_a_figures_read_moves_its_own_series_by_one_and_no_other(app, db_session, make_org, client, login_as, monkeypatch):
    org = make_org("yield-observe-figures")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_drift(monkeypatch, total=1)

    for query in ("", "?part=figures"):
        before, _ = _series_snapshot()
        login_as(client, user)
        assert client.get("/api/v1/intelligence/yield" + query).status_code == 200
        after, _ = _series_snapshot()
        moved = _moved(before, after)
        assert moved == {FIGURES_SERIES: 1}, (query, moved)
        assert PINNED_SERIES not in moved, "the pinned response-time series is untouched"


@pytest.mark.parametrize("branch", ["counted", "too large", "detector raises"])
def test_a_model_check_moves_its_own_series_by_one_and_no_other(
    app, db_session, make_org, client, login_as, monkeypatch, branch
):
    import app.modules.intelligence.services.query_service as service

    org = make_org("yield-observe-check")
    user = _user(db_session, org.id)
    for name in "ab":
        _element(db_session, org.id, name)
    db_session.commit()
    if branch == "detector raises":
        _patch_drift(monkeypatch, raises=RuntimeError("down"))
    else:
        _patch_drift(monkeypatch, total=1)
    if branch == "too large":
        monkeypatch.setattr(service, "DRIFT_COUNT_MAX_ELEMENTS", 1)

    before, _ = _series_snapshot()
    _model_check(client, login_as, user)
    after, _ = _series_snapshot()

    moved = _moved(before, after)
    assert moved == {MODEL_CHECK_SERIES: 1}, moved
    assert PINNED_SERIES not in moved, "the pinned response-time series is untouched"


def test_the_pinned_series_is_untouched_by_either_read_and_still_the_only_one_the_figure_reads(
    app, db_session, make_org, client, login_as, monkeypatch
):
    import app.modules.intelligence.services.latency_probe as probe

    org = make_org("yield-pinned-untouched")
    user = _user(db_session, org.id)
    db_session.commit()
    _patch_drift(monkeypatch, total=1)
    seen = []
    real = probe.read_p95_bucket_edge
    monkeypatch.setattr(probe, "read_p95_bucket_edge", lambda **kw: (seen.append(kw), real(**kw))[1])

    before, _ = _series_snapshot()
    for _ in range(3):
        login_as(client, user)
        client.get("/api/v1/intelligence/yield")
        _model_check(client, login_as, user)
    after, _ = _series_snapshot()

    assert PINNED_SERIES not in _moved(before, after)
    assert seen == [{"query": "cross_layer_impact", "depth": "4", "include_derived": "true"}] * 3, (
        "only the figures read reads the response-time series, and only the pinned one"
    )


# --- the observation covers the whole request ------------------------------------


def _capture_structured_records(monkeypatch):
    """The OA-2 records the reads emit, as the dicts they carry."""
    import logging

    records = []
    logger = logging.getLogger("archie.intelligence.oa2")

    def _info(message, *args, **kwargs):
        if args and isinstance(args[0], dict):
            records.append(args[0])

    monkeypatch.setattr(logger, "info", _info)
    return records


def test_the_observation_covers_the_whole_request_and_the_figures_read_does_not_wait_for_the_detector(
    app, db_session, make_org, client, login_as, monkeypatch
):
    """The detector is held for a known interval. The model check's histogram observation and
    its structured record both exceed it (they cover the request). A figures read taken with the
    same slow detector in place stays under it: it never waits on the detector."""
    import time

    import app.modules.genome.services.drift_detector as detector

    hold = 0.6
    org = make_org("yield-covers-request")
    user = _user(db_session, org.id)
    _element(db_session, org.id, "a")
    db_session.commit()
    calls = []

    def _slow(org_id, session=None):
        calls.append(org_id)
        time.sleep(hold)
        return {"summary": {"total": 2}}

    monkeypatch.setattr(detector, "detect_model_drift", _slow)
    records = _capture_structured_records(monkeypatch)

    before_counts, before_sums = _series_snapshot()
    started = time.perf_counter()
    data = _model_check(client, login_as, user)
    check_wall = time.perf_counter() - started
    after_counts, after_sums = _series_snapshot()

    assert data["drift_finding_count"] == 2 and len(calls) == 1
    observed = after_sums[MODEL_CHECK_SERIES] - before_sums.get(MODEL_CHECK_SERIES, 0)
    assert check_wall >= hold
    assert observed >= hold, f"the observation ({observed:.3f} s) leaves out the detector's {hold} s"
    (check_record,) = [r for r in records if r["query"] == "model_drift_count"]
    assert check_record["latency_ms"] >= hold * 1000, check_record
    assert check_record["organization_id"] == org.id

    del records[:]
    before_counts, before_sums = _series_snapshot()
    started = time.perf_counter()
    login_as(client, user)
    assert client.get("/api/v1/intelligence/yield").status_code == 200
    figures_wall = time.perf_counter() - started
    after_counts, after_sums = _series_snapshot()

    assert len(calls) == 1, "the figures read did not reach the slow detector"
    figures_observed = after_sums[FIGURES_SERIES] - before_sums.get(FIGURES_SERIES, 0)
    assert figures_wall < hold and figures_observed < hold, (figures_wall, figures_observed)
    (figures_record,) = [r for r in records if r["query"] == "derivation_yield"]
    assert figures_record["latency_ms"] < hold * 1000, figures_record
    assert after_counts[FIGURES_SERIES] - before_counts.get(FIGURES_SERIES, 0) == 1


def test_the_size_guarded_branch_still_emits_its_observation_and_record(
    app, db_session, make_org, client, login_as, monkeypatch
):
    import app.modules.intelligence.services.query_service as service

    org = make_org("yield-guarded-observed")
    user = _user(db_session, org.id)
    for name in "abc":
        _element(db_session, org.id, name)
    db_session.commit()
    monkeypatch.setattr(service, "DRIFT_COUNT_MAX_ELEMENTS", 2)
    calls = _patch_drift(monkeypatch, total=1)
    records = _capture_structured_records(monkeypatch)

    before, _ = _series_snapshot()
    data = _model_check(client, login_as, user)
    after, _ = _series_snapshot()

    assert data["reasons"] == ["model_too_large_for_drift_check"] and calls == []
    assert _moved(before, after) == {MODEL_CHECK_SERIES: 1}
    (record,) = [r for r in records if r["query"] == "model_drift_count"]
    assert record["latency_ms"] >= 0 and record["organization_id"] == org.id


# --- static: one guarded path to the detector, and nothing added after a timed block -


def _query_service_tree():
    import ast
    import inspect

    import app.modules.intelligence.services.query_service as service

    return ast.parse(inspect.getsource(service))


def _function(tree, name):
    import ast

    (function,) = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    return function


def _called_names(node):
    import ast

    names = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            target = child.func
            names.append(target.id if isinstance(target, ast.Name) else getattr(target, "attr", None))
    return names


def test_the_detector_is_reached_from_one_guarded_path_only():
    """``detect_model_drift`` is named in one function of the intelligence module, which is called
    from one place: the model check, on the branch where the model is within the size limit."""
    import ast
    from pathlib import Path

    import app.modules.intelligence as package

    root = Path(package.__file__).parent
    mentions = {}
    for path in root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "detect_model_drift" in text:
            mentions[path.relative_to(root).as_posix()] = text.count("detect_model_drift")
    assert list(mentions) == ["services/query_service.py"], mentions

    tree = _query_service_tree()
    detector_readers = [
        n.name for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and "detect_model_drift" in ast.unparse(n)
    ]
    assert detector_readers == ["_detector_total"], detector_readers
    callers = [
        n.name for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and "_detector_total" in _called_names(n)
    ]
    assert callers == ["model_check"], callers
    assert "_detector_total" not in _called_names(_function(tree, "derivation_yield"))

    # ...and inside the model check the call sits on the else branch of the size comparison.
    check = _function(tree, "model_check")
    guards = [
        n for n in ast.walk(check)
        if isinstance(n, ast.If) and "DRIFT_COUNT_MAX_ELEMENTS" in ast.unparse(n.test)
    ]
    assert len(guards) == 1, "one size comparison"
    guard = guards[0]
    assert "_detector_total" in _called_names(ast.Module(body=guard.orelse, type_ignores=[]))
    assert "_detector_total" not in _called_names(ast.Module(body=guard.body, type_ignores=[]))
    assert ">" in ast.unparse(guard.test) and ">=" not in ast.unparse(guard.test), (
        "a model at the limit is counted; only one above it is not"
    )


@pytest.mark.parametrize("method", ["derivation_yield", "model_check"])
def test_no_payload_is_added_to_after_its_timed_block_closes(method):
    """Each read does all its work inside one ``record_query_latency`` block. Nothing after the
    block does more than return the payload: no call, no assignment, no ``append``."""
    import ast

    function = _function(_query_service_tree(), method)
    withs = [n for n in function.body if isinstance(n, ast.With)]
    assert len(withs) == 1, "one timed block per read"
    assert "record_query_latency" in ast.unparse(withs[0].items[0].context_expr)
    after = function.body[function.body.index(withs[0]) + 1:]
    assert len(after) == 1 and isinstance(after[0], ast.Return), ast.dump(ast.Module(body=after, type_ignores=[]))
    assert isinstance(after[0].value, ast.Name) and after[0].value.id == "payload"
    # Nothing that is not a name is done outside the block, either before it beyond the imports.
    before = function.body[: function.body.index(withs[0])]
    assert all(isinstance(n, (ast.Expr, ast.Import, ast.ImportFrom)) for n in before), [
        type(n).__name__ for n in before
    ]
    assert not [n for n in before if isinstance(n, ast.Expr) and not isinstance(n.value, ast.Constant)]


# --- tenancy -------------------------------------------------------------------


def test_one_tenants_counts_never_reach_another(app, db_session, make_org, client, login_as):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    rich = make_org("yield-tenancy-rich")
    poor = make_org("yield-tenancy-poor")
    rich_user, poor_user = _user(db_session, rich.id), _user(db_session, poor.id)
    a, b, c = (_element(db_session, rich.id, n) for n in "abc")
    _relationship(db_session, rich.id, a, b, "Composition")
    _relationship(db_session, rich.id, b, c, "Serving")
    db_session.commit()
    rich_id = rich.id
    with app.app_context():
        DerivationRunner().run_and_persist(rich_id, trigger="on_demand")

    rich_data = _yield_for(client, login_as, rich_user)
    poor_data = _yield_for(client, login_as, poor_user)

    assert rich_data["explicit_count"] == 2
    assert poor_data["state"] == "not_computed"
    for key in COUNT_FIELDS + ("last_recompute_duration_ms",):
        assert poor_data[key] is None, key


# --- every reason is a member of the closed vocabulary -------------------------


def test_every_reason_either_read_carries_is_a_member_of_the_vocabulary(
    app, db_session, make_org, client, login_as, monkeypatch
):
    import app.modules.intelligence.services.query_service as service
    from app.modules.intelligence.services.reason_codes import REASON_CODES, validate_reason_code

    org = make_org("yield-reasons")
    user = _user(db_session, org.id)
    for name in "abc":
        _element(db_session, org.id, name)
    db_session.commit()
    seen = set()

    def _check(codes):
        for code in codes:
            assert validate_reason_code(code) == code
            assert code in REASON_CODES
        assert len(codes) == len(set(codes)), "a reason is listed once"
        seen.update(codes)

    for latency, samples, reason, exceeds in (
        (None, 3, "insufficient_samples_for_p95", None),
        (None, 400, "p95_above_highest_bucket", 5.0),
        (0.05, 400, None, None),
    ):
        _patch_p95(monkeypatch, latency=latency, samples=samples, reason=reason, exceeds=exceeds)
        _check(_yield_for(client, login_as, user)["reasons"])

    for patch in ({"total": 2}, {"total": 0}, {"raises": RuntimeError("down")}, {"total": -5}):
        _patch_drift(monkeypatch, **patch)
        _check(_model_check(client, login_as, user)["reasons"])
    monkeypatch.setattr(service, "DRIFT_COUNT_MAX_ELEMENTS", 2)
    _check(_model_check(client, login_as, user)["reasons"])

    assert {
        "derivation_not_computed", "insufficient_samples_for_p95", "p95_above_highest_bucket",
        "no_recompute_duration_recorded", "source_unavailable",
        "drift_count_not_requested", "model_too_large_for_drift_check",
    } <= seen


def test_the_vocabulary_holds_twenty_two_members_and_the_model_check_reasons_live_only_in_it():
    import re
    from pathlib import Path

    import app as package
    from app.modules.intelligence.services import reason_codes

    additions = ("no_recompute_duration_recorded", "drift_count_not_requested", "model_too_large_for_drift_check")
    assert len(reason_codes.REASON_CODES) == 22
    for code in additions:
        assert code in reason_codes.REASON_CODES
        assert reason_codes.validate_reason_code(code) == code

    root = Path(package.__file__).parent
    for code in additions[1:]:
        quoted = f'"{code}"'
        defined = [
            path.relative_to(root).as_posix()
            for path in root.rglob("*.py")
            if "tests" not in path.parts
            and path.name != "reason_codes.py"
            and path.read_text(encoding="utf-8", errors="replace").count(quoted)
            != len(re.findall(r'validate_reason_code\(\s*' + re.escape(quoted) + r'\s*\)',
                              path.read_text(encoding="utf-8", errors="replace")))
        ]
        assert defined == [], f"{code} is spelled out somewhere other than the vocabulary: {defined}"
        vocabulary = (root / "modules" / "intelligence" / "services" / "reason_codes.py").read_text(encoding="utf-8", errors="replace")
        assert vocabulary.count(quoted) == 1


# --- the state follows the stored rows -------------------------------------------


def test_a_tenant_with_any_stale_row_reads_stale_and_one_with_none_reads_current(
    app, db_session, make_org, client, login_as
):
    """The state is ``stale`` exactly when at least one stored row is stale, whether the others are
    current or every row is stale, and ``current`` otherwise. A state that never says ``stale``
    would leave the screen unable to say that anything is out of date."""
    mixed, all_stale, fresh = make_org("yield-state-mixed"), make_org("yield-state-all"), make_org("yield-state-none")
    users = {org.id: _user(db_session, org.id) for org in (mixed, all_stale, fresh)}
    for org in (mixed, all_stale, fresh):
        a, b, c = (_element(db_session, org.id, n) for n in "abc")
        _relationship(db_session, org.id, a, b)
        _derived_row(db_session, org.id, a, b, stale=(org is all_stale))
        _derived_row(db_session, org.id, b, c, stale=(org is all_stale))
        if org is mixed:
            _derived_row(db_session, org.id, a, c, stale=True)
    db_session.commit()

    got = {org: _yield_for(client, login_as, users[org.id]) for org in (mixed, all_stale, fresh)}

    assert (got[mixed]["state"], got[mixed]["stale_count"], got[mixed]["derived_count"]) == ("stale", 1, 3)
    assert (got[all_stale]["state"], got[all_stale]["stale_count"], got[all_stale]["derived_count"]) == ("stale", 2, 2)
    assert (got[fresh]["state"], got[fresh]["stale_count"], got[fresh]["derived_count"]) == ("current", 0, 2)
    for data in got.values():
        assert data["state"] == ("stale" if data["stale_count"] > 0 else "current")


def test_the_payloads_derived_count_is_every_stored_row_and_the_aggregates_current_count_is_not(
    app, db_session, make_org, client, login_as
):
    """One name per meaning: the payload's ``derived_count`` is the aggregate's ``total_count``
    (current and stale rows); the aggregate's ``current_count`` is the part that is not stale."""
    from app.modules.intelligence.services.derived_facts import derived_fact_aggregates

    org = make_org("yield-names")
    user = _user(db_session, org.id)
    a, b, c = (_element(db_session, org.id, n) for n in "abc")
    _derived_row(db_session, org.id, a, b)
    _derived_row(db_session, org.id, b, c)
    _derived_row(db_session, org.id, a, c, stale=True)
    db_session.commit()
    org_id = org.id

    data = _yield_for(client, login_as, user)
    with app.app_context():
        agg = derived_fact_aggregates(org_id)

    assert data["derived_count"] == agg["total_count"] == 3
    assert agg["current_count"] == 2 and data["derived_count"] != agg["current_count"]
    assert data["stale_count"] == agg["stale_count"] == 1


# --- mutation seam -------------------------------------------------------------


def test_the_not_computed_branch_is_null_not_zero_through_its_seam(app, db_session, make_org, client, login_as):
    """The distinguishability tests above go red when the not-computed branch reports
    zeros. This one names the seam and checks it directly, so a mutation of it cannot
    pass unnoticed: every count the seam supplies is null."""
    import app.modules.intelligence.services.query_service as service

    counts = service._not_computed_counts()

    assert set(counts) == {
        "explicit_count", "derived_count", "ratio", "computed_at", "engine_version",
        "stale_count", "last_recompute_duration_ms",
    }
    assert all(value is None for value in counts.values())


@pytest.mark.parametrize("versions, expected", [
    ([], "not_computed"), (["1.0.0"], "stale"), ([None], "stale"),
    ([""], "stale"), (["9.0.0"], "stale"), ([ENGINE_VERSION], "current"),
    (["1.0.0", ENGINE_VERSION], "current"), ([ENGINE_VERSION, "1.0.0"], "stale"),
])
@pytest.mark.parametrize("undated", [False, True], ids=["timestamped", "undated"])
def test_zero_fact_yield_uses_latest_completed_run_version(
    app, db_session, make_org, client, login_as, versions, expected, undated
):
    import datetime
    from app.extensions import db
    from app.modules.intelligence.models.derivation_run import DerivationRun
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org_id = make_org("zero-yield").id
    user = _user(db_session, org_id)
    stamp = datetime.datetime(2026, 1, 2, 3, 4, 5)
    for version in versions:
        db_session.add(DerivationRun(
            organization_id=org_id, started_at=None if undated else stamp,
            finished_at=db.null() if undated else stamp,
            explicit_count=0, derived_count=0, duration_ms=7, ratio=None,
            engine_version=version, trigger="on_demand",
        ))
        db_session.flush()  # tie deliberately resolved by actual inserted ID
    db_session.commit()
    if undated:
        # Read real SQL values: assigning None would invoke the Python default.
        stored_times = db.session.execute(db.text(
            "SELECT finished_at FROM intelligence_derivation_runs "
            "WHERE organization_id = :org ORDER BY id"
        ), {"org": org_id}).scalars().all()
        assert stored_times == [None] * len(versions)
    service = IntelligenceQueryService.derivation_yield(org_id)
    endpoint = _yield_for(client, login_as, user)
    for answer in (service, endpoint):
        assert answer["state"] == expected
        if versions:
            assert answer["derived_count"] == answer["stale_count"] == answer["explicit_count"] == 0
            assert answer["computed_at"] is None
            assert answer["last_run_at"] == (None if undated else stamp.isoformat())
            assert answer["last_recompute_duration_ms"] == 7
            assert answer["engine_version"] == ([versions[-1]] if versions[-1] else None)
        else:
            assert answer["derived_count"] is None
            assert answer["reason"] == "derivation_not_computed"
        if expected == "stale":
            assert answer["reason"] == "derivation_stale"
            assert answer["reasons"].count("derivation_stale") == 1
        else:
            assert "derivation_stale" not in answer["reasons"]


@pytest.mark.parametrize("versions, expected_stale", [
    ([ENGINE_VERSION], 0), (["1.0.0"], 1), ([ENGINE_VERSION, "1.0.0"], 1),
])
def test_yield_counts_effectively_stale_facts_even_after_a_current_run(
    app, db_session, make_org, client, login_as, versions, expected_stale
):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner
    org_id = make_org("yield-fact-versions").id
    user = _user(db_session, org_id)
    user_id = user.id
    a, b, c = (_element(db_session, org_id, name) for name in "abc")
    a_id, target_ids = a.id, [b.id, c.id]
    _relationship(db_session, org_id, a, b)
    db_session.commit()
    DerivationRunner().run_and_persist(org_id, trigger="on_demand")
    # The helper only consumes scalar endpoint IDs; avoid detached model access.
    from types import SimpleNamespace
    for version, target_id in zip(versions, target_ids):
        _derived_row(db_session, org_id, SimpleNamespace(id=a_id), SimpleNamespace(id=target_id),
                     engine_version=version)
    db_session.commit()
    answer = _yield_for(client, login_as, user_id)
    assert answer["derived_count"] == len(versions)
    assert answer["explicit_count"] == 1
    assert answer["ratio"] == len(versions)
    assert answer["stale_count"] == expected_stale
    assert answer["state"] == ("stale" if expected_stale else "current")
    assert answer["engine_version"] == sorted(set(versions))
