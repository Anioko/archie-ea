import click
from flask.cli import with_appcontext

from app.seed_data.seed_vendor_catalogue import seed_vendor_catalogue


@click.group()
def vendor_seed():
    """Vendor seeding commands."""
    pass


@vendor_seed.command("seed-flat")
@with_appcontext
def seed_flat_vendors():
    """Seed flat vendor dataset (DEV only)."""
    click.echo("Seeding flat vendor dataset...")
    seed_vendor_catalogue()
    click.echo("Done.")


def register_commands(app):
    app.cli.add_command(vendor_seed)
