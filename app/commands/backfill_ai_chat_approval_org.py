"""Backfill tenant ownership for legacy AI chat approval requests.

``AIChatCRUDApproval.organization_id`` is nullable during rollout because
``reconcile-schema`` can only add columns. Its owner is nevertheless exact:
the requester is a User, and ``users.organization_id`` is the organisation
that raised the change. Rows whose requester no longer has an organisation are
left NULL and reported as an operational failure rather than guessed at.
"""

import click
from flask.cli import with_appcontext

from app import db
from app.commands.tenant_schema import ensure_organization_index_and_fk


TABLE = "ai_chat_crud_approvals"


def run_backfill(*, dry_run: bool = False):
    """Attribute NULL approval rows to their requester, safely and idempotently."""
    from sqlalchemy import inspect, text

    conn = db.session.connection()
    inspector = inspect(conn)
    if TABLE not in inspector.get_table_names():
        return {"backfilled": 0, "remaining_nulls": 0}
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if "organization_id" not in columns:
        raise RuntimeError(
            "ai_chat_crud_approvals.organization_id is absent; run reconcile-schema first"
        )

    if dry_run:
        backfilled = conn.execute(
            text(
                "SELECT count(*) FROM ai_chat_crud_approvals a "
                "JOIN users u ON u.id = a.user_id "
                "WHERE a.organization_id IS NULL AND u.organization_id IS NOT NULL"
            )
        ).scalar() or 0
    else:
        backfilled = conn.execute(
            text(
                "UPDATE ai_chat_crud_approvals AS a "
                "SET organization_id = u.organization_id "
                "FROM users AS u "
                "WHERE a.user_id = u.id "
                "AND a.organization_id IS NULL "
                "AND u.organization_id IS NOT NULL"
            )
        ).rowcount or 0
        ensure_organization_index_and_fk(conn, TABLE, strict=True)

    remaining = conn.execute(
        text("SELECT count(*) FROM ai_chat_crud_approvals WHERE organization_id IS NULL")
    ).scalar() or 0
    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return {"backfilled": backfilled, "remaining_nulls": remaining}


@click.command("backfill-ai-chat-approval-org")
@click.option("--dry-run", is_flag=True, help="Report attribution without changing rows.")
@with_appcontext
def backfill_ai_chat_approval_org(dry_run):
    """Derive AI approval organization_id from each requester user."""
    stats = run_backfill(dry_run=dry_run)
    click.echo(
        "ai_chat_crud_approvals: backfilled=%d remaining_nulls=%d%s"
        % (stats["backfilled"], stats["remaining_nulls"], " (dry-run)" if dry_run else "")
    )
    if stats["remaining_nulls"]:
        raise click.ClickException(
            "%d approval row(s) remain unattributed; requester user/org is missing"
            % stats["remaining_nulls"]
        )


def init_app(app):
    """Register the tenant backfill command with Flask."""
    app.cli.add_command(backfill_ai_chat_approval_org)
