"""Idempotently separate PostgreSQL deployment ownership from app runtime.

This script is deliberately standalone: a one-shot deployment container runs it
with the PostgreSQL bootstrap credential, while web and worker containers never
receive that credential or the schema-owner credential.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable

import psycopg2
from psycopg2 import sql


DEPLOY_ROLE = "archie_deploy"
RUNTIME_ROLE = "archie_runtime"


def _psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql://", 1)


def _ensure_login_role(cursor, *, role: str, password: str) -> None:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    if cursor.fetchone() is None:
        cursor.execute(
            sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role))
        )
    cursor.execute(
        sql.SQL(
            "ALTER ROLE {} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
        ).format(sql.Identifier(role)),
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


def _configure_database(
    *, admin_url: str, database_name: str, deploy_role: str, runtime_role: str
) -> None:
    with psycopg2.connect(_psycopg_url(admin_url), dbname=database_name) as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
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
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                    "IN SCHEMA public TO {}"
                ).format(sql.Identifier(runtime_role))
            )
            cursor.execute(
                sql.SQL(
                    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}"
                ).format(sql.Identifier(runtime_role))
            )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                ).format(
                    sql.Identifier(deploy_role), sql.Identifier(runtime_role)
                )
            )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT USAGE, SELECT ON SEQUENCES TO {}"
                ).format(
                    sql.Identifier(deploy_role), sql.Identifier(runtime_role)
                )
            )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
                ).format(sql.Identifier(deploy_role))
            )


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

    with psycopg2.connect(_psycopg_url(admin_url)) as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            _ensure_login_role(cursor, role=deploy_role, password=deploy_password)
            _ensure_login_role(cursor, role=runtime_role, password=runtime_password)
            _revoke_role_memberships(cursor, member_role=runtime_role)
            for database_name in names:
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
                )
                if cursor.fetchone() is None:
                    raise ValueError(f"target database does not exist: {database_name}")
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
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(database_name), sql.Identifier(runtime_role)
                    )
                )

    for database_name in names:
        _configure_database(
            admin_url=admin_url,
            database_name=database_name,
            deploy_role=deploy_role,
            runtime_role=runtime_role,
        )


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
