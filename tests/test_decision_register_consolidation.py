"""R1-B09: one decision register, PR 1 (consolidation).

- architecture_decision_records pairs into architecture_decisions (dual-write);
  the source stays readable and stays the system of record for its own fields.
- decision_ledger gains a real organisation column and is fenced by the
  existing tenant middleware; before this, every ARB session's ledger loaded
  every organisation's rows.
"""
from __future__ import annotations

import pytest

from app import db
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
        assert ArchitectureDecision.query.get(canonical_id) is None
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
        paired = ArchitectureDecision.query.get(adr.retired_into_id)
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


def test_backfill_skips_a_record_with_no_organisation(db_session, make_org):
    """Never guess a tenant: a record with no org is left unpaired."""
    record = ArchitectureDecisionRecord(
        adr_number=1,
        title="Orphan",
        status="proposed",
        context="ctx",
        decision="dec",
        rationale="rat",
        consequences="cons",
        organization_id=None,
    )
    db.session.add(record)
    db.session.commit()

    adr_stats, _ = run_backfill(dry_run=False)
    assert adr_stats["skipped_no_org"] >= 1

    db.session.refresh(record)
    assert record.retired_into_id is None


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

    # Inserted with no organisation, as every pre-existing row would be
    # right after the schema expand (bypassing the ORM tenant stamp on
    # purpose, to simulate a genuinely un-migrated row).
    row = DecisionLedger(
        capability_id=str(cap_id),
        capability_name_snapshot="Backfill target",
        decision_id="DEC-BF-1",
        decision_summary="Needs an org",
    )
    db.session.add(row)
    db.session.commit()
    row_id = row.id

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
    row = DecisionLedger(
        capability_id="not-a-number",
        capability_name_snapshot="Unresolvable",
        decision_id="DEC-ORPHAN-1",
        decision_summary="No matching capability",
    )
    db.session.add(row)
    db.session.commit()
    row_id = row.id

    _, ledger_stats = run_backfill(dry_run=False)
    assert ledger_stats["orphan"] >= 1

    resolved_org = db.session.execute(
        db.text("SELECT organization_id FROM decision_ledger WHERE id = :i"), {"i": row_id}
    ).scalar()
    assert resolved_org is None
