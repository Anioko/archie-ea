"""Deployment/runtime PostgreSQL role separation for transformation guards."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest
import yaml
from psycopg2 import sql as pg_sql
from sqlalchemy import URL, create_engine

from app.models.transformation_db_guards import ensure_transformation_db_guards


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_ROLE = "archie_deploy"
RUNTIME_ROLE = "archie_runtime"


def _environment(service: dict) -> dict[str, str]:
    environment = service.get("environment", {})
    if isinstance(environment, dict):
        return environment
    return dict(item.split("=", 1) for item in environment)


def _maintenance_url() -> str:
    parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
    return urlunsplit(parsed._replace(path="/postgres"))


@dataclass(frozen=True)
class IsolatedRoleDatabase:
    database_name: str
    deploy_role: str
    runtime_role: str
    privileged_role: str
    deploy_password: str
    runtime_password: str

    def url(self, *, role: str, password: str) -> URL:
        parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
        return URL.create(
            "postgresql+psycopg2",
            username=role,
            password=password,
            host=parsed.hostname,
            port=parsed.port,
            database=self.database_name,
        )


@pytest.fixture
def isolated_role_database():
    """Unique cluster objects are always dropped, including after test failure."""
    suffix = uuid.uuid4().hex[:12]
    role_database = IsolatedRoleDatabase(
        database_name=f"task3_roles_{suffix}",
        deploy_role=f"task3_deploy_{suffix}",
        runtime_role=f"task3_runtime_{suffix}",
        privileged_role=f"task3_privileged_{suffix}",
        deploy_password=f"deploy-{uuid.uuid4().hex}",
        runtime_password=f"runtime-{uuid.uuid4().hex}",
    )
    maintenance = psycopg2.connect(_maintenance_url())
    maintenance.autocommit = True
    try:
        with maintenance.cursor() as cursor:
            cursor.execute(
                pg_sql.SQL("CREATE DATABASE {}").format(
                    pg_sql.Identifier(role_database.database_name)
                )
            )
    finally:
        maintenance.close()

    try:
        yield role_database
    finally:
        maintenance = psycopg2.connect(_maintenance_url())
        maintenance.autocommit = True
        try:
            with maintenance.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (role_database.database_name,),
                )
                cursor.execute(
                    pg_sql.SQL("DROP DATABASE IF EXISTS {}").format(
                        pg_sql.Identifier(role_database.database_name)
                    )
                )
                cursor.execute(
                    pg_sql.SQL("DROP ROLE IF EXISTS {}").format(
                        pg_sql.Identifier(role_database.runtime_role)
                    )
                )
                cursor.execute(
                    pg_sql.SQL("DROP ROLE IF EXISTS {}").format(
                        pg_sql.Identifier(role_database.privileged_role)
                    )
                )
                cursor.execute(
                    pg_sql.SQL("DROP ROLE IF EXISTS {}").format(
                        pg_sql.Identifier(role_database.deploy_role)
                    )
                )
        finally:
            maintenance.close()


_TRANSFORMATION_TABLES_SQL = """
CREATE TABLE command_idempotency_records (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    actor_id integer NOT NULL,
    operation varchar(120) NOT NULL,
    idempotency_key varchar(255) NOT NULL,
    request_digest varchar(64) NOT NULL,
    natural_key varchar(512) NOT NULL,
    status varchar(32) NOT NULL,
    lease_generation integer NOT NULL,
    claim_token varchar(64) NOT NULL,
    claimant_request_id varchar(255) NOT NULL,
    lease_expires_at timestamptz,
    operation_result_id integer,
    attempt_count integer NOT NULL,
    last_error_class varchar(255),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz
);
CREATE TABLE operation_results (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    actor_id integer NOT NULL,
    operation varchar(120) NOT NULL,
    natural_key varchar(512) NOT NULL,
    request_digest varchar(64) NOT NULL,
    receipt_id integer NOT NULL,
    receipt_generation integer NOT NULL,
    object_ids json NOT NULL,
    response_json json NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE transformation_outbox_events (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    operation_result_id integer NOT NULL,
    event_id varchar(36) NOT NULL,
    ordinal integer NOT NULL,
    event_type varchar(160) NOT NULL,
    payload_json json NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    published_at timestamptz,
    delivery_attempts integer NOT NULL DEFAULT 0
);
CREATE TABLE evidence_records (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    candidate_id integer NOT NULL,
    subject_type varchar(40) NOT NULL,
    subject_id integer NOT NULL,
    claim_key varchar(100) NOT NULL,
    classification varchar(40) NOT NULL,
    source_identity varchar(1024) NOT NULL,
    source_type varchar(80) NOT NULL,
    source_record_id integer,
    created_by_id integer NOT NULL,
    value_json json NOT NULL,
    cited_evidence_ids json NOT NULL DEFAULT '[]',
    supersedes_id integer
);
CREATE TABLE evidence_claim_heads (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    subject_type varchar(40) NOT NULL,
    subject_id integer NOT NULL,
    claim_key varchar(100) NOT NULL,
    source_identity varchar(1024) NOT NULL,
    current_record_id integer,
    revision integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE evidence_requests (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    candidate_id integer NOT NULL,
    subject_type varchar(40) NOT NULL,
    subject_id integer NOT NULL,
    claim_key varchar(100) NOT NULL,
    assigned_to_id integer NOT NULL
);
CREATE TABLE evidence_head_events (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    head_id integer NOT NULL,
    old_record_id integer,
    new_record_id integer NOT NULL UNIQUE,
    actor_id integer NOT NULL,
    command_receipt_id integer NOT NULL,
    command_generation integer NOT NULL,
    reason text NOT NULL,
    revision integer NOT NULL,
    created_txid bigint NOT NULL DEFAULT txid_current(),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (organization_id, head_id, revision)
)
"""


@pytest.fixture
def guarded_runtime_database(isolated_role_database):
    """Create the minimal guarded schema under deploy/runtime role separation."""
    from scripts.database.configure_roles import configure_database_roles

    role_database = isolated_role_database
    configure_database_roles(
        admin_url=_maintenance_url(),
        database_names=(role_database.database_name,),
        deploy_password=role_database.deploy_password,
        runtime_password=role_database.runtime_password,
        deploy_role=role_database.deploy_role,
        runtime_role=role_database.runtime_role,
    )
    deploy_engine = create_engine(
        role_database.url(
            role=role_database.deploy_role,
            password=role_database.deploy_password,
        )
    )
    try:
        with deploy_engine.begin() as connection:
            connection.exec_driver_sql(_TRANSFORMATION_TABLES_SQL)
            ensure_transformation_db_guards(
                connection,
                runtime_role=role_database.runtime_role,
            )
        yield role_database
    finally:
        deploy_engine.dispose()


def _runtime_attestation_conflict_pair(role_database, *, conflict_candidate_id: int):
    """Attempt one same-receipt attestation/conflict pair as the runtime role."""
    parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
    raw = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        dbname=role_database.database_name,
        user=role_database.runtime_role,
        password=role_database.runtime_password,
    )
    organization_id = 51001
    actor_id = 52001
    attestation_candidate_id = 53002
    subject_id = 54001
    claim_key = "application_owner"
    source_identity = f"attestation:user:{actor_id}"
    source_digest = hashlib.sha256(source_identity.encode("utf-8")).hexdigest()
    natural_key = (
        f"evidence:{attestation_candidate_id}:{claim_key}:{source_digest}:1"
    )
    claim_token = "c" * 64
    try:
        cursor = raw.cursor()
        cursor.execute(
            "INSERT INTO command_idempotency_records "
            "(organization_id, actor_id, operation, idempotency_key, "
            "request_digest, natural_key, status, lease_generation, "
            "claim_token, claimant_request_id, lease_expires_at, attempt_count) "
            "VALUES (%s, %s, 'evidence.attest', 'candidate-binding', %s, %s, "
            "'in_progress', 1, %s, 'candidate-binding-request', "
            "clock_timestamp() + interval '1 minute', 1) RETURNING id",
            (
                organization_id,
                actor_id,
                "d" * 64,
                natural_key,
                claim_token,
            ),
        )
        receipt_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO evidence_requests "
            "(organization_id, candidate_id, subject_type, subject_id, "
            "claim_key, assigned_to_id) VALUES (%s, %s, 'application', %s, %s, %s) "
            "RETURNING id",
            (
                organization_id,
                conflict_candidate_id,
                subject_id,
                claim_key,
                actor_id,
            ),
        )
        request_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO evidence_claim_heads "
            "(organization_id, subject_type, subject_id, claim_key, source_identity) "
            "VALUES (%s, 'application', %s, %s, %s) RETURNING id",
            (organization_id, subject_id, claim_key, source_identity),
        )
        attestation_head_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO evidence_records "
            "(organization_id, candidate_id, subject_type, subject_id, claim_key, "
            "classification, source_identity, source_type, source_record_id, "
            "created_by_id, value_json, cited_evidence_ids, supersedes_id) "
            "VALUES (%s, %s, 'application', %s, %s, 'attested', %s, "
            "'attestation', %s, %s, %s::json, '[]'::json, NULL) RETURNING id",
            (
                organization_id,
                attestation_candidate_id,
                subject_id,
                claim_key,
                source_identity,
                actor_id,
                actor_id,
                json.dumps("Candidate B attestation"),
            ),
        )
        attestation_record_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT public.archie_advance_evidence_head(%s, %s, 0, %s, %s, 1, %s)",
            (
                attestation_head_id,
                attestation_record_id,
                actor_id,
                receipt_id,
                claim_token,
            ),
        )
        attestation_revision = cursor.fetchone()[0]

        conflict_identity = f"conflict:request:{request_id}"
        cursor.execute(
            "INSERT INTO evidence_claim_heads "
            "(organization_id, subject_type, subject_id, claim_key, source_identity) "
            "VALUES (%s, 'application', %s, %s, %s) RETURNING id",
            (organization_id, subject_id, claim_key, conflict_identity),
        )
        conflict_head_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO evidence_records "
            "(organization_id, candidate_id, subject_type, subject_id, claim_key, "
            "classification, source_identity, source_type, source_record_id, "
            "created_by_id, value_json, cited_evidence_ids, supersedes_id) "
            "VALUES (%s, %s, 'application', %s, %s, 'conflict', %s, "
            "'governance_conflict', %s, %s, %s::json, %s::json, NULL) RETURNING id",
            (
                organization_id,
                conflict_candidate_id,
                subject_id,
                claim_key,
                conflict_identity,
                request_id,
                actor_id,
                json.dumps({"conflicting_evidence_ids": [attestation_record_id]}),
                json.dumps([attestation_record_id]),
            ),
        )
        conflict_record_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT public.archie_advance_evidence_head(%s, %s, 0, %s, %s, 1, %s)",
            (
                conflict_head_id,
                conflict_record_id,
                actor_id,
                receipt_id,
                claim_token,
            ),
        )
        conflict_revision = cursor.fetchone()[0]
        raw.commit()
        cursor.execute(
            "SELECT revision FROM evidence_claim_heads WHERE id = %s",
            (conflict_head_id,),
        )
        persisted_revision = cursor.fetchone()[0]
        cursor.execute(
            "SELECT count(*) FROM evidence_head_events WHERE command_receipt_id = %s",
            (receipt_id,),
        )
        event_count = cursor.fetchone()[0]
        return (
            attestation_revision,
            conflict_revision,
            persisted_revision,
            event_count,
        )
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def _runtime_conflict_resolution(role_database, *, supersede_governing_leaf: bool):
    """Call the definer directly with a current or superseded cited source leaf."""
    parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
    raw = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        dbname=role_database.database_name,
        user=role_database.runtime_role,
        password=role_database.runtime_password,
    )
    organization_id = 61001
    actor_id = 62001
    conflict_candidate_id = 63001
    governing_candidate_id = 63002
    subject_id = 64001
    claim_key = "application_owner"
    source_identity = "inventory:runtime-governing-owner"
    source_digest = hashlib.sha256(source_identity.encode("utf-8")).hexdigest()
    claim_token = "e" * 64

    def insert_receipt(cursor, *, natural_key: str, command_key: str):
        cursor.execute(
            "INSERT INTO command_idempotency_records "
            "(organization_id, actor_id, operation, idempotency_key, "
            "request_digest, natural_key, status, lease_generation, "
            "claim_token, claimant_request_id, lease_expires_at, attempt_count) "
            "VALUES (%s, %s, 'evidence.observe', %s, %s, %s, "
            "'in_progress', 1, %s, %s, clock_timestamp() + interval '1 minute', 1) "
            "RETURNING id",
            (
                organization_id,
                actor_id,
                command_key,
                "f" * 64,
                natural_key,
                claim_token,
                f"{command_key}-request",
            ),
        )
        return cursor.fetchone()[0]

    try:
        cursor = raw.cursor()
        cursor.execute(
            "INSERT INTO evidence_claim_heads "
            "(organization_id, subject_type, subject_id, claim_key, source_identity) "
            "VALUES (%s, 'application', %s, %s, %s) RETURNING id",
            (organization_id, subject_id, claim_key, source_identity),
        )
        governing_head_id = cursor.fetchone()[0]
        root_receipt_id = insert_receipt(
            cursor,
            natural_key=(
                f"evidence:{governing_candidate_id}:{claim_key}:{source_digest}:1"
            ),
            command_key="runtime-governing-root",
        )
        cursor.execute(
            "INSERT INTO evidence_records "
            "(organization_id, candidate_id, subject_type, subject_id, claim_key, "
            "classification, source_identity, source_type, source_record_id, "
            "created_by_id, value_json, cited_evidence_ids, supersedes_id) "
            "VALUES (%s, %s, 'application', %s, %s, 'observed', %s, "
            "'inventory', NULL, %s, %s::json, '[]'::json, NULL) RETURNING id",
            (
                organization_id,
                governing_candidate_id,
                subject_id,
                claim_key,
                source_identity,
                actor_id,
                json.dumps("Governed owner v1"),
            ),
        )
        governing_record_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT public.archie_advance_evidence_head(%s, %s, 0, %s, %s, 1, %s)",
            (
                governing_head_id,
                governing_record_id,
                actor_id,
                root_receipt_id,
                claim_token,
            ),
        )
        assert cursor.fetchone()[0] == 1
        raw.commit()

        if supersede_governing_leaf:
            correction_receipt_id = insert_receipt(
                cursor,
                natural_key=(
                    f"evidence:{governing_candidate_id}:{claim_key}:{source_digest}:2"
                ),
                command_key="runtime-governing-correction",
            )
            cursor.execute(
                "INSERT INTO evidence_records "
                "(organization_id, candidate_id, subject_type, subject_id, claim_key, "
                "classification, source_identity, source_type, source_record_id, "
                "created_by_id, value_json, cited_evidence_ids, supersedes_id) "
                "VALUES (%s, %s, 'application', %s, %s, 'observed', %s, "
                "'inventory', NULL, %s, %s::json, '[]'::json, %s) RETURNING id",
                (
                    organization_id,
                    governing_candidate_id,
                    subject_id,
                    claim_key,
                    source_identity,
                    actor_id,
                    json.dumps("Governed owner v2"),
                    governing_record_id,
                ),
            )
            correction_record_id = cursor.fetchone()[0]
            cursor.execute(
                "SELECT public.archie_advance_evidence_head(%s, %s, 1, %s, %s, 1, %s)",
                (
                    governing_head_id,
                    correction_record_id,
                    actor_id,
                    correction_receipt_id,
                    claim_token,
                ),
            )
            assert cursor.fetchone()[0] == 2
            raw.commit()

        cursor.execute(
            "INSERT INTO evidence_records "
            "(organization_id, candidate_id, subject_type, subject_id, claim_key, "
            "classification, source_identity, source_type, source_record_id, "
            "created_by_id, value_json, cited_evidence_ids, supersedes_id) "
            "VALUES (%s, %s, 'application', %s, %s, 'conflict', %s, "
            "'governance_conflict', NULL, %s, %s::json, %s::json, NULL) RETURNING id",
            (
                organization_id,
                conflict_candidate_id,
                subject_id,
                claim_key,
                "conflict:runtime-resolution-probe",
                actor_id,
                json.dumps({"conflicting_evidence_ids": [governing_record_id]}),
                json.dumps([governing_record_id]),
            ),
        )
        conflict_record_id = cursor.fetchone()[0]
        resolution_identity = f"resolution:conflict:{conflict_record_id}"
        cursor.execute(
            "INSERT INTO evidence_claim_heads "
            "(organization_id, subject_type, subject_id, claim_key, source_identity) "
            "VALUES (%s, 'application', %s, %s, %s) RETURNING id",
            (organization_id, subject_id, claim_key, resolution_identity),
        )
        resolution_head_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO command_idempotency_records "
            "(organization_id, actor_id, operation, idempotency_key, "
            "request_digest, natural_key, status, lease_generation, "
            "claim_token, claimant_request_id, lease_expires_at, attempt_count) "
            "VALUES (%s, %s, 'evidence.conflict.resolve', 'runtime-resolution', %s, %s, "
            "'in_progress', 1, %s, 'runtime-resolution-request', "
            "clock_timestamp() + interval '1 minute', 1) RETURNING id",
            (
                organization_id,
                actor_id,
                "a" * 64,
                (
                    f"evidence-conflict-resolution:{conflict_record_id}:"
                    f"{governing_record_id}"
                ),
                claim_token,
            ),
        )
        resolution_receipt_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO evidence_records "
            "(organization_id, candidate_id, subject_type, subject_id, claim_key, "
            "classification, source_identity, source_type, source_record_id, "
            "created_by_id, value_json, cited_evidence_ids, supersedes_id) "
            "VALUES (%s, %s, 'application', %s, %s, 'derived', %s, "
            "'governance_resolution', %s, %s, %s::json, %s::json, NULL) RETURNING id",
            (
                organization_id,
                conflict_candidate_id,
                subject_id,
                claim_key,
                resolution_identity,
                conflict_record_id,
                actor_id,
                json.dumps(
                    {
                        "conflict_evidence_id": conflict_record_id,
                        "governing_evidence_id": governing_record_id,
                        "rationale": "Runtime direct-call current-head probe",
                    }
                ),
                json.dumps([conflict_record_id, governing_record_id]),
            ),
        )
        resolution_record_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT public.archie_advance_evidence_head(%s, %s, 0, %s, %s, 1, %s)",
            (
                resolution_head_id,
                resolution_record_id,
                actor_id,
                resolution_receipt_id,
                claim_token,
            ),
        )
        revision = cursor.fetchone()[0]
        raw.commit()
        return revision
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def test_restricted_runtime_allows_same_candidate_attestation_conflict_pair(
    guarded_runtime_database,
):
    """Catches candidate binding accidentally rejecting the valid paired move."""
    assert _runtime_attestation_conflict_pair(
        guarded_runtime_database,
        conflict_candidate_id=53002,
    ) == (1, 1, 1, 2)


def test_restricted_runtime_rejects_cross_candidate_attestation_conflict_move(
    guarded_runtime_database,
):
    """Catches candidate B's receipt advancing candidate A's conflict head."""
    with pytest.raises(
        psycopg2.Error,
        match="attestation candidate does not match conflict request candidate",
    ):
        _runtime_attestation_conflict_pair(
            guarded_runtime_database,
            conflict_candidate_id=53001,
        )


def test_restricted_runtime_allows_resolution_with_current_cited_source_leaf(
    guarded_runtime_database,
):
    """Catches the definer rejecting a valid candidate-agnostic governing leaf."""
    assert _runtime_conflict_resolution(
        guarded_runtime_database,
        supersede_governing_leaf=False,
    ) == 1


def test_restricted_runtime_rejects_resolution_with_superseded_cited_source_leaf(
    guarded_runtime_database,
):
    """Catches a restricted direct call governing by a cited but superseded leaf."""
    with pytest.raises(psycopg2.Error, match="governing evidence is not current"):
        _runtime_conflict_resolution(
            guarded_runtime_database,
            supersede_governing_leaf=True,
        )


def test_compose_paths_separate_database_deployment_from_runtime():
    """Catches a web/worker process retaining database-owner credentials."""
    main = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    optimized = yaml.safe_load(
        (ROOT / "docker-compose.optimized.yml").read_text(encoding="utf-8")
    )

    for document, runtime_services in ((main, ("server", "worker")), (optimized, ("web", "web-dev"))):
        services = document["services"]
        assert {"database-bootstrap", "schema-deploy"} <= services.keys()
        bootstrap_env = _environment(services["database-bootstrap"])
        deploy_env = _environment(services["schema-deploy"])
        assert "postgresql://postgres:" in bootstrap_env["DATABASE_ADMIN_URL"]
        assert f"postgresql://{DEPLOY_ROLE}:" in deploy_env["DATABASE_URL"]
        for service_name in runtime_services:
            runtime_env = _environment(services[service_name])
            assert f"postgresql://{RUNTIME_ROLE}:" in runtime_env["DATABASE_URL"]
            assert "postgresql://postgres:" not in runtime_env["DATABASE_URL"]
            assert "DATABASE_ADMIN_URL" not in runtime_env
            assert "DATABASE_DEPLOY_PASSWORD" not in runtime_env

    optimized_backup = _environment(optimized["services"]["backup"])
    assert optimized_backup["PGPASSWORD"] == "${POSTGRES_PASSWORD}"


def test_role_bootstrap_is_idempotent_and_runtime_cannot_bypass_guards(
    isolated_role_database,
):
    """Catches superuser/owner powers making database guards optional at runtime."""
    from scripts.database.configure_roles import configure_database_roles

    role_database = isolated_role_database
    configure_database_roles(
        admin_url=_maintenance_url(),
        database_names=(role_database.database_name,),
        deploy_password=role_database.deploy_password,
        runtime_password=role_database.runtime_password,
        deploy_role=role_database.deploy_role,
        runtime_role=role_database.runtime_role,
    )
    maintenance = psycopg2.connect(_maintenance_url())
    maintenance.autocommit = True
    try:
        with maintenance.cursor() as cursor:
            cursor.execute(
                pg_sql.SQL("CREATE ROLE {} CREATEDB").format(
                    pg_sql.Identifier(role_database.privileged_role)
                )
            )
            cursor.execute(
                pg_sql.SQL("GRANT {} TO {}").format(
                    pg_sql.Identifier(role_database.deploy_role),
                    pg_sql.Identifier(role_database.runtime_role),
                )
            )
            cursor.execute(
                pg_sql.SQL("GRANT {} TO {}").format(
                    pg_sql.Identifier(role_database.privileged_role),
                    pg_sql.Identifier(role_database.runtime_role),
                )
            )
    finally:
        maintenance.close()

    configure_database_roles(
        admin_url=_maintenance_url(),
        database_names=(role_database.database_name,),
        deploy_password=role_database.deploy_password,
        runtime_password=role_database.runtime_password,
        deploy_role=role_database.deploy_role,
        runtime_role=role_database.runtime_role,
    )
    maintenance = psycopg2.connect(_maintenance_url())
    try:
        with maintenance.cursor() as cursor:
            cursor.execute(
                "SELECT granted.rolname FROM pg_auth_members membership "
                "JOIN pg_roles granted ON granted.oid = membership.roleid "
                "JOIN pg_roles member ON member.oid = membership.member "
                "WHERE member.rolname = %s ORDER BY granted.rolname",
                (role_database.runtime_role,),
            )
            assert cursor.fetchall() == []
    finally:
        maintenance.close()

    deploy_engine = create_engine(
        role_database.url(
            role=role_database.deploy_role,
            password=role_database.deploy_password,
        )
    )
    try:
        with deploy_engine.begin() as connection:
            connection.exec_driver_sql(_TRANSFORMATION_TABLES_SQL)
            ensure_transformation_db_guards(
                connection,
                runtime_role=role_database.runtime_role,
            )

        parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
        raw = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            dbname=role_database.database_name,
            user=role_database.runtime_role,
            password=role_database.runtime_password,
        )
        try:
            cursor = raw.cursor()
            cursor.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = %s",
                (role_database.runtime_role,),
            )
            assert cursor.fetchone() == (False, False, False, False, False)
            cursor.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication "
                "FROM pg_roles WHERE rolname = %s",
                (role_database.deploy_role,),
            )
            assert cursor.fetchone() == (False, False, False, False)
            cursor.execute(
                "SELECT tableowner FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename = 'operation_results'"
            )
            assert cursor.fetchone() == (role_database.deploy_role,)
            cursor.execute(
                "SELECT has_table_privilege(%s, 'operation_results', 'SELECT'), "
                "has_table_privilege(%s, 'operation_results', 'INSERT'), "
                "has_table_privilege(%s, 'operation_results', 'UPDATE'), "
                "has_table_privilege(%s, 'operation_results', 'DELETE'), "
                "has_table_privilege(%s, 'operation_results', 'TRUNCATE'), "
                "has_column_privilege(%s, 'command_idempotency_records', "
                "'status', 'UPDATE'), "
                "has_column_privilege(%s, 'command_idempotency_records', "
                "'idempotency_key', 'UPDATE'), "
                "has_sequence_privilege(%s, 'operation_results_id_seq', 'USAGE'), "
                "has_function_privilege(%s, "
                "'public.archie_guard_transformation_receipt()', 'EXECUTE')",
                (role_database.runtime_role,) * 9,
            )
            assert cursor.fetchone() == (
                True,
                True,
                False,
                False,
                False,
                True,
                False,
                True,
                False,
            )
            cursor.execute(
                "SELECT has_table_privilege(%s, 'evidence_head_events', 'SELECT'), "
                "has_table_privilege(%s, 'evidence_head_events', 'INSERT'), "
                "has_function_privilege(%s, "
                "'public.archie_advance_evidence_head(bigint,bigint,integer,bigint,bigint,integer,text)', "
                "'EXECUTE')",
                (role_database.runtime_role,) * 3,
            )
            assert cursor.fetchone() == (True, False, True)
            cursor.execute(
                "SELECT p.proname, pg_get_function_identity_arguments(p.oid) "
                "FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' "
                "AND NOT EXISTS ("
                "SELECT 1 FROM pg_depend dependency "
                "WHERE dependency.classid = 'pg_proc'::regclass "
                "AND dependency.objid = p.oid AND dependency.deptype = 'e'"
                ") AND has_function_privilege(%s, p.oid, 'EXECUTE')",
                (role_database.runtime_role,),
            )
            assert cursor.fetchall() == [
                (
                    "archie_advance_evidence_head",
                    "p_head_id bigint, p_new_record_id bigint, "
                    "p_expected_revision integer, p_actor_id bigint, "
                    "p_receipt_id bigint, p_generation integer, p_claim_token text",
                )
            ]

            cursor.execute(
                "INSERT INTO command_idempotency_records "
                "(organization_id, actor_id, operation, idempotency_key, "
                "request_digest, natural_key, status, lease_generation, "
                "claim_token, claimant_request_id, lease_expires_at, attempt_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'in_progress', 1, %s, %s, "
                "clock_timestamp() + interval '1 minute', 1) RETURNING id",
                (
                    41001,
                    42001,
                    "runtime.probe",
                    "runtime-probe",
                    "a" * 64,
                    "runtime:probe",
                    "b" * 64,
                    "runtime-request",
                ),
            )
            receipt_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO operation_results "
                "(organization_id, actor_id, operation, natural_key, "
                "request_digest, receipt_id, receipt_generation, object_ids, "
                "response_json) VALUES (%s, %s, %s, %s, %s, %s, 1, '{}', '{}') "
                "RETURNING id",
                (
                    41001,
                    42001,
                    "runtime.probe",
                    "runtime:probe",
                    "a" * 64,
                    receipt_id,
                ),
            )
            result_id = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE command_idempotency_records SET status = 'succeeded', "
                "operation_result_id = %s, lease_expires_at = NULL, "
                "completed_at = clock_timestamp() "
                "WHERE id = %s AND organization_id = %s AND actor_id = %s",
                (result_id, receipt_id, 41001, 42001),
            )
            cursor.execute(
                "INSERT INTO transformation_outbox_events "
                "(organization_id, operation_result_id, event_id, ordinal, "
                "event_type, payload_json) VALUES (%s, %s, %s, 0, %s, '{}')",
                (
                    41001,
                    result_id,
                    str(uuid.uuid4()),
                    "runtime.probe.created",
                ),
            )
            cursor.execute(
                "UPDATE transformation_outbox_events "
                "SET delivery_attempts = 1, published_at = clock_timestamp() "
                "WHERE operation_result_id = %s AND organization_id = %s",
                (result_id, 41001),
            )
            raw.commit()

            forbidden = (
                "SET session_replication_role = replica",
                f"SET ROLE {role_database.deploy_role}",
                f"SET ROLE {role_database.privileged_role}",
                "ALTER TABLE public.operation_results DISABLE TRIGGER ALL",
                "DROP TRIGGER trg_transformation_result_immutable ON public.operation_results",
                "TRUNCATE TABLE public.operation_results",
                "UPDATE public.operation_results SET request_digest = request_digest",
                "DELETE FROM public.command_idempotency_records",
                "INSERT INTO public.evidence_head_events DEFAULT VALUES",
                "SELECT public.archie_guard_transformation_receipt()",
                "CREATE TABLE public.runtime_guard_bypass (id integer)",
            )
            for statement in forbidden:
                try:
                    cursor.execute(statement)
                except psycopg2.Error:
                    pass
                else:
                    pytest.fail(
                        f"runtime role unexpectedly executed forbidden SQL: {statement}"
                    )
                raw.rollback()
        finally:
            raw.rollback()
            raw.close()
    finally:
        deploy_engine.dispose()
