"""The store-agreement gate asks every store and screen the same question.

Three things are pinned here:

* the registry names every store and screen that answers each concept, so a
  consolidation can prove it worked (a missing surface is a disagreement the
  gate can never see);
* the comparison judgement, driven through the gate's own ``--root`` probe
  mode: agreeing surfaces pass, a disagreement fails naming both surfaces and
  both numbers, a declared narrower scope is not reported, all-zero is
  ``no-evidence``, and a store that cannot be scoped to one organisation is a
  finding once it holds rows;
* tenancy: organisation B's rows never change organisation A's counts, whether
  the store has TenantMixin, a bare ``organization_id`` column, or only a link
  to a tenant-owned row.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "check_store_agreement.py")


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_store_agreement", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load_gate()

# concept -> the stores and screens that must be asked. Model paths for stores,
# URL paths (without query string) for screens.
EXPECTED = {
    "work packages": [
        "app.models.unified_work_package.UnifiedWorkPackage",
        "app.models.implementation_migration.WorkPackage",
        "app.models.implementation_migration.TechnologyRoadmapInitiative",
        "app.models.roadmap_models.RoadmapWorkPackage",
        "app.models.implementation_planning.ImplementationWorkPackage",
        "/enterprise/api/work-packages",
        "/api/roadmap/work-packages",
        "/api/roadmap-builder/work-packages",
        "/implementation/api/work-packages",
        "/capability-map/api/roadmap/work-packages",
    ],
    "gaps": [
        "app.models.implementation_migration.Gap",
        "app.models.roadmap_models.RoadmapGap",
        "app.models.implementation_planning.ImplementationGap",
        "app.models.compliance_models.ComplianceGap",
        "/capability-map/api/roadmap/gaps",
        "/api/roadmap/gaps",
        "/implementation/api/gaps",
    ],
    "risks": [
        "app.models.risk.Risk",
        "/api/risks",
    ],
    "application owners": [
        "app.models.application_owner.ApplicationOwner",
        "app.models.enterprise_intelligence.ApplicationOwnership",
        "app.models.application_portfolio.ApplicationComponent",
    ],
    "architecture decisions": [
        "app.models.architecture_decision.ArchitectureDecision",
        "app.models.adr.ArchitectureDecisionRecord",
        "app.models.decision_ledger.DecisionLedger",
        "/arb/api/decisions",
    ],
    "pending change proposals": [
        "app.models.ai_chat_crud_approval.AIChatCRUDApproval",
        "app.models.confidence_review.ReviewQueueItem",
        "app.models.archimate_core.RelationshipSuggestion",
        "app.models.solution_blueprint_proposal.SolutionBlueprintProposal",
        "/ai-chat/approvals/pending",
    ],
    "applications with a recorded annual cost": [
        "app.models.application_portfolio.ApplicationComponent",
        "app.models.enterprise_intelligence.ApplicationCost",
    ],
    "contracts": [
        "app.models.application_portfolio.VendorContract",
        "app.models.archimate_business.Contract",
    ],
    "vendors": [
        "app.models.vendor.vendor_organization.VendorOrganization",
        "/api/v1/vendors/",
    ],
}

# Surfaces whose store has no organisation column, no link to attribute a row
# by, and no shared declaration. Each is reported as unscoped once it holds
# rows; adding one is a decision made here, in review.
KNOWN_UNSCOPED = {"orm:DecisionLedger"}


def _targets(concept):
    return {s.target.split("?", 1)[0] for s in gate.CONCEPTS[concept]}


@pytest.mark.parametrize("concept", sorted(EXPECTED))
def test_registry_asks_every_store_and_screen(concept):
    assert concept in gate.CONCEPTS, "%r is not registered" % concept
    missing = set(EXPECTED[concept]) - _targets(concept)
    assert not missing, "%r does not ask %s" % (concept, sorted(missing))


def test_every_orm_surface_resolves_and_is_tenant_scoped(app):
    from app import db

    problems = []
    unscoped = set()
    with app.app_context():
        for concept, surfaces in gate.CONCEPTS.items():
            for surface in surfaces:
                if surface.kind != "orm":
                    continue
                module, _, cls = surface.target.rpartition(".")
                model = getattr(importlib.import_module(module), cls)
                columns = model.__table__.c
                named = list(surface.filter_eq)
                if surface.filter_not_null:
                    named += ([surface.filter_not_null]
                              if isinstance(surface.filter_not_null, str)
                              else list(surface.filter_not_null))
                if surface.distinct:
                    named.append(surface.distinct)
                named += [fk for fk, _ in surface.tenant_via]
                for column in named:
                    if column not in columns:
                        problems.append("%s: %s has no column %s"
                                        % (concept, cls, column))
                for _, parent in surface.tenant_via:
                    table = db.metadata.tables.get(parent)
                    if table is None or "organization_id" not in table.c:
                        problems.append("%s: %s links to %s, which has no "
                                        "organization_id" % (concept, cls, parent))
                if (not gate._session_scoped(model)
                        and "organization_id" not in columns
                        and not surface.tenant_via and not surface.shared):
                    unscoped.add(surface.name)
    assert not problems, problems
    assert unscoped == KNOWN_UNSCOPED


def test_every_http_surface_is_a_registered_get_route(app):
    adapter = app.url_map.bind("localhost")
    missing = []
    for concept, surfaces in gate.CONCEPTS.items():
        for surface in surfaces:
            if surface.kind != "http":
                continue
            path = surface.target.split("?", 1)[0]
            try:
                adapter.match(path, method="GET")
            except Exception as exc:  # NotFound, MethodNotAllowed, redirects
                missing.append("%s: %s (%s)" % (concept, path, type(exc).__name__))
    assert not missing, missing


# ---------------------------------------------------------------------------
# The judgement, through the gate's own --root probe mode.
# ---------------------------------------------------------------------------
def _run_probe(tmp_path, probe):
    (tmp_path / "store_agreement_probe.json").write_text(json.dumps(probe))
    proc = subprocess.run([sys.executable, SCRIPT, "--root", str(tmp_path)],
                          capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    return int(lines[-1]), proc.stdout


def _probe(concept, count, overrides=None):
    rows = []
    for surface in gate.CONCEPTS[concept]:
        n = count if surface.scope == "all" else max(count - 1, 0)
        rows.append({"surface": surface.name, "count": n, "scope": surface.scope})
    for name, value in (overrides or {}).items():
        for row in rows:
            if row["surface"] == name:
                row["count"] = value
    return {concept: rows}


def _whole_population(concept):
    return [s.name for s in gate.CONCEPTS[concept] if s.scope == "all"]


@pytest.mark.parametrize("concept", sorted(EXPECTED))
def test_probe_agreeing_surfaces_pass(tmp_path, concept):
    probe = _probe(concept, 7)
    # A declared narrower surface reading less than the whole is explained by
    # its declaration, never reported.
    probe[concept].append({"surface": "declared narrower", "count": 2,
                           "scope": "status=open"})
    count, out = _run_probe(tmp_path, probe)
    assert count == 0, out


@pytest.mark.parametrize("concept", sorted(EXPECTED))
def test_probe_disagreement_names_both_surfaces_and_numbers(tmp_path, concept):
    first, second = _whole_population(concept)[:2]
    count, out = _run_probe(tmp_path, _probe(concept, 7, {second: 10}))
    assert count == 1, out
    finding = [ln for ln in out.splitlines() if "[store-disagreement]" in ln]
    assert len(finding) == 1, out
    assert "%s=10" % second in finding[0]
    assert "%s=7" % first in finding[0]
    assert finding[0].strip().startswith(concept)


@pytest.mark.parametrize("concept", sorted(EXPECTED))
def test_probe_all_zero_is_no_evidence(tmp_path, concept):
    count, out = _run_probe(tmp_path, _probe(concept, 0))
    assert count == 0
    assert "%s [no-evidence]" % concept in out


def test_probe_narrower_scope_exceeding_the_whole_is_reported(tmp_path):
    probe = _probe("pending change proposals", 3)
    for row in probe["pending change proposals"]:
        if row["scope"] != "all":
            row["count"] = 9
    count, out = _run_probe(tmp_path, probe)
    assert count == 1, out
    assert "MORE than the unfiltered population" in out


def test_probe_unscoped_store_with_rows_is_a_finding(tmp_path):
    probe = _probe("architecture decisions", 4)
    for row in probe["architecture decisions"]:
        if row["surface"] == "orm:DecisionLedger":
            row["count"] = 11
            row["unscoped"] = True
    count, out = _run_probe(tmp_path, probe)
    assert count == 1, out
    assert "[unscoped-store] orm:DecisionLedger holds 11 rows" in out

    for row in probe["architecture decisions"]:
        if row["surface"] == "orm:DecisionLedger":
            row["count"] = 0
    count, out = _run_probe(tmp_path, probe)
    assert count == 0, out


# ---------------------------------------------------------------------------
# Two organisations: B's rows never move A's counts.
# ---------------------------------------------------------------------------
def _seed(db_session, org, user, owners, costs, risks, packages, approvals):
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval
    from app.models.application_owner import ApplicationOwner
    from app.models.application_portfolio import ApplicationComponent
    from app.models.enterprise_intelligence import ApplicationCost
    from app.models.risk import Risk
    from app.models.roadmap_models import RoadmapWorkPackage

    for i in range(max(owners, costs)):
        application = ApplicationComponent(
            name="App %s %s" % (i, uuid.uuid4().hex[:6]),
            organization_id=org.id,
            business_owner="Owner %s" % i if i < owners else None)
        db_session.add(application)
        db_session.flush()
        if i < owners:
            # Two owner rows for one application still count it once.
            for kind in ("primary", "technical"):
                db_session.add(ApplicationOwner(
                    application_id=application.id, user_id=user.id,
                    organization_id=org.id, ownership_type=kind))
        if i < costs:
            db_session.add(ApplicationCost(
                application_id=application.id, fiscal_year=2026,
                total_cost=1000))
    for i in range(risks):
        db_session.add(Risk(title="Risk %s" % i, likelihood=2, impact=3,
                            organization_id=org.id))
    for i in range(packages):
        db_session.add(RoadmapWorkPackage(name="Package %s" % i,
                                          business_capability="Billing",
                                          created_by=user.id))
    for i in range(approvals):
        db_session.add(AIChatCRUDApproval(
            user_id=user.id, organization_id=org.id, operation_type="create",
            entity_type="capability", original_command="add capability",
            operation_payload="{}", summary="Add a capability",
            expires_at=datetime.utcnow() + timedelta(hours=1)))
    db_session.flush()


def _make_user(db_session, org):
    from app.models.user import User

    user = User(email="sa-%s@example.com" % uuid.uuid4().hex[:10],
                first_name="Store", last_name="Agreement",
                organization_id=org.id)
    user.password = uuid.uuid4().hex
    db_session.add(user)
    db_session.flush()
    return user


def _counts(app, tenant_ctx, org_id):
    from app import db

    with tenant_ctx(org_id):
        observations, _notes = gate.observe_tenant(
            app, db, org_id, http=False,
            concepts={k: gate.CONCEPTS[k] for k in (
                "application owners", "applications with a recorded annual cost",
                "risks", "work packages", "pending change proposals",
                "architecture decisions")})
    return ({concept: {row[0]: row[1] for row in rows if len(row) < 4 or not row[3]}
             for concept, rows in observations.items()},
            {concept: {row[0] for row in rows if len(row) > 3 and row[3]}
             for concept, rows in observations.items()})


def test_two_organisations_never_change_each_others_counts(
        app, db_session, make_org, tenant_ctx):
    org_a, org_b = make_org("store-a"), make_org("store-b")
    user_a, user_b = _make_user(db_session, org_a), _make_user(db_session, org_b)
    _seed(db_session, org_a, user_a, owners=2, costs=1, risks=3, packages=1,
          approvals=2)

    before, unscoped = _counts(app, tenant_ctx, org_a.id)
    assert before["application owners"]["orm:ApplicationOwner(applications)"] == 2
    assert before["application owners"][
        "orm:ApplicationOwner(applications, primary)"] == 2
    assert before["application owners"][
        "orm:ApplicationComponent(owner text recorded)"] == 2
    assert before["applications with a recorded annual cost"][
        "orm:ApplicationCost(applications)"] == 1
    assert before["risks"]["orm:Risk"] == 3
    assert before["work packages"]["orm:RoadmapWorkPackage"] == 1
    assert before["pending change proposals"]["orm:AIChatCRUDApproval(pending)"] == 2
    assert unscoped["architecture decisions"] == {"orm:DecisionLedger"}

    _seed(db_session, org_b, user_b, owners=5, costs=4, risks=6, packages=3,
          approvals=1)
    after, _ = _counts(app, tenant_ctx, org_a.id)
    assert after == before

    b_counts, _ = _counts(app, tenant_ctx, org_b.id)
    assert b_counts["application owners"]["orm:ApplicationOwner(applications)"] == 5
    assert b_counts["applications with a recorded annual cost"][
        "orm:ApplicationCost(applications)"] == 4
    assert b_counts["risks"]["orm:Risk"] == 6
    assert b_counts["work packages"]["orm:RoadmapWorkPackage"] == 3
    assert b_counts["pending change proposals"][
        "orm:AIChatCRUDApproval(pending)"] == 1


def test_row_no_link_attributes_counts_for_no_organisation(
        app, db_session, make_org, tenant_ctx):
    from app.models.roadmap_models import RoadmapWorkPackage

    org = make_org("store-orphan")
    user = _make_user(db_session, org)
    db_session.add(RoadmapWorkPackage(name="Owned", business_capability="Billing",
                                      created_by=user.id))
    db_session.add(RoadmapWorkPackage(name="Orphan", business_capability="Billing"))
    db_session.flush()

    from app import db

    surface = next(s for s in gate.CONCEPTS["work packages"]
                   if s.name == "orm:RoadmapWorkPackage")
    with tenant_ctx(org.id):
        count, why, unscoped, unattributed = gate._count_orm(
            surface, db, org.id)
    assert (count, why, unscoped) == (1, None, False)
    assert unattributed >= 1
