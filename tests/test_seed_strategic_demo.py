"""The T-S1 demonstration data set seeder: tenancy and idempotency.

`flask seed-strategic-demo` exists because no existing seeder can create a
value stream -- `seed-demo-mappings` maps entities that already exist and is
pinned never to create one; the capability seeders create no value stream
and set no per-tenant maturity. Without it, T-S1's answer is correct on day
one but has nothing to show a reviewer.

Two safety properties matter, mirroring `tests/test_seed_demo_mappings.py`'s
own two: it stays inside the organisation it is given, and re-running it
creates nothing new and changes nothing.

Every id used after a `seed_strategic_demo(...)` call below is a plain int
captured *before* that call, never an attribute read off the original ORM
object afterwards. The command runs inside `tenant_scope()` (required by the
brief), whose `_reset_session()` calls `db.session.remove()` on entry and
exit -- by design for a CLI/job's own session lifecycle (see
`derived_facts.py`'s module docstring for the same hazard documented against
a live request). That detaches every object the `db_session` fixture had
already loaded, so touching `org.id` again afterwards raises
`DetachedInstanceError` -- a plain int captured earlier has no such problem
and every assertion below re-queries fresh rows by that int.
"""

from __future__ import annotations

import pytest

from app.commands.seed_strategic_demo import seed_strategic_demo


def _counts_for_org(org_id):
    from app.models.unified_capability import (
        CapabilityValueStreamMapping,
        UnifiedCapability,
        ValueStream,
        ValueStreamStage,
    )

    value_streams = ValueStream.query.filter_by(organization_id=org_id).all()
    vs_ids = [vs.id for vs in value_streams]
    stages = (
        ValueStreamStage.query.filter(ValueStreamStage.organization_id == org_id).count()
        if vs_ids
        else 0
    )
    capabilities = UnifiedCapability.query.filter_by(organization_id=org_id).count()
    mappings = CapabilityValueStreamMapping.query.filter(
        CapabilityValueStreamMapping.organization_id == org_id
    ).count()
    return {
        "value_streams": len(value_streams),
        "stages": stages,
        "capabilities": capabilities,
        "mappings": mappings,
    }


def _ts4_counts_for_org(org_id):
    """Elements, initiatives and metrics reached only through the elements
    this organisation owns -- never a code-string parse, matching Path C's
    own join shape (T-S4)."""
    from app.models import ArchiMateElement
    from app.models.enterprise_intelligence import InitiativeSuccessMetric, PortfolioInitiative

    element_ids = [e.id for e in ArchiMateElement.query.filter_by(organization_id=org_id).all()]
    capability_elements = ArchiMateElement.query.filter_by(
        organization_id=org_id, type="Capability"
    ).count()
    initiatives = (
        PortfolioInitiative.query.filter(
            PortfolioInitiative.archimate_element_id.in_(element_ids)
        ).all()
        if element_ids
        else []
    )
    initiative_ids = [i.id for i in initiatives]
    metrics = (
        InitiativeSuccessMetric.query.filter(
            InitiativeSuccessMetric.initiative_id.in_(initiative_ids)
        ).count()
        if initiative_ids
        else 0
    )
    return {
        "capability_elements": capability_elements,
        "initiatives": len(initiative_ids),
        "metrics": metrics,
    }


# --- Acceptance item 15: fresh organisation -----------------------------------


def test_fresh_organisation_gets_two_streams_four_stages_six_capabilities_eight_mappings(
    db_session, make_org
):
    org = make_org("strategic-demo-fresh")
    org_id = org.id
    db_session.commit()

    stats = seed_strategic_demo(org_id)

    assert stats["value_streams_created"] == 2
    assert stats["stages_created"] == 4
    assert stats["capabilities_created"] == 6
    assert stats["mappings_created"] == 8
    assert stats["mappings_updated"] == 0
    assert stats["elements_created"] == 4
    assert stats["initiatives_created"] == 3
    assert stats["metrics_created"] == 3
    assert stats["already_present"] == 0

    assert _counts_for_org(org_id) == {
        "value_streams": 2,
        "stages": 4,
        "capabilities": 6,
        "mappings": 8,
    }
    assert _ts4_counts_for_org(org_id) == {
        "capability_elements": 4,
        "initiatives": 3,
        "metrics": 3,
    }


def test_capability_elements_linked_to_the_correct_capabilities(db_session, make_org):
    """Four of the six seeded capabilities get an element; Case Triage and
    Issue Resolution are deliberately left unlinked, so
    capability_not_linked_to_model is visible on the seeded answer."""
    from app.models.unified_capability import UnifiedCapability

    org = make_org("strategic-demo-ts4-linkage")
    org_id = org.id
    db_session.commit()

    seed_strategic_demo(org_id)

    caps = {
        cap.code: cap
        for cap in UnifiedCapability.query.filter_by(organization_id=org_id).all()
    }
    for code in (
        "DEMO-CAP-ORDER-CAPTURE",
        "DEMO-CAP-DELIVERY-SCHED",
        "DEMO-CAP-KNOWLEDGE-BASE",
        "DEMO-CAP-INVENTORY",
    ):
        assert caps[code].archimate_element_id is not None, f"{code} should have an element"
    for code in ("DEMO-CAP-CASE-TRIAGE", "DEMO-CAP-ISSUE-RESOLUTION"):
        assert caps[code].archimate_element_id is None, f"{code} should have no element"


def test_route_shows_all_five_initiative_states_after_seeding(app, db_session, make_org):
    """Order Capture: an initiative with two metrics, one honestly
    unmeasured. Knowledge Base: an element but no initiative. Case Triage: no
    element at all. The Fulfilment row: an initiative with no metric. The
    Service Request row: no initiative."""
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("strategic-demo-ts4-route")
    org_id = org.id
    db_session.commit()

    seed_strategic_demo(org_id)

    result = IntelligenceQueryService.value_streams_at_risk(org_id)
    caps_by_code = {
        cap["code"]: cap for row in result["rows"] for cap in row["capabilities"]
    }
    rows_by_code = {row["value_stream"]["code"]: row for row in result["rows"]}

    order_capture = caps_by_code["DEMO-CAP-ORDER-CAPTURE"]
    assert order_capture["initiatives_reason"] is None
    assert len(order_capture["initiatives"]) == 1
    order_initiative = order_capture["initiatives"][0]
    assert order_initiative["success_metrics_reason"] is None
    assert len(order_initiative["success_metrics"]) == 2
    actual_values = {m["actual_value"] for m in order_initiative["success_metrics"]}
    assert None in actual_values, "one of the two metrics is honestly unmeasured"

    knowledge_base = caps_by_code["DEMO-CAP-KNOWLEDGE-BASE"]
    assert knowledge_base["initiatives"] == []
    assert knowledge_base["initiatives_reason"] == "no_initiative_linked"

    case_triage = caps_by_code["DEMO-CAP-CASE-TRIAGE"]
    assert case_triage["initiatives"] == []
    assert case_triage["initiatives_reason"] == "capability_not_linked_to_model"

    fulfilment_row = rows_by_code["DEMO-VSR-FULFIL"]
    assert fulfilment_row["value_stream_initiatives_reason"] is None
    assert len(fulfilment_row["value_stream_initiatives"]) == 1
    fulfilment_initiative = fulfilment_row["value_stream_initiatives"][0]
    assert fulfilment_initiative["success_metrics"] == []
    assert fulfilment_initiative["success_metrics_reason"] == "no_success_metric_recorded"

    service_row = rows_by_code["DEMO-VSR-SERVICE"]
    assert service_row["value_stream_initiatives"] == []
    assert service_row["value_stream_initiatives_reason"] == "no_initiative_linked"


def test_seeded_two_organisations_have_disjoint_initiative_ids(db_session, make_org):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org_a = make_org("strategic-demo-ts4-disjoint-a")
    org_b = make_org("strategic-demo-ts4-disjoint-b")
    org_a_id, org_b_id = org_a.id, org_b.id
    db_session.commit()

    seed_strategic_demo(org_a_id)
    seed_strategic_demo(org_b_id)

    def _initiative_ids(result):
        from_caps = {
            ini["id"]
            for row in result["rows"]
            for cap in row["capabilities"]
            for ini in cap["initiatives"]
        }
        from_rows = {
            ini["id"] for row in result["rows"] for ini in row["value_stream_initiatives"]
        }
        return from_caps | from_rows

    ids_a = _initiative_ids(IntelligenceQueryService.value_streams_at_risk(org_a_id))
    ids_b = _initiative_ids(IntelligenceQueryService.value_streams_at_risk(org_b_id))
    assert ids_a, "expected org A to have at least one visible initiative"
    assert ids_b, "expected org B to have at least one visible initiative"
    assert ids_a.isdisjoint(ids_b)


def test_existing_initiative_code_pointing_at_a_different_element_aborts_before_any_write(
    db_session, make_org
):
    """An existing ``PortfolioInitiative`` row whose code the seed's own spec
    would reuse, but whose ``archimate_element_id`` resolves to a DIFFERENT
    element than this run just resolved, aborts the whole run rather than
    silently repointing a row the seed does not own -- and the abort happens
    on the first spec in iteration order, before either of the other two
    named initiatives is ever attempted."""
    from app.models import ArchiMateElement
    from app.models.enterprise_intelligence import PortfolioInitiative

    org = make_org("strategic-demo-ts4-abort")
    org_id = org.id
    db_session.commit()

    foreign_element = ArchiMateElement(
        name="Foreign Element", type="Capability", layer="Strategy", organization_id=org_id
    )
    db_session.add(foreign_element)
    db_session.flush()
    foreign_element_id = foreign_element.id
    conflicting = PortfolioInitiative(
        name="Pre-existing conflicting initiative",
        code=f"DEMO-INI-ORDER-{org_id}",
        archimate_element_id=foreign_element_id,
    )
    db_session.add(conflicting)
    db_session.flush()
    conflicting_id = conflicting.id
    db_session.commit()

    with pytest.raises(RuntimeError):
        seed_strategic_demo(org_id)

    refreshed = PortfolioInitiative.query.filter_by(id=conflicting_id).first()
    assert refreshed.archimate_element_id == foreign_element_id, (
        "the seed must never repoint a row it does not own"
    )
    remaining = PortfolioInitiative.query.filter(
        PortfolioInitiative.code.in_(
            [f"DEMO-INI-DELIVERY-{org_id}", f"DEMO-INI-FULFIL-{org_id}"]
        )
    ).count()
    assert remaining == 0, "the abort on the first spec must stop before the later ones"


def test_reseeding_a_changed_mapping_reports_mappings_updated_not_created(db_session, make_org):
    """D2-7: a mapping row present with DIFFERENT values from the current
    spec counts as ``mappings_updated``, never folded into
    ``mappings_created``."""
    from app.models.unified_capability import CapabilityValueStreamMapping

    org = make_org("strategic-demo-ts4-mapupdate")
    org_id = org.id
    db_session.commit()

    seed_strategic_demo(org_id)

    changed = (
        CapabilityValueStreamMapping.query.filter_by(organization_id=org_id)
        .order_by(CapabilityValueStreamMapping.id)
        .first()
    )
    changed.support_level = 1 if changed.support_level != 1 else 2
    db_session.commit()

    second = seed_strategic_demo(org_id)

    assert second["mappings_updated"] == 1
    assert second["mappings_created"] == 0


def test_seeded_capabilities_include_both_below_and_at_or_above_default_threshold(
    db_session, make_org
):
    from app.models.unified_capability import UnifiedCapability

    org = make_org("strategic-demo-spread")
    org_id = org.id
    db_session.commit()

    seed_strategic_demo(org_id)

    levels = [
        cap.current_maturity_level
        for cap in UnifiedCapability.query.filter_by(organization_id=org_id).all()
    ]
    assert any(level is not None and level < 3 for level in levels)
    assert any(level is not None and level >= 3 for level in levels)


def test_route_shows_both_an_at_risk_and_a_safe_capability_after_seeding(
    app, db_session, make_org
):
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org = make_org("strategic-demo-route")
    org_id = org.id
    db_session.commit()

    seed_strategic_demo(org_id)

    result = IntelligenceQueryService.value_streams_at_risk(org_id)
    at_risk_flags = {cap["at_risk"] for row in result["rows"] for cap in row["capabilities"]}
    assert True in at_risk_flags, "expected at least one at_risk: true capability"
    assert False in at_risk_flags, "expected at least one at_risk: false capability"


# --- Acceptance item 15: idempotency --------------------------------------------


def test_rerun_creates_nothing_new(db_session, make_org):
    org = make_org("strategic-demo-rerun")
    org_id = org.id
    db_session.commit()

    seed_strategic_demo(org_id)
    before = _counts_for_org(org_id)

    second = seed_strategic_demo(org_id)

    assert second["value_streams_created"] == 0
    assert second["stages_created"] == 0
    assert second["capabilities_created"] == 0
    assert second["mappings_created"] == 0
    assert second["mappings_updated"] == 0
    assert second["elements_created"] == 0
    assert second["initiatives_created"] == 0
    assert second["metrics_created"] == 0
    assert _counts_for_org(org_id) == before


def test_rerun_does_not_change_mapping_field_values(db_session, make_org):
    """`upsert_mapping_cell` bumps `updated_at` on every call; re-seeding must
    not even call it a second time for an unchanged row (constraint: a
    re-run changes nothing, not just "creates nothing")."""
    from app.models.unified_capability import CapabilityValueStreamMapping

    org = make_org("strategic-demo-rerun-fields")
    org_id = org.id
    db_session.commit()

    seed_strategic_demo(org_id)
    mappings_before = {
        m.id: m.updated_at
        for m in CapabilityValueStreamMapping.query.filter_by(organization_id=org_id).all()
    }

    seed_strategic_demo(org_id)
    mappings_after = {
        m.id: m.updated_at
        for m in CapabilityValueStreamMapping.query.filter_by(organization_id=org_id).all()
    }

    assert mappings_after == mappings_before


# --- Acceptance item 15: --dry-run ----------------------------------------------


def test_dry_run_writes_nothing_but_reports_what_it_would_do(db_session, make_org):
    org = make_org("strategic-demo-dryrun")
    org_id = org.id
    db_session.commit()

    stats = seed_strategic_demo(org_id, dry_run=True)

    assert stats["value_streams_created"] == 2
    assert stats["stages_created"] == 4
    assert stats["capabilities_created"] == 6
    assert stats["mappings_created"] == 8

    assert _counts_for_org(org_id) == {
        "value_streams": 0, "stages": 0, "capabilities": 0, "mappings": 0,
    }, "dry run wrote rows"

    applied = seed_strategic_demo(org_id)
    assert applied["value_streams_created"] == stats["value_streams_created"]
    assert applied["stages_created"] == stats["stages_created"]
    assert applied["capabilities_created"] == stats["capabilities_created"]
    assert applied["mappings_created"] == stats["mappings_created"]


# --- Acceptance item 15: stays inside the organisation it is given -------------


def test_command_writes_only_inside_the_organisation_it_is_given(db_session, make_org):
    org_a = make_org("strategic-demo-scope-a")
    org_b = make_org("strategic-demo-scope-b")
    org_a_id, org_b_id = org_a.id, org_b.id
    db_session.commit()

    seed_strategic_demo(org_a_id)

    assert _counts_for_org(org_a_id) == {
        "value_streams": 2, "stages": 4, "capabilities": 6, "mappings": 8,
    }
    assert _counts_for_org(org_b_id) == {
        "value_streams": 0, "stages": 0, "capabilities": 0, "mappings": 0,
    }, "seeding one organisation must never write into another"


def test_command_never_touches_a_null_owner_capability_row(db_session, make_org):
    """Pinned safety property: the command creates no capability it did not
    create itself and never touches a row whose organization_id is null."""
    from app.models.unified_capability import UnifiedCapability

    org = make_org("strategic-demo-null-owner")
    org_id = org.id
    shared = UnifiedCapability(
        name="Pre-existing shared capability",
        code="STRATEGIC-DEMO-SHARED-PREEXISTING",
        organization_id=None,
        scope="reference",
        level=1,
        current_maturity_level=4,
        target_maturity_level=4,
    )
    db_session.add(shared)
    db_session.flush()
    shared_id = shared.id
    db_session.commit()

    seed_strategic_demo(org_id)

    refreshed = UnifiedCapability.query.filter_by(id=shared_id).first()
    assert refreshed.organization_id is None
    assert refreshed.current_maturity_level == 4, "a null-owner row must never be modified"


def test_cli_command_runs_end_to_end(app, db_session, make_org):
    org = make_org("strategic-demo-cli")
    org_id = org.id
    db_session.commit()

    result = app.test_cli_runner().invoke(args=["seed-strategic-demo", "--org-id", str(org_id)])

    assert result.exit_code == 0, f"command failed: {result.output}\n{result.exception!r}"
    assert "created" in result.output
    assert _counts_for_org(org_id) == {
        "value_streams": 2, "stages": 4, "capabilities": 6, "mappings": 8,
    }


def test_cli_command_requires_org_id(app):
    result = app.test_cli_runner().invoke(args=["seed-strategic-demo"])
    assert result.exit_code != 0


def test_cli_command_rejects_unknown_organisation(app):
    result = app.test_cli_runner().invoke(args=["seed-strategic-demo", "--org-id", "999999999"])
    assert result.exit_code != 0


# --- --dry-run on an ALREADY-SEEDED organisation --------------------------------


def test_dry_run_on_seeded_organisation_reports_nothing_to_create(db_session, make_org):
    """The mapping section used to short-circuit on
    ``dry_run`` before the existing-mapping lookup, so a dry-run against an
    already-seeded organisation reported "would create 8 mapping rows" it
    would not actually create. Seed for real first, then dry-run the SAME
    organisation: every created count is 0, every row is already present,
    and nothing changes.
    """
    org = make_org("strategic-demo-dryrun-seeded")
    org_id = org.id
    db_session.commit()

    seed_strategic_demo(org_id)
    before = _counts_for_org(org_id)

    stats = seed_strategic_demo(org_id, dry_run=True)

    assert stats["value_streams_created"] == 0
    assert stats["stages_created"] == 0
    assert stats["capabilities_created"] == 0
    assert stats["mappings_created"] == 0
    assert stats["already_present"] == 30
    assert _counts_for_org(org_id) == before, "dry run on a seeded organisation changed rows"


# --- Two organisations seeded on one database -----------------------------------


def test_two_organisations_seed_independently_on_one_database(db_session, make_org):
    """The seed looks up by ``(organization_id, code)``, so
    on a database whose per-organisation unique index was never applied a
    second organisation's seed still creates its own rows with the same
    codes -- intended, and untested until now. Each organisation ends up
    with exactly its own 2 value streams, 6 capabilities and 8 mappings, and
    each answer's capability id set is disjoint from the other's.
    """
    from app.modules.intelligence.services.query_service import IntelligenceQueryService

    org_a = make_org("strategic-demo-d18-a")
    org_b = make_org("strategic-demo-d18-b")
    org_a_id, org_b_id = org_a.id, org_b.id
    db_session.commit()

    seed_strategic_demo(org_a_id)
    seed_strategic_demo(org_b_id)

    assert _counts_for_org(org_a_id) == {
        "value_streams": 2, "stages": 4, "capabilities": 6, "mappings": 8,
    }
    assert _counts_for_org(org_b_id) == {
        "value_streams": 2, "stages": 4, "capabilities": 6, "mappings": 8,
    }

    result_a = IntelligenceQueryService.value_streams_at_risk(org_a_id)
    result_b = IntelligenceQueryService.value_streams_at_risk(org_b_id)
    assert result_a["summary"]["capabilities_considered"] == 6
    assert result_b["summary"]["capabilities_considered"] == 6

    ids_a = {c["id"] for row in result_a["rows"] for c in row["capabilities"]}
    ids_b = {c["id"] for row in result_b["rows"] for c in row["capabilities"]}
    assert ids_a.isdisjoint(ids_b)
