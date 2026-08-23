"""Deployment/runtime PostgreSQL role separation for transformation guards."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
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
COMMAND_CAPABILITY_SECRET = "63" * 32


def _claim_runtime_command(
    cursor,
    *,
    organization_id,
    actor_id,
    operation,
    command_key,
    request_digest,
    natural_key,
    claim_token,
    request_id,
    capability_secret=COMMAND_CAPABILITY_SECRET,
):
    """Exercise the same deployment-secret boundary as CommandService."""
    secret = bytes.fromhex(capability_secret)
    document = json.dumps(
        {
            "schema_version": "transformation-command-claim-r1",
            "key_id": hashlib.sha256(secret).hexdigest(),
            "organization_id": organization_id,
            "actor_id": actor_id,
            "operation": operation,
            "idempotency_key": command_key,
            "request_digest": request_digest,
            "natural_key": natural_key,
            "claim_token": claim_token,
            "claimant_request_id": request_id,
            "lease_milliseconds": 60000,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    capability = hmac.new(
        secret, document.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    cursor.execute(
        "SELECT * FROM public.archie_claim_transformation_command(%s, %s)",
        (document, capability),
    )
    claimed = cursor.fetchone()
    assert claimed[0] == "claimed"
    return claimed[1]


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


def _render_statement(cursor, statement) -> str:
    if isinstance(statement, pg_sql.Composable):
        return statement.as_string(cursor)
    return str(statement)


class _InterceptingCursor:
    """Delegate to psycopg2 while exposing executed SQL to one test callback."""

    def __init__(self, cursor, after_execute):
        self._cursor = cursor
        self._after_execute = after_execute

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._cursor.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def execute(self, statement, parameters=None):
        result = self._cursor.execute(statement, parameters)
        self._after_execute(_render_statement(self._cursor, statement))
        return result


class _InterceptingConnection:
    """Keep real transaction semantics while intercepting cursor execution."""

    def __init__(self, connection, after_execute):
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_after_execute", after_execute)

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return self._connection.__exit__(exc_type, exc_value, traceback)
        finally:
            self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __setattr__(self, name, value):
        setattr(self._connection, name, value)

    def cursor(self, *args, **kwargs):
        return _InterceptingCursor(
            self._connection.cursor(*args, **kwargs),
            self._after_execute,
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
    completed_at timestamptz,
    UNIQUE (organization_id, actor_id, operation, idempotency_key)
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
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (organization_id, operation, natural_key)
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
);
CREATE TABLE decision_brief_option_citations (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    brief_version_id integer NOT NULL,
    option_version_id integer NOT NULL
);
CREATE TABLE decision_briefs (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    workstream_id integer NOT NULL,
    status varchar(30) NOT NULL,
    revision integer NOT NULL
);
CREATE TABLE decision_brief_versions (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    brief_id integer NOT NULL,
    workstream_id integer NOT NULL,
    source_revision integer NOT NULL,
    created_by_id integer NOT NULL,
    submitted_by_id integer NOT NULL,
    content_hash varchar(64) NOT NULL,
    option_version_ids json NOT NULL,
    cited_evidence_ids json NOT NULL,
    frozen_payload json NOT NULL
);
CREATE TABLE decision_brief_evidence_citations (
    id serial PRIMARY KEY,
    organization_id integer NOT NULL,
    brief_version_id integer NOT NULL,
    evidence_record_id integer NOT NULL,
    evidence_head_id integer NOT NULL,
    head_revision_at_freeze integer NOT NULL,
    current_record_id_at_freeze integer NOT NULL,
    was_current boolean NOT NULL,
    acknowledged boolean NOT NULL,
    freshness_status varchar(30) NOT NULL
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
                capability_secrets=(COMMAND_CAPABILITY_SECRET,),
            )
        configure_database_roles(
            admin_url=_maintenance_url(),
            database_names=(role_database.database_name,),
            deploy_password=role_database.deploy_password,
            runtime_password=role_database.runtime_password,
            deploy_role=role_database.deploy_role,
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
        receipt_id = _claim_runtime_command(
            cursor,
            organization_id=organization_id,
            actor_id=actor_id,
            operation="evidence.attest",
            command_key="candidate-binding",
            request_digest="d" * 64,
            natural_key=natural_key,
            claim_token=claim_token,
            request_id="candidate-binding-request",
        )
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


def test_restricted_runtime_cannot_forge_receipt_brief_version_and_citations(
    guarded_runtime_database,
):
    """Catches runtime composing writable command/version rows into a forged dossier."""
    role_database = guarded_runtime_database
    parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
    raw = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        dbname=role_database.database_name,
        user=role_database.runtime_role,
        password=role_database.runtime_password,
    )
    exploit_succeeded = False
    try:
        cursor = raw.cursor()
        cursor.execute(
            "INSERT INTO decision_briefs "
            "(organization_id, workstream_id, status, revision) "
            "VALUES (71001, 72001, 'draft', 1) RETURNING id"
        )
        brief_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO command_idempotency_records "
            "(organization_id, actor_id, operation, idempotency_key, "
            " request_digest, natural_key, status, lease_generation, "
            " claim_token, claimant_request_id, lease_expires_at, attempt_count) "
            "VALUES (71001, 73001, 'brief.freeze', 'forged-brief', %s, %s, "
            " 'in_progress', 1, %s, 'forged-request', "
            " clock_timestamp() + interval '1 minute', 1) RETURNING id",
            (
                "d" * 64,
                f"brief:{brief_id}:version:1",
                "t" * 64,
            ),
        )
        receipt_id = cursor.fetchone()[0]
        frozen_payload = {
            "option_versions": [{"id": 74001}],
            "evidence": [],
        }
        cursor.execute(
            "INSERT INTO decision_brief_versions "
            "(organization_id, brief_id, workstream_id, source_revision, "
            " created_by_id, submitted_by_id, content_hash, "
            " option_version_ids, cited_evidence_ids, frozen_payload) "
            "VALUES (71001, %s, 72001, 1, 73001, 73001, %s, %s::json, "
            " '[]'::json, %s::json) RETURNING id",
            (
                brief_id,
                "a" * 64,
                json.dumps([74001]),
                json.dumps(frozen_payload),
            ),
        )
        version_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT public.archie_insert_decision_brief_citations("
            "%s, 73001, %s, 1, %s)",
            (version_id, receipt_id, "t" * 64),
        )
        raw.commit()
        exploit_succeeded = True
    except psycopg2.Error:
        raw.rollback()
    finally:
        raw.close()

    deploy_engine = create_engine(
        role_database.url(
            role=role_database.deploy_role,
            password=role_database.deploy_password,
        )
    )
    try:
        with deploy_engine.connect() as connection:
            artifact_count = connection.exec_driver_sql(
                "SELECT (SELECT count(*) FROM decision_brief_versions) + "
                "(SELECT count(*) FROM decision_brief_option_citations) + "
                "(SELECT count(*) FROM decision_brief_evidence_citations)"
            ).scalar_one()
    finally:
        deploy_engine.dispose()

    assert exploit_succeeded is False
    assert artifact_count == 0


def test_restricted_runtime_receipts_require_server_signed_claim(
    guarded_runtime_database,
):
    """Catches restoring direct receipt minting or exposing the owner-only HMAC key."""
    role_database = guarded_runtime_database
    deploy_engine = create_engine(
        role_database.url(
            role=role_database.deploy_role,
            password=role_database.deploy_password,
        )
    )
    try:
        with deploy_engine.connect() as connection:
            privileges = connection.exec_driver_sql(
                "SELECT "
                "has_table_privilege(%s, 'command_idempotency_records', 'INSERT'), "
                "has_table_privilege(%s, 'archie_command_capability_keys', 'SELECT'), "
                "has_function_privilege(%s, "
                "'public.archie_claim_transformation_command(text,text)', 'EXECUTE')",
                (role_database.runtime_role,) * 3,
            ).one()
    finally:
        deploy_engine.dispose()

    assert privileges == (False, False, True)

    parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
    raw = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        dbname=role_database.database_name,
        user=role_database.runtime_role,
        password=role_database.runtime_password,
    )
    try:
        with raw.cursor() as cursor, pytest.raises(psycopg2.Error):
            cursor.execute(
                "INSERT INTO command_idempotency_records "
                "(organization_id, actor_id, operation, idempotency_key, "
                " request_digest, natural_key, status, lease_generation, "
                " claim_token, claimant_request_id, lease_expires_at, attempt_count) "
                "VALUES (1, 2, 'brief.freeze', 'forged', %s, 'brief:3:version:1', "
                " 'in_progress', 1, %s, 'forged-request', "
                " clock_timestamp() + interval '1 minute', 1)",
                ("d" * 64, "t" * 64),
            )
    finally:
        raw.rollback()
        raw.close()


def test_capability_key_rotation_accepts_overlap_then_retires_previous_key(
    guarded_runtime_database,
):
    role_database = guarded_runtime_database
    next_secret = "64" * 32
    deploy_engine = create_engine(
        role_database.url(
            role=role_database.deploy_role,
            password=role_database.deploy_password,
        )
    )
    try:
        with deploy_engine.begin() as connection:
            ensure_transformation_db_guards(
                connection,
                runtime_role=role_database.runtime_role,
                capability_secrets=(next_secret, COMMAND_CAPABILITY_SECRET),
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
            with raw.cursor() as cursor:
                old_receipt = _claim_runtime_command(
                    cursor,
                    organization_id=81001,
                    actor_id=82001,
                    operation="rotation.probe",
                    command_key="overlap-old",
                    request_digest="8" * 64,
                    natural_key="rotation:old",
                    claim_token="9" * 64,
                    request_id="rotation-overlap",
                )
            raw.commit()
            assert old_receipt > 0

            with deploy_engine.begin() as connection:
                ensure_transformation_db_guards(
                    connection,
                    runtime_role=role_database.runtime_role,
                    capability_secrets=(next_secret,),
                )

            with raw.cursor() as cursor, pytest.raises(psycopg2.Error):
                _claim_runtime_command(
                    cursor,
                    organization_id=81001,
                    actor_id=82001,
                    operation="rotation.probe",
                    command_key="retired-old",
                    request_digest="8" * 64,
                    natural_key="rotation:retired",
                    claim_token="a" * 64,
                    request_id="rotation-retired",
                )
            raw.rollback()
            with raw.cursor() as cursor:
                current_receipt = _claim_runtime_command(
                    cursor,
                    organization_id=81001,
                    actor_id=82001,
                    operation="rotation.probe",
                    command_key="current-new",
                    request_digest="8" * 64,
                    natural_key="rotation:current",
                    claim_token="b" * 64,
                    request_id="rotation-current",
                    capability_secret=next_secret,
                )
            raw.commit()
            assert current_receipt > old_receipt
        finally:
            raw.close()
    finally:
        deploy_engine.dispose()


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
        return _claim_runtime_command(
            cursor,
            organization_id=organization_id,
            actor_id=actor_id,
            operation="evidence.observe",
            command_key=command_key,
            request_digest="f" * 64,
            natural_key=natural_key,
            claim_token=claim_token,
            request_id=f"{command_key}-request",
        )

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
        resolution_receipt_id = _claim_runtime_command(
            cursor,
            organization_id=organization_id,
            actor_id=actor_id,
            operation="evidence.conflict.resolve",
            command_key="runtime-resolution",
            request_digest="a" * 64,
            natural_key=(
                f"evidence-conflict-resolution:{conflict_record_id}:"
                f"{governing_record_id}"
            ),
            claim_token=claim_token,
            request_id="runtime-resolution-request",
        )
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


def _runtime_same_source_resolution_attack(
    role_database, *, duplicate_head_alias: bool
):
    """Attempt to make a resolution replace its own governing source head."""
    parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
    raw = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        dbname=role_database.database_name,
        user=role_database.runtime_role,
        password=role_database.runtime_password,
    )
    organization_id = 71001
    actor_id = 72001
    candidate_id = 73001
    subject_id = 74001
    claim_key = "application_owner"
    claim_token = "1" * 64

    def persisted_state(cursor):
        cursor.execute(
            "SELECT count(*) FROM evidence_records WHERE organization_id = %s",
            (organization_id,),
        )
        record_count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT count(*) FROM evidence_head_events WHERE organization_id = %s",
            (organization_id,),
        )
        event_count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT id, current_record_id, revision FROM evidence_claim_heads "
            "WHERE organization_id = %s ORDER BY id",
            (organization_id,),
        )
        return record_count, event_count, tuple(cursor.fetchall())

    try:
        cursor = raw.cursor()
        cursor.execute(
            "SELECT nextval(pg_get_serial_sequence('evidence_records', 'id'))"
        )
        governing_record_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO evidence_records "
            "(organization_id, candidate_id, subject_type, subject_id, claim_key, "
            "classification, source_identity, source_type, source_record_id, "
            "created_by_id, value_json, cited_evidence_ids, supersedes_id) "
            "VALUES (%s, %s, 'application', %s, %s, 'conflict', %s, "
            "'governance_conflict', NULL, %s, %s::json, %s::json, NULL) RETURNING id",
            (
                organization_id,
                candidate_id,
                subject_id,
                claim_key,
                "conflict:runtime-self-resolution-probe",
                actor_id,
                json.dumps({"conflicting_evidence_ids": [governing_record_id]}),
                json.dumps([governing_record_id]),
            ),
        )
        conflict_record_id = cursor.fetchone()[0]
        resolution_identity = f"resolution:conflict:{conflict_record_id}"
        source_digest = hashlib.sha256(
            resolution_identity.encode("utf-8")
        ).hexdigest()
        cursor.execute(
            "INSERT INTO evidence_claim_heads "
            "(organization_id, subject_type, subject_id, claim_key, source_identity) "
            "VALUES (%s, 'application', %s, %s, %s) RETURNING id",
            (organization_id, subject_id, claim_key, resolution_identity),
        )
        governing_head_id = cursor.fetchone()[0]
        observation_receipt_id = _claim_runtime_command(
            cursor,
            organization_id=organization_id,
            actor_id=actor_id,
            operation="evidence.observe",
            command_key="self-governing-root",
            request_digest="2" * 64,
            natural_key=f"evidence:{candidate_id}:{claim_key}:{source_digest}:1",
            claim_token=claim_token,
            request_id="self-governing-root-request",
        )
        cursor.execute(
            "INSERT INTO evidence_records "
            "(id, organization_id, candidate_id, subject_type, subject_id, claim_key, "
            "classification, source_identity, source_type, source_record_id, "
            "created_by_id, value_json, cited_evidence_ids, supersedes_id) "
            "VALUES (%s, %s, %s, 'application', %s, %s, 'observed', %s, "
            "'inventory', NULL, %s, %s::json, '[]'::json, NULL)",
            (
                governing_record_id,
                organization_id,
                candidate_id,
                subject_id,
                claim_key,
                resolution_identity,
                actor_id,
                json.dumps("Self-governing owner"),
            ),
        )
        cursor.execute(
            "SELECT public.archie_advance_evidence_head(%s, %s, 0, %s, %s, 1, %s)",
            (
                governing_head_id,
                governing_record_id,
                actor_id,
                observation_receipt_id,
                claim_token,
            ),
        )
        assert cursor.fetchone()[0] == 1
        target_head_id = governing_head_id
        expected_revision = 1
        supersedes_id = governing_record_id
        if duplicate_head_alias:
            cursor.execute(
                "INSERT INTO evidence_claim_heads "
                "(organization_id, subject_type, subject_id, claim_key, "
                "source_identity) VALUES (%s, 'application', %s, %s, %s) "
                "RETURNING id",
                (organization_id, subject_id, claim_key, resolution_identity),
            )
            target_head_id = cursor.fetchone()[0]
            expected_revision = 0
            supersedes_id = None
        raw.commit()
        before = persisted_state(cursor)

        resolution_receipt_id = _claim_runtime_command(
            cursor,
            organization_id=organization_id,
            actor_id=actor_id,
            operation="evidence.conflict.resolve",
            command_key="self-governing-attack",
            request_digest="3" * 64,
            natural_key=(
                f"evidence-conflict-resolution:{conflict_record_id}:"
                f"{governing_record_id}"
            ),
            claim_token=claim_token,
            request_id="self-governing-attack-request",
        )
        cursor.execute(
            "INSERT INTO evidence_records "
            "(organization_id, candidate_id, subject_type, subject_id, claim_key, "
            "classification, source_identity, source_type, source_record_id, "
            "created_by_id, value_json, cited_evidence_ids, supersedes_id) "
            "VALUES (%s, %s, 'application', %s, %s, 'derived', %s, "
            "'governance_resolution', %s, %s, %s::json, %s::json, %s) RETURNING id",
            (
                organization_id,
                candidate_id,
                subject_id,
                claim_key,
                resolution_identity,
                conflict_record_id,
                actor_id,
                json.dumps(
                    {
                        "conflict_evidence_id": conflict_record_id,
                        "governing_evidence_id": governing_record_id,
                        "rationale": "Attempt to replace the governing source",
                    }
                ),
                json.dumps([conflict_record_id, governing_record_id]),
                supersedes_id,
            ),
        )
        resolution_record_id = cursor.fetchone()[0]
        error_message = None
        try:
            cursor.execute(
                "SELECT public.archie_advance_evidence_head("
                "%s, %s, %s, %s, %s, 1, %s)",
                (
                    target_head_id,
                    resolution_record_id,
                    expected_revision,
                    actor_id,
                    resolution_receipt_id,
                    claim_token,
                ),
            )
            raw.commit()
        except psycopg2.Error as error:
            error_message = str(error)
            raw.rollback()
        after = persisted_state(cursor)
        return error_message, before, after
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


@pytest.mark.parametrize(
    "duplicate_head_alias",
    (False, True),
    ids=("same-head", "identical-full-key-alias"),
)
def test_restricted_runtime_rejects_self_governing_resolution_atomically(
    guarded_runtime_database,
    duplicate_head_alias,
):
    """Catches a resolution replacing its authority through the same source."""
    error, before, after = _runtime_same_source_resolution_attack(
        guarded_runtime_database,
        duplicate_head_alias=duplicate_head_alias,
    )

    assert "governing evidence source must differ from resolution source" in (
        error or ""
    )
    assert after == before


def test_compose_paths_separate_database_deployment_from_runtime():
    """Catches a web/worker process retaining database-owner credentials."""
    main = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    optimized = yaml.safe_load(
        (ROOT / "docker-compose.optimized.yml").read_text(encoding="utf-8")
    )

    for document, runtime_services in ((main, ("server", "worker")), (optimized, ("web", "web-dev"))):
        services = document["services"]
        assert {"database-bootstrap", "schema-deploy", "database-acl"} <= services.keys()
        bootstrap_env = _environment(services["database-bootstrap"])
        deploy_env = _environment(services["schema-deploy"])
        acl_env = _environment(services["database-acl"])
        assert "postgresql://postgres:" in bootstrap_env["DATABASE_ADMIN_URL"]
        assert "postgresql://postgres:" in acl_env["DATABASE_ADMIN_URL"]
        assert f"postgresql://{DEPLOY_ROLE}:" in deploy_env["DATABASE_URL"]
        assert services["schema-deploy"]["depends_on"]["database-bootstrap"] == {
            "condition": "service_completed_successfully"
        }
        assert services["database-acl"]["depends_on"]["schema-deploy"] == {
            "condition": "service_completed_successfully"
        }
        for service_name in runtime_services:
            runtime_env = _environment(services[service_name])
            assert f"postgresql://{RUNTIME_ROLE}:" in runtime_env["DATABASE_URL"]
            assert "postgresql://postgres:" not in runtime_env["DATABASE_URL"]
            assert "DATABASE_ADMIN_URL" not in runtime_env
            assert "DATABASE_DEPLOY_PASSWORD" not in runtime_env
            assert services[service_name]["depends_on"]["database-acl"] == {
                "condition": "service_completed_successfully"
            }

    optimized_backup = _environment(optimized["services"]["backup"])
    assert optimized_backup["PGPASSWORD"] == "${POSTGRES_PASSWORD}"


def test_compose_provisions_command_capability_to_schema_and_app_only():
    """Catches deploy/app capability keys diverging or reaching database bootstrap."""
    main = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    optimized = yaml.safe_load(
        (ROOT / "docker-compose.optimized.yml").read_text(encoding="utf-8")
    )

    for document, runtime_services in (
        (main, ("server", "worker")),
        (optimized, ("web", "web-dev")),
    ):
        services = document["services"]
        assert "TRANSFORMATION_COMMAND_CAPABILITY_SECRET" not in _environment(
            services["database-bootstrap"]
        )
        assert "TRANSFORMATION_COMMAND_CAPABILITY_SECRET" not in _environment(
            services["database-acl"]
        )
        assert _environment(services["schema-deploy"])[
            "TRANSFORMATION_COMMAND_CAPABILITY_SECRET"
        ] == "${TRANSFORMATION_COMMAND_CAPABILITY_SECRET}"
        for service_name in runtime_services:
            runtime = _environment(services[service_name])
            assert runtime["TRANSFORMATION_COMMAND_CAPABILITY_SECRET"] == (
                "${TRANSFORMATION_COMMAND_CAPABILITY_SECRET}"
            )
            assert "DATABASE_DEPLOY_PASSWORD" not in runtime


def test_new_tables_have_no_implicit_runtime_access_until_acl_finalization(
    isolated_role_database,
):
    """Catches default privileges silently giving every future table write access."""
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
            connection.exec_driver_sql(
                "CREATE TABLE future_runtime_records "
                "(id serial PRIMARY KEY, payload text NOT NULL)"
            )
            connection.exec_driver_sql(
                "CREATE FUNCTION future_runtime_probe() RETURNS integer "
                "LANGUAGE sql AS 'SELECT 1'"
            )

        maintenance = psycopg2.connect(
            _maintenance_url(), dbname=role_database.database_name
        )
        try:
            with maintenance.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege(%s, 'future_runtime_records', 'SELECT'), "
                    "has_table_privilege(%s, 'future_runtime_records', 'INSERT'), "
                    "has_table_privilege(%s, 'future_runtime_records', 'UPDATE'), "
                    "has_table_privilege(%s, 'future_runtime_records', 'DELETE'), "
                    "has_sequence_privilege(%s, 'future_runtime_records_id_seq', 'USAGE'), "
                    "has_function_privilege(%s, 'future_runtime_probe()', 'EXECUTE')",
                    (role_database.runtime_role,) * 6,
                )
                assert cursor.fetchone() == (False, False, False, False, False, False)
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

        parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
        raw = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            dbname=role_database.database_name,
            user=role_database.runtime_role,
            password=role_database.runtime_password,
        )
        try:
            with raw.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO future_runtime_records (payload) VALUES ('created') "
                    "RETURNING id"
                )
                record_id = cursor.fetchone()[0]
                cursor.execute(
                    "UPDATE future_runtime_records SET payload = 'updated' WHERE id = %s",
                    (record_id,),
                )
                cursor.execute(
                    "SELECT payload FROM future_runtime_records WHERE id = %s",
                    (record_id,),
                )
                assert cursor.fetchone() == ("updated",)
                cursor.execute(
                    "DELETE FROM future_runtime_records WHERE id = %s",
                    (record_id,),
                )
                with pytest.raises(psycopg2.Error):
                    cursor.execute("SELECT future_runtime_probe()")
            raw.rollback()
        finally:
            raw.close()
    finally:
        deploy_engine.dispose()


def test_role_bootstrap_after_guards_preserves_exact_runtime_acl(
    guarded_runtime_database,
):
    """Catches an idempotent bootstrap reopening protected transformation tables."""
    from scripts.database.configure_roles import configure_database_roles

    role_database = guarded_runtime_database
    configure_database_roles(
        admin_url=_maintenance_url(),
        database_names=(role_database.database_name,),
        deploy_password=role_database.deploy_password,
        runtime_password=role_database.runtime_password,
        deploy_role=role_database.deploy_role,
        runtime_role=role_database.runtime_role,
    )

    expected_table_acl = {
        "archie_command_capability_keys": (False, False, False, False, False),
        "command_idempotency_records": (True, False, False, False, False),
        "operation_results": (True, True, False, False, False),
        "transformation_outbox_events": (True, True, False, False, False),
        "evidence_records": (True, True, False, False, False),
        "evidence_claim_heads": (True, True, False, False, False),
        "evidence_head_events": (True, False, False, False, False),
        "decision_briefs": (True, False, False, False, False),
        "decision_brief_versions": (True, False, False, False, False),
        "decision_brief_option_citations": (True, False, False, False, False),
        "decision_brief_evidence_citations": (True, False, False, False, False),
    }
    maintenance = psycopg2.connect(
        _maintenance_url(), dbname=role_database.database_name
    )
    try:
        with maintenance.cursor() as cursor:
            for table_name, expected in expected_table_acl.items():
                cursor.execute(
                    "SELECT has_table_privilege(%s, %s, 'SELECT'), "
                    "has_table_privilege(%s, %s, 'INSERT'), "
                    "has_table_privilege(%s, %s, 'UPDATE'), "
                    "has_table_privilege(%s, %s, 'DELETE'), "
                    "has_table_privilege(%s, %s, 'TRUNCATE')",
                    (
                        role_database.runtime_role,
                        table_name,
                        role_database.runtime_role,
                        table_name,
                        role_database.runtime_role,
                        table_name,
                        role_database.runtime_role,
                        table_name,
                        role_database.runtime_role,
                        table_name,
                    ),
                )
                assert cursor.fetchone() == expected, table_name

            cursor.execute(
                "SELECT has_column_privilege(%s, 'command_idempotency_records', "
                "'status', 'UPDATE'), "
                "has_column_privilege(%s, 'command_idempotency_records', "
                "'idempotency_key', 'UPDATE'), "
                "has_column_privilege(%s, 'transformation_outbox_events', "
                "'delivery_attempts', 'UPDATE'), "
                "has_column_privilege(%s, 'transformation_outbox_events', "
                "'payload_json', 'UPDATE'), "
                "has_schema_privilege(%s, 'public', 'CREATE')",
                (role_database.runtime_role,) * 5,
            )
            assert cursor.fetchone() == (True, False, True, False, False)

            cursor.execute(
                "SELECT has_function_privilege(%s, "
                "'archie_claim_transformation_command(text,text)', 'EXECUTE'), "
                "has_function_privilege(%s, "
                "'archie_create_decision_brief(text,text,text)', 'EXECUTE'), "
                "has_function_privilege(%s, "
                "'archie_freeze_decision_brief_version(bigint,bigint,bigint,integer,text,text,text,integer,text,jsonb,text)', "
                "'EXECUTE'), "
                "has_function_privilege(%s, "
                "'archie_advance_evidence_head(bigint,bigint,integer,bigint,bigint,integer,text)', "
                "'EXECUTE'), "
                "has_function_privilege(%s, "
                "'archie_verify_command_capability(text,text,text)', 'EXECUTE'), "
                "has_function_privilege(%s, "
                "'archie_hmac_sha256(bytea,bytea)', 'EXECUTE')",
                (role_database.runtime_role,) * 6,
            )
            assert cursor.fetchone() == (True, True, True, True, False, False)
    finally:
        maintenance.close()


def test_role_bootstrap_failure_rolls_back_acl_and_keeps_runtime_fenced(
    guarded_runtime_database,
    monkeypatch,
):
    """Catches a mid-bootstrap failure committing a prefix of privilege changes."""
    import scripts.database.configure_roles as roles

    role_database = guarded_runtime_database
    deploy_engine = create_engine(
        role_database.url(
            role=role_database.deploy_role,
            password=role_database.deploy_password,
        )
    )
    try:
        with deploy_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE bootstrap_acl_probe "
                "(id serial PRIMARY KEY, payload text NOT NULL)"
            )
            connection.exec_driver_sql(
                f'REVOKE ALL ON TABLE bootstrap_acl_probe FROM "{role_database.runtime_role}"'
            )

        real_connect = psycopg2.connect
        raised = False

        def fail_after_probe_grant(statement):
            nonlocal raised
            normalized = " ".join(statement.upper().split())
            is_current_blanket_grant = " ON ALL TABLES IN SCHEMA PUBLIC " in (
                f" {normalized} "
            )
            is_explicit_probe_grant = (
                "GRANT " in normalized
                and "BOOTSTRAP_ACL_PROBE" in normalized
                and " ON TABLE " in f" {normalized} "
            )
            if not raised and (is_current_blanket_grant or is_explicit_probe_grant):
                raised = True
                raise RuntimeError("injected ACL finalization failure")

        def intercepted_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            if kwargs.get("dbname") == role_database.database_name:
                return _InterceptingConnection(connection, fail_after_probe_grant)
            return connection

        monkeypatch.setattr(roles.psycopg2, "connect", intercepted_connect)
        with pytest.raises(RuntimeError, match="injected ACL finalization failure"):
            roles.configure_database_roles(
                admin_url=_maintenance_url(),
                database_names=(role_database.database_name,),
                deploy_password=role_database.deploy_password,
                runtime_password=role_database.runtime_password,
                deploy_role=role_database.deploy_role,
                runtime_role=role_database.runtime_role,
            )
        assert raised

        maintenance = real_connect(
            _maintenance_url(), dbname=role_database.database_name
        )
        try:
            with maintenance.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege(%s, 'bootstrap_acl_probe', 'SELECT'), "
                    "has_table_privilege(%s, 'bootstrap_acl_probe', 'INSERT'), "
                    "has_table_privilege(%s, 'decision_briefs', 'INSERT'), "
                    "has_table_privilege(%s, 'archie_command_capability_keys', 'SELECT'), "
                    "(SELECT rolcanlogin FROM pg_roles WHERE rolname = %s)",
                    (role_database.runtime_role,) * 5,
                )
                assert cursor.fetchone() == (False, False, False, False, False)
        finally:
            maintenance.close()
    finally:
        deploy_engine.dispose()


def test_concurrent_runtime_cannot_observe_acl_bootstrap_intermediate_state(
    guarded_runtime_database,
):
    """Catches runtime attempts reading keys or forging drafts during ACL repair."""
    from scripts.database.configure_roles import configure_database_roles

    role_database = guarded_runtime_database
    parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
    bootstrap_finished = threading.Event()
    reader_ready = threading.Event()
    writer_ready = threading.Event()
    reader_finished = threading.Event()
    writer_finished = threading.Event()
    secret_read_succeeded = threading.Event()
    forged_write_committed = threading.Event()

    def connect_runtime():
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            dbname=role_database.database_name,
            user=role_database.runtime_role,
            password=role_database.runtime_password,
            connect_timeout=2,
        )

    def read_attacker():
        first_attempt = True
        while True:
            post_bootstrap_attempt = bootstrap_finished.is_set()
            connection = None
            try:
                connection = connect_runtime()
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '3s'")
                    cursor.execute(
                        "SELECT secret IS NOT NULL "
                        "FROM archie_command_capability_keys LIMIT 1"
                    )
                    if cursor.fetchone() == (True,):
                        secret_read_succeeded.set()
            except psycopg2.Error:
                pass
            finally:
                if connection is not None:
                    connection.close()
            if first_attempt:
                reader_ready.set()
                first_attempt = False
            if post_bootstrap_attempt:
                reader_finished.set()
                return

    def write_attacker():
        first_attempt = True
        while True:
            post_bootstrap_attempt = bootstrap_finished.is_set()
            connection = None
            try:
                connection = connect_runtime()
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '3s'")
                    cursor.execute(
                        "INSERT INTO decision_briefs "
                        "(organization_id, workstream_id, status, revision) "
                        "VALUES (91001, 92001, 'draft', 1)"
                    )
                connection.commit()
                forged_write_committed.set()
            except psycopg2.Error:
                if connection is not None:
                    try:
                        connection.rollback()
                    except psycopg2.Error:
                        pass
            finally:
                if connection is not None:
                    connection.close()
            if first_attempt:
                writer_ready.set()
                first_attempt = False
            if post_bootstrap_attempt:
                writer_finished.set()
                return

    reader = threading.Thread(target=read_attacker, daemon=True)
    writer = threading.Thread(target=write_attacker, daemon=True)
    reader.start()
    writer.start()
    assert reader_ready.wait(10)
    assert writer_ready.wait(10)

    configure_database_roles(
        admin_url=_maintenance_url(),
        database_names=(role_database.database_name,),
        deploy_password=role_database.deploy_password,
        runtime_password=role_database.runtime_password,
        deploy_role=role_database.deploy_role,
        runtime_role=role_database.runtime_role,
    )
    bootstrap_finished.set()
    assert reader_finished.wait(15)
    assert writer_finished.wait(15)
    reader.join(timeout=5)
    writer.join(timeout=5)

    assert secret_read_succeeded.is_set() is False
    assert forged_write_committed.is_set() is False

    maintenance = psycopg2.connect(
        _maintenance_url(), dbname=role_database.database_name
    )
    try:
        with maintenance.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM decision_briefs "
                "WHERE organization_id = 91001 AND workstream_id = 92001"
            )
            assert cursor.fetchone() == (0,)
    finally:
        maintenance.close()


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
                capability_secrets=(COMMAND_CAPABILITY_SECRET,),
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
                "has_table_privilege(%s, 'decision_briefs', 'INSERT'), "
                "has_table_privilege(%s, 'decision_brief_versions', 'INSERT'), "
                "has_table_privilege(%s, 'decision_brief_option_citations', 'INSERT'), "
                "has_table_privilege(%s, 'decision_brief_evidence_citations', 'INSERT'), "
                "has_function_privilege(%s, "
                "'public.archie_advance_evidence_head(bigint,bigint,integer,bigint,bigint,integer,text)', "
                "'EXECUTE'), "
                "has_function_privilege(%s, "
                "'public.archie_create_decision_brief(text,text,text)', 'EXECUTE')",
                (role_database.runtime_role,) * 8,
            )
            assert cursor.fetchone() == (
                True, False, False, False, False, False, True, True
            )
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
            assert sorted(cursor.fetchall()) == sorted([
                (
                    "archie_advance_evidence_head",
                    "p_head_id bigint, p_new_record_id bigint, "
                    "p_expected_revision integer, p_actor_id bigint, "
                    "p_receipt_id bigint, p_generation integer, p_claim_token text",
                ),
                (
                    "archie_claim_transformation_command",
                    "p_document text, p_capability text",
                ),
                (
                    "archie_create_decision_brief",
                    "p_capability_document text, p_capability text, "
                    "p_request_document text",
                ),
                (
                    "archie_freeze_decision_brief_version",
                    "p_brief_id bigint, p_actor_id bigint, "
                    "p_receipt_id bigint, p_generation integer, p_claim_token text, "
                    "p_capability_document text, p_capability text, "
                    "p_expected_revision integer, p_request_document text, "
                    "p_frozen_payload jsonb, p_canonical_document text",
                ),
            ])

            receipt_id = _claim_runtime_command(
                cursor,
                organization_id=41001,
                actor_id=42001,
                operation="runtime.probe",
                command_key="runtime-probe",
                request_digest="a" * 64,
                natural_key="runtime:probe",
                claim_token="b" * 64,
                request_id="runtime-request",
            )
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
