"""Behavioural tests for the business_capability -> unified_capabilities projection.

Each test works in a transaction-local cloned schema, so the shared test database's
real `unified_capabilities` is never projected into. This follows
`tests/test_capability_tenancy_cutover.py`, which established the pattern for the
sibling cutover command.

Fixtures come from `tests/conftest.py` (`db_session`, `app`, `make_org`,
`tenant_ctx`) — `db_session` runs each test inside a transaction that is always
rolled back, so a failure part-way through cannot leave residue. Do not hand-roll a
module-scoped `app` fixture here.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.commands.project_capabilities import (
    PROVENANCE_INDEX,
    ProjectionBlocked,
    run_projection,
)


pytestmark = pytest.mark.usefixtures("db_session")


_CLONED_TABLES = ("organizations", "business_capability", "unified_capabilities")


def _clone_schema(db_session, *, with_provenance_index: bool):
    """Clone only the tables the projection touches into a disposable schema.

    `CREATE TABLE ... LIKE` copies columns, defaults and CHECK constraints but not
    primary keys, indexes or foreign keys, so the keys the projection depends on are
    re-declared explicitly below — which is also what makes the missing-index test
    meaningful rather than an accident of the clone.
    """

    schema = f"capproj_{uuid.uuid4().hex[:12]}"
    connection = db_session.connection()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    for table in _CLONED_TABLES:
        connection.execute(
            text(
                f'CREATE TABLE "{schema}"."{table}" '
                f'(LIKE public."{table}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS)'
            )
        )
    connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
    connection.execute(text("ALTER TABLE organizations ADD PRIMARY KEY (id)"))
    connection.execute(text("ALTER TABLE business_capability ADD PRIMARY KEY (id)"))
    connection.execute(text("ALTER TABLE unified_capabilities ADD PRIMARY KEY (id)"))
    # The four partial unique indexes the model declares
    # (app/models/unified_capability.py:310-340). Present so a code or archimate_id
    # collision fails here exactly as it would in production.
    connection.execute(
        text(
            "CREATE UNIQUE INDEX ON unified_capabilities (organization_id, code) "
            "WHERE organization_id IS NOT NULL"
        )
    )
    connection.execute(
        text(
            "CREATE UNIQUE INDEX ON unified_capabilities (organization_id, archimate_id) "
            "WHERE organization_id IS NOT NULL AND archimate_id IS NOT NULL"
        )
    )

    # The post-cutover scope/owner CHECK (cutover_capability_tenancy.py:671-679).
    # Installed here on purpose: it makes every test prove the projected rows are
    # legal on a cut-over database, and it makes _cutover_is_complete() true so the
    # ordering guard does not mask the behaviour under test.
    connection.execute(
        text(
            "ALTER TABLE unified_capabilities "
            "DROP CONSTRAINT IF EXISTS ck_unified_capabilities_scope_owner, "
            "ADD CONSTRAINT ck_unified_capabilities_scope_owner CHECK ("
            "scope IS NOT NULL AND ("
            "(scope = 'reference' AND organization_id IS NULL) OR "
            "(scope = 'tenant' AND organization_id IS NOT NULL)))"
        )
    )

    if with_provenance_index:
        connection.execute(
            text(
                f"CREATE UNIQUE INDEX {PROVENANCE_INDEX} "
                "ON unified_capabilities (source_table, source_id) "
                "WHERE source_table IS NOT NULL AND source_id IS NOT NULL"
            )
        )
    return connection


@pytest.fixture
def projection_schema(db_session):
    return _clone_schema(db_session, with_provenance_index=True)


@pytest.fixture
def projection_schema_without_index(db_session):
    return _clone_schema(db_session, with_provenance_index=False)


def _make_org(connection, org_id: int, name: str) -> int:
    connection.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": org_id, "name": name, "slug": f"{name}-{org_id}"},
    )
    return org_id


def _make_capability(connection, *, capability_id, org_id, name, **columns):
    """Insert a business_capability row directly, with explicit ownership."""

    payload = {
        "id": capability_id,
        "organization_id": org_id,
        "name": name,
        "code": columns.pop("code", f"CAP-{capability_id}"),
        "level": columns.pop("level", 1),
        "parent_capability_id": columns.pop("parent_capability_id", None),
        "current_maturity_level": columns.pop("current_maturity_level", None),
        "business_value": columns.pop("business_value", None),
        "is_deprecated": columns.pop("is_deprecated", False),
    }
    assert not columns, f"unexpected columns: {sorted(columns)}"
    connection.execute(
        text(
            "INSERT INTO business_capability "
            "(id, organization_id, name, code, level, parent_capability_id, "
            " current_maturity_level, business_value, is_deprecated) "
            "VALUES (:id, :organization_id, :name, :code, :level, "
            ":parent_capability_id, :current_maturity_level, :business_value, "
            ":is_deprecated)"
        ),
        payload,
    )
    return capability_id


def _projected(connection):
    return connection.execute(
        text(
            "SELECT source_id, name, code, level, scope, organization_id, "
            "source_table, source_org_id, source_checksum, specialization_type, "
            "status, business_value, current_maturity_level, target_maturity_level, "
            "discovery_source, parent_capability_id, id "
            "FROM unified_capabilities WHERE source_table = 'business_capability' "
            "ORDER BY source_id::integer"
        )
    ).mappings().all()


# --------------------------------------------------------------- (d) index guard


def test_apply_refuses_without_the_provenance_index(projection_schema_without_index):
    """Without the unique index the ON CONFLICT arbiter does not exist.

    A command that proceeded anyway would double-insert on every re-run, so the
    refusal must be loud and must name the migration that fixes it.
    """

    connection = projection_schema_without_index
    org = _make_org(connection, 9101, "org-a")
    _make_capability(connection, capability_id=1, org_id=org, name="Order Management")

    with pytest.raises(ProjectionBlocked) as blocked:
        run_projection(connection, apply=True, row_limit=None)

    message = str(blocked.value)
    assert PROVENANCE_INDEX in message
    assert "migrate_unified_capability_provenance.sql" in message
    # Refused means refused: nothing was written.
    assert connection.execute(
        text("SELECT count(*) FROM unified_capabilities")
    ).scalar_one() == 0


def test_dry_run_also_refuses_without_the_index(projection_schema_without_index):
    """The dry-run's numbers are only meaningful if the apply it models can run."""

    with pytest.raises(ProjectionBlocked):
        run_projection(projection_schema_without_index, apply=False, row_limit=None)


# ---------------------------------------------------------------- (a) idempotency


def test_projecting_twice_creates_no_duplicate(projection_schema):
    connection = projection_schema
    org = _make_org(connection, 9201, "org-a")
    for capability_id in (1, 2, 3):
        _make_capability(
            connection, capability_id=capability_id, org_id=org,
            name=f"Capability {capability_id}",
        )

    first = run_projection(connection, apply=True, row_limit=None)
    assert first["writes"]["inserted_or_updated"] == 3
    assert first["after"]["projected_rows"] == 3

    second = run_projection(connection, apply=True, row_limit=None)
    # The DO UPDATE carries `WHERE source_checksum IS DISTINCT FROM EXCLUDED...`,
    # so an unchanged re-run writes zero rows rather than touching every row.
    assert second["writes"]["inserted_or_updated"] == 0
    assert second["writes"]["backlinked"] == 0
    assert second["plan"]["unchanged"] == 3
    assert second["plan"]["to_insert"] == 0
    assert second["after"]["projected_rows"] == 3
    assert second["before"]["unified_snapshot"] == second["after"]["unified_snapshot"]


def test_a_changed_source_row_is_refreshed_not_duplicated(projection_schema):
    """The checksum is what makes drift detectable; prove it drives an update."""

    connection = projection_schema
    org = _make_org(connection, 9301, "org-a")
    _make_capability(connection, capability_id=1, org_id=org, name="Original name")
    run_projection(connection, apply=True, row_limit=None)

    connection.execute(
        text("UPDATE business_capability SET name = 'Renamed' WHERE id = 1")
    )
    report = run_projection(connection, apply=True, row_limit=None)

    assert report["plan"]["to_update"] == 1
    assert report["writes"]["inserted_or_updated"] == 1
    assert report["after"]["projected_rows"] == 1
    rows = _projected(connection)
    assert len(rows) == 1
    assert rows[0]["name"] == "Renamed"


def test_limit_projects_only_the_first_n_rows(projection_schema):
    connection = projection_schema
    org = _make_org(connection, 9401, "org-a")
    for capability_id in (1, 2, 3):
        _make_capability(
            connection, capability_id=capability_id, org_id=org,
            name=f"Capability {capability_id}",
        )

    report = run_projection(connection, apply=True, row_limit=2)

    assert report["writes"]["inserted_or_updated"] == 2
    assert [row["source_id"] for row in _projected(connection)] == ["1", "2"]
    # The limited run must not claim the unprojected rows are done.
    assert report["after"]["source_rows"] == 3


# ------------------------------------------------------------------ (b) provenance


def test_projected_rows_carry_correct_provenance(projection_schema):
    connection = projection_schema
    org = _make_org(connection, 9501, "org-a")
    _make_capability(
        connection, capability_id=1, org_id=org, name="Parent", code="CAP-P", level=1,
    )
    _make_capability(
        connection, capability_id=2, org_id=org, name="Child", code=None, level=5,
        parent_capability_id=1, business_value=8, is_deprecated=True,
    )

    run_projection(connection, apply=True, row_limit=None)
    parent, child = _projected(connection)

    for row in (parent, child):
        assert row["source_table"] == "business_capability"
        assert row["source_org_id"] == org
        assert row["organization_id"] == org
        assert row["scope"] == "tenant"
        assert row["source_checksum"]
        assert row["specialization_type"] == "BUSINESS"
        assert row["discovery_source"] == "projection:business_capability"
    assert parent["source_id"] == "1"
    assert child["source_id"] == "2"

    # A NULL source code gets a deterministic fallback, or NULL codes would neither
    # collide nor deduplicate under the partial unique indexes.
    assert child["code"] == "BC-2"
    # Source level 5 is clamped into the target's documented L1-L3 range.
    assert child["level"] == 3
    # Integer 1-10 -> Text keeps the scale visible.
    assert child["business_value"] == "8/10"
    assert child["status"] == "retiring"
    assert parent["status"] == "defined"
    # Unassessed maturity must stay NULL, not acquire the target column's default.
    assert parent["current_maturity_level"] is None
    assert parent["target_maturity_level"] is None
    # Hierarchy is translated through provenance, not copied as a source id.
    assert child["parent_capability_id"] == parent["id"]

    # The back-link uses deprecated_in_favor_of_id, the only column on
    # BusinessCapability that FKs into unified_capabilities.
    backlinks = connection.execute(
        text(
            "SELECT bc.id, bc.deprecated_in_favor_of_id, bc.is_deprecated "
            "FROM business_capability AS bc ORDER BY bc.id"
        )
    ).mappings().all()
    assert backlinks[0]["deprecated_in_favor_of_id"] == parent["id"]
    assert backlinks[1]["deprecated_in_favor_of_id"] == child["id"]
    # Projecting a row does not retire it; is_deprecated is left exactly as found.
    assert backlinks[0]["is_deprecated"] is False


def test_dry_run_writes_nothing_but_reports_the_plan(projection_schema):
    connection = projection_schema
    org = _make_org(connection, 9601, "org-a")
    _make_capability(connection, capability_id=1, org_id=org, name="A", code=None, level=5)

    report = run_projection(connection, apply=False, row_limit=None)

    assert report["mode"] == "dry-run"
    assert report["plan"]["to_insert"] == 1
    assert report["plan"]["code_fallbacks"] == 1
    assert report["plan"]["levels_clamped"] == 1
    assert report["writes"]["inserted_or_updated"] == 0
    assert connection.execute(
        text("SELECT count(*) FROM unified_capabilities")
    ).scalar_one() == 0


# ------------------------------------------------------------------ (c) tenancy


def test_one_tenants_rows_never_reach_another_tenants_projection(projection_schema):
    """The projection runs across all organisations; each row must keep its own."""

    connection = projection_schema
    org_a = _make_org(connection, 9701, "org-a")
    org_b = _make_org(connection, 9702, "org-b")
    _make_capability(connection, capability_id=1, org_id=org_a, name="A only", code="X-1")
    _make_capability(connection, capability_id=2, org_id=org_b, name="B only", code="X-2")

    run_projection(connection, apply=True, row_limit=None)
    rows = {row["source_id"]: row for row in _projected(connection)}

    assert rows["1"]["organization_id"] == org_a
    assert rows["1"]["source_org_id"] == org_a
    assert rows["2"]["organization_id"] == org_b
    assert rows["2"]["source_org_id"] == org_b

    # No projected row may be visible under the wrong owner, in either direction.
    for org_id, expected_names in ((org_a, {"A only"}), (org_b, {"B only"})):
        visible = connection.execute(
            text(
                "SELECT name FROM unified_capabilities "
                "WHERE source_table = 'business_capability' AND organization_id = :org"
            ),
            {"org": org_id},
        ).scalars().all()
        assert set(visible) == expected_names

    # The back-link must not cross tenants either.
    crossed = connection.execute(
        text(
            "SELECT count(*) FROM business_capability AS bc "
            "JOIN unified_capabilities AS uc ON uc.id = bc.deprecated_in_favor_of_id "
            "WHERE uc.organization_id IS DISTINCT FROM bc.organization_id"
        )
    ).scalar_one()
    assert crossed == 0


def test_two_tenants_may_hold_the_same_code(projection_schema):
    """uq_unified_capabilities_tenant_code is per-organisation, so this must not fail.

    A shared code across tenants is a semantic duplicate, not a constraint violation;
    the projection links and marks, it never merges or deletes.
    """

    connection = projection_schema
    org_a = _make_org(connection, 9801, "org-a")
    org_b = _make_org(connection, 9802, "org-b")
    # `LIKE` does not copy unique indexes, so the clone permits the shared code the
    # global unique on business_capability.code would otherwise forbid. The point
    # under test is the target's per-tenant index, not the source's.
    _make_capability(connection, capability_id=1, org_id=org_a, name="Billing", code="BILL")
    _make_capability(connection, capability_id=2, org_id=org_b, name="Billing", code="BILL")

    report = run_projection(connection, apply=True, row_limit=None)

    assert report["writes"]["inserted_or_updated"] == 2
    codes = {(row["organization_id"], row["code"]) for row in _projected(connection)}
    assert codes == {(org_a, "BILL"), (org_b, "BILL")}


# --------------------------------------------------------------------- blockers


def test_apply_refuses_when_a_code_is_already_taken_in_the_same_tenant(projection_schema):
    """A colliding code is reported, never silently merged into the existing row."""

    connection = projection_schema
    org = _make_org(connection, 9901, "org-a")
    _make_capability(connection, capability_id=1, org_id=org, name="Billing", code="BILL")
    connection.execute(
        text(
            "INSERT INTO unified_capabilities "
            "(id, name, code, level, scope, organization_id, specialization_type) "
            "VALUES (77001, 'Pre-existing billing', 'BILL', 1, 'tenant', :org, 'BUSINESS')"
        ),
        {"org": org},
    )

    with pytest.raises(ProjectionBlocked) as blocked:
        run_projection(connection, apply=True, row_limit=None)
    assert "tenant_code_collision" in str(blocked.value)

    # The pre-existing row is untouched and no projection row was created.
    assert connection.execute(
        text("SELECT count(*) FROM unified_capabilities WHERE source_table IS NOT NULL")
    ).scalar_one() == 0


def test_apply_refuses_on_a_source_hierarchy_cycle(projection_schema):
    """A cycle becomes an unbounded while loop in get_full_hierarchy_path."""

    connection = projection_schema
    org = _make_org(connection, 9951, "org-a")
    _make_capability(connection, capability_id=1, org_id=org, name="One")
    _make_capability(connection, capability_id=2, org_id=org, name="Two",
                     parent_capability_id=1)
    connection.execute(
        text("UPDATE business_capability SET parent_capability_id = 2 WHERE id = 1")
    )

    with pytest.raises(ProjectionBlocked) as blocked:
        run_projection(connection, apply=True, row_limit=None)
    assert "source_hierarchy_cycle" in str(blocked.value)
