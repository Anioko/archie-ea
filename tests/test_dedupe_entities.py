"""ARCH-030(ii): flask dedupe-entities CLI (app/commands/dedupe_entities.py).

--dry-run report accuracy is checked against the shared test DB (read-only —
dry-run never writes). The real-write (non-dry-run) path is exercised ONLY
inside db_session, which always rolls back at teardown, per CLAUDE.md.
"""
from __future__ import annotations


def test_dry_run_reports_groups_without_deleting(db_session, make_org, tenant_ctx):
    from app.models.archimate_core import ArchiMateElement
    from app.commands.dedupe_entities import dedupe_model

    org = make_org("dedupe-dry")

    with tenant_ctx(org.id):
        winner = ArchiMateElement(name="Customer Portal", type="ApplicationComponent", organization_id=org.id)
        loser1 = ArchiMateElement(name="Customer  Portal", type="ApplicationComponent", organization_id=org.id)
        loser2 = ArchiMateElement(name="CUSTOMER PORTAL", type="ApplicationComponent", organization_id=org.id)
        distinct = ArchiMateElement(name="Billing Service", type="ApplicationComponent", organization_id=org.id)
        db_session.add_all([winner, loser1, loser2, distinct])
        db_session.flush()

        report = dedupe_model("archimate_element", dry_run=True)

        matching_groups = [
            g for g in report["group_detail"]
            if g["organization_id"] == org.id and g["normalized_name"] == "customer portal"
        ]
        assert len(matching_groups) == 1
        group = matching_groups[0]
        assert group["winner_id"] == winner.id
        assert set(group["loser_ids"]) == {loser1.id, loser2.id}

        # dry-run must not have deleted anything
        remaining = ArchiMateElement.query.filter(ArchiMateElement.id.in_(
            [winner.id, loser1.id, loser2.id]
        )).count()
        assert remaining == 3


def test_real_run_repoints_fk_and_deletes_losers(db_session, make_org, tenant_ctx):
    """Real (non-dry-run) write, confined to db_session's rolled-back transaction."""
    from app import db
    from app.models.archimate_core import ArchiMateElement
    from app.models.application_portfolio import ApplicationComponent
    from app.commands.dedupe_entities import dedupe_model

    org = make_org("dedupe-real")

    with tenant_ctx(org.id):
        winner = ArchiMateElement(name="Order Service", type="ApplicationComponent", organization_id=org.id)
        loser = ArchiMateElement(name="order service", type="ApplicationComponent", organization_id=org.id)
        db_session.add_all([winner, loser])
        db_session.flush()

        # A row referencing the loser via a real FK -- exercise the generic
        # reflected-FK repoint against capability_archimate_classifications,
        # which has archimate_element_id -> archimate_elements.id.
        from app.models.business_capabilities import BusinessCapability
        from app.models.capability_archimate_mapping import CapabilityArchiMateClassification

        cap = BusinessCapability(name="Order Management", organization_id=org.id)
        db_session.add(cap)
        db_session.flush()

        ref = CapabilityArchiMateClassification(
            capability_id=cap.id,
            archimate_layer="application",
            archimate_element_type="ApplicationComponent",
            archimate_element_id=loser.id,
        )
        db_session.add(ref)
        db_session.flush()
        ref_id = ref.id
        winner_id, loser_id = winner.id, loser.id

        report = dedupe_model("archimate_element", dry_run=False)

        assert report["rows_deleted"] >= 1
        db_session.expire_all()
        remaining_ids = {
            row[0]
            for row in db.session.execute(
                db.text("SELECT id FROM archimate_elements WHERE id IN (:w, :l)"),
                {"w": winner_id, "l": loser_id},
            )
        }
        assert winner_id in remaining_ids
        assert loser_id not in remaining_ids

        repointed = db.session.execute(
            db.text("SELECT archimate_element_id FROM capability_archimate_classifications WHERE id = :id"),
            {"id": ref_id},
        ).scalar()
        assert repointed == winner.id


def test_merge_duplicate_rows_rejects_cross_org(db_session, make_org, tenant_ctx):
    """ARCH-030(ii) admin merge engine: never merges across organisations."""
    from app.models.archimate_core import ArchiMateElement
    from app.commands.dedupe_entities import merge_duplicate_rows

    org_a = make_org("merge-a")
    org_b = make_org("merge-b")

    winner = ArchiMateElement(name="Payments Gateway", type="ApplicationComponent", organization_id=org_a.id)
    same_org_loser = ArchiMateElement(name="Payments Gateway Dup", type="ApplicationComponent", organization_id=org_a.id)
    other_org_row = ArchiMateElement(name="Payments Gateway Other", type="ApplicationComponent", organization_id=org_b.id)
    db_session.add_all([winner, same_org_loser, other_org_row])
    db_session.flush()
    winner_id = winner.id
    same_org_loser_id = same_org_loser.id
    other_org_row_id = other_org_row.id

    report = merge_duplicate_rows(
        "archimate_element",
        winner_id,
        [same_org_loser_id, other_org_row_id],
        organization_id=org_a.id,
        dry_run=False,
    )

    assert report["rows_deleted"] == 1
    assert other_org_row_id in report["rejected_ids"]

    from app import db
    remaining_ids = {
        row[0]
        for row in db.session.execute(
            db.text("SELECT id FROM archimate_elements WHERE id IN (:a, :b)"),
            {"a": same_org_loser_id, "b": other_org_row_id},
        )
    }
    assert same_org_loser_id not in remaining_ids  # merged
    assert other_org_row_id in remaining_ids  # untouched, different org
