"""
CLI Command for Vendor Seed Management

Commands:
    flask seed-vendors                  Load/seed vendors from vendors.yaml
    flask seed-vendors --dry-run        Validate without committing
    flask seed-vendors --rollback v1.0  Rollback vendors from version v1.0
    flask seed-vendors --status         Show current seed version counts
"""

import logging
from typing import Optional

import click
from flask import current_app
from flask.cli import with_appcontext

from app import db
from app.models.vendor.vendor_organization import VendorOrganization
from app.services.unified_vendor_seeder import UnifiedVendorSeeder

logger = logging.getLogger(__name__)


@click.command('seed-vendors')
@click.option('--dry-run', is_flag=True, help='Validate without committing changes')
@click.option('--rollback', type=str, help='Rollback vendors from specific version (e.g., v1.0)')
@click.option('--status', is_flag=True, help='Show current seed status')
@with_appcontext
def seed_vendors_command(dry_run: bool = False, rollback: Optional[str] = None, status: bool = False):
    """
    Vendor seed management command.
    
    Examples:
        flask seed-vendors                  # Normal seeding
        flask seed-vendors --dry-run        # Validate only
        flask seed-vendors --rollback v1.0  # Rollback from version
        flask seed-vendors --status         # Show statistics
    """
    try:
        if status:
            _show_seed_status()
        elif rollback:
            _perform_rollback(rollback)
        else:
            _perform_seeding(dry_run)
    
    except Exception as e:
        logger.error(f"Command failed: {e}", exc_info=True)
        click.echo(f"❌ Error: {e}", err=True)
        raise click.ClickException(str(e))


def _perform_seeding(dry_run: bool):
    """Execute vendor seeding."""
    click.echo("\n" + "="*70)
    click.echo("VENDOR SEED MANAGEMENT")
    click.echo("="*70)
    
    # Get preview of what will be seeded
    try:
        seeder = UnifiedVendorSeeder()
        seed_data = seeder.load_seed_data()
        vendors = seed_data.get('vendors', [])
        version = seed_data.get('seed_metadata', {}).get('version', 'unknown')
        
        click.echo(f"\nVersion: {version}")
        click.echo(f"Vendors to seed: {len(vendors)}")
        click.echo(f"\nVendors:")
        for idx, v in enumerate(vendors[:10], 1):
            click.echo(f"  {idx}. {v.get('name', 'Unknown')}")
        if len(vendors) > 10:
            click.echo(f"  ... and {len(vendors) - 10} more")
        
        # Require confirmation
        if not dry_run:
            if not click.confirm(
                "\n⚠️  This will UPDATE/CREATE vendors in the database. Continue?",
                default=False
            ):
                click.echo("Aborted.")
                return
        else:
            click.echo("\n⚠️  DRY RUN MODE - Changes will NOT be committed\n")
    
    except Exception as e:
        click.echo(f"\n❌ Error loading seed data: {e}", err=True)
        raise click.ClickException(str(e))
    
    # Perform seeding
    result = seeder.seed(dry_run=dry_run)
    
    # Output results
    click.echo(f"\n{result['message']}")
    
    stats = result.get('stats', {})
    click.echo(f"\nResults:")
    click.echo(f"  ✓ Created:  {stats.get('created', 0)} vendors")
    click.echo(f"  ✓ Updated:  {stats.get('updated', 0)} vendors")
    click.echo(f"  ⊘ Skipped:  {stats.get('skipped', 0)} vendors")
    click.echo(f"  ✗ Failed:   {stats.get('failed', 0)} vendors")
    
    errors = result.get('errors', [])
    if errors:
        click.echo(f"\nErrors:")
        for error in errors[:5]:
            click.echo(f"  - {error}")
        if len(errors) > 5:
            click.echo(f"  ... and {len(errors) - 5} more errors")
    
    click.echo("\n" + "="*70 + "\n")
    
    if not result['success']:
        raise click.ClickException("Seeding failed")


def _perform_rollback(version: str):
    """Execute rollback from specific version."""
    click.echo("\n" + "="*70)
    click.echo(f"ROLLBACK: Removing vendors from version {version}")
    click.echo("="*70 + "\n")
    
    # Confirm rollback
    click.confirm(
        f"⚠️  This will DELETE all vendors where seed_version == '{version}'. Continue?",
        default=False,
        abort=True
    )
    
    seeder = UnifiedVendorSeeder()
    result = seeder.rollback(version)
    
    click.echo(f"\n{result['message']}")
    
    stats = result.get('stats', {})
    click.echo(f"  Deleted: {stats.get('deleted', 0)} vendors")
    
    click.echo("\n" + "="*70 + "\n")
    
    if not result['success']:
        raise click.ClickException("Rollback failed")


def _show_seed_status():
    """Display current seed status."""
    click.echo("\n" + "="*70)
    click.echo("SEED STATUS")
    click.echo("="*70 + "\n")

    try:
        from sqlalchemy import func
        
        # Use GROUP BY to count vendors by seed version (single query, not N+1)
        results = db.session.query(
            VendorOrganization.seed_version,
            VendorOrganization.is_seed_data,
            func.count(VendorOrganization.id).label('count')
        ).filter(
            VendorOrganization.seed_version.isnot(None)
        ).group_by(
            VendorOrganization.seed_version,
            VendorOrganization.is_seed_data
        ).all()
        
        if not results:
            click.echo("No seeded vendors found in database.\n")
            return
        
        # Group results by version
        version_stats = {}
        for version, is_seed, count in results:
            if version not in version_stats:
                version_stats[version] = {'seed': 0, 'manual': 0}
            
            if is_seed:
                version_stats[version]['seed'] += count
            else:
                version_stats[version]['manual'] += count
        
        # Display stats
        click.echo("Vendors by Seed Version:")
        for version in sorted(version_stats.keys()):
            stats = version_stats[version]
            total = stats['seed'] + stats['manual']
            click.echo(
                f"  {version}: {total} vendors "
                f"({stats['seed']} from seed, {stats['manual']} manual)"
            )
        
        # Total count
        total_seeded = sum(stats['seed'] for stats in version_stats.values())
        total_manual = sum(stats['manual'] for stats in version_stats.values())
        click.echo(f"\n  TOTAL: {total_seeded + total_manual} vendors")
        click.echo(f"         ({total_seeded} from seed, {total_manual} manual)")
        
    except Exception as e:
        click.echo(f"Error retrieving status: {e}\n", err=True)
    
    click.echo("\n" + "="*70 + "\n")


def register_seed_commands(app):
    """Register seed management commands with Flask app."""
    app.cli.add_command(seed_vendors_command)
