"""T-003 / task 01 acceptance criteria 5, 6, 7 (via run_and_persist / upsert)."""

from __future__ import annotations

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
