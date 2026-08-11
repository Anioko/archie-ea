"""``flask sync-roles`` — reseed the Role rows and their default flag.

``Role.insert_roles()`` is the single definition of which roles exist, what
permissions each carries, and which one ``User.__init__`` assigns to a new
account. It runs from ``setup-dev`` / ``setup-prod`` / ``create_admin.py`` and
**not** from ``init-db``, which is what the container actually boots with. So a
change to that definition never reached a database that already existed.

That mattered when the default moved off ``Architect``. Until this runs, an
upgraded deployment keeps handing every new account a role named for a job it
may not do — harmless now that ``require_roles`` ignores roles carrying no
permissions, but misleading in the admin UI and a hole waiting to reopen if
anyone reinstates name-based granting.

Idempotent, and safe to run on every boot: it writes only the three role
definitions and never touches a user's assignment.

    flask --app manage sync-roles
    flask --app manage sync-roles --dry-run

Replaces ``backfill-architect-role``, which promoted every plain-"User" account
to "Architect" so that ``require_roles("admin", "architect")`` would let them
edit their own data. That is now what the persona does.
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext

from app import db
from app.models.user import Role


@click.command("sync-roles")
@click.option("--dry-run", is_flag=True, help="Report what would change; change nothing.")
@with_appcontext
def sync_roles(dry_run):
    """Reseed the Role definitions, including which one is the default."""
    before = {
        role.name: (role.permissions, role.index, role.default)
        for role in Role.query.all()
    }

    if dry_run:
        # insert_roles() commits, so the dry run reports the intended state
        # rather than applying and rolling back — a rollback here would race a
        # concurrent boot doing the real thing.
        click.echo("current:")
        for name, (permissions, index, is_default) in sorted(before.items()):
            click.echo(
                f"    {name}: permissions={permissions} index={index!r} "
                f"default={is_default}"
            )
        click.echo("dry-run: no changes committed.")
        return

    Role.insert_roles()
    db.session.expire_all()

    after = {
        role.name: (role.permissions, role.index, role.default)
        for role in Role.query.all()
    }

    changed = False
    for name in sorted(set(before) | set(after)):
        if before.get(name) != after.get(name):
            changed = True
            click.echo(f"  + {name}: {before.get(name)} -> {after.get(name)}")
    if not changed:
        click.echo("  roles already match their definition")

    default_role = Role.query.filter_by(default=True).first()
    click.echo(
        f"sync-roles: done. Default role for new accounts is "
        f"{default_role.name if default_role else 'NONE — new users get no role'}."
    )


def init_app(app):
    """Register the sync-roles CLI command."""
    app.cli.add_command(sync_roles)
