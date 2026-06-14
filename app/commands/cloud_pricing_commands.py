"""Flask CLI commands for cloud pricing sync."""
import click
from flask.cli import with_appcontext


@click.group("cloud-pricing")
def cloud_pricing():
    """Cloud pricing API sync commands."""
    pass


@cloud_pricing.command("sync")
@click.option("--provider", required=True, type=click.Choice(["aws", "azure", "gcp"]),
              help="Cloud provider to sync")
@click.option("--service", default=None, help="Specific service code to sync (default: all)")
@click.option("--region", default="eu-west-1", help="Default region for pricing")
@with_appcontext
def sync_pricing(provider, service, region):
    """Sync cloud pricing from provider API."""
    click.echo(f"Syncing {provider} pricing (region: {region})...")

    if provider == "aws":
        from app.modules.vendors.connectors.aws_connector import AWSPricingConnector
        connector = AWSPricingConnector(default_region=region)
    else:
        click.echo(f"Provider '{provider}' connector not yet implemented.")
        return

    if not connector.health_check():
        click.echo(f"ERROR: {provider} API is unreachable. Aborting.")
        return

    result = connector.sync(service_filter=service)
    click.echo(f"Sync complete:")
    click.echo(f"  Services synced: {result.services_synced}")
    click.echo(f"  Pricing rows created: {result.pricing_rows_created}")
    click.echo(f"  Pricing rows updated: {result.pricing_rows_updated}")
    if result.errors:
        click.echo(f"  Errors: {len(result.errors)}")
        for err in result.errors[:5]:
            click.echo(f"    - {err}")


@cloud_pricing.command("health")
@click.option("--provider", required=True, type=click.Choice(["aws", "azure", "gcp"]))
@with_appcontext
def check_health(provider):
    """Check cloud pricing API connectivity."""
    if provider == "aws":
        from app.modules.vendors.connectors.aws_connector import AWSPricingConnector
        healthy = AWSPricingConnector().health_check()
    else:
        click.echo(f"Provider '{provider}' connector not yet implemented.")
        return

    status = "HEALTHY" if healthy else "UNHEALTHY"
    click.echo(f"{provider.upper()} pricing API: {status}")


def register_commands(app):
    """Register cloud pricing CLI commands with the Flask app."""
    app.cli.add_command(cloud_pricing)
