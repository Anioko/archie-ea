"""Behavioural tests for the UnifiedCapability tenancy maintenance cutover.

Each cutover test works in a transaction-local cloned schema.  The production
schema is never classified, deduplicated, or constraint-swapped by this suite.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.commands.cutover_capability_tenancy import (
    CutoverBlocked,
    classify_capability,
    install_cutover_constraints,
    run_cutover,
)


pytestmark = pytest.mark.usefixtures("db_session")


@pytest.fixture
def capability_schema(db_session):
    """Clone only the tables exercised by the maintenance classifier."""

    schema = f"capcut_{uuid.uuid4().hex[:12]}"
    connection = db_session.connection()
    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    for table in (
        "organizations",
        "unified_capabilities",
        "application_components",
        "unified_application_capability_mapping",
        "benefits",
        "work_packages",
    ):
        connection.execute(
            text(
                f'CREATE TABLE "{schema}"."{table}" '
                f'(LIKE public."{table}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS)'
            )
        )

    connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
    for ddl in (
        "ADD COLUMN IF NOT EXISTS organization_id INTEGER",
        "ADD COLUMN IF NOT EXISTS scope VARCHAR(16)",
        "ADD COLUMN IF NOT EXISTS reference_capability_id BIGINT",
        "ADD COLUMN IF NOT EXISTS source_table VARCHAR(128)",
        "ADD COLUMN IF NOT EXISTS source_id VARCHAR(255)",
        "ADD COLUMN IF NOT EXISTS source_org_id INTEGER",
        "ADD COLUMN IF NOT EXISTS source_checksum VARCHAR(64)",
        "ADD COLUMN IF NOT EXISTS retired_into_id BIGINT",
    ):
        connection.execute(text(f"ALTER TABLE unified_capabilities {ddl}"))
    connection.execute(text("ALTER TABLE organizations ADD PRIMARY KEY (id)"))
    connection.execute(text("ALTER TABLE unified_capabilities ADD PRIMARY KEY (id)"))
    connection.execute(
        text(
            "ALTER TABLE unified_application_capability_mapping "
            "ADD CONSTRAINT fk_cutover_test_mapping_capability "
            "FOREIGN KEY (unified_capability_id) REFERENCES unified_capabilities(id)"
        )
    )
    return connection


def _organization(connection, organization_id: int):
    connection.execute(
        text(
            "INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": organization_id,
            "name": f"Organization {organization_id}",
            "slug": f"organization-{organization_id}",
        },
    )


def _capability(
    connection,
    capability_id: int,
    code: str,
    *,
    source_table: str,
    source_org_id: int | None,
    archimate_id: str | None = None,
):
    connection.execute(
        text(
            """
            INSERT INTO unified_capabilities
                (id, name, code, level, version, archimate_id, source_table,
                 source_id, source_org_id, source_checksum)
            VALUES
                (:id, :name, :code, 1, 1, :archimate_id, :source_table,
                 :source_id, :source_org_id, :source_checksum)
            """
        ),
        {
            "id": capability_id,
            "name": f"Capability {capability_id}",
            "code": code,
            "archimate_id": archimate_id,
            "source_table": source_table,
            "source_id": str(capability_id),
            "source_org_id": source_org_id,
            "source_checksum": f"{'a' if source_org_id is None else 'b'}{capability_id:063d}",
        },
    )


def _application_link(connection, mapping_id: int, capability_id: int, app_id: int, org_id: int):
    _organization(connection, org_id)
    connection.execute(
        text(
            "INSERT INTO application_components (id, name, organization_id) "
            "VALUES (:id, :name, :org_id)"
        ),
        {"id": app_id, "name": f"Application {app_id}", "org_id": org_id},
    )
    connection.execute(
        text(
            "INSERT INTO unified_application_capability_mapping "
            "(id, unified_capability_id, application_component_id, is_active) "
            "VALUES (:id, :capability_id, :app_id, true)"
        ),
        {"id": mapping_id, "capability_id": capability_id, "app_id": app_id},
    )


def test_classifier_uses_only_audited_provenance_and_relationship_owners(capability_schema):
    """Wrong ownership logic (for example name/code guessing) changes these literal results."""

    connection = capability_schema
    _capability(connection, 101, "REF-101", source_table="seeded_import", source_org_id=None)
    _capability(connection, 102, "TEN-102", source_table="tenant_import", source_org_id=41)
    _capability(connection, 103, "AMB-103", source_table="tenant_import", source_org_id=41)
    _application_link(connection, 201, 102, 301, 41)
    _application_link(connection, 202, 103, 302, 41)
    _application_link(connection, 203, 103, 303, 42)

    reference = classify_capability(connection, 101)
    tenant = classify_capability(connection, 102)
    ambiguous = classify_capability(connection, 103)

    assert (reference.scope, reference.organization_id) == ("reference", None)
    assert (tenant.scope, tenant.organization_id) == ("tenant", 41)
    assert (ambiguous.scope, ambiguous.organization_id) == ("ambiguous", None)
    assert "application_components:301:organization_id=41" in tenant.evidence
    assert "application_components:303:organization_id=42" in ambiguous.evidence


def test_dry_run_reports_stable_measurements_without_writing(capability_schema):
    """A dry run must catch an accidental UPDATE or constraint swap."""

    connection = capability_schema
    _capability(connection, 111, "REF-111", source_table="seeded_import", source_org_id=None)
    _capability(connection, 112, "TEN-112", source_table="tenant_import", source_org_id=51)
    _capability(connection, 113, "AMB-113", source_table="tenant_import", source_org_id=51)
    _application_link(connection, 211, 112, 311, 51)
    _application_link(connection, 212, 113, 312, 51)
    _application_link(connection, 213, 113, 313, 52)

    report = run_cutover(connection, apply=False)

    assert report["writes"] == 0
    assert report["counts"] == {
        "classified": 3,
        "reference": 1,
        "tenant": 1,
        "ambiguous": 1,
    }
    assert report["before"]["checksum"] == report["after"]["checksum"]
    assert connection.execute(
        text("SELECT count(*) FROM unified_capabilities WHERE scope IS NOT NULL")
    ).scalar_one() == 0


def test_apply_requires_backup_manifest_and_blocks_ambiguous_active_links(
    capability_schema, tmp_path
):
    """Apply must stop before any classification write when recovery or ownership is unsafe."""

    connection = capability_schema
    _capability(connection, 121, "AMB-121", source_table="tenant_import", source_org_id=61)
    _application_link(connection, 221, 121, 321, 61)
    _application_link(connection, 222, 121, 322, 62)

    with pytest.raises(CutoverBlocked, match="backup manifest"):
        run_cutover(connection, apply=True)

    manifest = tmp_path / "backup.json"
    manifest.write_text(json.dumps({"backup_path": "s3://backups/capabilities-20260822.dump"}))
    with pytest.raises(CutoverBlocked, match="ambiguous active links"):
        run_cutover(connection, apply=True, backup_manifest=manifest)

    row = connection.execute(
        text("SELECT scope, organization_id FROM unified_capabilities WHERE id = 121")
    ).one()
    assert tuple(row) == (None, None)


def test_apply_merges_same_scope_duplicates_and_preserves_every_fk_count(
    capability_schema, tmp_path
):
    """A wrong repoint predicate or dropped relationship changes the measured FK totals."""

    connection = capability_schema
    _capability(connection, 131, "DUP-REF", source_table="seeded_import", source_org_id=None)
    _capability(connection, 132, "DUP-REF", source_table="seeded_import", source_org_id=None)
    _capability(connection, 133, "DUP-TEN", source_table="tenant_import", source_org_id=71)
    _capability(connection, 134, "DUP-TEN", source_table="tenant_import", source_org_id=71)
    _application_link(connection, 231, 133, 331, 71)
    _application_link(connection, 232, 134, 332, 71)
    manifest = tmp_path / "backup.json"
    manifest.write_text(json.dumps({"backup_path": "C:/backups/capabilities.dump"}))

    report = run_cutover(connection, apply=True, backup_manifest=manifest)

    assert report["counts"]["ambiguous"] == 0
    assert report["duplicates"] == [
        {
            "source_id": 132,
            "target_id": 131,
            "scope": "reference",
            "organization_id": None,
            "code": "DUP-REF",
        },
        {
            "source_id": 134,
            "target_id": 133,
            "scope": "tenant",
            "organization_id": 71,
            "code": "DUP-TEN",
        },
    ]
    retired = connection.execute(
        text(
            "SELECT id, code, retired_into_id FROM unified_capabilities "
            "WHERE id IN (132, 134) ORDER BY id"
        )
    ).all()
    assert [tuple(row) for row in retired] == [(132, None, 131), (134, None, 133)]
    assert connection.execute(
        text(
            "SELECT unified_capability_id FROM unified_application_capability_mapping "
            "WHERE id = 232"
        )
    ).scalar_one() == 133
    assert report["foreign_keys"]["before"] == report["foreign_keys"]["after"]
    assert all(count == 0 for count in report["foreign_keys"]["orphans"].values())


def test_partial_indexes_enforce_reference_and_tenant_uniqueness(capability_schema):
    """The four required uniqueness boundaries must be enforced by PostgreSQL."""

    connection = capability_schema
    install_cutover_constraints(connection)
    _organization(connection, 81)
    _organization(connection, 82)
    connection.execute(
        text(
            "INSERT INTO unified_capabilities "
            "(id, name, code, archimate_id, level, version, scope, organization_id) VALUES "
            "(141, 'Reference', 'SAME', 'ARCH-SAME', 1, 1, 'reference', NULL), "
            "(142, 'Tenant A', 'SAME', 'ARCH-SAME', 1, 1, 'tenant', 81), "
            "(143, 'Tenant B', 'SAME', 'ARCH-SAME', 1, 1, 'tenant', 82)"
        )
    )

    for values in (
        "(144, 'Reference duplicate code', 'SAME', NULL, 1, 1, 'reference', NULL)",
        "(145, 'Tenant duplicate code', 'SAME', NULL, 1, 1, 'tenant', 81)",
        "(146, 'Reference duplicate ArchiMate', 'OTHER-REF', 'ARCH-SAME', 1, 1, 'reference', NULL)",
        "(147, 'Tenant duplicate ArchiMate', 'OTHER-TEN', 'ARCH-SAME', 1, 1, 'tenant', 81)",
    ):
        nested = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO unified_capabilities "
                    "(id, name, code, archimate_id, level, version, scope, organization_id) "
                    f"VALUES {values}"
                )
            )
        nested.rollback()


def test_apply_installs_validated_ownership_fks_and_database_write_guard(
    capability_schema, tmp_path
):
    """The CLI constraint swap must not depend on running a second manual script."""

    connection = capability_schema
    _capability(connection, 151, "REF-151", source_table="seeded_import", source_org_id=None)
    manifest = tmp_path / "backup.json"
    manifest.write_text(json.dumps({"backup_path": "C:/backups/capabilities.dump"}))

    report = run_cutover(connection, apply=True, backup_manifest=manifest)

    constraints = dict(
        connection.execute(
            text(
                "SELECT conname, convalidated FROM pg_constraint "
                "WHERE conrelid = to_regclass('unified_capabilities') "
                "AND conname IN ("
                "'fk_unified_capabilities_organization', "
                "'fk_unified_capabilities_source_org', "
                "'fk_unified_capabilities_reference', "
                "'fk_unified_capabilities_retired_into')"
            )
        ).all()
    )
    assert constraints == {
        "fk_unified_capabilities_organization": True,
        "fk_unified_capabilities_source_org": True,
        "fk_unified_capabilities_reference": True,
        "fk_unified_capabilities_retired_into": True,
    }
    assert connection.execute(
        text(
            "SELECT count(*) FROM pg_trigger "
            "WHERE tgrelid = to_regclass('unified_capabilities') "
            "AND tgname = 'trg_unified_capability_write_scope' AND NOT tgisinternal"
        )
    ).scalar_one() == 1
    assert report["constraint_swap"] is True


def test_cli_rejects_apply_without_a_recorded_backup(app, tmp_path):
    """The public command cannot enter apply mode without a recovery record."""

    report = tmp_path / "report.json"
    result = app.test_cli_runner().invoke(
        args=["cutover-capability-tenancy", "--apply", "--report", str(report)]
    )

    assert result.exit_code != 0
    assert "backup manifest" in result.output.lower()
    assert not report.exists()
