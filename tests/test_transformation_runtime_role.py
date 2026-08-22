"""Deployment/runtime PostgreSQL role separation for transformation guards."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2
import pytest
import yaml
from sqlalchemy import text

from app import db
from app.models.transformation_db_guards import ensure_transformation_db_guards
from app.models.organization import Organization
from app.models.user import User


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_ROLE = "archie_deploy"
RUNTIME_ROLE = "archie_runtime"


def _environment(service: dict) -> dict[str, str]:
    environment = service.get("environment", {})
    if isinstance(environment, dict):
        return environment
    return dict(item.split("=", 1) for item in environment)


def _database_name() -> str:
    return urlsplit(os.environ["TEST_DATABASE_URL"]).path.lstrip("/")


def _maintenance_url() -> str:
    parsed = urlsplit(os.environ["TEST_DATABASE_URL"])
    return urlunsplit(parsed._replace(path="/postgres"))


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


def test_role_bootstrap_is_idempotent_and_runtime_cannot_bypass_guards(app, _schema):
    """Catches superuser/owner powers making database guards optional at runtime."""
    from scripts.database.configure_roles import configure_database_roles

    deploy_password = f"deploy-{uuid.uuid4().hex}"
    runtime_password = f"runtime-{uuid.uuid4().hex}"
    for _ in range(2):
        configure_database_roles(
            admin_url=_maintenance_url(),
            database_names=(_database_name(),),
            deploy_password=deploy_password,
            runtime_password=runtime_password,
        )

    with app.app_context():
        db.session.remove()
        with db.engine.begin() as connection:
            ensure_transformation_db_guards(connection)

        suffix = uuid.uuid4().hex[:12]
        organization = Organization(
            name=f"Runtime Role Org {suffix}", slug=f"runtime-role-{suffix}"
        )
        db.session.add(organization)
        db.session.flush()
        user = User(
            email=f"runtime-role-{suffix}@example.test",
            organization_id=organization.id,
            confirmed=True,
            enterprise_role="enterprise_architect",
        )
        db.session.add(user)
        db.session.commit()
        organization_id = organization.id
        user_id = user.id
        db.session.remove()

        raw = psycopg2.connect(
            os.environ["TEST_DATABASE_URL"].replace(
                "postgresql+psycopg2://", "postgresql://", 1
            ),
            user=RUNTIME_ROLE,
            password=runtime_password,
        )
        try:
            cursor = raw.cursor()
            cursor.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = %s",
                (RUNTIME_ROLE,),
            )
            assert cursor.fetchone() == (False, False, False, False, False)
            cursor.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication "
                "FROM pg_roles WHERE rolname = %s",
                (DEPLOY_ROLE,),
            )
            assert cursor.fetchone() == (False, False, False, False)
            cursor.execute(
                "SELECT tableowner FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename = 'operation_results'"
            )
            assert cursor.fetchone() == (DEPLOY_ROLE,)
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
                (RUNTIME_ROLE,) * 9,
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
                "SELECT count(*) "
                "FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' "
                "AND NOT EXISTS ("
                "SELECT 1 FROM pg_depend dependency "
                "WHERE dependency.classid = 'pg_proc'::regclass "
                "AND dependency.objid = p.oid AND dependency.deptype = 'e'"
                ") AND has_function_privilege(%s, p.oid, 'EXECUTE')",
                (RUNTIME_ROLE,),
            )
            assert cursor.fetchone() == (0,)

            cursor.execute(
                "INSERT INTO command_idempotency_records "
                "(organization_id, actor_id, operation, idempotency_key, "
                "request_digest, natural_key, status, lease_generation, "
                "claim_token, claimant_request_id, lease_expires_at, attempt_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'in_progress', 1, %s, %s, "
                "clock_timestamp() + interval '1 minute', 1) RETURNING id",
                (
                    organization_id,
                    user_id,
                    "runtime.probe",
                    f"runtime-{suffix}",
                    "a" * 64,
                    f"runtime:{suffix}",
                    "b" * 64,
                    f"runtime-request-{suffix}",
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
                    organization_id,
                    user_id,
                    "runtime.probe",
                    f"runtime:{suffix}",
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
                (result_id, receipt_id, organization_id, user_id),
            )
            cursor.execute(
                "INSERT INTO transformation_outbox_events "
                "(organization_id, operation_result_id, event_id, ordinal, "
                "event_type, payload_json) VALUES (%s, %s, %s, 0, %s, '{}')",
                (
                    organization_id,
                    result_id,
                    str(uuid.uuid4()),
                    "runtime.probe.created",
                ),
            )
            cursor.execute(
                "UPDATE transformation_outbox_events "
                "SET delivery_attempts = 1, published_at = clock_timestamp() "
                "WHERE operation_result_id = %s AND organization_id = %s",
                (result_id, organization_id),
            )
            raw.commit()

            forbidden = (
                "SET session_replication_role = replica",
                f"SET ROLE {DEPLOY_ROLE}",
                "ALTER TABLE public.operation_results DISABLE TRIGGER ALL",
                "DROP TRIGGER trg_transformation_result_immutable ON public.operation_results",
                "TRUNCATE TABLE public.operation_results",
                "UPDATE public.operation_results SET request_digest = request_digest",
                "DELETE FROM public.command_idempotency_records",
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
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    "SET LOCAL session_replication_role = replica"
                )
                for table_name in (
                    "transformation_outbox_events",
                    "operation_results",
                    "command_idempotency_records",
                    "users",
                ):
                    connection.execute(
                        text(
                            f'DELETE FROM "{table_name}" '
                            "WHERE organization_id = :organization_id"
                        ),
                        {"organization_id": organization_id},
                    )
                connection.execute(
                    text("DELETE FROM organizations WHERE id = :organization_id"),
                    {"organization_id": organization_id},
                )
