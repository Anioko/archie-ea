"""One decision register, consolidation PR 1.

- architecture_decision_records pairs into architecture_decisions (dual-write);
  the source stays readable and stays the system of record for its own fields.
- decision_ledger gains a real organisation column and is fenced by the
  existing tenant middleware; before this, every ARB session's ledger loaded
  every organisation's rows.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app import db

REPO_ROOT = Path(__file__).resolve().parents[1]
from app.commands.backfill_decision_register_consolidation import run_backfill
from app.models.adr import ArchitectureDecisionRecord
from app.models.architecture_decision import ArchitectureDecision
from app.models.decision_ledger import DecisionLedger
from app.models.unified_capability import UnifiedCapability


def _make_adr_record(org_id, **overrides):
    defaults = dict(
        adr_number=1,
        title="Use REST for external integrations",
        status="proposed",
        context="Need a standard integration approach",
        decision="Use RESTful APIs",
        rationale="Industry standard",
        consequences="Need an API gateway",
        organization_id=org_id,
    )
    defaults.update(overrides)
    record = ArchitectureDecisionRecord(**defaults)
    db.session.add(record)
    db.session.flush()
    return record


def _make_capability(org_id, name="Customer Acquisition"):
    cap = UnifiedCapability(name=name, level=1, organization_id=org_id)
    db.session.add(cap)
    db.session.flush()
    return cap


# ------------------------------------------------- ADR -> canonical pairing


def test_pairing_creates_a_visible_canonical_decision(db_session, make_org, tenant_ctx):
    org = make_org("adr-pair")
    with tenant_ctx(org.id):
        record = _make_adr_record(org.id)
        canonical = record.pair_with_canonical_register()
        db.session.commit()

        assert canonical is not None
        assert record.retired_into_id == canonical.id
        assert canonical.organization_id == org.id
        assert canonical.source_table == "architecture_decision_records"
        assert canonical.source_id == record.id
        assert canonical.title == record.title


def test_pairing_is_idempotent(db_session, make_org, tenant_ctx):
    org = make_org("adr-idem")
    with tenant_ctx(org.id):
        record = _make_adr_record(org.id)
        first = record.pair_with_canonical_register()
        db.session.commit()
        second = record.pair_with_canonical_register()
        db.session.commit()

        assert first.id == second.id
        assert ArchitectureDecision.query.filter_by(
            source_table="architecture_decision_records", source_id=record.id
        ).count() == 1


def test_pairing_never_visible_to_another_organisation(db_session, make_org, tenant_ctx):
    org_a = make_org("adr-a")
    org_b = make_org("adr-b")
    with tenant_ctx(org_a.id):
        record = _make_adr_record(org_a.id, title="Org A's decision")
        canonical = record.pair_with_canonical_register()
        db.session.commit()
        canonical_id = canonical.id

    with tenant_ctx(org_b.id):
        # filter_by (not .get(), which checks the identity map first and can
        # return an already-loaded row from another org without re-querying,
        # bypassing the tenant filter -- see app/models/adr.py's own note).
        assert ArchitectureDecision.query.filter_by(id=canonical_id).first() is None
        assert ArchitectureDecision.query.filter_by(title="Org A's decision").first() is None


def test_repointed_constructor_site_pairs_immediately(db_session, make_org, tenant_ctx):
    """The pattern every repointed call site now follows: add, flush, pair, commit."""
    org = make_org("adr-site")
    with tenant_ctx(org.id):
        adr = ArchitectureDecisionRecord(
            adr_number=1,
            title="AI-recorded decision",
            status="proposed",
            context="ctx",
            decision="dec",
            rationale="rat",
            consequences="cons",
        )
        db.session.add(adr)
        db.session.flush()
        adr.pair_with_canonical_register()
        db.session.commit()

        assert adr.retired_into_id is not None
        paired = ArchitectureDecision.query.filter_by(id=adr.retired_into_id).first()
        assert paired.organization_id == org.id
        assert paired.title == "AI-recorded decision"


# ------------------------------------------------------- backfill command


def test_backfill_pairs_every_pending_record(db_session, make_org, tenant_ctx):
    org = make_org("adr-backfill")
    with tenant_ctx(org.id):
        r1 = _make_adr_record(org.id, adr_number=1, title="First")
        r2 = _make_adr_record(org.id, adr_number=2, title="Second")
        db.session.commit()

    adr_stats, _ = run_backfill(dry_run=False)
    assert adr_stats["paired"] >= 2

    db.session.refresh(r1)
    db.session.refresh(r2)
    assert r1.retired_into_id is not None
    assert r2.retired_into_id is not None


def test_backfill_run_twice_creates_no_duplicate_pairs(db_session, make_org, tenant_ctx):
    org = make_org("adr-backfill-idem")
    with tenant_ctx(org.id):
        record = _make_adr_record(org.id)
        db.session.commit()
        record_id = record.id

    run_backfill(dry_run=False)
    run_backfill(dry_run=False)  # second run must be a no-op for this row

    assert ArchitectureDecision.query.filter_by(
        source_table="architecture_decision_records", source_id=record_id
    ).count() == 1


# No test for an ArchitectureDecisionRecord with organization_id=None: the
# column is NOT NULL at the database level (it has carried TenantMixin since
# before this brief) and that constraint is enforced regardless of insert
# path, so the state cannot actually occur. The backfill command's
# `skipped_no_org` branch is defensive (belt-and-suspenders, matching the
# same-named guard in other backfill_*.py commands) rather than reachable.


# --------------------------------------------- decision_ledger tenant fence


def test_decision_ledger_never_shows_another_organisations_rows(db_session, make_org, tenant_ctx):
    org_a = make_org("ledger-a")
    org_b = make_org("ledger-b")

    with tenant_ctx(org_a.id):
        row_a = DecisionLedger(
            capability_id="999001",
            capability_name_snapshot="Org A capability",
            decision_id="DEC-A-1",
            decision_summary="Org A decision",
        )
        db.session.add(row_a)
        db.session.commit()

    with tenant_ctx(org_b.id):
        row_b = DecisionLedger(
            capability_id="999002",
            capability_name_snapshot="Org B capability",
            decision_id="DEC-B-1",
            decision_summary="Org B decision",
        )
        db.session.add(row_b)
        db.session.commit()

        # The exact bug this closes: before TenantMixin, this query returned
        # every organisation's rows.
        visible = DecisionLedger.query.all()
        assert [r.decision_summary for r in visible] == ["Org B decision"]

    with tenant_ctx(org_a.id):
        visible = DecisionLedger.query.all()
        assert [r.decision_summary for r in visible] == ["Org A decision"]


def test_decision_ledger_backfill_derives_org_from_capability(db_session, make_org, tenant_ctx):
    org = make_org("ledger-backfill")
    with tenant_ctx(org.id):
        cap = _make_capability(org.id)
        cap_id = cap.id
        db.session.commit()

    # Raw SQL, explicit NULL organisation_id: every pre-existing row is in
    # exactly this state right after the schema expand. Deliberately not the
    # ORM constructor -- its default fills organization_id from context in
    # ways that would make this fixture's own state depend on ambient test
    # ordering rather than asserting the thing this test is actually about.
    row_id = db.session.execute(db.text(
        "INSERT INTO decision_ledger "
        "(capability_id, capability_name_snapshot, decision_id, decision_summary, decision_sequence, decision_date, created_at, organization_id) "
        "VALUES (:cap_id, 'Backfill target', 'DEC-BF-1', 'Needs an org', 1, now(), now(), NULL) RETURNING id"
    ), {"cap_id": str(cap_id)}).scalar()
    db.session.commit()

    assert db.session.execute(
        db.text("SELECT organization_id FROM decision_ledger WHERE id = :i"), {"i": row_id}
    ).scalar() is None

    _, ledger_stats = run_backfill(dry_run=False)
    assert ledger_stats["backfilled"] >= 1

    resolved_org = db.session.execute(
        db.text("SELECT organization_id FROM decision_ledger WHERE id = :i"), {"i": row_id}
    ).scalar()
    assert resolved_org == org.id


def test_decision_ledger_backfill_leaves_unresolvable_rows_as_orphans(db_session, make_org):
    row_id = db.session.execute(db.text(
        "INSERT INTO decision_ledger "
        "(capability_id, capability_name_snapshot, decision_id, decision_summary, decision_sequence, decision_date, created_at, organization_id) "
        "VALUES ('not-a-number', 'Unresolvable', 'DEC-ORPHAN-1', 'No matching capability', 1, now(), now(), NULL) "
        "RETURNING id"
    )).scalar()
    db.session.commit()

    _, ledger_stats = run_backfill(dry_run=False)
    assert ledger_stats["orphan"] >= 1

    resolved_org = db.session.execute(
        db.text("SELECT organization_id FROM decision_ledger WHERE id = :i"), {"i": row_id}
    ).scalar()
    assert resolved_org is None


# ----------------------------------------------- final-check fix round


def test_solution_teardown_deletes_the_paired_canonical_row_too(app):
    """Regression (final check DEFECT-1): a solution's full architecture
    teardown hard-deletes architecture_decision_records by
    architecture_model_id with no awareness of retired_into_id, leaving the
    paired architecture_decisions row dangling.

    Does not use the db_session fixture: _engine_archimate_cleanup
    deliberately opens its own db.engine.begin() connection (see its own
    docstring -- avoiding lock contention with the ORM session), which is
    outside db_session's SAVEPOINT-based rollback contract and would not see
    data set up through it. Commits for real instead, with manual cleanup.
    """
    from app.models.architecture_decision import ArchitectureDecision
    from app.models.adr import ArchitectureDecisionRecord
    from app.models.models import ArchitectureModel
    from app.models.organization import Organization
    from app.models.solution_models import Solution
    from app.modules.solutions_strategic.v2.routes.solution_design_routes import (
        _engine_archimate_cleanup,
    )

    with app.app_context():
        org = Organization(name="Teardown test org", slug=f"teardown-{uuid.uuid4().hex[:10]}")
        db.session.add(org)
        db.session.flush()

        solution = Solution(name="Teardown target", organization_id=org.id)
        db.session.add(solution)
        db.session.flush()

        model = ArchitectureModel(
            organization_id=org.id, name="Teardown model", version="1.0",
            solution_id=solution.id, model_data="{}", is_default=False,
        )
        db.session.add(model)
        db.session.flush()

        record = _make_adr_record(org.id, architecture_model_id=model.id)
        canonical = record.pair_with_canonical_register()
        db.session.commit()
        record_id, canonical_id, solution_id, model_id, org_id = (
            record.id, canonical.id, solution.id, model.id, org.id,
        )

        try:
            _engine_archimate_cleanup([solution_id])
            db.session.expire_all()

            remaining_record = db.session.get(ArchitectureDecisionRecord, record_id)
            remaining_canonical = db.session.get(ArchitectureDecision, canonical_id)
            assert remaining_record is None
            assert remaining_canonical is None, (
                "canonical row left dangling after its source was deleted"
            )
        finally:
            db.session.rollback()
            db.session.execute(
                db.text("DELETE FROM architecture_decisions WHERE id = :i"), {"i": canonical_id}
            )
            db.session.execute(
                db.text("DELETE FROM architecture_decision_records WHERE id = :i"), {"i": record_id}
            )
            db.session.execute(
                db.text("DELETE FROM architecture_models WHERE id = :i"), {"i": model_id}
            )
            db.session.execute(
                db.text("DELETE FROM solutions WHERE id = :i"), {"i": solution_id}
            )
            db.session.execute(
                db.text("DELETE FROM organizations WHERE id = :i"), {"i": org_id}
            )
            db.session.commit()


def test_set_status_updates_the_paired_canonical_row_too(db_session, make_org, tenant_ctx):
    """Regression (final check DEFECT-2): SolutionOptionsAdvisor.set_status()
    updated only ArchitectureDecisionRecord, leaving the paired
    ArchitectureDecision stale.
    """
    from app.modules.solutions_strategic.v2.services.solution_options_advisor import (
        SolutionOptionsAdvisor,
    )

    org = make_org("setstatus")
    with tenant_ctx(org.id):
        record = _make_adr_record(org.id, status="proposed")
        canonical = record.pair_with_canonical_register()
        db.session.commit()

        result = SolutionOptionsAdvisor.set_status(record.id, "accepted", user_id=1)

        assert result["success"] is True
        db.session.refresh(record)
        db.session.refresh(canonical)
        assert record.status == "accepted"
        assert canonical.status == "accepted", "paired canonical row left stale after set_status"


def test_architecture_decision_record_is_no_longer_a_store_agreement_peer():
    """Regression (final check DEFECT-3): a canonical-only ArchitectureDecision
    (no paired ArchitectureDecisionRecord) used to make the "architecture
    decisions" store-agreement concept disagree, since
    ArchitectureDecisionRecord was listed as an independent peer surface --
    e.g. one canonical-only row gave architecture_decisions=1,
    architecture_decision_records=0 for the same organisation. It is now a
    satellite of the canonical store (paired via retired_into_id), not a
    peer answering the same question, so it must no longer be one of the
    concept's compared surfaces.
    """
    source = (REPO_ROOT / "scripts" / "check_store_agreement.py").read_text()
    start = source.index('"architecture decisions": [')
    end = source.index("],", start)
    concept_block = source[start:end]
    assert 'Surface("orm:ArchitectureDecisionRecord"' not in concept_block, (
        "ArchitectureDecisionRecord must not be a peer surface of the "
        "architecture decisions concept any more"
    )
    assert 'Surface("orm:ArchitectureDecision"' in concept_block  # the concept itself still exists


def test_adr_record_json_api_surfaces_its_canonical_pairing(db_session, make_org, tenant_ctx, client, login_as):
    """Regression (final check DEFECT-5, MEDIUM): the only ADR route that
    still reads architecture_decision_records directly (the rest already
    redirected to the canonical register before this PR) now also surfaces
    the pairing, so a caller can reach the canonical register from here too.
    This field does not exist on anioko/main.
    """
    from app.models.user import User

    org = make_org("adr-json-pairing")
    with tenant_ctx(org.id):
        user = User(
            email=f"adr-view-{uuid.uuid4().hex[:10]}@example.test",
            first_name="ADR", last_name="Viewer",
            organization_id=org.id, confirmed=True,
        )
        db_session.add(user)
        db_session.flush()

        record = _make_adr_record(org.id)
        canonical = record.pair_with_canonical_register()
        db_session.commit()
        record_id, canonical_id = record.id, canonical.id

    login_as(client, user)
    resp = client.get(f"/architecture/adrs/records/{record_id}")

    assert resp.status_code == 200
    payload = resp.get_json()["adr"]
    assert payload["canonical_decision_id"] == canonical_id
    assert payload["canonical_decision_url"] is not None
    assert str(canonical_id) in payload["canonical_decision_url"]
