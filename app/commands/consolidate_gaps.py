"""
Gap register consolidation: merge-gap-stores.

The one gap register (`gaps`, app.models.implementation_migration.Gap) already
carries TenantMixin -- every row created through the register has an
organisation. Three other stores answer the same "gap" question with no
tenant column at all: `roadmap_gaps` (RoadmapGap), `implementation_gaps`
(ImplementationGap) and `compliance_gaps` (ComplianceGap). This module merges
all three into `gaps`, recording provenance (source_table/source_id) and
marking each merged source row with retired_into_id. It never drops a source
row or table (CLAUDE.md).

`capability_gap_analysis` and `capability_gap_details` are a different
concept -- maturity gaps, not planned architecture gaps -- and stay on
capability_heatmap_service.py under the capability-gap concept; they are
deliberately not merged here (r1-build-briefs-v1.md, R1-B05, MIG-R-0068/0069
excluded from wave 1).

Attribution rule per source, in this order, else quarantine (organization_id
left NULL -- the tenant filter's `=` comparison then matches no organisation,
visible to no tenant, never a guess):

    roadmap_gaps           source_application_id -> application_components,
                            else source_capability_id -> unified_capabilities
                            (source_org_id; NULL for a shared/enterprise
                            capability, so this often falls through),
                            else created_by -> users
    implementation_gaps    architecture_id -> architecture_models
    compliance_gaps        assigned_to_id -> users,
                            else identified_by_id -> users

Run:

    flask --app manage merge-gap-stores [--dry-run]

Idempotent: only ever touches a source row whose retired_into_id is still
NULL, and only inserts a Gap when no existing row already carries that
(source_table, source_id) pair (checked with NOT EXISTS -- reconcile-schema
is ADD-COLUMN-nullable-only, ADR 0002, so this is a code-level uniqueness
check, not a database constraint).
"""

import click
from flask.cli import with_appcontext
from sqlalchemy import text

from app import db


def _count(conn, sql, **params):
    return conn.execute(text(sql), params).scalar()


# Each entry describes one superseded store. `insert_sql` selects straight
# into the exact column list `gaps` needs (including the columns `gaps`
# requires but has no server_default for: name, context, auto_generated,
# created_at, updated_at -- a raw INSERT bypasses every Python-side ORM
# default, so each is supplied explicitly here). `org_joins` / `org_expr`
# resolve organization_id per the attribution rule above; COALESCE falls
# through to NULL (quarantine) when nothing matches.
_MERGE_SOURCES = (
    {
        "table": "roadmap_gaps",
        "org_joins": (
            "LEFT JOIN application_components ac ON ac.id = s.source_application_id "
            "LEFT JOIN unified_capabilities uc ON uc.id = s.source_capability_id "
            "LEFT JOIN users u ON u.id = s.created_by"
        ),
        "org_expr": "COALESCE(ac.organization_id, uc.source_org_id, u.organization_id)",
        "select": """
            LEFT(s.name, 255) AS name,
            COALESCE(s.description, '')
                || CASE WHEN s.impact_assessment IS NOT NULL
                        THEN E'\\n\\nImpact: ' || s.impact_assessment ELSE '' END
                AS description,
            LEFT(s.gap_type, 30) AS gap_type,
            s.risk_level AS severity,
            s.priority AS priority,
            CASE WHEN s.status = 'open' THEN 'identified' ELSE s.status END AS resolution_status,
            LEFT(s.current_state, 255) AS current_state_ref,
            LEFT(s.target_state, 255) AS target_state_ref,
            COALESCE(s.created_at, now()) AS created_at,
            COALESCE(s.updated_at, s.created_at, now()) AS updated_at
        """,
    },
    {
        "table": "implementation_gaps",
        "org_joins": "LEFT JOIN architecture_models am ON am.id = s.architecture_id",
        "org_expr": "am.organization_id",
        "select": """
            LEFT(s.name, 255) AS name,
            COALESCE(s.gap_description, s.description, '')
                || CASE WHEN s.impact_description IS NOT NULL
                        THEN E'\\n\\nImpact: ' || s.impact_description ELSE '' END
                || CASE WHEN s.business_impact IS NOT NULL
                        THEN E'\\n\\nBusiness impact: ' || s.business_impact ELSE '' END
                AS description,
            LEFT(s.gap_type, 30) AS gap_type,
            s.impact_level AS severity,
            s.priority AS priority,
            s.status AS resolution_status,
            LEFT(s.baseline_state, 255) AS current_state_ref,
            LEFT(s.target_state, 255) AS target_state_ref,
            COALESCE(s.created_at, now()) AS created_at,
            COALESCE(s.updated_at, s.created_at, now()) AS updated_at
        """,
    },
    {
        "table": "compliance_gaps",
        "org_joins": (
            "LEFT JOIN users ua ON ua.id = s.assigned_to_id "
            "LEFT JOIN users ui ON ui.id = s.identified_by_id"
        ),
        "org_expr": "COALESCE(ua.organization_id, ui.organization_id)",
        "select": """
            LEFT(s.title, 255) AS name,
            s.description AS description,
            LEFT(s.gap_type, 30) AS gap_type,
            s.risk_level AS severity,
            s.risk_level AS priority,
            CASE WHEN s.status = 'open' THEN 'identified' ELSE s.status END AS resolution_status,
            NULL AS current_state_ref,
            NULL AS target_state_ref,
            COALESCE(s.identified_at, now()) AS created_at,
            COALESCE(s.resolved_at, s.identified_at, now()) AS updated_at
        """,
    },
)

_TARGET_COLUMNS = (
    "name", "description", "gap_type", "severity", "priority", "resolution_status",
    "current_state_ref", "target_state_ref", "created_at", "updated_at",
    "context", "auto_generated", "gap_kind", "organization_id", "source_table", "source_id",
)


def _merge_one(conn, spec, dry_run):
    table = spec["table"]
    eligible = _count(conn, f'SELECT count(*) FROM "{table}" WHERE retired_into_id IS NULL')
    if not eligible:
        click.echo(f"  {table}: nothing to merge")
        return
    if dry_run:
        click.echo(f"  - {table}: would merge {eligible} row(s) into gaps")
        return

    select_columns = (
        spec["select"].strip().rstrip(",")
        + ", 'architecture', false, 'capability_shortfall', "
        + f"{spec['org_expr']}, '{table}', s.id"
    )
    sql = (
        "WITH inserted AS ("
        f"INSERT INTO gaps ({', '.join(_TARGET_COLUMNS)}) "
        f"SELECT {select_columns} "
        f'FROM "{table}" s {spec["org_joins"]} '
        "WHERE s.retired_into_id IS NULL "
        "AND NOT EXISTS ("
        "SELECT 1 FROM gaps g WHERE g.source_table = :source_table AND g.source_id = s.id"
        ") "
        "RETURNING id AS new_id, source_id AS old_id"
        ") "
        f'UPDATE "{table}" SET retired_into_id = inserted.new_id '
        f'FROM inserted WHERE "{table}".id = inserted.old_id'
    )
    conn.execute(text(sql), {"source_table": table})
    click.echo(f"  + {table}: merged {eligible} row(s), marked retired_into_id")


@click.command("merge-gap-stores")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def merge_gap_stores(dry_run):
    """Merge roadmap_gaps, implementation_gaps and compliance_gaps into gaps,
    recording provenance (source_table/source_id) and marking each merged
    source row with retired_into_id. Never drops a source row or table."""
    conn = db.session.connection()

    before = _count(conn, "SELECT count(*) FROM gaps")
    click.echo(f"gaps: {before} row(s) before merge")

    for spec in _MERGE_SOURCES:
        _merge_one(conn, spec, dry_run)

    if dry_run:
        click.echo("dry-run: no changes committed.")
        db.session.rollback()
        return

    after = _count(conn, "SELECT count(*) FROM gaps")
    quarantined = _count(conn, "SELECT count(*) FROM gaps WHERE organization_id IS NULL")
    db.session.commit()
    click.echo(
        f"merge-gap-stores: done. gaps: {before} -> {after} row(s), "
        f"{quarantined} quarantined (unattributable)."
    )


def init_app(app):
    """Register the gap consolidation CLI command."""
    app.cli.add_command(merge_gap_stores)
