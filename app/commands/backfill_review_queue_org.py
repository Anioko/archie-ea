"""Report unowned review queue items and complete the tenant schema.

``ReviewQueueItem.organization_id`` is nullable because ``reconcile-schema`` can
only add nullable columns, so items created before the column existed have none.
The tenant filter compares with ``=``, so an item without an organisation is
listed for nobody until ownership is independently established.

Historical application and reviewer references describe an item's subject and
participants, but do not establish its originating organisation. All items
without an organisation remain unassigned until independent ownership evidence
is available. Matching references, including genuine-looking historical rows,
do not change that rule. Already-attributed rows are preserved.

The command reports the reference shapes for planning: reviewers and application
agree, reviewers only, application only, no evidence, reviewers disagree, or
application conflict. These are diagnostic categories, not attribution rules.
No queue row is changed or deleted. Dry runs also leave the schema untouched.

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

ATTRIBUTED = ()
LEFT_UNATTRIBUTED = (
    "reviewers_and_application", "reviewers", "application_only", "no_evidence",
    "reviewers_disagree", "application_conflict",
)

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


def classify(reviewer_orgs, reviewer_org, application_org):
    """Return the reference shape and no owner without independent evidence."""
    if reviewer_orgs > 1:
        return "reviewers_disagree", None
    if reviewer_orgs == 0:
        return ("application_only" if application_org is not None else "no_evidence"), None
    if application_org is None:
        return "reviewers", None
    if application_org == reviewer_org:
        return "reviewers_and_application", None
    return "application_conflict", None


def run_backfill(*, dry_run: bool = False):
    """Report unowned items and complete their tenant schema, idempotently.

    Returns how many items each outcome covers, how many items each organisation
    receives, and how many items have no organisation afterwards. With
    ``dry_run`` the same classification is made and nothing is written, so the
    counts are exactly what a real run produces.
    """
    from sqlalchemy import bindparam, inspect, text

    outcomes = {name: 0 for name in ATTRIBUTED + LEFT_UNATTRIBUTED}
    conn = db.session.connection()
    inspector = inspect(conn)
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

    rows = conn.execute(
        text(_CLASSIFY_SQL).bindparams(bindparam("types", expanding=True)),
        {"types": sorted(APPLICATION_ITEM_TYPES)},
    ).all()

    for _item_id, reviewer_orgs, reviewer_org, application_org in rows:
        outcome, _ = classify(reviewer_orgs, reviewer_org, application_org)
        outcomes[outcome] += 1

    if not dry_run:
        ensure_organization_index_and_fk(conn, TABLE, strict=True)

    total_nulls = conn.execute(
        text("SELECT count(*) FROM review_queue_items WHERE organization_id IS NULL")
    ).scalar() or 0

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return {
        "attributed": {name: outcomes[name] for name in ATTRIBUTED},
        "left": {name: outcomes[name] for name in LEFT_UNATTRIBUTED},
        "by_organisation": {},
        "examined": len(rows),
        "remaining_nulls": total_nulls,
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
        "  ownership withheld: legacy references do not establish the originating organisation",
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
    """Report unowned items and complete the review queue tenant schema."""
    for line in format_report(run_backfill(dry_run=dry_run), dry_run=dry_run):
        click.echo(line)


def init_app(app):
    """Register the review queue backfill command with Flask."""
    app.cli.add_command(backfill_review_queue_org)
