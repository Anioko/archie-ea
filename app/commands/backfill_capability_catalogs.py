"""Backfill the four remaining superseded capability stores into unified_capabilities.

ADR 0008 names `unified_capabilities` the one system of record for capabilities.
`flask project-capabilities` already projects the first and largest superseded
store, `business_capability`. This command retires the other four the same
ADR names for retirement (`docs/adr/0008-one-system-of-record.md`):
`capabilities` (the `Capability` model), `enterprise_capabilities`,
`archimate_capabilities` and `technical_capabilities`.

Design, in order of preference per row:

1. **A row that already stands for a projected `business_capability`.**
   `enterprise_capabilities` and `archimate_capabilities` both carry a
   `business_capability_id` column documented as "link to the single source of
   truth" (see the docstrings in app/models/capabilities.py). When it is set
   and the referenced `business_capability` has already been projected (it
   runs first in scripts/database/deploy-schema.sh), this row is not a new
   capability at all -- it is retired straight into that projection's own
   `unified_capabilities` row. No new row is ever created for it.
2. **A row identified by a real identifier.** `capabilities.archimate_id`,
   `archimate_capabilities.archimate_id` and `technical_capabilities.code`
   are each unique on their own table already. If an existing
   `unified_capabilities` row in the same scope (the same organisation for a
   tenant-owned row, the shared reference set otherwise) already carries that
   identifier, this row is retired into it (keep-oldest: whichever row was
   already there wins). Otherwise this row becomes the new canonical
   `unified_capabilities` row for that identifier.
3. **A row with no identifier and no resolvable link.** Matched by normalised
   name within the same scope, same keep-oldest rule. Otherwise it becomes
   canonical.

Organisation ownership, never guessed (settled design rule 3):

- `capabilities` (`Capability`) carries `TenantMixin` -- every row already has
  a real, NOT NULL `organization_id`. Projected as `scope='tenant'`.
- `enterprise_capabilities` / `archimate_capabilities` have no organisation
  column at all. A row linked to a projected `business_capability` inherits
  that capability's ownership by construction (step 1 above -- it is retired
  into that exact row, tenant or reference). A row with no such link, or whose
  link's target has not been projected yet, has no organisation this command
  can respect a tenant to be -- it is one of:
    - genuinely shared catalogue data (no `business_capability_id` at all --
      these tables are COBIT/ITIL/ArchiMate framework catalogues by design,
      never tenant business data, which is BusinessCapability's job per their
      own docstrings) -> `scope='reference'`;
    - unresolvable for now (`business_capability_id` set but that
      `business_capability` has not been projected yet) -> quarantined in
      `ErrorEvent` (reusing the platform-wide, admin-visible surface
      `backfill_review_queue_approvals.py` already established for exactly
      this job, at `/admin/errors`), and left for the next run.
- `technical_capabilities` has no organisation column and no per-row link to
  a business capability (only many-to-many mapping tables) -- it is a fixed
  7-domain ACM taxonomy, so every row is `scope='reference'`.

Idempotent: only rows with `retired_into_id IS NULL` on their own legacy table
are read; once resolved -- merged or newly canonical -- that column is set and
the row is never revisited. Re-running after every row is resolved writes
nothing. The command exits non-zero while any row remains neither merged nor
quarantined.

    flask backfill-capability-catalogs --dry-run
    flask backfill-capability-catalogs --apply
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import click
from flask.cli import with_appcontext
from sqlalchemy import text

from app import db

# Neighbours of project-capabilities' 1_684_220_027 and the cutover's
# 1_684_220_026 (app/commands/cutover_capability_tenancy.py) -- serialises
# this command against itself and refuses to interleave with either, since
# all three read and write unified_capabilities' scope/ownership columns.
ADVISORY_LOCK_ID = 1_684_220_028

_WHITESPACE_RE = re.compile(r"\s+")


class BackfillBlocked(RuntimeError):
    """Raised before this backfill can proceed safely (matches ProjectionBlocked
    and CutoverBlocked's role in the sibling commands)."""


def normalise_name(name: str) -> str:
    """The one place capability names are folded for identity comparison."""

    return _WHITESPACE_RE.sub(" ", (name or "").strip()).casefold()


@dataclass(frozen=True)
class _SourceRow:
    table: str
    id: int
    name: str
    description: Optional[str]
    level: int
    category: Optional[str]
    identifier: Optional[str]
    identifier_column: str  # "archimate_id" or "code" -- which unified column it matches
    business_capability_id: Optional[int]
    organization_id: Optional[int]  # only ever set for `capabilities`
    created_at: Optional[datetime]
    current_maturity_level: Optional[int] = None
    target_maturity_level: Optional[int] = None
    status: Optional[str] = None
    code_prefix: str = field(default="CAP")


def _fetch_capabilities(connection) -> list[_SourceRow]:
    rows = connection.execute(
        text(
            "SELECT id, name, description, level, archimate_id, "
            "organization_id, created_at "
            "FROM capabilities WHERE retired_into_id IS NULL ORDER BY created_at NULLS LAST, id"
        )
    ).mappings().all()
    return [
        _SourceRow(
            table="capabilities",
            id=row["id"],
            name=row["name"],
            description=row["description"],
            level=min(max(row["level"] or 1, 1), 3),
            category=None,
            identifier=row["archimate_id"],
            identifier_column="archimate_id",
            business_capability_id=None,
            organization_id=row["organization_id"],
            created_at=row["created_at"],
            code_prefix="CAP",
        )
        for row in rows
    ]


def _fetch_enterprise_capabilities(connection) -> list[_SourceRow]:
    rows = connection.execute(
        text(
            "SELECT id, name, description, category, maturity_level, status, "
            "business_capability_id, created_at "
            "FROM enterprise_capabilities WHERE retired_into_id IS NULL "
            "ORDER BY created_at NULLS LAST, id"
        )
    ).mappings().all()
    return [
        _SourceRow(
            table="enterprise_capabilities",
            id=row["id"],
            name=row["name"],
            description=row["description"],
            level=1,
            category=row["category"],
            identifier=None,
            identifier_column="archimate_id",
            business_capability_id=row["business_capability_id"],
            organization_id=None,
            created_at=row["created_at"],
            current_maturity_level=row["maturity_level"],
            status=row["status"],
            code_prefix="ENT",
        )
        for row in rows
    ]


def _fetch_archimate_capabilities(connection) -> list[_SourceRow]:
    rows = connection.execute(
        text(
            "SELECT id, name, description, archimate_id, current_maturity, "
            "target_maturity, business_capability_id "
            "FROM archimate_capabilities WHERE retired_into_id IS NULL ORDER BY id"
        )
    ).mappings().all()
    return [
        _SourceRow(
            table="archimate_capabilities",
            id=row["id"],
            name=row["name"],
            description=row["description"],
            level=1,
            category=None,
            identifier=row["archimate_id"],
            identifier_column="archimate_id",
            business_capability_id=row["business_capability_id"],
            organization_id=None,
            # This table has no created_at/updated_at column at all (verified
            # against app/models/capabilities.py); id order is the only
            # available "oldest first" proxy.
            created_at=None,
            current_maturity_level=row["current_maturity"],
            target_maturity_level=row["target_maturity"],
            code_prefix="ARC",
        )
        for row in rows
    ]


def _fetch_technical_capabilities(connection) -> list[_SourceRow]:
    rows = connection.execute(
        text(
            "SELECT id, name, description, code, created_at "
            "FROM technical_capabilities WHERE retired_into_id IS NULL "
            "ORDER BY created_at NULLS LAST, id"
        )
    ).mappings().all()
    return [
        _SourceRow(
            table="technical_capabilities",
            id=row["id"],
            name=row["name"],
            description=row["description"],
            level=1,
            category=None,
            identifier=row["code"],
            identifier_column="code",
            business_capability_id=None,
            organization_id=None,
            created_at=row["created_at"],
            code_prefix="TECH",
        )
        for row in rows
    ]


# Fixed processing order across tables: `capabilities` mirrors
# `business_capability` most directly (its own docstring calls it "the
# canonical ArchiMate strategy capability registry entry" and it is the only
# other tenant-owned store of the four), so it is treated as the
# next-most-authoritative after business_capability, which is always already
# projected. The remaining three are catalogue/framework tables with no
# organisation of their own; their relative order does not change which
# organisation anything belongs to, only which of two same-named *reference*
# rows would survive, which none of the production counts in ADR 0008 show
# ever colliding.
_FETCHERS = (
    _fetch_capabilities,
    _fetch_enterprise_capabilities,
    _fetch_archimate_capabilities,
    _fetch_technical_capabilities,
)

_RETIRE_SQL = {
    "capabilities": "UPDATE capabilities SET retired_into_id = :target WHERE id = :id",
    "enterprise_capabilities": (
        "UPDATE enterprise_capabilities SET retired_into_id = :target WHERE id = :id"
    ),
    "archimate_capabilities": (
        "UPDATE archimate_capabilities SET retired_into_id = :target WHERE id = :id"
    ),
    "technical_capabilities": (
        "UPDATE technical_capabilities SET retired_into_id = :target WHERE id = :id"
    ),
}


def _find_business_capability_projection(connection, business_capability_id: int):
    return connection.execute(
        text(
            "SELECT id FROM unified_capabilities "
            "WHERE source_table = 'business_capability' AND source_id = :source_id"
        ),
        {"source_id": str(business_capability_id)},
    ).scalar_one_or_none()


def _find_by_identifier(connection, *, column: str, value: str, organization_id):
    # tenancy-ok: the organisation predicate is explicit and part of the
    # match itself, not a scoping omission -- a tenant row and a reference
    # row are never allowed to satisfy the same lookup.
    if organization_id is not None:
        query = text(
            f"SELECT id FROM unified_capabilities "  # nosec B608 -- column is one of two module literals, never request input
            f"WHERE organization_id = :organization_id AND {column} = :value"
        )
        params = {"organization_id": organization_id, "value": value}
    else:
        query = text(
            f"SELECT id FROM unified_capabilities "  # nosec B608 -- column is one of two module literals, never request input
            f"WHERE organization_id IS NULL AND scope = 'reference' AND {column} = :value"
        )
        params = {"value": value}
    return connection.execute(query, params).scalar_one_or_none()


def _find_by_name(connection, *, normalised_name: str, organization_id):
    if organization_id is not None:
        query = text(
            "SELECT id, name FROM unified_capabilities "
            "WHERE organization_id = :organization_id"
        )
        params = {"organization_id": organization_id}
    else:
        query = text(
            "SELECT id, name FROM unified_capabilities "
            "WHERE organization_id IS NULL AND scope = 'reference'"
        )
        params = {}
    for candidate_id, candidate_name in connection.execute(query, params).all():
        if normalise_name(candidate_name) == normalised_name:
            return candidate_id
    return None


def _insert_canonical(connection, row: _SourceRow, *, scope: str, organization_id) -> int:
    code = row.identifier if row.identifier_column == "code" and row.identifier else None
    archimate_id = row.identifier if row.identifier_column == "archimate_id" and row.identifier else None
    if code is None and archimate_id is None:
        code = f"{row.code_prefix}-{row.id}"
    checksum = hashlib.md5(  # noqa: S324 -- drift fingerprint, not a security control (matches project_capabilities.py's own md5 use)
        "|".join(
            str(part) for part in (
                row.table, row.id, row.name, row.description or "",
                row.level, row.category or "", row.identifier or "",
            )
        ).encode("utf-8")
    ).hexdigest()
    new_id = connection.execute(
        text(
            "INSERT INTO unified_capabilities ("
            "name, description, code, level, scope, organization_id, "
            "source_table, source_id, source_org_id, source_checksum, "
            "specialization_type, category, current_maturity_level, "
            "target_maturity_level, status, discovery_source, archimate_id, "
            "created_at, updated_at"
            ") VALUES ("
            ":name, :description, :code, :level, :scope, :organization_id, "
            ":source_table, :source_id, :source_org_id, :source_checksum, "
            "'BUSINESS', :category, :current_maturity_level, "
            ":target_maturity_level, :status, :discovery_source, :archimate_id, "
            "COALESCE(:created_at, now()), now()"
            ") RETURNING id"
        ),
        {
            "name": row.name,
            "description": row.description,
            "code": code,
            "level": row.level,
            "scope": scope,
            "organization_id": organization_id,
            "source_table": row.table,
            "source_id": str(row.id),
            "source_org_id": organization_id,
            "source_checksum": checksum,
            "category": row.category,
            "current_maturity_level": row.current_maturity_level,
            "target_maturity_level": row.target_maturity_level,
            "status": row.status or "defined",
            "discovery_source": f"projection:{row.table}",
            "archimate_id": archimate_id,
            "created_at": row.created_at,
        },
    ).scalar_one()
    return new_id


def _record_quarantine(connection, row: _SourceRow) -> None:
    """Persist one row this run could not attribute an organisation to.

    Reuses ``ErrorEvent`` (app/models/error_event.py), the same
    platform-wide, nullable-organisation, dedup-by-fingerprint surface
    ``backfill_review_queue_approvals.py`` already reuses for identical
    reasoning -- one canonical "a backfill needs a human" surface
    (/admin/errors and its digest email) instead of a second one for this
    consolidation.
    """
    from app.models.error_event import ErrorEvent

    fingerprint = f"backfill-capability-catalogs:{row.table}:{row.id}"[:64]
    now = datetime.utcnow()
    existing = ErrorEvent.query.filter_by(fingerprint=fingerprint, resolved=False).first()
    if existing:
        existing.occurrence_count = (existing.occurrence_count or 0) + 1
        existing.last_seen_at = now
        return
    db.session.add(ErrorEvent(
        fingerprint=fingerprint,
        source="server",
        level="WARNING",
        message=(
            f"backfill-capability-catalogs: {row.table} #{row.id} links "
            f"business_capability #{row.business_capability_id}, which has not "
            "been projected into unified_capabilities yet. Run "
            "`flask project-capabilities --apply` first, then re-run this "
            "backfill."
        ),
        location=f"app.commands.backfill_capability_catalogs:{row.table}",
        organization_id=None,
        occurrence_count=1,
        first_seen_at=now,
        last_seen_at=now,
        resolved=False,
    ))


def _resolve_quarantine(row: _SourceRow) -> None:
    from app.models.error_event import ErrorEvent

    fingerprint = f"backfill-capability-catalogs:{row.table}:{row.id}"[:64]
    existing = ErrorEvent.query.filter_by(fingerprint=fingerprint, resolved=False).first()
    if existing:
        existing.resolved = True
        existing.resolved_at = datetime.utcnow()


def _process_row(connection, row: _SourceRow) -> str:
    """Resolve one source row. Returns 'merged', 'canonical' or 'quarantined'."""

    if row.organization_id is not None:
        scope, organization_id = "tenant", row.organization_id
    elif row.business_capability_id is not None:
        target = _find_business_capability_projection(connection, row.business_capability_id)
        if target is None:
            _record_quarantine(connection, row)
            return "quarantined"
        connection.execute(
            text(_RETIRE_SQL[row.table]), {"target": target, "id": row.id}
        )
        _resolve_quarantine(row)
        return "merged"
    else:
        scope, organization_id = "reference", None

    target = None
    if row.identifier:
        target = _find_by_identifier(
            connection, column=row.identifier_column, value=row.identifier,
            organization_id=organization_id,
        )
    if target is None:
        target = _find_by_name(
            connection, normalised_name=normalise_name(row.name),
            organization_id=organization_id,
        )

    if target is not None:
        connection.execute(
            text(_RETIRE_SQL[row.table]), {"target": target, "id": row.id}
        )
        return "merged"

    new_id = _insert_canonical(connection, row, scope=scope, organization_id=organization_id)
    connection.execute(
        text(_RETIRE_SQL[row.table]), {"target": new_id, "id": row.id}
    )
    return "canonical"


def _counts(connection) -> dict[str, int]:
    row = connection.execute(
        text(
            "SELECT "
            "(SELECT count(*) FROM capabilities) AS capabilities_total, "
            "(SELECT count(*) FROM capabilities WHERE retired_into_id IS NULL) AS capabilities_pending, "
            "(SELECT count(*) FROM enterprise_capabilities) AS enterprise_total, "
            "(SELECT count(*) FROM enterprise_capabilities WHERE retired_into_id IS NULL) AS enterprise_pending, "
            "(SELECT count(*) FROM archimate_capabilities) AS archimate_total, "
            "(SELECT count(*) FROM archimate_capabilities WHERE retired_into_id IS NULL) AS archimate_pending, "
            "(SELECT count(*) FROM technical_capabilities) AS technical_total, "
            "(SELECT count(*) FROM technical_capabilities WHERE retired_into_id IS NULL) AS technical_pending, "
            "(SELECT count(*) FROM unified_capabilities) AS unified_total"
        )
    ).mappings().one()
    return {key: int(value) for key, value in row.items()}


def run_backfill(connection, *, apply: bool) -> dict:
    """Measure, and optionally apply, the four-table capability backfill."""

    if not connection.execute(
        text("SELECT pg_try_advisory_xact_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_ID}
    ).scalar_one():
        raise BackfillBlocked(
            "another capability catalog backfill holds the advisory lock"
        )

    before = _counts(connection)
    report: dict[str, object] = {
        "mode": "apply" if apply else "dry-run",
        "before": before,
        "after": dict(before),
        "merged": 0,
        "canonical": 0,
        "quarantined": 0,
        "pending_before": sum(
            before[f"{name}_pending"]
            for name in ("capabilities", "enterprise", "archimate", "technical")
        ),
    }
    if not apply:
        return report

    outcomes = {"merged": 0, "canonical": 0, "quarantined": 0}
    for fetch in _FETCHERS:
        for row in fetch(connection):
            outcome = _process_row(connection, row)
            outcomes[outcome] += 1

    report["merged"] = outcomes["merged"]
    report["canonical"] = outcomes["canonical"]
    report["quarantined"] = outcomes["quarantined"]
    report["after"] = _counts(connection)
    report["unreconciled"] = sum(
        report["after"][f"{name}_pending"]
        for name in ("capabilities", "enterprise", "archimate", "technical")
    )
    return report


@click.command("backfill-capability-catalogs")
@click.option("--dry-run", is_flag=True, help="Measure without writing.")
@click.option("--apply", "apply_changes", is_flag=True, help="Apply the backfill.")
@with_appcontext
def backfill_capability_catalogs(dry_run, apply_changes):
    """Retire capabilities/enterprise_capabilities/archimate_capabilities/technical_capabilities into unified_capabilities."""

    if dry_run == apply_changes:
        raise click.UsageError("choose exactly one of --dry-run or --apply")

    connection = db.session.connection()
    try:
        report = run_backfill(connection, apply=apply_changes)
    except BackfillBlocked as exc:
        raise click.ClickException(str(exc)) from exc
    if apply_changes:
        db.session.commit()

    click.echo(
        f"{report['mode']}: before={report['before']}, "
        f"pending_before={report['pending_before']}"
    )
    if apply_changes:
        click.echo(
            f"merged={report['merged']} canonical={report['canonical']} "
            f"quarantined={report['quarantined']}"
        )
        click.echo(f"after={report['after']}")
        if report["unreconciled"]:
            raise click.ClickException(
                f"{report['unreconciled']} row(s) remain neither merged nor "
                "quarantined after this run; investigate before relying on "
                "unified_capabilities for these stores."
            )


def init_app(app):
    app.cli.add_command(backfill_capability_catalogs)
