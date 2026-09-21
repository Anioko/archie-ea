"""Attribute existing review queue items to an organisation.

``ReviewQueueItem.organization_id`` is nullable because ``reconcile-schema`` can
only add nullable columns, so items created before the column existed have none.
The tenant filter compares with ``=``, so an item without an organisation is
listed for nobody until this command gives it one.

An item is attributed from the users named on it: the assigned reviewer and the
user who decided it. It is never attributed from the application it is about.
``item_id`` is supplied by whoever queues the item, so it says which application
an item concerns, not who created it; here it is only used to check the users'
organisation against the application's.

The outcome for each item without an organisation:

* ``reviewers_and_application`` - the item is about an application, and every
  user named on it belongs to that application's organisation. The item takes it.
* ``reviewers`` - the item is not about a known application, and every user named
  on it belongs to one organisation. The item takes it.
* ``application_only`` - the item is about an application and names no user.
  Left without an organisation.
* ``no_evidence`` - names no user and is not about a known application. Left
  without an organisation.
* ``reviewers_disagree`` - the users named on it belong to different
  organisations. Left without an organisation.
* ``application_conflict`` - the users named on it belong to a different
  organisation than the application. Left without an organisation.

An item left without an organisation stays hidden from every organisation:
nothing is assigned to a guessed organisation and no row is deleted. Only rows
whose organisation is NULL are examined, so the command is safe to run again, on
an empty table, and after new items exist. ``--dry-run`` classifies the same rows
and prints where each outcome would land, changing nothing.

It also gives the column the index and foreign key the model declares, which
``reconcile-schema`` does not add.

    flask --app manage backfill-review-queue-org --dry-run
    flask --app manage backfill-review-queue-org

Run after reconcile-schema.
"""

import click
from flask.cli import with_appcontext

from app import db
from app.commands.tenant_schema import ensure_organization_index_and_fk
from app.models.confidence_review import APPLICATION_ITEM_TYPES

TABLE = "review_queue_items"

ATTRIBUTED = ("reviewers_and_application", "reviewers")
LEFT_UNATTRIBUTED = ("application_only", "no_evidence", "reviewers_disagree", "application_conflict")

DESCRIPTIONS = {
    "reviewers_and_application": "reviewers belong to the reviewed application's organisation",
    "reviewers": "reviewers in one organisation, no known application",
    "application_only": "reviewed application, no reviewer named",
    "no_evidence": "no reviewer named, no known application",
    "reviewers_disagree": "reviewers in different organisations",
    "application_conflict": "reviewers in a different organisation than the reviewed application",
}

# One row per item without an organisation: how many organisations its named
# users belong to, which one, and the organisation of the application it is about.
_CLASSIFY_SQL = (
    "SELECT q.id, "
    "COUNT(DISTINCT u.organization_id) AS reviewer_orgs, "
    "MIN(u.organization_id) AS reviewer_org, "
    "MIN(a.organization_id) AS application_org "
    "FROM review_queue_items AS q "
    "LEFT JOIN users AS u "
    "ON u.id IN (q.assigned_to_id, q.reviewed_by_id) AND u.organization_id IS NOT NULL "
    "LEFT JOIN application_components AS a "
    "ON a.id = q.item_id AND q.item_type IN :types AND a.organization_id IS NOT NULL "
    "WHERE q.organization_id IS NULL "
    "GROUP BY q.id"
)

_ATTRIBUTE_SQL = (
    "UPDATE review_queue_items SET organization_id = :org "
    "WHERE id = ANY(:ids) AND organization_id IS NULL"
)


def classify(reviewer_orgs, reviewer_org, application_org):
    """Return ``(outcome, organisation id or None)`` for one item."""
    if reviewer_orgs > 1:
        return "reviewers_disagree", None
    if reviewer_orgs == 0:
        return ("application_only" if application_org is not None else "no_evidence"), None
    if application_org is None:
        return "reviewers", reviewer_org
    if application_org == reviewer_org:
        return "reviewers_and_application", reviewer_org
    return "application_conflict", None


def run_backfill(*, dry_run: bool = False):
    """Attribute items that have no organisation, idempotently.

    Returns how many items each outcome covers, how many items each organisation
    receives, and how many items have no organisation afterwards. With
    ``dry_run`` the same classification is made and nothing is written, so the
    counts are exactly what a real run produces.
    """
    from sqlalchemy import bindparam, inspect, text

    outcomes = {name: 0 for name in ATTRIBUTED + LEFT_UNATTRIBUTED}
    inspector = inspect(db.engine)
    if TABLE not in inspector.get_table_names():
        return {
            "attributed": {name: 0 for name in ATTRIBUTED},
            "left": {name: 0 for name in LEFT_UNATTRIBUTED},
            "by_organisation": {},
            "examined": 0,
            "remaining_nulls": 0,
        }
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if "organization_id" not in columns:
        raise RuntimeError("review_queue_items.organization_id is absent; run reconcile-schema first")

    conn = db.session.connection()
    rows = conn.execute(
        text(_CLASSIFY_SQL).bindparams(bindparam("types", expanding=True)),
        {"types": sorted(APPLICATION_ITEM_TYPES)},
    ).all()

    targets = {}
    for item_id, reviewer_orgs, reviewer_org, application_org in rows:
        outcome, organisation = classify(reviewer_orgs, reviewer_org, application_org)
        outcomes[outcome] += 1
        if organisation is not None:
            targets.setdefault(organisation, []).append(item_id)

    if not dry_run:
        for organisation, item_ids in targets.items():
            conn.execute(text(_ATTRIBUTE_SQL), {"org": organisation, "ids": item_ids})
        ensure_organization_index_and_fk(conn, TABLE, strict=True)

    attributed = sum(outcomes[name] for name in ATTRIBUTED)
    total_nulls = conn.execute(
        text("SELECT count(*) FROM review_queue_items WHERE organization_id IS NULL")
    ).scalar() or 0
    # A dry run has written nothing, so the items it would attribute still count.
    remaining = total_nulls - attributed if dry_run else total_nulls

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return {
        "attributed": {name: outcomes[name] for name in ATTRIBUTED},
        "left": {name: outcomes[name] for name in LEFT_UNATTRIBUTED},
        "by_organisation": {organisation: len(ids) for organisation, ids in sorted(targets.items())},
        "examined": len(rows),
        "remaining_nulls": remaining,
    }


def format_report(stats, dry_run=False):
    """The lines the command prints: a summary, then each outcome and where items land."""
    attributed = sum(stats["attributed"].values())
    left = sum(stats["left"].values())
    suffix = " (dry-run)" if dry_run else ""
    lines = [
        "review_queue_items: attributed=%d left=%d remaining_nulls=%d%s"
        % (attributed, left, stats["remaining_nulls"], suffix),
        "  examined %d item(s) without an organisation" % stats["examined"],
        "  attributed: %d" % attributed,
    ]
    lines += ["    %-26s %d  %s" % (name, stats["attributed"][name], DESCRIPTIONS[name]) for name in ATTRIBUTED]
    lines.append("  left without an organisation, hidden from every organisation: %d" % left)
    lines += ["    %-26s %d  %s" % (name, stats["left"][name], DESCRIPTIONS[name]) for name in LEFT_UNATTRIBUTED]
    verb = "would attribute" if dry_run else "attributed"
    if stats["by_organisation"]:
        placed = ", ".join(
            "organisation %s: %d" % (organisation, count)
            for organisation, count in stats["by_organisation"].items()
        )
        lines.append("  %s to: %s" % (verb, placed))
    else:
        lines.append("  %s to no organisation" % verb)
    return lines


@click.command("backfill-review-queue-org")
@click.option("--dry-run", is_flag=True, help="Report where items would land without changing rows.")
@with_appcontext
def backfill_review_queue_org(dry_run):
    """Attribute existing review queue items to an organisation."""
    for line in format_report(run_backfill(dry_run=dry_run), dry_run=dry_run):
        click.echo(line)


def init_app(app):
    """Register the review queue backfill command with Flask."""
    app.cli.add_command(backfill_review_queue_org)
