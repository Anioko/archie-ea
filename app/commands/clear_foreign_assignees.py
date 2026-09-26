"""``flask clear-foreign-assignees`` — null out stored assignee ids that name
another organisation's user.

``kanban_cards.assigned_to_id`` and ``solution_issues.assigned_to_id`` were
writable from a request with no organisation check before the tenant fence
went in (see the writers in ``adm_kanban_routes.py`` and
``solution_issue_service.py``). Every reader is now fenced, so a row still
holding a foreign id names nobody today — but the id itself is stale and
worth clearing rather than left in place.

One-off housekeeping command, not a scheduled job. Dry-run by default;
clears only with ``--apply``.
"""

import click

_TABLES = (
    ("kanban_cards", "assigned_to_id"),
    ("solution_issues", "assigned_to_id"),
)


def _foreign_assignee_counts(conn):
    from sqlalchemy import text

    counts = {}
    for table, column in _TABLES:
        counts[table] = conn.execute(
            text(
                f'SELECT count(*) FROM "{table}" t JOIN users u ON u.id = t."{column}" '
                f'WHERE t."{column}" IS NOT NULL '
                f'AND u.organization_id IS DISTINCT FROM t.organization_id'
            )
        ).scalar()
    return counts


def _clear_foreign_assignees(conn):
    """Null out assigned_to_id on every row whose stored id names a user of a
    different organisation. Returns nothing; call ``_foreign_assignee_counts``
    before and after to measure the effect."""
    from sqlalchemy import text

    for table, column in _TABLES:
        conn.execute(
            text(
                f'UPDATE "{table}" t SET "{column}" = NULL '
                f'FROM users u WHERE u.id = t."{column}" '
                f'AND u.organization_id IS DISTINCT FROM t.organization_id'
            )
        )


def init_app(app):
    @app.cli.command("clear-foreign-assignees")
    @click.option(
        "--apply",
        is_flag=True,
        default=False,
        help="Actually clear foreign assignee ids. Without this flag the command prints counts only.",
    )
    def clear_foreign_assignees(apply):
        """Null out assigned_to_id where it names a user of another organisation."""
        from app import db

        conn = db.session.connection()
        before = _foreign_assignee_counts(conn)
        for table, count in before.items():
            click.echo(f"{table}: {count} row(s) with a foreign assignee")

        if not apply:
            click.echo("Dry run — use --apply to clear.")
            return

        _clear_foreign_assignees(conn)
        db.session.commit()

        after = _foreign_assignee_counts(conn)
        for table, count in after.items():
            click.echo(f"{table}: {count} row(s) with a foreign assignee after clearing")
