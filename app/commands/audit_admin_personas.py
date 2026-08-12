"""``flask audit-admin-personas`` — find accounts that are administrators by accident.

``User.enterprise_role`` is ``nullable=False`` with ``default=platform_admin``,
a backward-compatibility choice so accounts predating the persona system kept
full access. ``AdminUserService.invite_user`` never set the column, so **every
colleague an administrator invited was created as a platform administrator** of
the organisation. That is fixed — the invite form now requires the persona — but
the fix only governs new accounts. The ones already created that way are still
administrators, and no code change can decide which of them should be.

This makes that decision cheap and reversible instead of a database query
somebody has to write under pressure:

    flask --app manage audit-admin-personas
        list every platform_admin, with the signals that suggest whether the
        role was chosen or inherited — whether the admin flags are set, whether
        the account is the configured ADMIN_EMAIL, and when it was created

    flask --app manage audit-admin-personas --demote-invited --to business_architect
        move the accounts that look inherited — platform_admin persona, both
        admin flags false, not the configured admin — onto a named persona

Nothing is demoted without ``--demote-invited``, the configured ADMIN_EMAIL is
never touched, and an account whose ``is_platform_admin`` flag is set is never
touched either: somebody set that deliberately.
"""

from __future__ import annotations

import click
from flask.cli import with_appcontext

from app import db


def _candidates():
    """platform_admin accounts that show no sign of having been made one."""
    from flask import current_app

    from app.models.user import ROLE_PLATFORM_ADMIN, User

    configured = (current_app.config.get("ADMIN_EMAIL") or "").strip().lower()
    rows = User.query.filter_by(enterprise_role=ROLE_PLATFORM_ADMIN).all()

    inherited, deliberate = [], []
    for user in rows:
        email = (user.email or "").strip().lower()
        if email and email == configured:
            deliberate.append((user, "is the configured ADMIN_EMAIL"))
        elif getattr(user, "is_platform_admin", False) or getattr(user, "is_org_admin", False):
            deliberate.append((user, "an admin flag is set"))
        else:
            inherited.append(user)
    return inherited, deliberate


@click.command("audit-admin-personas")
@click.option("--demote-invited", is_flag=True,
              help="Actually change the accounts that look inherited.")
@click.option("--to", "target", default=None,
              help="The persona to move them to (required with --demote-invited).")
@with_appcontext
def audit_admin_personas(demote_invited, target):
    """Report — and optionally correct — accounts that are platform_admin by default."""
    from app.models.user import ROLE_DISPLAY_NAMES, VALID_ROLES

    inherited, deliberate = _candidates()

    click.echo(f"{len(inherited) + len(deliberate)} account(s) with the platform_admin persona\n")

    if deliberate:
        click.echo("  Deliberate — not touched:")
        for user, why in deliberate:
            click.echo(f"    {user.email:<44} {why}")
        click.echo("")

    if not inherited:
        click.echo("  No account looks like it inherited the persona. Nothing to do.")
        return

    click.echo("  Looks inherited — platform_admin, no admin flag, not the configured admin:")
    for user in inherited:
        created = getattr(user, "created_at", None)
        stamp = created.strftime("%Y-%m-%d") if created else "unknown"
        click.echo(f"    {user.email:<44} created {stamp}")

    if not demote_invited:
        click.echo(
            f"\n  {len(inherited)} account(s) would change. Re-run with "
            "--demote-invited --to <persona> to apply.\n"
            "  Personas: " + ", ".join(VALID_ROLES)
        )
        return

    if target not in VALID_ROLES:
        raise click.UsageError(
            f"--to must be one of: {', '.join(VALID_ROLES)}"
        )
    if target == "platform_admin":
        raise click.UsageError("--to platform_admin would change nothing")

    for user in inherited:
        user.enterprise_role = target
    db.session.commit()
    click.echo(
        f"\n  moved {len(inherited)} account(s) to "
        f"{ROLE_DISPLAY_NAMES.get(target, target)}."
    )


def init_app(app):
    """Register the audit-admin-personas CLI command."""
    app.cli.add_command(audit_admin_personas)
