"""
CLI Commands for Seed Data Operations

Provides command-line interface for seeding curated data.
Integrates with Flask CLI system for easy execution.
"""

import click
from flask.cli import with_appcontext

from app.services.data_enrichment_service import DataEnrichmentService
from app.services.unified_seed_orchestrator import UnifiedSeedOrchestrator


@click.group("seed")
def seed_cli():
    """Seed data management commands."""
    pass


@click.group("seed")
def seed_cli():
    """Seed data management commands."""
    pass


@seed_cli.command("all")
@click.option(
    "--skip-errors", is_flag=True, help="Continue seeding even if individual seeders fail"
)
@with_appcontext
def seed_all(skip_errors):
    """Seed all curated data in dependency order."""
    click.echo("🌱 Starting comprehensive seed data orchestration...")

    orchestrator = UnifiedSeedOrchestrator()
    result = orchestrator.seed_all(skip_errors=skip_errors)

    if result["success"]:
        click.echo("✅ Seed orchestration completed successfully!")
        summary = result["data"]["summary"]
        click.echo(
            f"📊 Summary: {summary['successful_seeders']}/{summary['total_seeders']} seeders successful"
        )
        click.echo(
            f"📈 Records: {summary['total_records_created']} created, {summary['total_records_updated']} updated"
        )
        click.echo(".2f")
    else:
        click.echo("❌ Seed orchestration completed with errors!")
        click.echo(f"Error: {result['message']}")

    return result


@seed_cli.command("vendor-orgs")
@with_appcontext
def seed_vendor_organizations():
    """Seed vendor organization data."""
    click.echo("🏢 Seeding vendor organizations...")

    orchestrator = UnifiedSeedOrchestrator()
    result = orchestrator.seed_specific(["vendor_organizations"])

    if result["success"]:
        click.echo("✅ Vendor organizations seeded successfully!")
        data = result["data"]["results"]["vendor_organizations"]["data"]
        click.echo(f"📊 Records: {data['created']} created, {data['updated']} updated")
    else:
        click.echo("❌ Vendor organization seeding failed!")
        click.echo(f"Error: {result['data']['results']['vendor_organizations']['message']}")

    return result


@seed_cli.command("vendor-products")
@with_appcontext
def seed_vendor_products():
    """Seed vendor product data."""
    click.echo("📦 Seeding vendor products...")

    orchestrator = UnifiedSeedOrchestrator()
    result = orchestrator.seed_specific(["vendor_products"])

    if result["success"]:
        click.echo("✅ Vendor products seeded successfully!")
        data = result["data"]["results"]["vendor_products"]["data"]
        click.echo(f"📊 Records: {data['created']} created, {data['updated']} updated")
    else:
        click.echo("❌ Vendor product seeding failed!")
        click.echo(f"Error: {result['data']['results']['vendor_products']['message']}")

    return result


@seed_cli.command("business-capabilities")
@with_appcontext
def seed_business_capabilities():
    """Seed business capability data."""
    click.echo("🎯 Seeding business capabilities...")

    orchestrator = UnifiedSeedOrchestrator()
    result = orchestrator.seed_specific(["business_capabilities"])

    if result["success"]:
        click.echo("✅ Business capabilities seeded successfully!")
        data = result["data"]["results"]["business_capabilities"]["data"]
        click.echo(f"📊 Records: {data['created']} created, {data['updated']} updated")
    else:
        click.echo("❌ Business capability seeding failed!")
        click.echo(f"Error: {result['data']['results']['business_capabilities']['message']}")

    return result


@seed_cli.command("technical-capabilities")
@with_appcontext
def seed_technical_capabilities():
    """Seed technical capability data."""
    click.echo("⚙️ Seeding technical capabilities...")

    orchestrator = UnifiedSeedOrchestrator()
    result = orchestrator.seed_specific(["technical_capabilities"])

    if result["success"]:
        click.echo("✅ Technical capabilities seeded successfully!")
        data = result["data"]["results"]["technical_capabilities"]["data"]
        click.echo(f"📊 Records: {data['created']} created, {data['updated']} updated")
    else:
        click.echo("❌ Technical capability seeding failed!")
        click.echo(f"Error: {result['data']['results']['technical_capabilities']['message']}")

    return result


@seed_cli.command("rollback")
@with_appcontext
def rollback_all():
    """Rollback all seeded data."""
    click.echo("🔄 Starting seed data rollback...")

    orchestrator = UnifiedSeedOrchestrator()
    result = orchestrator.rollback_all()

    if result["success"]:
        click.echo("✅ Seed rollback completed successfully!")
    else:
        click.echo("⚠️ Seed rollback completed with some errors!")
        click.echo(f"Details: {result['message']}")

    return result


@seed_cli.command("status")
@with_appcontext
def seed_status():
    """Show current seeding status."""
    click.echo("📋 Checking seed data status...")

    orchestrator = UnifiedSeedOrchestrator()
    result = orchestrator.get_status()

    if result["success"]:
        click.echo("✅ Seed status retrieved successfully!")
        seeders = result["data"]["seeders"]
        for name, info in seeders.items():
            status = "✅ Available" if info["available"] else "❌ Unavailable"
            click.echo(f"  {name}: {status}")
    else:
        click.echo("❌ Failed to retrieve seed status!")
        click.echo(f"Error: {result['message']}")

    return result


@seed_cli.command("enrich-vendors")
@click.option(
    "--skip-errors", is_flag=True, help="Continue enrichment even if individual vendors fail"
)
@with_appcontext
def enrich_vendors(skip_errors):
    """Enrich all vendor organizations with external data."""
    click.echo("🔍 Starting vendor data enrichment...")

    enrichment_service = DataEnrichmentService()
    result = enrichment_service.enrich_all_vendors(skip_errors=skip_errors)

    successful = result["successful_enrichments"]
    total = result["total_vendors"]

    if successful > 0:
        click.echo(f"✅ Vendor enrichment completed: {successful}/{total} successful")
        click.echo(
            f"📊 Enriched vendors with external intelligence from G2 Crowd, Crunchbase, and GitHub"
        )
    else:
        click.echo("❌ Vendor enrichment completed with no successful enrichments")
        click.echo(f"Total vendors processed: {total}")

    if result["failed_enrichments"] > 0:
        click.echo(f"⚠️  Failed enrichments: {result['failed_enrichments']}")

    return result


@seed_cli.command("enrich-products")
@click.option(
    "--skip-errors", is_flag=True, help="Continue enrichment even if individual products fail"
)
@with_appcontext
def enrich_products(skip_errors):
    """Enrich all vendor products with external data."""
    click.echo("🔍 Starting product data enrichment...")

    enrichment_service = DataEnrichmentService()
    result = enrichment_service.enrich_all_products(skip_errors=skip_errors)

    successful = result["successful_enrichments"]
    total = result["total_products"]

    if successful > 0:
        click.echo(f"✅ Product enrichment completed: {successful}/{total} successful")
        click.echo(f"📊 Enriched products with ratings, technical stack, and community metrics")
    else:
        click.echo("❌ Product enrichment completed with no successful enrichments")
        click.echo(f"Total products processed: {total}")

    if result["failed_enrichments"] > 0:
        click.echo(f"⚠️  Failed enrichments: {result['failed_enrichments']}")

    return result


@seed_cli.command("enrich-all")
@click.option(
    "--skip-errors", is_flag=True, help="Continue enrichment even if individual items fail"
)
@with_appcontext
def enrich_all(skip_errors):
    """Enrich all vendors and products with external data."""
    click.echo("🔍 Starting comprehensive data enrichment...")

    enrichment_service = DataEnrichmentService()

    # Enrich vendors first
    click.echo("🏢 Enriching vendor organizations...")
    vendor_result = enrichment_service.enrich_all_vendors(skip_errors=skip_errors)

    # Then enrich products
    click.echo("📦 Enriching vendor products...")
    product_result = enrichment_service.enrich_all_products(skip_errors=skip_errors)

    # Summary
    total_successful = (
        vendor_result["successful_enrichments"] + product_result["successful_enrichments"]
    )
    total_processed = vendor_result["total_vendors"] + product_result["total_products"]

    if total_successful > 0:
        click.echo(
            f"✅ Comprehensive enrichment completed: {total_successful}/{total_processed} successful"
        )
        click.echo(
            f"🏢 Vendors: {vendor_result['successful_enrichments']}/{vendor_result['total_vendors']}"
        )
        click.echo(
            f"📦 Products: {product_result['successful_enrichments']}/{product_result['total_products']}"
        )
    else:
        click.echo("❌ Comprehensive enrichment completed with no successful enrichments")

    return {
        "vendors": vendor_result,
        "products": product_result,
        "total_successful": total_successful,
        "total_processed": total_processed,
    }


@seed_cli.command("enrichment-status")
@with_appcontext
def enrichment_status():
    """Show current data enrichment status."""
    click.echo("📊 Checking data enrichment status...")

    enrichment_service = DataEnrichmentService()
    status = enrichment_service.get_enrichment_status()

    if "error" not in status:
        click.echo("✅ Enrichment status retrieved successfully!")
        click.echo("🏢 Vendor Organizations:")
        vendors = status["vendors"]
        click.echo(f"  Total: {vendors['total']}")
        click.echo(f"  Enriched: {vendors['enriched']} ({vendors['enrichment_rate']:.1%})")
        click.echo(f"  Recently enriched: {vendors['recently_enriched']}")

        click.echo("📦 Vendor Products:")
        products = status["products"]
        click.echo(f"  Total: {products['total']}")
        click.echo(f"  Enriched: {products['enriched']} ({products['enrichment_rate']:.1%})")
        click.echo(f"  Recently enriched: {products['recently_enriched']}")

        click.echo("🔗 API Pipeline Health:")
        api_health = status["api_health"]
        if api_health["overall_healthy"]:
            click.echo("  ✅ All API clients healthy")
        else:
            click.echo("  ❌ Some API clients unhealthy")
            for name, client_status in api_health["clients"].items():
                status_icon = "✅" if client_status["healthy"] else "❌"
                click.echo(f"    {status_icon} {name}")
    else:
        click.echo("❌ Failed to retrieve enrichment status!")
        click.echo(f"Error: {status['error']}")

    return status


# Register the CLI group with Flask
def register_commands(app):
    """Register seed commands with Flask app."""
    app.cli.add_command(seed_cli)
