"""``flask purge-sessions`` -- housekeeping sweep for the session registry.

``user_sessions`` (app/models/user_session.py) gets a new row on every login
and is never deleted by the request path (revoke() only sets revoked_at), so
without this it grows without bound. Deleting an old row has no security
effect either way -- a missing row is already treated as inactive by
``session_registry.is_active`` -- this is cleanup only.
"""

import click


def init_app(app):
    @app.cli.command("purge-sessions")
    @click.option(
        "--older-than-days",
        default=30,
        type=int,
        help="Delete registry rows revoked (or, if never revoked, created) more than this many days ago.",
    )
    def purge_sessions(older_than_days):
        """Delete stale rows from the server-side session registry."""
        from datetime import datetime, timedelta

        from app.services import session_registry

        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        deleted = session_registry.purge_expired(cutoff)
        click.echo(f"Purged {deleted} session registry row(s) older than {older_than_days} day(s).")
