"""Historical review references leave ownership unassigned until it is established."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")

NOT_FOUND = {"success": False, "error": "Review item not found"}


def _make_user(db_session, org):
    from werkzeug.security import generate_password_hash

    from app.models.user import User

    user = User(
        email=f"backfill-{uuid.uuid4().hex[:10]}@example.com",
        first_name="Backfill",
        last_name="Tester",
        confirmed=True,
        organization_id=org.id,
        password_hash=generate_password_hash(uuid.uuid4().hex),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _application(db_session, org):
    from app.models.application_portfolio import ApplicationComponent

    application = ApplicationComponent(name=f"App {uuid.uuid4().hex[:8]}", organization_id=org.id)
    db_session.add(application)
    db_session.flush()
    return application


def _unattributed_item(db_session, item_type, item_id, assigned_to=None, reviewed_by=None):
    """An item as it exists before the backfill: no organisation."""
    from sqlalchemy import text

    from app.models.confidence_review import ReviewQueueItem

    item = ReviewQueueItem(
        item_type=item_type,
        item_id=item_id,
        item_name=f"Item {uuid.uuid4().hex[:8]}",
        confidence_score=0.5,
        assigned_to_id=getattr(assigned_to, "id", None),
        reviewed_by_id=getattr(reviewed_by, "id", None),
    )
    db_session.add(item)
    db_session.flush()
    db_session.execute(
        text("UPDATE review_queue_items SET organization_id = NULL WHERE id = :id"),
        {"id": item.id},
    )
    db_session.expire(item)
    return item.id


def _organisation_of(db_session, item_id):
    from sqlalchemy import text

    return db_session.execute(
        text("SELECT organization_id FROM review_queue_items WHERE id = :id"), {"id": item_id}
    ).scalar()


@pytest.fixture
def seeded(db_session, make_org):
    """Items covering every outcome of the backfill."""
    from app.commands.backfill_review_queue_org import run_backfill

    # Settle any unattributed rows already in the database, and remember what is
    # left, so the counts below are exactly those of the rows seeded here.
    leftover = run_backfill()["left"]

    org_a, org_b = make_org("backfill-a"), make_org("backfill-b")
    user_a, user_a2, user_b, user_b2 = (
        _make_user(db_session, o) for o in (org_a, org_a, org_b, org_b)
    )
    app_a, app_b = _application(db_session, org_a), _application(db_session, org_b)

    items = {
        # About an application, and every user named belongs to its organisation.
        "application_and_reviewer": _unattributed_item(
            db_session, "capability_mapping", app_a.id, assigned_to=user_a
        ),
        "application_and_both_reviewers": _unattributed_item(
            db_session, "process_mapping", app_b.id, assigned_to=user_b, reviewed_by=user_b2
        ),
        # Not about a known application: the users share one organisation.
        "assigned_reviewer": _unattributed_item(
            db_session, "archimate_element", 999, assigned_to=user_a
        ),
        "deciding_user": _unattributed_item(
            db_session, "archimate_element", 999, reviewed_by=user_b
        ),
        "reviewers_agree": _unattributed_item(
            db_session, "archimate_element", 999, assigned_to=user_a, reviewed_by=user_a2
        ),
        "application_that_does_not_exist": _unattributed_item(
            db_session, "capability_mapping", 0, assigned_to=user_a2
        ),
        # Left without an organisation.
        "application_only": _unattributed_item(db_session, "capability_mapping", app_a.id),
        "other_application_only": _unattributed_item(db_session, "vendor_analysis", app_b.id),
        "application_of_another_organisation": _unattributed_item(
            db_session, "vendor_analysis", app_b.id, assigned_to=user_a
        ),
        "application_of_another_organisation_decided": _unattributed_item(
            db_session, "taxonomy_validation", app_b.id, reviewed_by=user_a
        ),
        "reviewers_disagree": _unattributed_item(
            db_session, "archimate_element", 999, assigned_to=user_a, reviewed_by=user_b
        ),
        "application_and_reviewers_disagree": _unattributed_item(
            db_session, "capability_mapping", app_a.id, assigned_to=user_a, reviewed_by=user_b
        ),
        "no_reviewers": _unattributed_item(db_session, "archimate_element", 999),
    }
    # Commit so a dry run, which rolls back its own statements, keeps these rows.
    db_session.commit()
    return {
        "items": items,
        "orgs": (org_a, org_b),
        "leftover": leftover,
        "expected": {
            "application_and_reviewer": None,
            "application_and_both_reviewers": None,
            "assigned_reviewer": None,
            "deciding_user": None,
            "reviewers_agree": None,
            "application_that_does_not_exist": None,
            "application_only": None,
            "other_application_only": None,
            "application_of_another_organisation": None,
            "application_of_another_organisation_decided": None,
            "reviewers_disagree": None,
            "application_and_reviewers_disagree": None,
            "no_reviewers": None,
        },
        "counts": {
            "attributed": {},
            "left": {
                "reviewers_and_application": 2,
                "reviewers": 4,
                "application_only": 2,
                "no_evidence": 1,
                "reviewers_disagree": 2,
                "application_conflict": 2,
            },
            "by_organisation": {},
        },
    }


def _expected_stats(seeded):
    """The stats a run over the seeded items reports, on top of what was left before."""
    counts = seeded["counts"]
    left = {name: seeded["leftover"][name] + n for name, n in counts["left"].items()}
    return {
        "attributed": counts["attributed"],
        "left": left,
        "by_organisation": counts["by_organisation"],
        "examined": sum(counts["attributed"].values()) + sum(left.values()),
        "remaining_nulls": sum(left.values()),
    }


def test_each_outcome_attributes_or_leaves_its_items(db_session, seeded):
    from app.commands.backfill_review_queue_org import run_backfill

    result = run_backfill()

    assert result == _expected_stats(seeded)
    for name, item_id in seeded["items"].items():
        assert _organisation_of(db_session, item_id) == seeded["expected"][name], name


def test_all_unowned_reference_shapes_are_hidden_through_routes(
    db_session, seeded, client, login_as
):
    from app.commands.backfill_review_queue_org import run_backfill

    run_backfill()
    hidden_ids = set(seeded["items"].values())
    for org in seeded["orgs"]:
        user = _make_user(db_session, org)
        for item_id in hidden_ids:
            login_as(client, user)
            response = client.get(f"/api/confidence/queue/{item_id}")
            assert (response.status_code, response.get_json()) == (404, NOT_FOUND)
        login_as(client, user)
        listing = client.get("/api/confidence/queue?limit=100").get_json()
        assert hidden_ids.isdisjoint(item["id"] for item in listing["items"])


def test_an_application_alone_never_attributes_an_item(db_session, seeded):
    """An item that names an application and no user stays unattributed."""
    from app.commands.backfill_review_queue_org import run_backfill

    run_backfill()

    for name in ("application_only", "other_application_only"):
        assert _organisation_of(db_session, seeded["items"][name]) is None, name


def test_users_of_another_organisation_than_the_application_leave_the_item_unattributed(
    db_session, seeded
):
    from app.commands.backfill_review_queue_org import run_backfill

    run_backfill()

    for name in (
        "application_of_another_organisation",
        "application_of_another_organisation_decided",
        "application_and_reviewers_disagree",
    ):
        assert _organisation_of(db_session, seeded["items"][name]) is None, name


def test_an_item_naming_another_organisations_application_is_visible_to_neither_after_the_backfill(
    db_session, client, login_as, make_org
):
    """The author's item about someone else's application is handed to nobody."""
    from app.commands.backfill_review_queue_org import run_backfill

    org_author, org_owner = make_org("backfill-author"), make_org("backfill-owner")
    author, owner = _make_user(db_session, org_author), _make_user(db_session, org_owner)
    application = _application(db_session, org_owner)
    other_org_item = _unattributed_item(
        db_session, "capability_mapping", application.id, assigned_to=author
    )
    owned_item = _unattributed_item(
        db_session, "capability_mapping", application.id, assigned_to=owner
    )
    db_session.commit()

    run_backfill()

    assert _organisation_of(db_session, other_org_item) is None
    assert _organisation_of(db_session, owned_item) is None
    for user in (owner, author):
        login_as(client, user)
        for item_id in (other_org_item, owned_item):
            login_as(client, user)
            response = client.get(f"/api/confidence/queue/{item_id}")
            assert (response.status_code, response.get_json()) == (404, NOT_FOUND)
        login_as(client, user)
        listing = client.get("/api/confidence/queue?limit=100").get_json()
        assert {other_org_item, owned_item}.isdisjoint(item["id"] for item in listing["items"])


def test_running_the_backfill_again_changes_nothing(db_session, seeded):
    from app.commands.backfill_review_queue_org import run_backfill

    first = run_backfill()
    stored = {name: _organisation_of(db_session, i) for name, i in seeded["items"].items()}
    second = run_backfill()

    # All unowned items remain unowned on every run.
    assert second["attributed"] == {}
    assert second["left"] == first["left"]
    assert second["by_organisation"] == {}
    assert second["remaining_nulls"] == first["remaining_nulls"]
    assert {name: _organisation_of(db_session, i) for name, i in seeded["items"].items()} == stored


def test_an_item_that_already_has_an_organisation_is_left_alone(db_session, seeded):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    org_a, org_b = seeded["orgs"]
    application = _application(db_session, org_a)
    user_a = _make_user(db_session, org_a)
    item_id = _unattributed_item(
        db_session, "capability_mapping", application.id, assigned_to=user_a
    )
    db_session.execute(
        text("UPDATE review_queue_items SET organization_id = :org WHERE id = :id"),
        {"org": org_b.id, "id": item_id},
    )

    run_backfill()

    assert _organisation_of(db_session, item_id) == org_b.id


def test_a_dry_run_reports_the_counts_and_changes_nothing(db_session, seeded, monkeypatch):
    from app.commands import backfill_review_queue_org as command

    with monkeypatch.context() as patch:
        def unexpected_schema_change(*args, **kwargs):
            pytest.fail("A dry run must not change the schema")

        patch.setattr(command, "ensure_organization_index_and_fk", unexpected_schema_change)
        dry = command.run_backfill(dry_run=True)
    assert dry == _expected_stats(seeded)
    for item_id in seeded["items"].values():
        assert _organisation_of(db_session, item_id) is None
    assert command.run_backfill() == dry


def test_a_dry_run_prints_each_outcome_and_where_items_would_land(app, db_session, seeded):
    from app.commands.backfill_review_queue_org import backfill_review_queue_org

    result = app.test_cli_runner().invoke(backfill_review_queue_org, ["--dry-run"])

    assert result.exit_code == 0, result.output
    assert "(dry-run)" in result.output
    for name in (
        "reviewers_and_application",
        "reviewers",
        "application_only",
        "no_evidence",
        "reviewers_disagree",
        "application_conflict",
    ):
        assert name in result.output
    assert "would attribute to no organisation" in result.output
    assert "ownership withheld" in result.output
    # Nothing was written.
    for item_id in seeded["items"].values():
        assert _organisation_of(db_session, item_id) is None


def test_the_backfill_runs_on_an_empty_table(db_session):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    if db_session.execute(text("SELECT count(*) FROM review_queue_items")).scalar_one():
        pytest.skip("Requires an empty authorized scratch queue; existing rows are preserved")

    empty = {
        "attributed": {},
        "left": {
            "reviewers_and_application": 0,
            "reviewers": 0,
            "application_only": 0,
            "no_evidence": 0,
            "reviewers_disagree": 0,
            "application_conflict": 0,
        },
        "by_organisation": {},
        "examined": 0,
        "remaining_nulls": 0,
    }
    assert run_backfill() == empty
    assert run_backfill(dry_run=True) == empty


def test_the_backfill_leaves_one_index_and_one_foreign_key_on_the_column(db_session):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    run_backfill()
    run_backfill()

    foreign_keys = db_session.execute(
        text(
            "SELECT count(*) FROM pg_constraint c "
            "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
            "WHERE c.conrelid = 'review_queue_items'::regclass AND c.contype = 'f' "
            "AND a.attname = 'organization_id'"
        )
    ).scalar()
    indexes = db_session.execute(
        text(
            "SELECT count(*) FROM pg_indexes WHERE tablename = 'review_queue_items' "
            "AND indexdef LIKE '%(organization_id)%'"
        )
    ).scalar()
    assert foreign_keys == 1
    assert indexes == 1


@pytest.mark.parametrize(
    "reviewer_orgs, reviewer_org, application_org",
    [
        pytest.param(1, 202, 202, id="matching-application-reviewer"),
        pytest.param(1, 202, None, id="reviewer-only"),
        pytest.param(2, 101, 202, id="conflicting-reviewers"),
        pytest.param(0, None, 202, id="null-org-reviewer"),
        pytest.param(0, None, None, id="absent-users"),
        pytest.param(1, 101, None, id="missing-application"),
        pytest.param(0, None, None, id="no-references"),
        pytest.param(1, 101, 101, id="matching-historical-references"),
    ],
)
def test_reference_shapes_do_not_establish_historical_ownership(
    reviewer_orgs, reviewer_org, application_org
):
    from app.commands.backfill_review_queue_org import classify

    assert classify(reviewer_orgs, reviewer_org, application_org)[1] is None


def test_missing_organisation_column_requires_reconciliation(db_session):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill

    # Transactional DDL restores the original column and its constraints.
    with db_session.begin_nested() as savepoint:
        db_session.execute(text("ALTER TABLE review_queue_items DROP COLUMN organization_id CASCADE"))
        for dry_run in (True, False):
            with pytest.raises(RuntimeError, match="run reconcile-schema first"):
                run_backfill(dry_run=dry_run)
        savepoint.rollback()


def _generic_subset(monkeypatch, *names):
    """Use real declared policies, limiting schema perturbations to named tables."""
    from app.commands import backfill_layer_tenancy as command

    inventory = command._tenant_tables()
    selected = [(name, nullable) for name, nullable in inventory if name in names]
    assert {name for name, _ in selected} == set(names)
    monkeypatch.setattr(command, "_tenant_tables", lambda: selected)
    return command


def _catalog(conn, table):
    from sqlalchemy import inspect

    inspector = inspect(conn)
    return {
        "columns": [(c["name"], str(c["type"]), c["nullable"], c.get("default"))
                    for c in inspector.get_columns(table, schema="public")],
        "indexes": inspector.get_indexes(table, schema="public"),
        "foreign_keys": inspector.get_foreign_keys(table, schema="public"),
    }


@pytest.fixture
def schema_shape(db_session):
    """Contain committed command DDL inside the shared fixture's connection."""
    from contextlib import contextmanager

    @contextmanager
    def shape(*tables):
        db_session.commit()
        conn = db_session.get_bind()
        before = {t: _catalog(conn, t) for t in tables}
        savepoint = conn.begin_nested()
        try:
            yield conn
        finally:
            db_session.rollback()
            savepoint.rollback()
            assert {t: _catalog(conn, t) for t in tables} == before

    return shape


@pytest.mark.parametrize("selection", [None, 0, 1])
def test_generic_preserves_review_quarantine_and_routes(
    db_session, seeded, monkeypatch, client, login_as, selection
):
    from sqlalchemy import text

    from app.commands.backfill_review_queue_org import run_backfill
    from app.models.confidence_review import ReviewDecision

    command = _generic_subset(monkeypatch, "review_queue_items")
    org_id = None if selection is None else seeded["orgs"][selection].id
    owned = []
    for org in seeded["orgs"]:
        item_id = _unattributed_item(db_session, "archimate_element", 999)
        db_session.execute(text(
            "UPDATE review_queue_items SET organization_id = :org WHERE id = :id"
        ), {"org": org.id, "id": item_id})
        reviewer = _make_user(db_session, org)
        db_session.add(ReviewDecision(
            review_item_id=item_id, reviewer_id=reviewer.id,
            decision_type="approve", decision_reason=uuid.uuid4().hex,
        ))
        owned.append(item_id)
    db_session.flush()
    before = db_session.execute(text(
        "SELECT to_jsonb(q) FROM review_queue_items q WHERE id = ANY(:ids) ORDER BY id"
    ), {"ids": owned}).scalars().all()
    decisions = db_session.execute(text(
        "SELECT to_jsonb(d) FROM review_decisions d WHERE review_item_id = ANY(:ids) ORDER BY id"
    ), {"ids": owned}).scalars().all()
    db_session.commit()
    run_backfill()
    for dry_run in (True, False, False):
        command.repair_layer_tenancy(org_id=org_id, dry_run=dry_run)
        for item_id in seeded["items"].values():
            assert _organisation_of(db_session, item_id) is None
        assert db_session.execute(text(
            "SELECT to_jsonb(q) FROM review_queue_items q WHERE id = ANY(:ids) ORDER BY id"
        ), {"ids": owned}).scalars().all() == before
        assert db_session.execute(text(
            "SELECT to_jsonb(d) FROM review_decisions d WHERE review_item_id = ANY(:ids) ORDER BY id"
        ), {"ids": owned}).scalars().all() == decisions
    # The existing route assertions cover every legacy reference shape for both tenants.
    test_all_unowned_reference_shapes_are_hidden_through_routes(
        db_session, seeded, client, login_as
    )


@pytest.mark.parametrize("shape", ["missing", "hardened_empty", "hardened_owned", "nullable", "absent"])
def test_generic_nullable_shapes_dry_run_repair_and_repeat(
    app, db_session, monkeypatch, schema_shape, shape, make_org, client, login_as
):
    from datetime import datetime

    from sqlalchemy import event, text

    from app.commands.backfill_review_queue_org import run_backfill
    from app.services.confidence_review_service import ConfidenceReviewService, ReviewQueueItemData

    command = _generic_subset(monkeypatch, "review_queue_items")
    org = make_org("nullable-shape")
    user = _make_user(db_session, org)
    table = "review_queue_items"
    with schema_shape(table) as conn:
        owned_id = None
        null_ids = []
        if shape == "hardened_empty" and conn.execute(text(
            "SELECT count(*) FROM review_queue_items"
        )).scalar_one():
            pytest.skip("Empty hardened shape requires an empty authorized scratch queue")
        if shape.startswith("hardened"):
            if conn.execute(text(
                "SELECT count(*) FROM review_queue_items WHERE organization_id IS NULL"
            )).scalar_one():
                pytest.skip("Hardened shape requires no unrelated NULL owners")
            if shape == "hardened_owned":
                owned_id = _unattributed_item(db_session, "archimate_element", 0)
                db_session.execute(text(
                    "UPDATE review_queue_items SET organization_id = :org WHERE id = :id"
                ), {"org": org.id, "id": owned_id})
            db_session.execute(text(
                "ALTER TABLE review_queue_items ALTER COLUMN organization_id SET NOT NULL"
            ))
        elif shape == "missing":
            null_ids.append(_unattributed_item(db_session, "archimate_element", 0))
            db_session.execute(text("ALTER TABLE review_queue_items DROP COLUMN organization_id CASCADE"))
        elif shape == "nullable":
            null_ids.append(_unattributed_item(db_session, "archimate_element", 0))
        elif shape == "absent":
            db_session.execute(text('ALTER TABLE review_queue_items RENAME TO review_queue_items_shape_test'))
        db_session.commit()
        before = None if shape == "absent" else _catalog(conn, table)
        writes = []

        def no_writes(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().split(None, 1)[0].upper() in {"ALTER", "UPDATE", "INSERT", "DELETE", "CREATE", "DROP"}:
                writes.append(statement)

        event.listen(conn, "before_cursor_execute", no_writes)
        try:
            dry = command.repair_layer_tenancy(dry_run=True)
        finally:
            event.remove(conn, "before_cursor_execute", no_writes)
        assert writes == []
        if before is not None:
            assert _catalog(conn, table) == before
        first = command.repair_layer_tenancy(org_id=org.id)
        assert first == dry
        second = command.repair_layer_tenancy()
        assert second["repaired"] == []
        if shape == "absent":
            assert first["absent"] == [table]
            return
        after = _catalog(conn, table)
        owner = next(c for c in after["columns"] if c[0] == "organization_id")
        assert owner[2] is True
        if shape == "missing":
            assert owner[3] is None
        assert after["indexes"] == before["indexes"]
        assert after["foreign_keys"] == before["foreign_keys"]
        for item_id in null_ids:
            assert _organisation_of(db_session, item_id) is None
        if owned_id is not None:
            assert _organisation_of(db_session, owned_id) == org.id
        run_backfill()
        run_backfill()
        finished = _catalog(conn, table)
        assert len([i for i in finished["indexes"] if i["column_names"] == ["organization_id"]]) == 1
        assert len([f for f in finished["foreign_keys"] if f["constrained_columns"] == ["organization_id"]]) == 1
        result = ConfidenceReviewService().add_to_review_queue(
            ReviewQueueItemData(
                item_type="archimate_element", item_id=0, item_name=uuid.uuid4().hex,
                item_data={}, confidence_score=0.5, confidence_factors={},
                ai_model_used="test-model", generation_timestamp=datetime.utcnow(),
                threshold_name="test",
            ),
            {"success": True, "action": {"priority": 5, "estimated_review_time": 24}},
        )
        assert result["success"], result
        item_id = result["review_item_id"]
        assert _organisation_of(db_session, item_id) is None
        login_as(client, user)
        response = client.get(f"/api/confidence/queue/{item_id}")
        assert (response.status_code, response.get_json()) == (404, NOT_FOUND)


def test_generic_inventory_follows_all_declared_policies(db_session, monkeypatch):
    import os

    from app import db
    from app.commands import backfill_layer_tenancy as command
    from app.models.mixins import TenantMixin

    mappers = list(db.Model.registry.mappers)
    expected = {}
    for mapper in mappers:
        if issubclass(mapper.class_, TenantMixin):
            expected[mapper.local_table.name] = mapper.local_table.c.organization_id.nullable
    inventory = command._tenant_tables()
    assert inventory == sorted(expected.items())
    if os.environ.get("APP_FAST_INIT") != "1":
        assert len([policy for policy in expected.values() if policy]) == 19
    for table in ("outcomes", "principles", "review_queue_items", "ai_chat_crud_approvals"):
        assert expected[table] is True
    for table in ("kanban_boards", "vendor_contracts", "license_entitlements", "vendor_product_capabilities"):
        assert expected[table] is False
    for table in ("arb_governance_standards", "arb_workflow_stages", "ea_workflow_definitions", "unified_capabilities", "users"):
        assert table not in expected
    from types import SimpleNamespace

    monkeypatch.setattr(command, "db", SimpleNamespace(Model=SimpleNamespace(
        registry=SimpleNamespace(mappers=list(reversed(mappers)))
    )))
    assert command._tenant_tables() == inventory


@pytest.mark.parametrize("fault", ["agree", "conflict", "missing", "mapped_conflict", "ambiguous", "schema", "bind", "name", "unknown"])
def test_generic_metadata_refuses_before_sql(db_session, monkeypatch, fault):
    from types import SimpleNamespace

    import click
    from sqlalchemy import Column, Integer, MetaData, Table

    from app.commands import backfill_layer_tenancy as command
    from app.models.mixins import TenantMixin

    class Mapping(TenantMixin):
        pass

    def mapping(nullable, *, schema=None, bind=None, name="review_queue_items"):
        metadata = MetaData(info={"bind_key": bind})
        table = Table(name, metadata, Column("organization_id", Integer, nullable=nullable), schema=schema)
        return SimpleNamespace(class_=Mapping, local_table=table,
                               column_attrs={"organization_id": SimpleNamespace(columns=[table.c.organization_id])})

    first, second = mapping(True), mapping(fault != "conflict")
    if fault == "missing":
        second.column_attrs = {}
    elif fault == "mapped_conflict":
        retained = second.local_table.c.organization_id
        second.local_table.append_column(Column("organization_id", Integer, nullable=False), replace_existing=True)
        assert retained is not second.local_table.c.organization_id
    elif fault == "ambiguous":
        second.column_attrs["organization_id"].columns *= 2
    elif fault == "schema":
        second = mapping(True, schema="other")
    elif fault == "bind":
        second = mapping(True, bind="other")
    elif fault == "name":
        second = mapping(True, name="bad-name")
    elif fault == "unknown":
        second.local_table.c.organization_id.nullable = None
    errors = []
    for mappers in ([first, second], [second, first]):
        class NoSQLSession:
            def connection(self):
                pytest.fail("Invalid metadata reached SQL")

            def rollback(self):
                pass

        monkeypatch.setattr(command, "db", SimpleNamespace(
            Model=SimpleNamespace(registry=SimpleNamespace(mappers=mappers)), session=NoSQLSession()
        ))
        if fault == "agree":
            assert command._tenant_tables() == [("review_queue_items", True)]
        else:
            with pytest.raises(click.ClickException, match="organization_id|identity") as error:
                command.repair_layer_tenancy()
            errors.append(str(error.value))
    if errors:
        assert errors[0] == errors[1]


@pytest.mark.parametrize("selection", ["explicit", "multi", "invalid"])
def test_generic_required_assignment_refusal_and_preservation(
    app, db_session, make_org, monkeypatch, schema_shape, selection
):
    from sqlalchemy import text

    from app.models.adm_kanban import KanbanBoard

    command = _generic_subset(monkeypatch, "kanban_boards")
    org_a, org_b = make_org("required-a"), make_org("required-b")
    user = _make_user(db_session, org_a)
    rows = [KanbanBoard(name=uuid.uuid4().hex, created_by_id=user.id, organization_id=org_a.id)
            for _ in range(2)]
    db_session.add_all(rows)
    db_session.flush()
    ids = [row.id for row in rows]
    with schema_shape("kanban_boards") as conn:
        db_session.execute(text("ALTER TABLE kanban_boards ALTER COLUMN organization_id DROP NOT NULL"))
        db_session.execute(text("UPDATE kanban_boards SET organization_id = NULL WHERE id = :id"), {"id": ids[0]})
        db_session.commit()
        before = _catalog(conn, "kanban_boards")
        args = [] if selection == "multi" else ["--org-id", str(org_b.id if selection == "explicit" else -1)]
        dry = app.test_cli_runner().invoke(command.backfill_layer_tenancy, args + ["--dry-run"])
        assert _catalog(conn, "kanban_boards") == before
        result = app.test_cli_runner().invoke(command.backfill_layer_tenancy, args)
        owners = dict(conn.execute(text(
            "SELECT id, organization_id FROM kanban_boards WHERE id = ANY(:ids)"
        ), {"ids": ids}).all())
        assert owners[ids[1]] == org_a.id
        if selection == "explicit":
            assert dry.exit_code == result.exit_code == 0, result.output
            assert owners[ids[0]] == org_b.id
            assert next(c for c in _catalog(conn, "kanban_boards")["columns"] if c[0] == "organization_id")[2] is False
            assert command.repair_layer_tenancy()["repaired"] == []
        else:
            assert dry.exit_code != 0 and result.exit_code != 0
            assert owners[ids[0]] is None
            assert _catalog(conn, "kanban_boards") == before
            assert "already healthy" not in result.output


@pytest.mark.parametrize("failure", ["add", "drop", "index", "set", "catalog"])
def test_generic_sql_failure_rolls_back_and_next_invocation_works(
    app, db_session, monkeypatch, schema_shape, failure
):
    from sqlalchemy import event, text

    required = failure in {"index", "set"}
    table = "kanban_boards" if required else "review_queue_items"
    command = _generic_subset(monkeypatch, table)
    with schema_shape(table) as conn:
        if conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one():
            pytest.skip("DDL failure shapes require an empty authorized scratch table")
        if failure == "add":
            db_session.execute(text(f'ALTER TABLE "{table}" DROP COLUMN organization_id CASCADE'))
        elif failure in {"drop", "catalog"}:
            db_session.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN organization_id SET NOT NULL'))
        else:
            db_session.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN organization_id DROP NOT NULL'))
            if failure == "index":
                for index in _catalog(conn, table)["indexes"]:
                    if index["column_names"] == ["organization_id"]:
                        # Names come from the live catalog, quoted by the dialect.
                        quoted = conn.dialect.identifier_preparer.quote(index["name"])
                        db_session.execute(text(f'DROP INDEX public.{quoted}'))
        db_session.commit()
        before = _catalog(conn, table)
        fired = []
        ddl_seen = []

        def fail_statement(connection, cursor, statement, parameters, context, executemany):
            sql = statement.upper()
            if sql.startswith("ALTER TABLE"):
                ddl_seen.append(sql)
            trigger = {"add": "ADD COLUMN", "drop": "DROP NOT NULL", "index": "CREATE INDEX", "set": "SET NOT NULL"}.get(failure)
            if not fired and ((trigger and trigger in sql) or (failure == "catalog" and ddl_seen and "PG_CATALOG" in sql)):
                fired.append(statement)
                cursor.execute("SELECT 1 / 0")  # Actual PostgreSQL transaction failure.

        event.listen(conn, "before_cursor_execute", fail_statement)
        try:
            result = app.test_cli_runner().invoke(command.backfill_layer_tenancy)
        finally:
            event.remove(conn, "before_cursor_execute", fail_statement)
        assert fired, result.output
        assert result.exit_code != 0
        assert "already healthy" not in result.output
        assert _catalog(conn, table) == before
        assert conn.execute(text("SELECT 1")).scalar_one() == 1
        result = app.test_cli_runner().invoke(command.backfill_layer_tenancy)
        assert result.exit_code == 0, result.output


@pytest.mark.parametrize("generic_first", [False, True])
def test_generic_preserves_ai_requester_policy_and_unresolved_failure(
    app, db_session, make_org, monkeypatch, schema_shape, generic_first
):
    from datetime import datetime, timedelta

    from sqlalchemy import text

    from app.commands.backfill_ai_chat_approval_org import backfill_ai_chat_approval_org
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval

    command = _generic_subset(monkeypatch, "ai_chat_crud_approvals")
    org_a, org_b = make_org("ai-a"), make_org("ai-b")
    users = [_make_user(db_session, org) for org in (org_a, org_b, org_a, org_a)]
    approvals = [AIChatCRUDApproval(
        user_id=user.id, organization_id=org_a.id, operation_type="create",
        entity_type="capability", original_command=uuid.uuid4().hex,
        operation_payload="{}", summary="Test approval",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    ) for user in users + users[:1]]
    db_session.add_all(approvals)
    db_session.flush()
    ids = [row.id for row in approvals]
    null_user_id = users[2].id
    with schema_shape("users", "ai_chat_crud_approvals") as conn:
        db_session.execute(text("ALTER TABLE users ALTER COLUMN organization_id DROP NOT NULL"))
        db_session.execute(text("UPDATE users SET organization_id = NULL WHERE id = :id"), {"id": null_user_id})
        for fk in _catalog(conn, "ai_chat_crud_approvals")["foreign_keys"]:
            if fk["constrained_columns"] == ["user_id"]:
                quoted = conn.dialect.identifier_preparer.quote(fk["name"])
                db_session.execute(text(f'ALTER TABLE ai_chat_crud_approvals DROP CONSTRAINT {quoted}'))
        db_session.execute(text("UPDATE ai_chat_crud_approvals SET user_id = -1 WHERE id = :id"), {"id": ids[3]})
        db_session.execute(text("UPDATE ai_chat_crud_approvals SET organization_id = NULL WHERE id = ANY(:ids)"), {"ids": ids[:4]})
        db_session.commit()
        before = _catalog(conn, "ai_chat_crud_approvals")
        if generic_first:
            command.repair_layer_tenancy(org_id=org_b.id)
            assert conn.execute(text(
                "SELECT count(*) FROM ai_chat_crud_approvals WHERE id = ANY(:ids) AND organization_id IS NULL"
            ), {"ids": ids[:4]}).scalar_one() == 4
        result = app.test_cli_runner().invoke(backfill_ai_chat_approval_org)
        assert result.exit_code != 0 and "remain unattributed" in result.output
        for explicit in (None, org_a.id, org_b.id):
            command.repair_layer_tenancy(org_id=explicit)
            actual = dict(conn.execute(text(
                "SELECT id, organization_id FROM ai_chat_crud_approvals WHERE id = ANY(:ids)"
            ), {"ids": ids}).all())
            assert actual == dict(zip(ids, [org_a.id, org_b.id, None, None, org_a.id]))
            assert _catalog(conn, "ai_chat_crud_approvals") == before
        result = app.test_cli_runner().invoke(backfill_ai_chat_approval_org)
        assert result.exit_code != 0 and "remain unattributed" in result.output


@pytest.mark.parametrize("generic_first", [False, True])
def test_generic_preserves_outcome_parent_precedence_and_unresolved_rows(
    app, db_session, make_org, monkeypatch, generic_first
):
    from sqlalchemy import text

    from app.commands.backfill_outcome_org import backfill_outcome_org
    from app.models.models import ArchiMateElement, ArchitectureModel, Outcome

    command = _generic_subset(monkeypatch, "outcomes")
    org_a, org_b = make_org("outcome-a"), make_org("outcome-b")
    model = ArchitectureModel(name=uuid.uuid4().hex, organization_id=org_b.id)
    element = ArchiMateElement(name=uuid.uuid4().hex, organization_id=org_a.id)
    db_session.add_all([model, element])
    db_session.flush()
    rows = [
        Outcome(name=uuid.uuid4().hex, archimate_element_id=element.id, architecture_id=model.id),
        Outcome(name=uuid.uuid4().hex, architecture_id=model.id),
        Outcome(name=uuid.uuid4().hex),
        Outcome(name=uuid.uuid4().hex, organization_id=org_b.id, archimate_element_id=element.id),
    ]
    db_session.add_all(rows)
    db_session.flush()
    ids = [row.id for row in rows]
    db_session.execute(text("UPDATE outcomes SET organization_id = NULL WHERE id = ANY(:ids)"), {"ids": ids[:3]})
    db_session.commit()
    if generic_first:
        command.repair_layer_tenancy(org_id=org_b.id)
        assert db_session.execute(text(
            "SELECT count(*) FROM outcomes WHERE id = ANY(:ids) AND organization_id IS NULL"
        ), {"ids": ids[:3]}).scalar_one() == 3
    result = app.test_cli_runner().invoke(backfill_outcome_org)
    assert result.exit_code == 0, result.output
    before = _catalog(db_session.connection(), "outcomes")
    for explicit in (None, org_a.id, org_b.id):
        command.repair_layer_tenancy(org_id=explicit)
        actual = dict(db_session.execute(text(
            "SELECT id, organization_id FROM outcomes WHERE id = ANY(:ids)"
        ), {"ids": ids}).all())
        assert actual == dict(zip(ids, [org_a.id, org_b.id, None, org_b.id]))
        assert _catalog(db_session.connection(), "outcomes") == before
    result = app.test_cli_runner().invoke(backfill_outcome_org)
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("missing_column", [False, True])
@pytest.mark.parametrize("residual", [False, True])
def test_generic_required_parent_derivation_precedes_fallback_in_dry_run_and_apply(
    app, db_session, make_org, monkeypatch, schema_shape, missing_column, residual
):
    from sqlalchemy import text

    from app.models.business_capabilities import BusinessCapability
    from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct, VendorProductCapability

    command = _generic_subset(monkeypatch, "vendor_product_capabilities")
    org_a, org_b = make_org("parent-a"), make_org("parent-b")
    capabilities = [BusinessCapability(name=uuid.uuid4().hex, code=uuid.uuid4().hex,
                                       organization_id=org.id) for org in (org_a, org_b)]
    vendor = VendorOrganization(name=uuid.uuid4().hex)
    db_session.add_all([vendor, *capabilities])
    db_session.flush()
    product = VendorProduct(name=uuid.uuid4().hex, vendor_organization_id=vendor.id)
    db_session.add(product)
    db_session.flush()
    rows = [VendorProductCapability(vendor_product_id=product.id, business_capability_id=c.id,
                                    coverage_percentage=50, organization_id=org_a.id)
            for c in capabilities]
    db_session.add_all(rows)
    db_session.flush()
    ids = [row.id for row in rows]
    with schema_shape("vendor_product_capabilities", "business_capability") as conn:
        if missing_column:
            if conn.execute(text(
                "SELECT count(*) FROM vendor_product_capabilities WHERE id != ALL(:ids)"
            ), {"ids": ids}).scalar_one():
                pytest.skip("Missing-column shape requires only fixture-owned rows")
            db_session.execute(text("ALTER TABLE vendor_product_capabilities DROP COLUMN organization_id CASCADE"))
        else:
            db_session.execute(text("ALTER TABLE vendor_product_capabilities ALTER COLUMN organization_id DROP NOT NULL"))
            db_session.execute(text("UPDATE vendor_product_capabilities SET organization_id = NULL WHERE id = ANY(:ids)"), {"ids": ids})
        if residual:
            db_session.execute(text("ALTER TABLE business_capability ALTER COLUMN organization_id DROP NOT NULL"))
            db_session.execute(text("UPDATE business_capability SET organization_id = NULL WHERE id = :id"), {"id": capabilities[1].id})
        db_session.commit()
        before = _catalog(conn, "vendor_product_capabilities")
        args = ["--org-id", str(org_b.id)] if residual else []
        dry = app.test_cli_runner().invoke(command.backfill_layer_tenancy, args + ["--dry-run"])
        assert dry.exit_code == 0, dry.output
        assert f"derive {1 if residual else 2} owner(s)" in dry.output
        assert ("assign 1 residual owner(s)" in dry.output) is residual
        assert _catalog(conn, "vendor_product_capabilities") == before
        if missing_column:
            assert "ADD COLUMN" in dry.output
        result = app.test_cli_runner().invoke(command.backfill_layer_tenancy, args)
        assert result.exit_code == 0, result.output
        actual = dict(conn.execute(text(
            "SELECT id, organization_id FROM vendor_product_capabilities WHERE id = ANY(:ids)"
        ), {"ids": ids}).all())
        assert actual == dict(zip(ids, [org_a.id, org_b.id]))
        assert command.repair_layer_tenancy()["repaired"] == []


@pytest.mark.parametrize("org_count", [0, 1])
@pytest.mark.parametrize("required", [False, True])
def test_generic_zero_and_sole_org_policy_on_empty_scratch(
    app, db_session, make_org, monkeypatch, schema_shape, org_count, required
):
    from types import SimpleNamespace

    from sqlalchemy import text

    from app.models.adm_kanban import KanbanBoard

    if db_session.execute(text("SELECT count(*) FROM organizations")).scalar_one():
        pytest.skip("Requires an authorized scratch database with no pre-existing organizations")
    table = "kanban_boards" if required else "review_queue_items"
    command = _generic_subset(monkeypatch, table)
    with schema_shape(table, "users") as conn:
        org = make_org("sole-owner") if org_count else SimpleNamespace(id=None)
        if required:
            db_session.execute(text("ALTER TABLE users ALTER COLUMN organization_id DROP NOT NULL"))
            db_session.execute(text("ALTER TABLE kanban_boards ALTER COLUMN organization_id DROP NOT NULL"))
            user = _make_user(db_session, org)
            board = KanbanBoard(name=uuid.uuid4().hex, created_by_id=user.id, organization_id=org.id)
            db_session.add(board)
            db_session.flush()
            item_id = board.id
            db_session.execute(text("UPDATE kanban_boards SET organization_id = NULL WHERE id = :id"), {"id": item_id})
        else:
            item_id = _unattributed_item(db_session, "archimate_element", 0)
        db_session.commit()
        before = _catalog(conn, table)
        for args in (["--dry-run"], []):
            result = app.test_cli_runner().invoke(command.backfill_layer_tenancy, args)
            owner = conn.execute(text(
                f'SELECT organization_id FROM "{table}" WHERE id = :id'
            ), {"id": item_id}).scalar_one()
            if required and not org_count:
                assert result.exit_code != 0 and "0 organizations exist" in result.output
                assert owner is None
                assert _catalog(conn, table) == before
            else:
                assert result.exit_code == 0, result.output
                assert owner == (org.id if required and not args else None)
            if args:
                assert _catalog(conn, table) == before
        if required and org_count:
            assert next(c for c in _catalog(conn, table)["columns"] if c[0] == "organization_id")[2] is False
        if not required:
            assert next(c for c in _catalog(conn, table)["columns"] if c[0] == "organization_id")[2] is True


def test_generic_keeps_arb_workflow_attribution_with_its_dedicated_command(
    db_session, make_org, monkeypatch
):
    from sqlalchemy import text

    from app.commands.backfill_arb_ea_tenancy import run_backfill
    from app.models.architecture_review_board import ARBReviewItem
    from app.models.workflow_models import EAWorkflowDefinition, EAWorkflowInstance

    command = _generic_subset(monkeypatch, "arb_review_items", "ea_workflow_instances")
    org_a, org_b = make_org("arb-a"), make_org("arb-b")
    user = _make_user(db_session, org_a)
    review = ARBReviewItem(review_number=uuid.uuid4().hex, title="Test review",
                           review_type="architecture_change", submitter_id=user.id)
    definition = EAWorkflowDefinition(workflow_code=uuid.uuid4().hex, workflow_name="Test workflow",
                                      workflow_category="architecture", steps=[{"id": "step1"}])
    db_session.add_all([review, definition])
    db_session.flush()
    instances = [EAWorkflowInstance(instance_code=uuid.uuid4().hex,
                                    workflow_definition_id=definition.id, started_by_id=starter)
                 for starter in (user.id, None)]
    db_session.add_all(instances)
    db_session.flush()
    review_id, definition_id = review.id, definition.id
    ids = [instance.id for instance in instances]
    db_session.execute(text("UPDATE arb_review_items SET organization_id = NULL WHERE id = :id"), {"id": review_id})
    db_session.execute(text("UPDATE ea_workflow_instances SET organization_id = NULL WHERE id = ANY(:ids)"), {"ids": ids})
    db_session.commit()
    command.repair_layer_tenancy(org_id=org_b.id)
    assert db_session.execute(text("SELECT organization_id FROM arb_review_items WHERE id = :id"), {"id": review_id}).scalar_one() is None
    run_backfill()
    command.repair_layer_tenancy(org_id=org_b.id)
    assert db_session.execute(text("SELECT organization_id FROM arb_review_items WHERE id = :id"), {"id": review_id}).scalar_one() == org_a.id
    actual = dict(db_session.execute(text(
        "SELECT id, organization_id FROM ea_workflow_instances WHERE id = ANY(:ids)"
    ), {"ids": ids}).all())
    assert actual == dict(zip(ids, [org_a.id, None]))
    assert db_session.execute(text("SELECT organization_id FROM ea_workflow_definitions WHERE id = :id"), {"id": definition_id}).scalar_one() is None
    run_backfill(org_id=org_b.id)
    assert db_session.execute(text("SELECT organization_id FROM ea_workflow_instances WHERE id = :id"), {"id": ids[1]}).scalar_one() == org_b.id
    assert db_session.execute(text("SELECT organization_id FROM ea_workflow_definitions WHERE id = :id"), {"id": definition_id}).scalar_one() is None
