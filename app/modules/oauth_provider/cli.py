"""``flask oauth prune-clients`` — delete registered clients that have never
completed a token exchange in the last 30 days.

A client with at least one successful exchange (``last_token_exchange_at``
set within the window) is kept regardless of how long ago it registered.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import click
from flask import current_app
from flask.cli import AppGroup

from app.extensions import db
from app.modules.oauth_provider.models import OAuthClient

oauth_cli = AppGroup("oauth", help="OAuth connector maintenance commands")


def _stale_client_query(days: int):
    cutoff = datetime.utcnow() - timedelta(days=days)
    return OAuthClient.query.filter(
        db.or_(
            OAuthClient.last_token_exchange_at.is_(None),
            OAuthClient.last_token_exchange_at < cutoff,
        ),
        OAuthClient.created_at < cutoff,
    )


@oauth_cli.command("prune-clients")
@click.option("--days", default=30, show_default=True, help="Idle window in days")
@click.option("--dry-run", is_flag=True, default=False, help="Print what would be deleted, delete nothing")
def prune_clients(days: int, dry_run: bool):
    """Delete clients with no successful token exchange in --days days."""
    before_count = OAuthClient.query.count()
    stale = _stale_client_query(days).all()

    click.echo(f"before: {before_count} registered clients")
    click.echo(f"stale (no exchange in {days}d): {len(stale)} clients")

    if dry_run:
        for client in stale:
            click.echo(f"  would delete: {client.client_id} ({client.client_name!r})")
        click.echo(f"after (dry-run, unchanged): {before_count} registered clients")
        return

    for client in stale:
        db.session.delete(client)
    db.session.commit()

    after_count = OAuthClient.query.count()
    click.echo(f"after: {after_count} registered clients")


def register_cli(app):
    app.cli.add_command(oauth_cli)
