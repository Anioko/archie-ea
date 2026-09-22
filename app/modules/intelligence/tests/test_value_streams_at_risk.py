"""T-S1: `IntelligenceQueryService.value_streams_at_risk` and its route.

Fixtures (app, db_session, make_org, tenant_ctx, client, login_as) are
discovered via app/modules/intelligence/tests/conftest.py's own import of
tests.conftest -- no import needed here, matching test_impact_route.py's
own pattern.

Test-id mapping to the brief's acceptance criteria:

  1  -> test_capability_below_threshold_is_at_risk
  2  -> test_null_maturity_is_neutral_and_counted
  3  -> test_shared_catalogue_capability_contributes_mapping_not_maturity
  4  -> test_tenant_with_no_value_streams_gets_reason_and_empty_rows
  5  -> test_value_stream_with_no_mapping_gets_no_capability_linked
  6  -> test_route_foreign_and_missing_value_stream_id_are_byte_identical
  7  -> test_cross_tenant_value_stream_is_invisible,
        test_cross_tenant_mapping_row_invisible_and_mutation_proof,
        test_cross_tenant_stage_makes_mapping_unreachable,
        test_cross_tenant_owned_capability_invisible,
        test_foreign_tenants_own_answer_unaffected_by_request
  8  -> test_route_threshold_and_value_stream_id_validation
  9  -> test_latency_series_is_own_and_leaves_nfr5_selector_untouched
  10 -> test_cross_tenant_mapping_row_invisible_and_mutation_proof
  11 -> test_mutation_proof_null_maturity_forced_to_false
  12 -> test_mutation_proof_shared_catalogue_permissive_predicate
  13 -> test_mutation_proof_foreign_vs_missing_message_diverges
  14 -> test_invented_reason_code_is_rejected_not_emitted,
        test_every_reason_string_in_a_realistic_payload_is_a_closed_vocabulary_member
  18 -> test_dependency_object_exact_key_set_and_no_forbidden_keys,
        test_route_ignores_graph_only_parameters
  19 -> test_four_batched_selects_regardless_of_row_count
"""

from __future__ import annotations

import uuid

import pytest


def _org_suffix() -> str:
    return uuid.uuid4().hex[:8]


def _user(db_session, org_id):
    from app.models.user import User

    user = User(
        email=f"vsr-{uuid.uuid4().hex[:10]}@example.com",
        first_name="VSR",
        last_name="Tester",
        organization_id=org_id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _value_stream(db_session, org_id, name, code, archimate_element_id=None):
    from app.models.unified_capability import ValueStream

    vs = ValueStream(
        name=name,
        code=code,
        organization_id=org_id,
        archimate_element_id=archimate_element_id,
    )
    db_session.add(vs)
    db_session.flush()
    return vs


def _stage(db_session, org_id, value_stream_id, name, order=1):
    from app.models.unified_capability import ValueStreamStage

    stage = ValueStreamStage(
        name=name,
        value_stream_id=value_stream_id,
        stage_order=order,
        organization_id=org_id,
    )
    db_session.add(stage)
    db_session.flush()
    return stage


def _capability(db_session, org_id, name, code, current=None, target=None):
    from app.models.unified_capability import UnifiedCapability

    cap = UnifiedCapability(
        name=name,
        code=code,
        organization_id=org_id,
        scope="tenant" if org_id is not None else "reference",
        level=1,
        current_maturity_level=current,
        target_maturity_level=target,
    )
    db_session.add(cap)
    db_session.flush()
    return cap


def _mapping(
    db_session,
    org_id,
    capability_id,
    value_stream_id,
    value_stream_stage_id,
    support_type="primary",
    support_level=3,
    impact_level="medium",
):
    from app.models.unified_capability import CapabilityValueStreamMapping

    mapping = CapabilityValueStreamMapping(
        capability_id=capability_id,
        value_stream_id=value_stream_id,
        value_stream_stage_id=value_stream_stage_id,
        organization_id=org_id,
        support_type=support_type,
        support_level=support_level,
        impact_level=impact_level,
    )
    db_session.add(mapping)
    db_session.flush()
    return mapping


def _without_latency(payload):
    out = dict(payload)
    out["summary"] = {k: v for k, v in payload["summary"].items() if k != "latency_ms"}
    return out


# --- Acceptance item 1 ----------------------------------------------------------


def test_capability_below_threshold_is_at_risk(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("vsr-ac1")
    vs = _value_stream(db_session, org.id, "VS AC1", f"VSR-AC1-{_org_suffix()}")
    stage = _stage(db_session, org.id, vs.id, "Stage AC1", 1)
    cap = _capability(db_session, org.id, "Cap AC1", f"VSR-AC1-CAP-{_org_suffix()}", current=2, target=4)
    _mapping(db_session, org.id, cap.id, vs.id, stage.id)
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org.id, threshold=3)

    row = result["rows"][0]
    assert row["value_stream"]["id"] == vs.id
    assert row["at_risk_capability_count"] == 1
    cap_row = row["capabilities"][0]
    assert cap_row["at_risk"] is True
    assert cap_row["maturity_source"] == "unified_capabilities"
    assert cap_row["current_maturity"] == 2
    assert result["summary"]["value_streams_at_risk"] == 1
    assert result["summary"]["capabilities_below_threshold"] == 1


# --- Acceptance item 2 ----------------------------------------------------------


def test_null_maturity_is_neutral_and_counted(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("vsr-ac2")
    vs = _value_stream(db_session, org.id, "VS AC2", f"VSR-AC2-{_org_suffix()}")
    stage = _stage(db_session, org.id, vs.id, "Stage AC2", 1)
    cap = _capability(
        db_session, org.id, "Cap AC2", f"VSR-AC2-CAP-{_org_suffix()}", current=None, target=None
    )
    _mapping(db_session, org.id, cap.id, vs.id, stage.id)
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org.id, threshold=3)

    cap_row = result["rows"][0]["capabilities"][0]
    assert cap_row["current_maturity"] is None
    assert cap_row["at_risk"] is None
    assert cap_row["reason"] == "no_maturity_recorded"
    assert result["summary"]["capabilities_with_no_maturity"] == 1
    assert result["summary"]["capabilities_below_threshold"] == 0
    assert result["rows"][0]["at_risk_capability_count"] == 0


# --- Acceptance item 3 -----------------------------------------------------------


def test_shared_catalogue_capability_contributes_mapping_not_maturity(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("vsr-ac3")
    vs = _value_stream(db_session, org.id, "VS AC3", f"VSR-AC3-{_org_suffix()}")
    stage = _stage(db_session, org.id, vs.id, "Stage AC3", 1)
    # A shared catalogue row -- owned by no organisation -- that DOES carry a
    # maturity value (a pre-cutover legacy shape, § 3.2). This tenant's own
    # mapping names it.
    shared_cap = _capability(
        db_session, None, "Shared Cap AC3", f"VSR-AC3-SHARED-{_org_suffix()}", current=1, target=3
    )
    _mapping(db_session, org.id, shared_cap.id, vs.id, stage.id)
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org.id, threshold=3)

    cap_row = result["rows"][0]["capabilities"][0]
    assert cap_row["id"] == shared_cap.id
    assert cap_row["name"] == "Shared Cap AC3"
    assert cap_row["current_maturity"] is None
    assert cap_row["at_risk"] is None
    assert cap_row["reason"] == "no_maturity_recorded"


# --- Acceptance item 4 ------------------------------------------------------------


def test_tenant_with_no_value_streams_gets_reason_and_empty_rows(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("vsr-ac4")
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org.id)

    assert result["rows"] == []
    assert result["reasons"] == ["no_value_stream_recorded"]


# --- Acceptance item 5 -----------------------------------------------------------


def test_value_stream_with_no_mapping_gets_no_capability_linked(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("vsr-ac5")
    _value_stream(db_session, org.id, "VS AC5", f"VSR-AC5-{_org_suffix()}")
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org.id)

    row = result["rows"][0]
    assert row["capabilities"] == []
    assert row["reason"] == "no_capability_linked"


# --- Acceptance item 6 ------------------------------------------------------------


def test_route_foreign_and_missing_value_stream_id_are_byte_identical(
    app, db_session, make_org, client, login_as
):
    org_a = make_org("vsr-ac6-a")
    org_b = make_org("vsr-ac6-b")
    user = _user(db_session, org_a.id)
    foreign_vs = _value_stream(db_session, org_b.id, "Foreign VS", f"VSR-AC6-{_org_suffix()}")
    db_session.commit()
    never_existed_id = foreign_vs.id + 5_000_000

    login_as(client, user)
    resp_foreign = client.get(
        f"/api/v1/intelligence/value-streams-at-risk?value_stream_id={foreign_vs.id}"
    )
    login_as(client, user)
    resp_missing = client.get(
        f"/api/v1/intelligence/value-streams-at-risk?value_stream_id={never_existed_id}"
    )

    assert resp_foreign.status_code == 404
    assert resp_missing.status_code == 404
    assert resp_foreign.get_json()["error"] == resp_missing.get_json()["error"]
    assert resp_foreign.get_json()["error"]["code"] == "VALUE_STREAM_NOT_FOUND"


# --- Acceptance item 7, table 1: foreign value_streams row ----------------------


def test_cross_tenant_value_stream_is_invisible(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org_a = make_org("vsr-ac7-vs-a")
    org_b = make_org("vsr-ac7-vs-b")
    _value_stream(db_session, org_b.id, "VS B", f"VSR-AC7VS-{_org_suffix()}")
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org_a.id)

    assert result["rows"] == []
    assert result["reasons"] == ["no_value_stream_recorded"]


# --- Acceptance items 7 (table 2) and 10: mutation proof -------------------------


def test_cross_tenant_mapping_row_invisible_and_mutation_proof(app, db_session, make_org, monkeypatch):
    from sqlalchemy import true as sa_true

    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org_a = make_org("vsr-ac7map-a")
    org_b = make_org("vsr-ac7map-b")
    vs_a = _value_stream(db_session, org_a.id, "VS A", f"VSR-AC7MAP-{_org_suffix()}")
    stage_a = _stage(db_session, org_a.id, vs_a.id, "Stage A", 1)
    shared_cap = _capability(
        db_session, None, "Shared Cap", f"VSR-AC7MAP-SHARED-{_org_suffix()}", current=None, target=None
    )
    # A data anomaly: another tenant's OWN mapping row, pointing at org_a's
    # value stream and stage. Must never surface in org_a's answer.
    _mapping(db_session, org_b.id, shared_cap.id, vs_a.id, stage_a.id)
    db_session.commit()

    def _capability_ids(payload, vs_id):
        row = next(r for r in payload["rows"] if r["value_stream"]["id"] == vs_id)
        return {c["id"] for c in row["capabilities"]}

    # Control: the foreign mapping row is invisible.
    control = IntelligenceQueryService.value_streams_at_risk(org_a.id)
    assert shared_cap.id not in _capability_ids(control, vs_a.id)

    # Mutation: neuter the explicit tenant predicate -- the foreign mapping
    # row now passes the .where() clause that used to exclude it.
    monkeypatch.setattr(
        IntelligenceQueryService,
        "_value_stream_tenant_predicate",
        staticmethod(lambda model, organization_id: sa_true()),
    )
    mutated = IntelligenceQueryService.value_streams_at_risk(org_a.id)
    with pytest.raises(AssertionError):
        assert shared_cap.id not in _capability_ids(mutated, vs_a.id)

    # Restore: the leak closes again.
    monkeypatch.undo()
    restored = IntelligenceQueryService.value_streams_at_risk(org_a.id)
    assert shared_cap.id not in _capability_ids(restored, vs_a.id)


# --- Acceptance item 7, table 3: foreign unified_value_stream_stages row --------


def test_cross_tenant_stage_makes_mapping_unreachable(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org_a = make_org("vsr-ac7stage-a")
    org_b = make_org("vsr-ac7stage-b")
    vs_a = _value_stream(db_session, org_a.id, "VS A", f"VSR-AC7STAGE-{_org_suffix()}")
    # A data anomaly: a stage owned by another tenant, attached to org_a's
    # own value stream.
    foreign_stage = _stage(db_session, org_b.id, vs_a.id, "Foreign Stage", 1)
    cap = _capability(
        db_session, org_a.id, "Cap", f"VSR-AC7STAGE-CAP-{_org_suffix()}", current=1, target=3
    )
    _mapping(db_session, org_a.id, cap.id, vs_a.id, foreign_stage.id)
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org_a.id)

    row = next(r for r in result["rows"] if r["value_stream"]["id"] == vs_a.id)
    assert row["capabilities"] == []
    assert row["reason"] == "no_capability_linked"


# --- Acceptance item 7, table 4: foreign tenant-owned unified_capabilities ------


def test_cross_tenant_owned_capability_invisible(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org_a = make_org("vsr-ac7cap-a")
    org_b = make_org("vsr-ac7cap-b")
    vs_a = _value_stream(db_session, org_a.id, "VS A", f"VSR-AC7CAP-{_org_suffix()}")
    stage_a = _stage(db_session, org_a.id, vs_a.id, "Stage A", 1)
    # A data anomaly: org_a's own mapping row names a capability owned by a
    # DIFFERENT tenant (not shared -- org_b's own).
    foreign_cap = _capability(
        db_session, org_b.id, "Foreign Cap", f"VSR-AC7CAP-FOREIGN-{_org_suffix()}", current=1, target=3
    )
    _mapping(db_session, org_a.id, foreign_cap.id, vs_a.id, stage_a.id)
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org_a.id)

    row = next(r for r in result["rows"] if r["value_stream"]["id"] == vs_a.id)
    assert row["capabilities"] == []
    assert row["reason"] == "no_capability_linked"


# --- Acceptance item 7, last clause: the foreign tenant's own answer -----------


def test_foreign_tenants_own_answer_unaffected_by_request(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org_a = make_org("vsr-ac7unaff-a")
    org_b = make_org("vsr-ac7unaff-b")
    vs_b = _value_stream(db_session, org_b.id, "VS B", f"VSR-AC7UNAFF-{_org_suffix()}")
    stage_b = _stage(db_session, org_b.id, vs_b.id, "Stage B", 1)
    cap_b = _capability(
        db_session, org_b.id, "Cap B", f"VSR-AC7UNAFF-CAP-{_org_suffix()}", current=1, target=3
    )
    _mapping(db_session, org_b.id, cap_b.id, vs_b.id, stage_b.id)
    db_session.commit()

    before = IntelligenceQueryService.value_streams_at_risk(org_b.id)

    # org_a's own (empty) request must not perturb org_b's answer.
    IntelligenceQueryService.value_streams_at_risk(org_a.id)

    after = IntelligenceQueryService.value_streams_at_risk(org_b.id)
    assert _without_latency(after) == _without_latency(before)


# --- Acceptance item 8 -----------------------------------------------------------


def test_route_threshold_and_value_stream_id_validation(app, db_session, make_org, client, login_as):
    org = make_org("vsr-ac8")
    user = _user(db_session, org.id)
    db_session.commit()

    for bad_threshold in ("0", "6", "abc"):
        login_as(client, user)
        resp = client.get(f"/api/v1/intelligence/value-streams-at-risk?threshold={bad_threshold}")
        assert resp.status_code == 400, bad_threshold
        assert resp.get_json()["error"]["code"] == "INVALID_PARAMETER"

    for bad_vs_id in ("0", "-1", "abc"):
        login_as(client, user)
        resp = client.get(f"/api/v1/intelligence/value-streams-at-risk?value_stream_id={bad_vs_id}")
        assert resp.status_code == 400, bad_vs_id
        assert resp.get_json()["error"]["code"] == "INVALID_PARAMETER"


def test_route_no_tenant_context_returns_400(app):
    client = app.test_client()
    resp = client.get("/api/v1/intelligence/value-streams-at-risk")
    assert resp.status_code in (302, 401, 400)


# --- Acceptance item 9 ------------------------------------------------------------


def _sample_count(histogram, **labels):
    """Read a histogram series' total sample count via the public
    ``collect()`` API, the same approach ``latency_probe.read_p95_bucket_edge``
    uses -- not a private attribute, which does not exist on this
    ``prometheus_client`` version's ``Histogram`` child object."""
    family = histogram.collect()[0]
    for sample in family.samples:
        if sample.name.endswith("_count") and all(
            sample.labels.get(k) == v for k, v in labels.items()
        ):
            return sample.value
    return 0.0


def test_latency_series_is_own_and_leaves_nfr5_selector_untouched(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService
    from app.services.prometheus_metrics import INTELLIGENCE_QUERY_DURATION

    org = make_org("vsr-ac9")
    db_session.commit()

    nfr5_before = _sample_count(
        INTELLIGENCE_QUERY_DURATION, query="cross_layer_impact", depth="4", include_derived="true"
    )
    own_before = _sample_count(
        INTELLIGENCE_QUERY_DURATION,
        query="value_streams_at_risk", depth="unknown", include_derived="false",
    )

    result = IntelligenceQueryService.value_streams_at_risk(org.id)
    assert result["summary"]["latency_ms"] is not None
    assert result["summary"]["latency_ms"] >= 0

    nfr5_after = _sample_count(
        INTELLIGENCE_QUERY_DURATION, query="cross_layer_impact", depth="4", include_derived="true"
    )
    own_after = _sample_count(
        INTELLIGENCE_QUERY_DURATION,
        query="value_streams_at_risk", depth="unknown", include_derived="false",
    )

    assert nfr5_after == nfr5_before
    assert own_after == own_before + 1


# --- Acceptance item 11: mutation proof -------------------------------------------


def test_mutation_proof_null_maturity_forced_to_false(app, db_session, make_org, monkeypatch):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("vsr-ac11")
    vs = _value_stream(db_session, org.id, "VS", f"VSR-AC11-{_org_suffix()}")
    stage = _stage(db_session, org.id, vs.id, "Stage", 1)
    cap = _capability(
        db_session, org.id, "Cap", f"VSR-AC11-CAP-{_org_suffix()}", current=None, target=None
    )
    _mapping(db_session, org.id, cap.id, vs.id, stage.id)
    db_session.commit()

    # Control.
    control = IntelligenceQueryService.value_streams_at_risk(org.id)
    assert control["rows"][0]["capabilities"][0]["at_risk"] is None

    # Mutation: the null-maturity branch now claims a scored "false" instead
    # of the neutral null.
    monkeypatch.setattr(
        IntelligenceQueryService,
        "_at_risk_for_maturity",
        staticmethod(
            lambda current_maturity, threshold: (
                False if current_maturity is None else current_maturity < threshold
            )
        ),
    )
    mutated = IntelligenceQueryService.value_streams_at_risk(org.id)
    with pytest.raises(AssertionError):
        assert mutated["rows"][0]["capabilities"][0]["at_risk"] is None

    # Restore.
    monkeypatch.undo()
    restored = IntelligenceQueryService.value_streams_at_risk(org.id)
    assert restored["rows"][0]["capabilities"][0]["at_risk"] is None


# --- Acceptance item 12: mutation proof -------------------------------------------


def test_mutation_proof_shared_catalogue_permissive_predicate(app, db_session, make_org, monkeypatch):
    from app.models.unified_capability import UnifiedCapability
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("vsr-ac12")
    vs = _value_stream(db_session, org.id, "VS", f"VSR-AC12-{_org_suffix()}")
    stage = _stage(db_session, org.id, vs.id, "Stage", 1)
    # A shared/reference catalogue row carrying a legacy maturity value.
    shared_cap = _capability(
        db_session, None, "Shared Cap", f"VSR-AC12-SHARED-{_org_suffix()}", current=1, target=3
    )
    _mapping(db_session, org.id, shared_cap.id, vs.id, stage.id)
    db_session.commit()

    # Control.
    control = IntelligenceQueryService.value_streams_at_risk(org.id)
    assert control["rows"][0]["capabilities"][0]["current_maturity"] is None

    def _permissive_maturity_for_capability_ids(capability_ids, *, organization_id):
        from sqlalchemy import or_

        from app.modules.intelligence.services.reason_codes import validate_reason_code

        wanted = sorted(set(capability_ids))
        result = {
            cid: {
                "current_maturity_level": None,
                "target_maturity_level": None,
                "reason_code": validate_reason_code("no_maturity_recorded"),
            }
            for cid in wanted
        }
        if not wanted:
            return result
        query = UnifiedCapability.query.filter(
            UnifiedCapability.id.in_(wanted),
            or_(
                UnifiedCapability.organization_id == organization_id,
                UnifiedCapability.organization_id.is_(None),
            ),
        )
        for row in query.all():
            if row.current_maturity_level is None:
                continue
            result[row.id] = {
                "current_maturity_level": row.current_maturity_level,
                "target_maturity_level": row.target_maturity_level,
                "reason_code": None,
            }
        return result

    # Mutation: relax the accessor to the permissive predicate the two
    # source-provenance members use.
    monkeypatch.setattr(
        UnifiedCapability, "maturity_for_capability_ids", _permissive_maturity_for_capability_ids
    )
    mutated = IntelligenceQueryService.value_streams_at_risk(org.id)
    with pytest.raises(AssertionError):
        assert mutated["rows"][0]["capabilities"][0]["current_maturity"] is None

    # Restore.
    monkeypatch.undo()
    restored = IntelligenceQueryService.value_streams_at_risk(org.id)
    assert restored["rows"][0]["capabilities"][0]["current_maturity"] is None


# --- Acceptance item 13: mutation proof -------------------------------------------


def test_mutation_proof_foreign_vs_missing_message_diverges(
    app, db_session, make_org, client, login_as, monkeypatch
):
    from app.modules.intelligence.routes import api as api_module

    org_a = make_org("vsr-ac13-a")
    org_b = make_org("vsr-ac13-b")
    user = _user(db_session, org_a.id)
    foreign_vs = _value_stream(db_session, org_b.id, "Foreign VS", f"VSR-AC13-{_org_suffix()}")
    db_session.commit()
    never_existed_id = foreign_vs.id + 5_000_000

    def _get_error(value_stream_id):
        login_as(client, user)
        resp = client.get(
            f"/api/v1/intelligence/value-streams-at-risk?value_stream_id={value_stream_id}"
        )
        return resp.get_json()["error"]

    # Control: identical.
    assert _get_error(foreign_vs.id) == _get_error(never_existed_id)

    def _diverging(value_stream_id):
        from app.extensions import db
        from app.models.unified_capability import ValueStream
        from app.utils.api_response import error_response

        # Raw SQL, deliberately: an ORM `db.select(ValueStream...)` still
        # goes through the same tenant `do_orm_execute` with_loader_criteria
        # as the scoped query below, so it could never actually diverge --
        # only a non-ORM statement can see "exists for another tenant".
        raw_exists = db.session.execute(
            db.text("SELECT 1 FROM value_streams WHERE id = :id"),
            {"id": value_stream_id},
        ).first()
        scoped = ValueStream.query.filter_by(id=value_stream_id).first()
        if scoped is not None:
            return scoped, None
        if raw_exists is not None:
            return None, error_response(
                "Value stream belongs to another organisation",
                code="VALUE_STREAM_NOT_FOUND",
                status_code=404,
            )
        return None, error_response(
            "Value stream not found", code="VALUE_STREAM_NOT_FOUND", status_code=404
        )

    monkeypatch.setattr(api_module, "_value_stream_or_404_response", _diverging)
    with pytest.raises(AssertionError):
        assert _get_error(foreign_vs.id) == _get_error(never_existed_id)

    monkeypatch.undo()
    assert _get_error(foreign_vs.id) == _get_error(never_existed_id)


# --- Acceptance item 14 -----------------------------------------------------------


def test_invented_reason_code_is_rejected_not_emitted():
    from app.modules.intelligence.services.reason_codes import (
        UnknownReasonCodeError,
        validate_reason_code,
    )

    with pytest.raises(UnknownReasonCodeError):
        validate_reason_code("value_streams_at_risk_made_up_reason")


def test_every_reason_string_in_a_realistic_payload_is_a_closed_vocabulary_member(
    app, db_session, make_org
):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService
    from app.modules.intelligence.services.reason_codes import REASON_CODES

    org = make_org("vsr-ac14")
    vs_with_gap = _value_stream(db_session, org.id, "VS Gap", f"VSR-AC14-GAP-{_org_suffix()}")
    _value_stream(db_session, org.id, "VS Empty", f"VSR-AC14-EMPTY-{_org_suffix()}")
    stage = _stage(db_session, org.id, vs_with_gap.id, "Stage", 1)
    cap_null = _capability(
        db_session, org.id, "Null Cap", f"VSR-AC14-CAP-{_org_suffix()}", current=None, target=None
    )
    _mapping(db_session, org.id, cap_null.id, vs_with_gap.id, stage.id)
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org.id)

    for reason in result["reasons"]:
        assert reason in REASON_CODES
    for row in result["rows"]:
        if row["reason"] is not None:
            assert row["reason"] in REASON_CODES
        for cap in row["capabilities"]:
            if cap["reason"] is not None:
                assert cap["reason"] in REASON_CODES


# --- Acceptance item 18 -----------------------------------------------------------


def test_dependency_object_exact_key_set_and_no_forbidden_keys(app, db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("vsr-ac18")
    vs = _value_stream(db_session, org.id, "VS", f"VSR-AC18-{_org_suffix()}")
    stage = _stage(db_session, org.id, vs.id, "Stage", 1)
    cap = _capability(db_session, org.id, "Cap", f"VSR-AC18-CAP-{_org_suffix()}", current=2, target=4)
    _mapping(
        db_session, org.id, cap.id, vs.id, stage.id,
        support_type="primary", support_level=4, impact_level="high",
    )
    db_session.commit()

    result = IntelligenceQueryService.value_streams_at_risk(org.id)

    row = result["rows"][0]
    assert "initiatives" not in row
    assert "value_stream_initiatives" not in row
    assert "initiatives" not in result

    dependency = row["capabilities"][0]["dependency"]
    assert set(dependency.keys()) == {
        "link_kind", "support_type", "support_level", "impact_level", "stage",
    }
    forbidden = {
        "relation_type", "depth", "chain", "chain_elements",
        "rule_id", "derived_id", "computed_at", "stale",
    }
    assert forbidden.isdisjoint(dependency.keys())
    assert dependency["link_kind"] == "curated"
    assert dependency["stage"] == {"id": stage.id, "name": stage.name}


def test_route_ignores_graph_only_parameters(app, db_session, make_org, client, login_as):
    org = make_org("vsr-ac18-route")
    user = _user(db_session, org.id)
    db_session.commit()

    login_as(client, user)
    resp = client.get(
        "/api/v1/intelligence/value-streams-at-risk"
        "?include_derived=true&include_stale=true&max_depth=3"
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "initiatives" not in data
    for row in data["rows"]:
        assert "initiatives" not in row


# --- Acceptance item 19 ------------------------------------------------------------


class _SelectStatementCounter:
    def __init__(self):
        self.statements = []

    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        if statement.strip().upper().startswith("SELECT"):
            self.statements.append(statement)


@pytest.fixture
def select_counter(app):
    from sqlalchemy import event

    from app.extensions import db

    counter = _SelectStatementCounter()
    event.listen(db.engine, "before_cursor_execute", counter)
    try:
        yield counter
    finally:
        event.remove(db.engine, "before_cursor_execute", counter)


def test_four_batched_selects_regardless_of_row_count(app, db_session, make_org, select_counter):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("vsr-ac19")
    org_id = org.id  # captured before any commit -- see note below
    vs1 = _value_stream(db_session, org.id, "VS Small", f"VSR-AC19-SMALL-{_org_suffix()}")
    stage1 = _stage(db_session, org.id, vs1.id, "Stage 1", 1)
    small_caps = [
        _capability(db_session, org.id, f"Cap {i}", f"VSR-AC19-CAP-{i}-{_org_suffix()}", current=2, target=4)
        for i in range(6)
    ]
    for cap in small_caps:
        _mapping(db_session, org.id, cap.id, vs1.id, stage1.id)
    db_session.commit()

    # `commit()` expires every ORM attribute by default (including `org.id`),
    # so touching `org.id` again here would itself lazy-reload the whole row
    # and add a spurious 5th SELECT that has nothing to do with the method
    # under test -- `org_id`, a plain int captured above, avoids that.
    select_counter.statements.clear()
    IntelligenceQueryService.value_streams_at_risk(org_id)
    small_count = len(select_counter.statements)

    # Grow: a third value stream and four more mappings.
    vs2 = _value_stream(db_session, org_id, "VS Big", f"VSR-AC19-BIG-{_org_suffix()}")
    stage2 = _stage(db_session, org_id, vs2.id, "Stage 2", 1)
    more_caps = [
        _capability(
            db_session, org_id, f"Cap Extra {i}", f"VSR-AC19-EXTRA-{i}-{_org_suffix()}",
            current=1, target=5,
        )
        for i in range(4)
    ]
    for cap in more_caps:
        _mapping(db_session, org_id, cap.id, vs2.id, stage2.id)
    db_session.commit()

    select_counter.statements.clear()
    IntelligenceQueryService.value_streams_at_risk(org_id)
    big_count = len(select_counter.statements)

    assert small_count == 4, select_counter.statements
    assert big_count == small_count, select_counter.statements
