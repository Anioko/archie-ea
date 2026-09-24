"""Attribute pre-existing review_queue_items rows to an organisation.

`ReviewQueueItem` gained `TenantMixin`, so `do_orm_execute` now filters every
read by `organization_id`. Rows written before that have it NULL and are
therefore invisible to every tenant — live review queues would empty on deploy.

The attribution is determinable rather than guessed. Each item references
several rows that carry an organisation:

1. ``assigned_to_id`` → ``users.organization_id`` (most direct — the reviewer
   assigned to the item belongs to the organisation that owns it)
2. ``reviewed_by_id`` → ``users.organization_id`` (the person who reviewed it)
3. ``escalated_to_id`` → ``users.organization_id`` (the escalation target)

``threshold_id`` points at ``confidence_thresholds``, which has no organisation
column. ``item_type`` / ``item_id`` is a polymorphic reference with no FK, so
it cannot be joined deterministically.

Idempotent (only touches NULLs) and non-destructive. A row whose user FKs are
all NULL, or whose referenced users have no organisation, is left NULL and
reported — inventing an owner would be worse than leaving it unattributed.

    flask --app manage backfill-review-queue-org --dry-run
    flask --app manage backfill-review-queue-org
"""
import click
from flask.cli import with_appcontext


def init_app(app):
    app.cli.add_command(backfill_review_queue_org)


@click.command("backfill-review-queue-org")
@click.option("--dry-run", is_flag=True, help="Report what would change, write nothing.")
@with_appcontext
def backfill_review_queue_org(dry_run):
    """Set organization_id on review_queue_items rows that have none."""
    from app.extensions import db

    total = db.session.execute(
        db.text("SELECT COUNT(*) FROM review_queue_items")
    ).scalar() or 0
    orphaned = db.session.execute(
        db.text("SELECT COUNT(*) FROM review_queue_items WHERE organization_id IS NULL")
    ).scalar() or 0

    if orphaned == 0:
        click.echo(f"review_queue_items: {total} row(s), none unattributed — nothing to do.")
        return

    # Count resolvable rows in each preference tier.
    r1 = db.session.execute(
        db.text(
            "SELECT COUNT(*) FROM review_queue_items r "
            "JOIN users u ON u.id = r.assigned_to_id "
            "WHERE r.organization_id IS NULL AND u.organization_id IS NOT NULL"
        )
    ).scalar() or 0

    r2 = db.session.execute(
        db.text(
            "SELECT COUNT(*) FROM review_queue_items r "
            "JOIN users u ON u.id = r.reviewed_by_id "
            "WHERE r.organization_id IS NULL "
            "AND r.assigned_to_id IS NULL "
            "AND u.organization_id IS NOT NULL"
        )
    ).scalar() or 0

    r3 = db.session.execute(
        db.text(
            "SELECT COUNT(*) FROM review_queue_items r "
            "JOIN users u ON u.id = r.escalated_to_id "
            "WHERE r.organization_id IS NULL "
            "AND r.assigned_to_id IS NULL "
            "AND r.reviewed_by_id IS NULL "
            "AND u.organization_id IS NOT NULL"
        )
    ).scalar() or 0

    resolvable = r1 + r2 + r3
    unresolvable = orphaned - resolvable

    click.echo(f"review_queue_items: {total} row(s), {orphaned} unattributed.")
    click.echo(f"  resolvable via assigned_to_id: {r1}")
    click.echo(f"  resolvable via reviewed_by_id:  {r2}")
    click.echo(f"  resolvable via escalated_to_id: {r3}")
    if unresolvable:
        click.echo(
            f"  NOT resolvable (no user FK or user has no org): {unresolvable} — left NULL"
        )

    if dry_run:
        click.echo("dry run — nothing written.")
        return

    updated = 0

    # Tier 1: assigned_to_id → users.organization_id
    result = db.session.execute(
        db.text(
            "UPDATE review_queue_items r SET organization_id = u.organization_id "
            "FROM users u "
            "WHERE u.id = r.assigned_to_id "
            "AND r.organization_id IS NULL "
            "AND u.organization_id IS NOT NULL"
        )
    )
    updated += result.rowcount

    # Tier 2: reviewed_by_id → users.organization_id (only rows still NULL)
    result = db.session.execute(
        db.text(
            "UPDATE review_queue_items r SET organization_id = u.organization_id "
            "FROM users u "
            "WHERE u.id = r.reviewed_by_id "
            "AND r.organization_id IS NULL "
            "AND u.organization_id IS NOT NULL"
        )
    )
    updated += result.rowcount

    # Tier 3: escalated_to_id → users.organization_id (only rows still NULL)
    result = db.session.execute(
        db.text(
            "UPDATE review_queue_items r SET organization_id = u.organization_id "
            "FROM users u "
            "WHERE u.id = r.escalated_to_id "
            "AND r.organization_id IS NULL "
            "AND u.organization_id IS NOT NULL"
        )
    )
    updated += result.rowcount

    db.session.commit()
    click.echo(f"attributed {updated} row(s).")