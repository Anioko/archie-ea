"""Attribute existing review queue items to an organisation.

``ReviewQueueItem.organization_id`` is nullable because ``reconcile-schema`` can
only add nullable columns, so items created before the column existed have none.
The tenant filter compares with ``=``, so an item without an organisation is
listed for nobody until this command gives it one.

Each item is attributed by the first rule that applies:

1. The reviewed application. For the item types in ``APPLICATION_ITEM_TYPES``,
   ``item_id`` is an ``application_components.id`` and the item takes that
   application's organisation.
2. The reviewers. The organisation of the assigned reviewer and of the user who
   decided the item, when every one of those users belongs to the same
   organisation.

An item that neither rule resolves keeps a NULL organisation and stays hidden;
nothing is assigned to a guessed organisation and no row is deleted. Only rows
whose organisation is NULL are touched, so the command is safe to run again,
on an empty table, and after new items exist.

It also gives the column the index and foreign key the model declares, which
``reconcile-schema`` does not add.

    flask --app manage backfill-review-queue-org --dry-run
    flask --app manage backfill-review-queue-org

Run after reconcile-schema.
"""

import click
from flask.cli import with_appcontext

from app import db
from app.models.confidence_review import APPLICATION_ITEM_TYPES

TABLE = "review_queue_items"


# Rule 1: the organisation of the reviewed application.
_APPLICATION_SQL = (
    "UPDATE review_queue_items AS r "
    "SET organization_id = a.organization_id "
    "FROM application_components AS a "
    "WHERE r.item_type IN :types AND r.item_id = a.id "
    "AND r.organization_id IS NULL AND a.organization_id IS NOT NULL"
)

# Rule 2: the organisation shared by the assigned reviewer and the deciding user.
_REVIEWER_SQL = (
    "UPDATE review_queue_items AS r "
    "SET organization_id = d.organization_id "
    "FROM ( "
    "  SELECT q.id AS item_id, MIN(u.organization_id) AS organization_id "
    "  FROM review_queue_items AS q "
    "  JOIN users AS u ON u.id IN (q.assigned_to_id, q.reviewed_by_id) "
    "  WHERE q.organization_id IS NULL AND u.organization_id IS NOT NULL "
    "  GROUP BY q.id "
    "  HAVING COUNT(DISTINCT u.organization_id) = 1 "
    ") AS d "
    "WHERE r.id = d.item_id AND r.organization_id IS NULL"
)


def run_backfill(*, dry_run: bool = False):
    """Attribute NULL-organisation items, idempotently.

    Returns the number of items each rule attributed and the number left with no
    organisation. With ``dry_run`` the same statements run and are rolled back,
    so the counts are exactly what a real run would produce.
    """
    from sqlalchemy import bindparam, inspect, text

    inspector = inspect(db.engine)
    if TABLE not in inspector.get_table_names():
        return {"by_application": 0, "by_reviewer": 0, "remaining_nulls": 0}
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if "organization_id" not in columns:
        raise RuntimeError("review_queue_items.organization_id is absent; run reconcile-schema first")

    conn = db.session.connection()
    by_application = (
        conn.execute(
            text(_APPLICATION_SQL).bindparams(bindparam("types", expanding=True)),
            {"types": sorted(APPLICATION_ITEM_TYPES)},
        ).rowcount
        or 0
    )
    by_reviewer = conn.execute(text(_REVIEWER_SQL)).rowcount or 0
    remaining = (
        conn.execute(
            text("SELECT count(*) FROM review_queue_items WHERE organization_id IS NULL")
        ).scalar()
        or 0
    )

    if dry_run:
        db.session.rollback()
    else:
        _add_index_and_fk(conn)
        db.session.commit()
    return {
        "by_application": by_application,
        "by_reviewer": by_reviewer,
        "remaining_nulls": remaining,
    }


def _add_index_and_fk(conn):
    """Match the model metadata on databases where reconcile added only a column."""
    from sqlalchemy import text

    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_review_queue_items_organization_id "
            "ON review_queue_items (organization_id)"
        )
    )
    conn.execute(
        text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_constraint c "
            "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
            "WHERE c.conrelid = 'review_queue_items'::regclass AND c.contype = 'f' "
            "AND a.attname = 'organization_id') THEN "
            "ALTER TABLE review_queue_items "
            "ADD CONSTRAINT fk_review_queue_items_organization "
            "FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE; "
            "END IF; END $$"
        )
    )


@click.command("backfill-review-queue-org")
@click.option("--dry-run", is_flag=True, help="Report attribution without changing rows.")
@with_appcontext
def backfill_review_queue_org(dry_run):
    """Attribute existing review queue items to an organisation."""
    stats = run_backfill(dry_run=dry_run)
    click.echo(
        "review_queue_items: by_application=%d by_reviewer=%d remaining_nulls=%d%s"
        % (
            stats["by_application"],
            stats["by_reviewer"],
            stats["remaining_nulls"],
            " (dry-run)" if dry_run else "",
        )
    )


def init_app(app):
    """Register the review queue backfill command with Flask."""
    app.cli.add_command(backfill_review_queue_org)
