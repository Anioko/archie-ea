"""
flask backfill-architect-role — make CRUD work for existing users.

New sign-ups get the "Architect" default role (see Role.insert_roles), which the
CRUD route guards `require_roles("admin", "architect")` accept. But users created
BEFORE that change sit on the old default "User" role and get 403 on
create/update/delete of their own data. This command ensures the roles exist and
promotes every account still on the plain "User" role to "Architect".

Safe and idempotent:
  - Never touches Administrator accounts.
  - Re-running is a no-op once everyone is migrated.

Usage:
    flask --app manage backfill-architect-role
    flask --app manage backfill-architect-role --dry-run
"""
import click
from flask.cli import with_appcontext

from app import db
from app.models.user import Role, User


@click.command("backfill-architect-role")
@click.option("--dry-run", is_flag=True, help="Report who would change without writing.")
@with_appcontext
def backfill_architect_role(dry_run):
    """Promote users on the legacy 'User' role to 'Architect' so CRUD works."""
    Role.insert_roles()  # ensure Architect (default) + User + Administrator exist

    user_role = Role.query.filter_by(name="User").first()
    architect_role = Role.query.filter_by(name="Architect").first()
    if architect_role is None:
        click.echo("ERROR: Architect role missing after insert_roles(); aborting.")
        raise SystemExit(1)
    if user_role is None:
        click.echo("No legacy 'User' role present — nothing to migrate.")
        return

    affected = User.query.filter(User.role_id == user_role.id).all()
    click.echo(f"backfill-architect-role: {len(affected)} user(s) on 'User' -> 'Architect'"
               + (" (dry-run)" if dry_run else ""))
    for u in affected:
        click.echo(f"  {'would promote' if dry_run else 'promoting'}: {u.email}")
        if not dry_run:
            u.role_id = architect_role.id
            db.session.add(u)
    if not dry_run:
        db.session.commit()
        click.echo("Done. Those users can now create/update/delete their own data.")


def init_app(app):
    """Register the backfill-architect-role CLI command."""
    app.cli.add_command(backfill_architect_role)
