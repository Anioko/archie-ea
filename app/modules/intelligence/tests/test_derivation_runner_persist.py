"""T-003 / task 01 acceptance criteria 5, 6, 7 (via run_and_persist / upsert)."""

from __future__ import annotations

import pytest

from app.extensions import db


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


def _rows(db_session, org_id):
    from app.modules.intelligence.models.derived_relationship import DerivedRelationship

    return (
        db.session.execute(
            db.select(DerivedRelationship).where(DerivedRelationship.organization_id == org_id)
        )
        .scalars()
        .all()
    )


def test_run_and_persist_writes_chain_and_rule_id(app, db_session, make_org):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org = make_org("dr-persist")
    a = _make_element(db_session, org.id, "a")
    b = _make_element(db_session, org.id, "b")
    c = _make_element(db_session, org.id, "c")
    _make_relationship(db_session, org.id, a, b, "Composition")
    _make_relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()

    runner = DerivationRunner()
    with app.app_context():
        result = runner.run_and_persist(org.id, trigger="on_demand")

    assert result.derived_count >= 1
    rows = _rows(db_session, org.id)
    assert len(rows) == result.derived_count
    for row in rows:
        assert row.rule_id
        assert row.chain
        assert row.stale is False
        assert row.stale_since is None


def test_run_and_persist_is_idempotent(app, db_session, make_org):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org = make_org("dr-idempotent")
    a = _make_element(db_session, org.id, "a")
    b = _make_element(db_session, org.id, "b")
    c = _make_element(db_session, org.id, "c")
    _make_relationship(db_session, org.id, a, b, "Composition")
    _make_relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()

    runner = DerivationRunner()
    with app.app_context():
        first = runner.run_and_persist(org.id, trigger="on_demand")
    first_rows = {(r.source_element_id, r.target_element_id, r.rule_id): r.computed_at for r in _rows(db_session, org.id)}

    with app.app_context():
        second = runner.run_and_persist(org.id, trigger="on_demand")
    second_rows = _rows(db_session, org.id)

    assert second.derived_count == first.derived_count
    assert len(second_rows) == len(first_rows)
    for row in second_rows:
        key = (row.source_element_id, row.target_element_id, row.rule_id)
        assert key in first_rows


def test_run_and_persist_deletes_rows_no_longer_produced(app, db_session, make_org):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner
    from app.models import ArchiMateRelationship

    org = make_org("dr-prune")
    a = _make_element(db_session, org.id, "a")
    b = _make_element(db_session, org.id, "b")
    c = _make_element(db_session, org.id, "c")
    r1 = _make_relationship(db_session, org.id, a, b, "Composition")
    _make_relationship(db_session, org.id, b, c, "Serving")
    db_session.commit()

    runner = DerivationRunner()
    with app.app_context():
        first = runner.run_and_persist(org.id, trigger="on_demand")
    assert first.derived_count >= 1

    # Remove the relationship the derived chain depended on.
    db.session.delete(db.session.get(ArchiMateRelationship, r1.id))
    db_session.commit()

    with app.app_context():
        second = runner.run_and_persist(org.id, trigger="on_demand")

    rows = _rows(db_session, org.id)
    assert len(rows) == second.derived_count
    assert second.derived_count < first.derived_count or second.derived_count == 0


def test_pruning_is_scoped_to_one_tenant(app, db_session, make_org):
    from app.modules.intelligence.services.derivation_runner import DerivationRunner

    org_a = make_org("dr-prune-a")
    org_b = make_org("dr-prune-b")

    a1 = _make_element(db_session, org_a.id, "a1")
    a2 = _make_element(db_session, org_a.id, "a2")
    a3 = _make_element(db_session, org_a.id, "a3")
    _make_relationship(db_session, org_a.id, a1, a2, "Composition")
    _make_relationship(db_session, org_a.id, a2, a3, "Serving")

    b1 = _make_element(db_session, org_b.id, "b1")
    b2 = _make_element(db_session, org_b.id, "b2")
    b3 = _make_element(db_session, org_b.id, "b3")
    _make_relationship(db_session, org_b.id, b1, b2, "Composition")
    _make_relationship(db_session, org_b.id, b2, b3, "Serving")
    db_session.commit()

    runner = DerivationRunner()
    with app.app_context():
        runner.run_and_persist(org_a.id, trigger="on_demand")
        runner.run_and_persist(org_b.id, trigger="on_demand")

    rows_a_before = len(_rows(db_session, org_a.id))
    rows_b_before = len(_rows(db_session, org_b.id))
    assert rows_a_before >= 1
    assert rows_b_before >= 1

    # Re-run org_a with no relationships at all (simulate everything pruned).
    from app.models import ArchiMateRelationship

    for rel in db.session.execute(
        db.select(ArchiMateRelationship).where(ArchiMateRelationship.organization_id == org_a.id)
    ).scalars().all():
        db.session.delete(rel)
    db_session.commit()

    with app.app_context():
        runner.run_and_persist(org_a.id, trigger="on_demand")

    assert len(_rows(db_session, org_a.id)) == 0
    assert len(_rows(db_session, org_b.id)) == rows_b_before


# D1: actual OEF parser/importer -> normal models -> actual tenant job/readers.
def _oef_model(elements, edges):
    from xml.etree.ElementTree import Element, SubElement, tostring

    root = Element("model", {"xmlns": "http://www.opengroup.org/xsd/archimate/3.0/",
                             "identifier": "lantern-quay-d1"})
    node = SubElement(root, "elements")
    for key, name, kind in elements:
        element = SubElement(node, "element", identifier=key, type=kind)
        SubElement(element, "name").text = name
        SubElement(element, "documentation").text = "Fictional Lantern Quay D1 regression input."
    node = SubElement(root, "relationships")
    for key, source, target, kind in edges:
        edge = SubElement(node, "relationship", identifier=key, source=source, target=target, type=kind)
        SubElement(edge, "documentation").text = "Fictional Lantern Quay D1 explicit connection."
    return tostring(root, encoding="unicode")


def _import_oef(org_id, xml):
    from app.jobs.tenant_safe_job import tenant_scope
    from app.models import ArchiMateElement, ArchiMateRelationship
    from app.services.archimate_import_service import ArchiMateImportService

    with tenant_scope(org_id):
        importer = ArchiMateImportService()
        parsed = importer.parse_oef_xml(xml)
        assert parsed["errors"] == []
        preview = importer.preview_import(parsed)
        assert preview["errors"] == []
        assert preview["summary"]["invalid"] == 0
        assert preview["summary"]["relationships_invalid"] == 0
        assert preview["summary"]["relationships_valid"] == len(parsed["relationships"])
        result = importer.execute_import(parsed, strategy="update_existing")
        assert result["failed"] == 0
        assert result["errors"] == []
        assert result["relationships_failed"] == []
        elements = {e.name: e.id for e in db.session.execute(db.select(ArchiMateElement)).scalars()}
        relationships = {
            (r.source_id, r.target_id, r.type): r.id
            for r in db.session.execute(db.select(ArchiMateRelationship)).scalars()
        }
        assert all(kind == kind.lower() for _, _, kind in relationships)
        return elements, relationships, result


def _lantern_quay_model():
    elements = [
        ("pool", "Quay Compute Pool", "Node"),
        ("transport", "Event Transport", "TechnologyService"),
        ("relay", "Event Relay", "ApplicationComponent"),
        ("delivery", "Event Delivery", "ApplicationService"),
        ("release", "Release calibrated batch", "BusinessProcess"),
        ("pack", "Pack calibrated batch", "BusinessProcess"),
        ("dispatch", "Dispatch calibrated batch", "BusinessProcess"),
        ("ledger", "Calibration Ledger", "ApplicationComponent"),
        ("evaluate", "Evaluate calibration", "ApplicationFunction"),
        ("result", "Calibration result", "DataObject"),
        ("receive", "Receive recovered assembly", "BusinessProcess"),
        ("inspect", "Inspect recovered assembly", "BusinessProcess"),
        ("recertify", "Recertify recovered assembly", "BusinessProcess"),
        ("planner", "Dispatch Planner", "ApplicationComponent"),
        ("promise", "Stock Promise", "ApplicationService"),
        ("reserve", "Reserve replacement stock", "BusinessProcess"),
    ]
    edges = [
        ("pool-transport", "pool", "transport", "Realization"),
        ("transport-relay", "transport", "relay", "Serving"),
        ("relay-delivery", "relay", "delivery", "Realization"),
        ("delivery-release", "delivery", "release", "Serving"),
        ("release-pack", "release", "pack", "Triggering"),
        ("pack-dispatch", "pack", "dispatch", "Triggering"),
        ("ledger-evaluate", "ledger", "evaluate", "Assignment"),
        ("evaluate-result", "evaluate", "result", "Access"),
        ("receive-inspect", "receive", "inspect", "Triggering"),
        ("inspect-recertify", "inspect", "recertify", "Triggering"),
        ("recovery-loop", "recertify", "receive", "Triggering"),
        ("planner-promise", "planner", "promise", "Realization"),
        ("promise-reserve", "promise", "reserve", "Serving"),
        ("planner-reserve", "planner", "reserve", "Association"),
    ]
    return _oef_model(elements, edges)


def _job_succeeded(run, org_id):
    assert not run.skipped_locked
    assert run.failed == 0
    assert len(run.results) == 1
    result = run.results[0]
    assert result.organization_id == org_id
    assert result.ok
    assert result.value["skipped_locked"] is False


def _stored_snapshot(org_id):
    from app.jobs.tenant_safe_job import tenant_scope
    from app.models import ArchiMateElement, ArchiMateRelationship
    from app.modules.intelligence.models.derivation_run import DerivationRun
    from app.modules.intelligence.services.derived_facts import list_derived_facts

    with tenant_scope(org_id):
        return {
            "elements": [(e.id, e.name, e.type) for e in db.session.execute(
                db.select(ArchiMateElement).order_by(ArchiMateElement.id)).scalars()],
            "edges": [(r.id, r.source_id, r.target_id, r.type) for r in db.session.execute(
                db.select(ArchiMateRelationship).order_by(ArchiMateRelationship.id)).scalars()],
            "facts": sorted(list_derived_facts(org_id, include_stale=True), key=lambda r: r["id"]),
            "runs": [(r.id, r.engine_version, r.finished_at, r.trigger, r.derived_count)
                     for r in db.session.execute(db.select(DerivationRun).order_by(DerivationRun.id)).scalars()],
        }


@pytest.mark.parametrize("proof_index", [0, 1, 2], ids=["serving", "access", "triggering"])
def test_lantern_quay_oef_to_job_proofs_reimport_and_foreign_isolation(
    app, db_session, make_org, proof_index
):
    from app.modules.intelligence.services.derivation_runner import ENGINE_VERSION
    from app.modules.intelligence.services.derived_facts import get_derived_fact, list_derived_facts
    from app.modules.intelligence.services.recompute_job import recompute_derived_facts_on_demand

    mine, theirs = make_org("d1-lantern-a"), make_org("d1-lantern-b")
    mine_id, theirs_id = mine.id, theirs.id
    db_session.commit()
    xml = _lantern_quay_model()
    foreign_nodes, foreign_edges, _ = _import_oef(theirs_id, xml)
    _job_succeeded(recompute_derived_facts_on_demand(app, theirs_id), theirs_id)
    foreign_before = _stored_snapshot(theirs_id)
    nodes, edges, imported = _import_oef(mine_id, xml)
    assert imported["created"] == len(nodes) == 16
    assert imported["relationships_created"] == len(edges) == 14
    assert set(nodes.values()).isdisjoint(foreign_nodes.values())
    assert set(edges.values()).isdisjoint(foreign_edges.values())
    _job_succeeded(recompute_derived_facts_on_demand(app, mine_id), mine_id)
    facts = list_derived_facts(mine_id)
    by_pair = {(f["source_element_id"], f["target_element_id"]): f for f in facts}
    examples = [
        (["Quay Compute Pool", "Event Transport", "Event Relay", "Event Delivery", "Release calibrated batch"],
         ["realization", "serving", "realization", "serving"], "Serving", "table:Serving:Serving"),
        (["Calibration Ledger", "Evaluate calibration", "Calibration result"],
         ["assignment", "access"], "Access", "transparent:Assignment:Access"),
        (["Receive recovered assembly", "Inspect recovered assembly", "Recertify recovered assembly"],
         ["triggering", "triggering"], "Triggering", "table:Triggering:Triggering"),
    ]
    for names, kinds, expected_type, rule in examples[proof_index:proof_index + 1]:
        path = [nodes[name] for name in names]
        fact = by_pair[path[0], path[-1]]
        assert fact["derived_type"] == expected_type
        assert fact["rule_id"] == rule
        assert fact["depth"] == len(kinds)
        assert fact["chain_element_ids"] == path
        assert fact["chain"] == [edges[src, tgt, kind] for src, tgt, kind in zip(path, path[1:], kinds)]
        assert fact["engine_version"] == ENGINE_VERSION
        assert fact["stale"] is False
    assert (nodes["Dispatch Planner"], nodes["Reserve replacement stock"]) not in by_pair
    assert by_pair[nodes["Quay Compute Pool"], nodes["Pack calibrated batch"]]["depth"] == 5
    assert (nodes["Quay Compute Pool"], nodes["Dispatch calibrated batch"]) not in by_pair
    assert all(len(f["chain_element_ids"]) == len(set(f["chain_element_ids"])) for f in facts)
    assert all(f["depth"] <= 5 for f in facts)
    for foreign_fact in foreign_before["facts"]:
        assert get_derived_fact(mine_id, foreign_fact["id"]) is None
    repeat_nodes, repeat_edges, repeated = _import_oef(mine_id, xml)
    assert repeated["created"] == repeated["relationships_created"] == 0
    assert repeated["relationships_skipped"] == len(edges)
    assert (repeat_nodes, repeat_edges) == (nodes, edges)
    _job_succeeded(recompute_derived_facts_on_demand(app, mine_id), mine_id)
    assert {f["id"] for f in list_derived_facts(mine_id)} == {f["id"] for f in facts}
    assert _stored_snapshot(theirs_id) == foreign_before


@pytest.mark.parametrize("raw, canonical, source_kind, target_kind", [
    ("realizes", "realization", "ApplicationComponent", "ApplicationService"),
    ("serves", "serving", "ApplicationComponent", "ApplicationComponent"),
    ("uses", "serving", "ApplicationComponent", "ApplicationComponent"),
    ("triggers", "triggering", "BusinessProcess", "BusinessProcess"),
    ("flows", "flow", "BusinessProcess", "BusinessProcess"),
    ("composes", "composition", "ApplicationComponent", "ApplicationComponent"),
    ("aggregates", "aggregation", "ApplicationComponent", "ApplicationComponent"),
    ("assigns", "assignment", "ApplicationComponent", "ApplicationFunction"),
    ("specializes", "specialization", "ApplicationComponent", "ApplicationComponent"),
    ("associates", "association", "ApplicationComponent", "ApplicationComponent"),
])
@pytest.mark.parametrize("form", ["alias", "suffix", "alias_suffix"])
def test_oef_aliases_and_terminal_suffix_keep_canonical_meaning(
    app, db_session, make_org, raw, canonical, source_kind, target_kind, form
):
    from app.modules.intelligence.services.derived_facts import list_derived_facts
    from app.modules.intelligence.services.recompute_job import recompute_derived_facts_on_demand

    org_id = make_org("d1-alias").id
    db_session.commit()
    token = {"alias": raw, "suffix": canonical + "ReLaTiOnShIp",
             "alias_suffix": raw + "Relationship"}[form]
    elements = [("a", "Lantern Quay source", source_kind),
                ("b", "Lantern Quay middle", source_kind),
                ("c", "Lantern Quay target", target_kind)]
    xml = _oef_model(elements, [("ab", "a", "b", "Composition"), ("bc", "b", "c", token)])
    nodes, edges, _ = _import_oef(org_id, xml)
    _job_succeeded(recompute_derived_facts_on_demand(app, org_id), org_id)
    fact, = list_derived_facts(org_id)
    path = [nodes[name] for _, name, _ in elements]
    assert fact["derived_type"] == canonical.title()
    assert fact["rule_id"] == f"transparent:Composition:{canonical.title()}"
    assert fact["chain_element_ids"] == path
    assert fact["chain"] == [edges[path[0], path[1], "composition"], edges[path[1], path[2], canonical]]


@pytest.mark.parametrize("raw, source_kind, target_kind", [
    ("ServingRelationship ", "ApplicationComponent", "ApplicationComponent"),
    ("DataFlow", "BusinessProcess", "BusinessProcess"),
    ("Assignment", "DataObject", "Node"),
])
def test_oef_invalid_types_and_endpoints_are_rejected_upstream(
    app, db_session, make_org, raw, source_kind, target_kind
):
    from app.jobs.tenant_safe_job import tenant_scope
    from app.models import ArchiMateRelationship
    from app.services.archimate_import_service import ArchiMateImportService
    from app.modules.intelligence.services.derived_facts import latest_derivation_run

    org_id = make_org("d1-invalid-import").id
    db_session.commit()
    with tenant_scope(org_id):
        importer = ArchiMateImportService()
        parsed = importer.parse_oef_xml(_oef_model(
            [("a", "Lantern Quay source", source_kind), ("b", "Lantern Quay target", target_kind)],
            [("invalid", "a", "b", raw)],
        ))
        assert parsed["errors"] == []
        preview = importer.preview_import(parsed)
        assert preview["summary"]["relationships_invalid"] == 1
        assert preview["relationships"][0]["reason"]
        result = importer.execute_import(parsed, strategy="update_existing")
        assert result["relationships_created"] == 0
        assert len(result["relationships_failed"]) == 1
        assert db.session.execute(db.select(ArchiMateRelationship)).scalars().all() == []
        assert latest_derivation_run(org_id) is None


@pytest.mark.parametrize("failure", ["invalid_type", "persist", "record", "commit", "lock"])
def test_legacy_fact_repair_is_atomic_and_retryable(app, db_session, make_org, monkeypatch, failure):
    from contextlib import nullcontext
    from app.jobs.tenant_safe_job import job_lock, tenant_scope
    from app.modules.intelligence.services.derivation_runner import DerivationRunner, ENGINE_VERSION
    from app.modules.intelligence.services.derived_facts import list_derived_facts
    from app.modules.intelligence.services.recompute_job import (
        per_tenant_lock_name, recompute_derived_facts_on_demand, stale_carrying_organization_ids,
    )

    org_id = make_org("d1-repair").id
    db_session.commit()
    nodes, edges, _ = _import_oef(org_id, _lantern_quay_model())
    _job_succeeded(recompute_derived_facts_on_demand(app, org_id), org_id)
    original = _stored_snapshot(org_id)
    wrong_id = next(f["id"] for f in original["facts"] if
                    (f["source_element_id"], f["target_element_id"]) ==
                    (nodes["Calibration Ledger"], nodes["Calibration result"]))
    edge_id = edges[nodes["Calibration Ledger"], nodes["Evaluate calibration"], "assignment"]
    # Deliberate historical fixtures: model the old clean-flag store, including
    # one wrong natural key and unchanged keys that must retain their identities.
    with tenant_scope(org_id):
        db.session.execute(db.text("UPDATE archimate_derived_relationships SET engine_version = '1.0.0', "
                                   "stale = FALSE, stale_since = NULL, stale_reason = NULL "
                                   "WHERE organization_id = :org"), {"org": org_id})
        db.session.execute(db.text("UPDATE archimate_derived_relationships SET derived_type = 'Association', "
                                   "rule_id = 'fallback:assignment:access' WHERE organization_id = :org AND id = :id"),
                           {"org": org_id, "id": wrong_id})
        db.session.execute(db.text("UPDATE intelligence_derivation_runs SET engine_version = '1.0.0' "
                                   "WHERE organization_id = :org"), {"org": org_id})
        if failure == "invalid_type":
            db.session.execute(db.text("UPDATE archimate_relationships SET type = 'DataFlow' "
                                       "WHERE organization_id = :org AND id = :id"),
                               {"org": org_id, "id": edge_id})
        db.session.commit()
    before = _stored_snapshot(org_id)
    assert list_derived_facts(org_id) == []
    assert all(f["stale"] and f["reason"] == "derivation_stale" for f in before["facts"])

    with monkeypatch.context() as patch:
        if failure in ("persist", "record"):
            method = "_persist" if failure == "persist" else "_record_run"
            real_method = getattr(DerivationRunner, method)

            def fail_after_write(self, *args, **kwargs):
                real_method(self, *args, **kwargs)
                db.session.flush()
                raise RuntimeError("D1 injected transaction failure")

            patch.setattr(DerivationRunner, method, fail_after_write)
        elif failure == "commit":
            def fail_commit():
                db.session.flush()
                raise RuntimeError("D1 injected commit failure")
            patch.setattr(db.session, "commit", fail_commit)
        held = job_lock(per_tenant_lock_name(org_id), required=True) if failure == "lock" else nullcontext()
        with held:
            failed = recompute_derived_facts_on_demand(app, org_id)
        assert not failed.skipped_locked
        assert len(failed.results) == 1
        if failure == "lock":
            assert failed.results[0].ok
            assert failed.results[0].value["skipped_locked"] is True
        else:
            assert failed.failed == 1
            if failure == "invalid_type":
                assert str(edge_id) in failed.results[0].error
                assert "DataFlow" in failed.results[0].error
    assert _stored_snapshot(org_id) == before
    assert list_derived_facts(org_id) == []
    assert org_id in stale_carrying_organization_ids()
    if failure == "invalid_type":
        with tenant_scope(org_id):
            db.session.execute(db.text("UPDATE archimate_relationships SET type = 'assignment' "
                                       "WHERE organization_id = :org AND id = :id"),
                               {"org": org_id, "id": edge_id})
            db.session.commit()
    _job_succeeded(recompute_derived_facts_on_demand(app, org_id), org_id)
    after = _stored_snapshot(org_id)
    assert after["elements"] == original["elements"]
    assert after["edges"] == original["edges"]
    assert after["runs"][:-1] == before["runs"]
    assert len(after["runs"]) == len(before["runs"]) + 1
    assert after["runs"][-1][1] == ENGINE_VERSION
    assert after["runs"][-1][3] == "on_demand"
    assert wrong_id not in {f["id"] for f in after["facts"]}
    assert {f["id"] for f in before["facts"] if f["id"] != wrong_id}.issubset(
        {f["id"] for f in after["facts"]})
    repaired = next(f for f in after["facts"] if f["source_element_id"] == nodes["Calibration Ledger"]
                    and f["target_element_id"] == nodes["Calibration result"])
    assert (repaired["derived_type"], repaired["rule_id"]) == ("Access", "transparent:Assignment:Access")
    assert all(f["engine_version"] == ENGINE_VERSION and not f["stale"] for f in after["facts"])
    assert org_id not in stale_carrying_organization_ids()
