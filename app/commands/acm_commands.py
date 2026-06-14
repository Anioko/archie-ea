"""
ACM (Application Capability Model) CLI Commands

Flask CLI commands for managing ACM technical capabilities:
- seed-acm: Seed the database with ACM capabilities
- acm-domains: List all ACM domains
- acm-stats: Show ACM capability statistics
- acm-gaps: Analyze capability gaps
"""

import click
from flask.cli import with_appcontext

from ..models.technical_capability import ACMDomain
from ..services.acm_technical_capability_service import ACMTechnicalCapabilityService


@click.group()
def acm():
    """Application Capability Model (ACM) commands."""
    pass


@acm.command("seed")
@with_appcontext
def seed_acm():
    """Seed the database with ACM technical capabilities."""
    click.echo("Seeding ACM technical capabilities...")

    result = ACMTechnicalCapabilityService.seed_capabilities()

    click.echo(f"\nACM Seed Results:")
    click.echo(f"  Created: {result['created']}")
    click.echo(f"  Updated: {result['updated']}")
    click.echo(f"  Total capabilities: {result['total']}")
    click.echo(f"  Domains: {result['domains']}")
    click.echo("\nACM capabilities seeded successfully!")


@acm.command("domains")
@with_appcontext
def list_domains():
    """List all ACM domains with descriptions."""
    domains = ACMTechnicalCapabilityService.get_domains()

    click.echo("\nACM Domains (7 Technical Capability Domains):")
    click.echo("-" * 80)

    for domain in domains:
        click.echo(f"\n{domain['code']}")
        click.echo(f"  {domain['description']}")


@acm.command("stats")
@with_appcontext
def show_stats():
    """Show ACM capability statistics."""
    summary = ACMTechnicalCapabilityService.get_domain_summary()

    click.echo("\nACM Capability Statistics:")
    click.echo("-" * 80)

    total = 0
    for domain, stats in summary.items():
        total += stats["total_capabilities"]
        click.echo(f"\n{domain}")
        click.echo(f"  Total: {stats['total_capabilities']}")
        click.echo(
            f"  By Level: L1={stats['by_level']['L1']}, L2={stats['by_level']['L2']}, L3={stats['by_level']['L3']}, L4={stats['by_level']['L4']}"
        )

    click.echo(f"\nTotal Capabilities: {total}")


@acm.command("gaps")
@click.option("--domain", "-d", default=None, help="Filter by ACM domain")
@with_appcontext
def analyze_gaps(domain):
    """Analyze technical capability gaps."""
    analysis = ACMTechnicalCapabilityService.analyze_capability_gaps(domain)

    click.echo("\nACM Capability Gap Analysis:")
    click.echo("-" * 80)

    click.echo(f"\nOverall Coverage: {analysis['coverage_percentage']}%")
    click.echo(f"  Total Capabilities: {analysis['total_capabilities']}")
    click.echo(f"  Covered: {analysis['covered']}")
    click.echo(f"  Uncovered: {analysis['uncovered']}")

    click.echo("\nBy Domain:")
    for domain_key, stats in analysis["by_domain"].items():
        click.echo(
            f"  {domain_key}: {stats['coverage_percentage']}% coverage ({stats['covered']}/{stats['total']})"
        )

    if analysis["uncovered_capabilities"][:10]:
        click.echo("\nTop Uncovered Capabilities:")
        for cap in analysis["uncovered_capabilities"][:10]:
            click.echo(f"  - [{cap['code']}] {cap['name']} ({cap['domain']})")


@acm.command("auto-map")
@click.option("--app-id", "-a", type=int, help="Application ID to auto-map")
@click.option("--all", "map_all", is_flag=True, help="Auto-map all applications")
@with_appcontext
def auto_map_apps(app_id, map_all):
    """Auto-map applications to ACM capabilities based on tech stack."""
    from ..models.application_portfolio import ApplicationComponent

    if app_id:
        result = ACMTechnicalCapabilityService.auto_map_application_capabilities(app_id)
        click.echo(f"\nAuto-mapped {result['application_name']}:")
        click.echo(f"  Suggested Domains: {', '.join(result['suggested_domains'])}")
        click.echo(f"  Mappings Created: {result['mappings_created']}")
    elif map_all:
        apps = ApplicationComponent.query.all()
        click.echo(f"\nAuto-mapping {len(apps)} applications...")

        total_mappings = 0
        for app in apps:
            result = ACMTechnicalCapabilityService.auto_map_application_capabilities(
                app.id, commit=False
            )
            total_mappings += result.get("mappings_created", 0)
            if result.get("suggested_domains"):
                click.echo(f"  [{app.id}] {app.name}: {', '.join(result['suggested_domains'])}")

        from .. import db

        db.session.commit()

        click.echo(f"\nTotal mappings created: {total_mappings}")
    else:
        click.echo("Please specify --app-id or --all")


def register_commands(app):
    """Register ACM CLI commands with Flask app."""
    app.cli.add_command(acm)
