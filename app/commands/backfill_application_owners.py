"""
flask backfill-application-owners — migrate legacy ownership into application_owners.

Migrates legacy ownership data into the application_owners table one
organisation at a time:

1. Rows from the application_ownership table (enterprise_intelligence.py).
2. Text business_owner / technical_owner columns on ApplicationComponent.

A text owner that matches no user in that organisation is written to a
per-organisation unresolved list and is never guessed.

Safe and idempotent:
  - Only creates rows that do not already exist.
  - Re-running is a no-op once everything is migrated.

Usage:
    flask --app manage backfill-application-owners
    flask --app manage backfill-application-owners --dry-run
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
      3. Case-insensitive match on first or last name alone

    Returns ``None`` when no single user matches.
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

    # First- or last-name match (only when it uniquely identifies one user)
    first_matches = (
        User.query.filter(User.organization_id == org_id)
        .filter(db.func.lower(User.first_name) == name_lower)
        .all()
    )
    if len(first_matches) == 1:
        return first_matches[0]

    last_matches = (
        User.query.filter(User.organization_id == org_id)
        .filter(db.func.lower(User.last_name) == name_lower)
        .all()
    )
    if len(last_matches) == 1:
        return last_matches[0]

    return None


def _record_unresolved(org_id: int, app_name: str, field: str, name: str, unresolved: List[Dict]) -> None:
    """Append an unresolved entry to the list."""
    unresolved.append({
        "organization_id": org_id,
        "application_name": app_name,
        "field": field,
        "name": name,
    })


def backfill_owner_data(dry_run: bool = False) -> Dict:
    """Run the full backfill, returning stats per organisation."""
    from app.models.application_owner import ApplicationOwner
    from app.models.application_portfolio import ApplicationComponent
    from app.models.enterprise_intelligence import ApplicationOwnership

    org_ids = [
        row[0]
        for row in db.session.query(ApplicationComponent.organization_id).distinct().all()
        if row[0] is not None
    ]

    total_legacy_ownership = 0
    total_text_owners = 0
    total_skipped = 0
    all_unresolved = {}

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
            new_type = type_map.get(legacy_type, "primary")
            # Check for existing row
            existing = ApplicationOwner.query.filter(
                ApplicationOwner.application_id == lo.application_id,
                ApplicationOwner.user_id.is_(None),  # no user FK on legacy table
                ApplicationOwner.ownership_type == new_type,
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

            if not dry_run:
                owner = ApplicationOwner(
                    application_id=lo.application_id,
                    organization_id=org_id,
                    ownership_type=new_type,
                )
                if user is not None:
                    owner.user_id = user.id
                db.session.add(owner)
            total_legacy_ownership += 1

        # ── 2. Migrate text owner columns ───────────────────────────
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

                # Check for existing ApplicationOwner row of this type
                existing = (
                    db.session.query(ApplicationOwner)
                    .join(ApplicationComponent, ApplicationOwner.application_id == ApplicationComponent.id)
                    .filter(
                        ApplicationOwner.application_id == app_obj.id,
                        ApplicationOwner.ownership_type == new_type,
                        ApplicationOwner.organization_id == org_id,
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

                if not dry_run:
                    owner = ApplicationOwner(
                        application_id=app_obj.id,
                        organization_id=org_id,
                        ownership_type=new_type,
                    )
                    if user is not None:
                        owner.user_id = user.id
                    db.session.add(owner)
                total_text_owners += 1

        if org_unresolved and not dry_run:
            db.session.flush()

        if unresolved:
            all_unresolved[str(org_id)] = unresolved
            click.echo(f"    unresolved: {len(unresolved)} text owner(s) matched no user")
            for u in unresolved:
                click.echo(f"      {u['application_name']}: {u['field']} = \"{u['name']}\"")

    if not dry_run:
        db.session.commit()

    # Write unresolved list as JSON
    if all_unresolved and not dry_run:
        try:
            import os
            path = "/home/ubuntu/verify/seats/rb03/backfill-unresolved.json"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(all_unresolved, f, indent=2)
            click.echo(f"\n  Unresolved list written to {path}")
        except Exception as e:
            click.echo(f"\n  Warning: could not write unresolved list: {e}")

    return {
        "legacy_ownership_rows": total_legacy_ownership,
        "text_owner_fields": total_text_owners,
        "skipped_existing": total_skipped,
        "organisations_processed": len(org_ids),
        "unresolved_orgs": len(all_unresolved),
    }


@click.command("backfill-application-owners")
@click.option("--dry-run", is_flag=True, help="Report what would change without writing.")
@with_appcontext
def backfill_application_owners_command(dry_run):
    """Migrate legacy ownership data into application_owners."""
    click.echo("backfill-application-owners:" + (" (dry-run)" if dry_run else ""))
    stats = backfill_owner_data(dry_run=dry_run)
    click.echo("\n  Results:")
    for key, value in stats.items():
        click.echo(f"    {key}: {value}")
    click.echo("Done.")


def init_app(app):
    """Register the backfill-application-owners CLI command."""
    app.cli.add_command(backfill_application_owners_command)