"""
flask backfill-application-owners — migrate legacy ownership into application_owners.

Migrates legacy ownership data into the application_owners table one
organisation at a time:

1. Rows from the application_ownership table (enterprise_intelligence.py).
2. Text business_owner / technical_owner columns on ApplicationComponent.

A text owner that matches no user in that organisation is recorded in a
per-organisation unresolved list and is never guessed.

Safe and idempotent:
  - Only creates rows that do not already exist.
  - Re-running is a no-op once everything is migrated.
  - Provenance (source_table, source_id) is recorded on each created row.

Usage:
    flask --app manage backfill-application-owners
    flask --app manage backfill-application-owners --dry-run
    flask --app manage backfill-application-owners --org-ids 1,2
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

import click
from flask.cli import with_appcontext

from app import db

logger = logging.getLogger(__name__)


def _resolve_user_by_name(name: str, org_id: int) -> Optional[object]:
    """Find a user in *org_id* whose display name or email matches *name*.

    Tries, in order:
      1. Exact case-insensitive match on ``first_name || ' ' || last_name``
      2. Exact case-insensitive match on ``email``

    Returns ``None`` when no single user matches.  Does NOT match on
    first-name-only or last-name-only — the brief says "never guessed".
    """
    from app.models.user import User

    name_lower = name.strip().lower()

    # Full-name match
    users = (
        User.query.filter(User.organization_id == org_id)
        .filter(db.func.lower(db.func.concat(User.first_name, " ", User.last_name)) == name_lower)
        .all()
    )
    if len(users) == 1:
        return users[0]

    # Email match
    users = (
        User.query.filter(User.organization_id == org_id)
        .filter(db.func.lower(User.email) == name_lower)
        .all()
    )
    if len(users) == 1:
        return users[0]

    return None


def _record_unresolved(org_id: int, app_name: str, field: str, name: str, unresolved: List[Dict]) -> None:
    """Append an unresolved entry to the list."""
    unresolved.append({
        "organization_id": org_id,
        "application_name": app_name,
        "field": field,
        "name": name,
    })


def backfill_owner_data(dry_run: bool = False, organization_ids: Optional[List[int]] = None) -> Dict:
    """Run the full backfill, returning stats per organisation.

    When *organization_ids* is given, only those organisations are processed.
    Each organisation is processed in its own tenant context: set, commit,
    ``db.session.remove()``.
    """
    from app.models.application_owner import ApplicationOwner
    from app.models.application_portfolio import ApplicationComponent
    from app.models.enterprise_intelligence import ApplicationOwnership

    if organization_ids:
        org_ids = sorted(organization_ids)
    else:
        org_ids = [
            row[0]
            for row in db.session.query(ApplicationComponent.organization_id).distinct().all()
            if row[0] is not None
        ]

    total_legacy_ownership = 0
    total_text_owners = 0
    total_skipped = 0
    all_unresolved = {}
    total_merged = 0

    for org_id in sorted(org_ids):
        click.echo(f"\n  Organisation {org_id}:")
        unresolved: List[Dict] = []

        # ── 1. Migrate application_ownership rows ───────────────────
        legacy_rows = (
            db.session.query(ApplicationOwnership)
            .filter(ApplicationOwnership.organization_id == org_id)
            .all()
        )
        org_unresolved = False
        for lo in legacy_rows:
            # Map legacy ownership_type to the new vocabulary
            legacy_type = (lo.ownership_type or "").lower()
            type_map = {
                "business owner": "business",
                "product owner": "business",
                "technical owner": "technical",
                "budget holder": "business",
            }
            new_type = type_map.get(legacy_type)
            if new_type is None:
                # Unknown legacy type: go to unresolved list, never guessed
                app_obj_lo = db.session.get(ApplicationComponent, lo.application_id)
                app_name_lo = app_obj_lo.name if app_obj_lo else f"App #{lo.application_id}"
                _record_unresolved(org_id, app_name_lo, "application_ownership (unknown type)", lo.primary_contact or "(no name)", unresolved)
                org_unresolved = True
                continue

            # Check for existing row by provenance (source_table, source_id)
            existing = ApplicationOwner.query.filter(
                ApplicationOwner.application_id == lo.application_id,
                ApplicationOwner.source_table == "application_ownership",
                ApplicationOwner.source_id == lo.id,
                ApplicationOwner.organization_id == org_id,
            ).first()
            if existing:
                total_skipped += 1
                continue

            # Try to find a user from the contact info
            contact_name = lo.primary_contact or ""
            user = _resolve_user_by_name(contact_name, org_id) if contact_name else None

            if user is None and contact_name:
                app_obj = db.session.get(ApplicationComponent, lo.application_id)
                app_name = app_obj.name if app_obj else f"App #{lo.application_id}"
                _record_unresolved(org_id, app_name, "application_ownership", contact_name, unresolved)
                org_unresolved = True

            if not dry_run and user is not None:
                owner = ApplicationOwner(
                    application_id=lo.application_id,
                    user_id=user.id,
                    organization_id=org_id,
                    ownership_type=new_type,
                    source_table="application_ownership",
                    source_id=lo.id,
                )
                db.session.add(owner)
                total_legacy_ownership += 1

        # ── 2. Mark migrated application_ownership rows as retired ──
        if not dry_run and legacy_rows:
            migrated = ApplicationOwner.query.filter(
                ApplicationOwner.organization_id == org_id,
                ApplicationOwner.source_table == "application_ownership",
            ).all()
            for mo in migrated:
                legacy_row = db.session.get(ApplicationOwnership, mo.source_id)
                if legacy_row and not legacy_row.retired_into_id:
                    legacy_row.retired_into_id = mo.id
            total_merged += len(migrated)

        # ── 3. Migrate text owner columns ───────────────────────────
        apps = (
            db.session.query(ApplicationComponent)
            .filter(ApplicationComponent.organization_id == org_id)
            .all()
        )
        for app_obj in apps:
            for field_name, new_type in [("business_owner", "business"), ("technical_owner", "technical")]:
                name = getattr(app_obj, field_name, None)
                if not name or not name.strip():
                    continue

                # Check for existing ApplicationOwner row of this type with provenance
                existing = (
                    db.session.query(ApplicationOwner)
                    .filter(
                        ApplicationOwner.application_id == app_obj.id,
                        ApplicationOwner.ownership_type == new_type,
                        ApplicationOwner.organization_id == org_id,
                        ApplicationOwner.source_table == field_name,
                    )
                    .first()
                )
                if existing:
                    total_skipped += 1
                    continue

                user = _resolve_user_by_name(name, org_id)
                if user is None:
                    _record_unresolved(org_id, app_obj.name, field_name, name.strip(), unresolved)
                    org_unresolved = True

                if not dry_run and user is not None:
                    owner = ApplicationOwner(
                        application_id=app_obj.id,
                        user_id=user.id,
                        organization_id=org_id,
                        ownership_type=new_type,
                        source_table=field_name,
                        source_id=app_obj.id,
                    )
                    db.session.add(owner)
                    total_text_owners += 1

        if unresolved:
            all_unresolved[str(org_id)] = unresolved
            click.echo(f"    unresolved: {len(unresolved)} text owner(s) matched no user")
            for u in unresolved:
                click.echo(f"      {u['application_name']}: {u['field']} = \"{u['name']}\"")

        if not dry_run:
            db.session.commit()
            # Clear the session per organisation so tenant context is clean
            # for the next organisation, without detaching admin-scope objects.
            db.session.expire_all()

    # Print per-organisation unresolved list instead of writing to a hard-coded path
    if all_unresolved:
        click.echo("\n  Unresolved owners per organisation:")
        click.echo(json.dumps(all_unresolved, indent=2))

    return {
        "legacy_ownership_rows": total_legacy_ownership,
        "text_owner_fields": total_text_owners,
        "skipped_existing": total_skipped,
        "organisations_processed": len(org_ids),
        "unresolved_orgs": len(all_unresolved),
        "merged_legacy_rows": total_merged,
    }


@click.command("backfill-application-owners")
@click.option("--dry-run", is_flag=True, help="Report what would change without writing.")
@click.option("--org-ids", default=None, help="Comma-separated organisation IDs to process.")
@with_appcontext
def backfill_application_owners_command(dry_run, org_ids):
    """Migrate legacy ownership data into application_owners."""
    click.echo("backfill-application-owners:" + (" (dry-run)" if dry_run else ""))
    parsed_ids = [int(x.strip()) for x in org_ids.split(",")] if org_ids else None
    stats = backfill_owner_data(dry_run=dry_run, organization_ids=parsed_ids)
    click.echo("\n  Results:")
    for key, value in stats.items():
        click.echo(f"    {key}: {value}")
    click.echo("Done.")


def init_app(app):
    """Register the backfill-application-owners CLI command."""
    app.cli.add_command(backfill_application_owners_command)