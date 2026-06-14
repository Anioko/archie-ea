import click
from flask.cli import with_appcontext

from ..services.manufacturing_seed_service import ManufacturingSeedService


@click.group()
def manufacturing():
    """Manufacturing-related CLI commands."""
    pass


@manufacturing.command("seed")
@with_appcontext
@click.option(
    "--no-create-unified",
    is_flag=True,
    default=False,
    help="Do not create a unified capability if none found",
)
def seed_manufacturing(no_create_unified):
    """Seed a small sample ManufacturingCapability for local verification."""
    click.echo("Seeding manufacturing capability (sample)...")

    result = ManufacturingSeedService.seed_sample(create_unified_if_missing=not no_create_unified)

    click.echo("\nSeed Results:")
    click.echo(f"  Created unified capabilities: {result.get('created_unified', 0)}")
    click.echo(f"  Created manufacturing capabilities: {result.get('created_manufacturing', 0)}")
    click.echo(f"  Updated manufacturing capabilities: {result.get('updated_manufacturing', 0)}")
    click.echo(f"  Errors: {result.get('errors', 0)}")
    click.echo("\nDone.")


@manufacturing.command("seed-full")
@with_appcontext
def seed_manufacturing_full():
    """Seed full manufacturing taxonomy (two-pass)."""
    click.echo("Seeding manufacturing capability taxonomy (full)...")
    result = ManufacturingSeedService.seed_capabilities()
    click.echo("\nSeed Results:")
    click.echo(f"  Created: {result.get('created', 0)}")
    click.echo(f"  Updated: {result.get('updated', 0)}")
    click.echo(f"  Total: {result.get('total', 0)}")
    click.echo(f"  Errors: {result.get('errors', 0)}")
    click.echo("\nDone.")


def register_commands(app):
    app.cli.add_command(manufacturing)
