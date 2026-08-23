"""Idempotently separate PostgreSQL deployment ownership from app runtime.

This script is deliberately standalone: one-shot deployment containers run it
before and after schema deployment with the PostgreSQL bootstrap credential,
while web and worker containers never receive that credential or the schema-
owner credential.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable

import psycopg2
from psycopg2 import sql

from scripts.database.transformation_privilege_policy import (
    PROTECTED_RUNTIME_TABLE_PRIVILEGES,
    PROTECTED_RUNTIME_UPDATE_COLUMNS,
    RUNTIME_EXECUTE_FUNCTIONS,
    RUNTIME_NO_ACCESS_TABLES,
)


DEPLOY_ROLE = "archie_deploy"
RUNTIME_ROLE = "archie_runtime"


def _psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql://", 1)


def _ensure_role(
    cursor, *, role: str, password: str, can_login: bool
) -> None:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    if cursor.fetchone() is None:
        cursor.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(role)))
    login = sql.SQL("LOGIN") if can_login else sql.SQL("NOLOGIN")
    cursor.execute(
        sql.SQL(
            "ALTER ROLE {} WITH {} PASSWORD %s NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
        ).format(sql.Identifier(role), login),
        (password,),
    )


def _revoke_role_memberships(cursor, *, member_role: str) -> None:
    """Remove every SET ROLE path from the non-owner runtime identity."""
    cursor.execute(
        """
        SELECT granted.rolname
        FROM pg_auth_members membership
        JOIN pg_roles granted ON granted.oid = membership.roleid
        JOIN pg_roles member ON member.oid = membership.member
        WHERE member.rolname = %s
        ORDER BY granted.rolname
        """,
        (member_role,),
    )
    for (granted_role,) in cursor.fetchall():
        cursor.execute(
            sql.SQL("REVOKE {} FROM {}").format(
                sql.Identifier(granted_role),
                sql.Identifier(member_role),
            )
        )


def _transfer_public_objects(
    cursor, *, deploy_role: str, runtime_role: str
) -> None:
    cursor.execute(
        """
        SELECT c.relname, c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
          AND (
              c.relkind <> 'S'
              OR NOT EXISTS (
                  SELECT 1 FROM pg_depend ownership
                  WHERE ownership.classid = 'pg_class'::regclass
                    AND ownership.objid = c.oid
                    AND ownership.refclassid = 'pg_class'::regclass
                    AND ownership.deptype IN ('a', 'i')
              )
          )
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend dependency
              WHERE dependency.classid = 'pg_class'::regclass
                AND dependency.objid = c.oid
                AND dependency.deptype = 'e'
          )
        ORDER BY CASE WHEN c.relkind = 'S' THEN 2 ELSE 1 END, c.relkind, c.relname
        """
    )
    statements = {
        "r": "ALTER TABLE {}.{} OWNER TO {}",
        "p": "ALTER TABLE {}.{} OWNER TO {}",
        "v": "ALTER VIEW {}.{} OWNER TO {}",
        "m": "ALTER MATERIALIZED VIEW {}.{} OWNER TO {}",
        "S": "ALTER SEQUENCE {}.{} OWNER TO {}",
        "f": "ALTER FOREIGN TABLE {}.{} OWNER TO {}",
    }
    for name, kind in cursor.fetchall():
        cursor.execute(
            sql.SQL(statements[kind]).format(
                sql.Identifier("public"),
                sql.Identifier(name),
                sql.Identifier(deploy_role),
            )
        )

    cursor.execute(
        """
        SELECT p.proname, pg_get_function_identity_arguments(p.oid)
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend dependency
              WHERE dependency.classid = 'pg_proc'::regclass
                AND dependency.objid = p.oid
                AND dependency.deptype = 'e'
          )
        ORDER BY p.proname, p.oid
        """
    )
    for name, identity_arguments in cursor.fetchall():
        function = sql.SQL("{}.{}({})").format(
            sql.Identifier("public"),
            sql.Identifier(name),
            sql.SQL(identity_arguments),
        )
        cursor.execute(
            sql.SQL("ALTER FUNCTION {} OWNER TO {}").format(
                function, sql.Identifier(deploy_role)
            )
        )
        cursor.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON FUNCTION {} FROM PUBLIC").format(
                function
            )
        )
        cursor.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON FUNCTION {} FROM {}").format(
                function, sql.Identifier(runtime_role)
            )
        )


def _public_relations(cursor) -> tuple[tuple[str, str], ...]:
    cursor.execute(
        """
        SELECT relation.relname, relation.relkind
        FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend dependency
              WHERE dependency.classid = 'pg_class'::regclass
                AND dependency.objid = relation.oid
                AND dependency.deptype = 'e'
          )
        ORDER BY relation.relname
        """
    )
    return tuple(cursor.fetchall())


def _runtime_table_privileges(table_name: str, relation_kind: str) -> tuple[str, ...]:
    if table_name in RUNTIME_NO_ACCESS_TABLES:
        return ()
    protected = PROTECTED_RUNTIME_TABLE_PRIVILEGES.get(table_name)
    if protected is not None:
        return protected
    if relation_kind in {"r", "p", "f"}:
        return ("SELECT", "INSERT", "UPDATE", "DELETE")
    return ("SELECT",)


def _configure_table_privileges(cursor, *, runtime_role: str) -> None:
    runtime = sql.Identifier(runtime_role)
    for table_name, relation_kind in _public_relations(cursor):
        table = sql.SQL("{}.{}").format(
            sql.Identifier("public"), sql.Identifier(table_name)
        )
        cursor.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM PUBLIC").format(table)
        )
        cursor.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM {}").format(
                table, runtime
            )
        )
        privileges = _runtime_table_privileges(table_name, relation_kind)
        if privileges:
            cursor.execute(
                sql.SQL("GRANT {} ON TABLE {} TO {}").format(
                    sql.SQL(", ").join(map(sql.SQL, privileges)),
                    table,
                    runtime,
                )
            )
        update_columns = PROTECTED_RUNTIME_UPDATE_COLUMNS.get(table_name, ())
        if update_columns:
            cursor.execute(
                sql.SQL("GRANT UPDATE ({}) ON TABLE {} TO {}").format(
                    sql.SQL(", ").join(map(sql.Identifier, update_columns)),
                    table,
                    runtime,
                )
            )


def _public_sequences(cursor) -> tuple[tuple[str, str | None], ...]:
    cursor.execute(
        """
        SELECT DISTINCT sequence.relname, owned_table.relname
        FROM pg_class sequence
        JOIN pg_namespace namespace ON namespace.oid = sequence.relnamespace
        LEFT JOIN pg_depend ownership
          ON ownership.classid = 'pg_class'::regclass
         AND ownership.objid = sequence.oid
         AND ownership.refclassid = 'pg_class'::regclass
         AND ownership.deptype IN ('a', 'i')
        LEFT JOIN pg_class owned_table ON owned_table.oid = ownership.refobjid
        WHERE namespace.nspname = 'public'
          AND sequence.relkind = 'S'
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend dependency
              WHERE dependency.classid = 'pg_class'::regclass
                AND dependency.objid = sequence.oid
                AND dependency.deptype = 'e'
          )
        ORDER BY sequence.relname, owned_table.relname
        """
    )
    return tuple(cursor.fetchall())


def _configure_sequence_privileges(cursor, *, runtime_role: str) -> None:
    runtime = sql.Identifier(runtime_role)
    for sequence_name, owned_table_name in _public_sequences(cursor):
        sequence = sql.SQL("{}.{}").format(
            sql.Identifier("public"), sql.Identifier(sequence_name)
        )
        cursor.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON SEQUENCE {} FROM PUBLIC").format(
                sequence
            )
        )
        cursor.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON SEQUENCE {} FROM {}").format(
                sequence, runtime
            )
        )
        if owned_table_name is not None:
            privileges = _runtime_table_privileges(owned_table_name, "r")
            if "INSERT" not in privileges:
                continue
        cursor.execute(
            sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {} TO {}").format(
                sequence, runtime
            )
        )


def _configure_function_privileges(cursor, *, runtime_role: str) -> None:
    runtime = sql.Identifier(runtime_role)
    for function_name, identity_arguments in RUNTIME_EXECUTE_FUNCTIONS:
        cursor.execute(
            "SELECT to_regprocedure(%s)",
            (f"public.{function_name}({identity_arguments})",),
        )
        if cursor.fetchone()[0] is None:
            continue
        function = sql.SQL("{}.{}({})").format(
            sql.Identifier("public"),
            sql.Identifier(function_name),
            sql.SQL(identity_arguments),
        )
        cursor.execute(
            sql.SQL("GRANT EXECUTE ON FUNCTION {} TO {}").format(
                function, runtime
            )
        )


def _configure_default_privileges(
    cursor, *, deploy_role: str, runtime_role: str
) -> None:
    deploy = sql.Identifier(deploy_role)
    runtime = sql.Identifier(runtime_role)
    for object_type in ("TABLES", "SEQUENCES"):
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "REVOKE ALL PRIVILEGES ON {} FROM PUBLIC"
            ).format(deploy, sql.SQL(object_type))
        )
        cursor.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "REVOKE ALL PRIVILEGES ON {} FROM {}"
            ).format(deploy, sql.SQL(object_type), runtime)
        )
    cursor.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} "
            "REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC"
        ).format(deploy)
    )
    cursor.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} "
            "REVOKE ALL PRIVILEGES ON FUNCTIONS FROM {}"
        ).format(deploy, runtime)
    )


def _configure_database(
    *, admin_url: str, database_name: str, deploy_role: str, runtime_role: str
) -> None:
    with psycopg2.connect(_psycopg_url(admin_url), dbname=database_name) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"archie_runtime_acl:public:{runtime_role}",),
            )
            cursor.execute(
                sql.SQL("ALTER SCHEMA public OWNER TO {}").format(
                    sql.Identifier(deploy_role)
                )
            )
            _transfer_public_objects(
                cursor,
                deploy_role=deploy_role,
                runtime_role=runtime_role,
            )
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cursor.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(
                    sql.Identifier(runtime_role)
                )
            )
            cursor.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier(runtime_role)
                )
            )
            _configure_table_privileges(cursor, runtime_role=runtime_role)
            _configure_sequence_privileges(cursor, runtime_role=runtime_role)
            _configure_default_privileges(
                cursor,
                deploy_role=deploy_role,
                runtime_role=runtime_role,
            )
            _configure_function_privileges(cursor, runtime_role=runtime_role)


def configure_database_roles(
    *,
    admin_url: str,
    database_names: Iterable[str],
    deploy_password: str,
    runtime_password: str,
    deploy_role: str = DEPLOY_ROLE,
    runtime_role: str = RUNTIME_ROLE,
) -> None:
    """Create/refresh roles, ownership and least runtime privileges."""
    if not admin_url or not deploy_password or not runtime_password:
        raise ValueError("admin URL and both generated role passwords are required")
    names = tuple(dict.fromkeys(name.strip() for name in database_names if name.strip()))
    if not names:
        raise ValueError("at least one target database is required")

    coordinator = psycopg2.connect(_psycopg_url(admin_url))
    lock_key = f"archie_database_role_bootstrap:{deploy_role}:{runtime_role}"
    lock_acquired = False
    try:
        with coordinator.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(hashtext(%s))", (lock_key,))
            lock_acquired = True
        coordinator.commit()

        with coordinator.cursor() as cursor:
            for database_name in names:
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
                )
                if cursor.fetchone() is None:
                    raise ValueError(
                        f"target database does not exist: {database_name}"
                    )

            _ensure_role(
                cursor,
                role=deploy_role,
                password=deploy_password,
                can_login=True,
            )
            # Commit a cluster-visible fence before touching any database ACL.
            # Existing sessions are terminated immediately afterwards; a failed
            # bootstrap deliberately leaves runtime NOLOGIN rather than exposing
            # a partial or stale privilege state.
            _ensure_role(
                cursor,
                role=runtime_role,
                password=runtime_password,
                can_login=False,
            )
            _revoke_role_memberships(cursor, member_role=runtime_role)
            for database_name in names:
                cursor.execute(
                    sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                        sql.Identifier(database_name), sql.Identifier(deploy_role)
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(
                        sql.Identifier(database_name), sql.Identifier(runtime_role)
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(
                        sql.Identifier(database_name), sql.Identifier(runtime_role)
                    )
                )
        coordinator.commit()

        with coordinator.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE usename = %s "
                "AND datname = ANY(%s) "
                "AND pid <> pg_backend_pid()",
                (runtime_role, list(names)),
            )
            cursor.fetchall()
        coordinator.commit()

        for database_name in names:
            _configure_database(
                admin_url=admin_url,
                database_name=database_name,
                deploy_role=deploy_role,
                runtime_role=runtime_role,
            )

        with coordinator.cursor() as cursor:
            for database_name in names:
                cursor.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(database_name), sql.Identifier(runtime_role)
                    )
                )
            _ensure_role(
                cursor,
                role=runtime_role,
                password=runtime_password,
                can_login=True,
            )
        coordinator.commit()
    except BaseException:
        coordinator.rollback()
        raise
    finally:
        if lock_acquired:
            try:
                with coordinator.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_unlock(hashtext(%s))", (lock_key,)
                    )
                    cursor.fetchone()
                coordinator.commit()
            except psycopg2.Error:
                coordinator.rollback()
        coordinator.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--admin-url", default=os.environ.get("DATABASE_ADMIN_URL", "")
    )
    parser.add_argument(
        "--databases", default=os.environ.get("DATABASE_NAMES", "")
    )
    parser.add_argument(
        "--deploy-password", default=os.environ.get("DATABASE_DEPLOY_PASSWORD", "")
    )
    parser.add_argument(
        "--runtime-password", default=os.environ.get("DATABASE_RUNTIME_PASSWORD", "")
    )
    args = parser.parse_args()
    configure_database_roles(
        admin_url=args.admin_url,
        database_names=args.databases.split(","),
        deploy_password=args.deploy_password,
        runtime_password=args.runtime_password,
    )
    print("database roles configured")


if __name__ == "__main__":
    main()
