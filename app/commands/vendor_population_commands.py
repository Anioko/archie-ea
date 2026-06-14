"""
Vendor Data Population Commands - LLM-PRD - 02 Implementation

Management commands for comprehensive vendor data population with:
- Bulk vendor and product creation
- Data integrity validation
- Market intelligence management
- Population status tracking

Usage:
    python manage.py populate-vendors
    python manage.py populate-vendors --force-update
    python manage.py validate-vendor-data
    python manage.py vendor-population-status
"""

import logging

import click
from flask.cli import with_appcontext

from app import db
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
from app.services.vendor_data_population_service import get_vendor_population_service

logger = logging.getLogger(__name__)


@click.command()
@click.option("--force-update", is_flag=True, help="Force update existing vendors")
@click.option("--batch-size", default=50, help="Batch size for processing")
@click.option("--categories", help="Comma-separated list of categories to populate")
@with_appcontext
def populate_vendors(force_update, batch_size, categories):
    """Populate vendor database with comprehensive data."""

    click.echo("🚀 Starting Comprehensive Vendor Data Population...")

    # Parse categories if provided
    category_list = []
    if categories:
        category_list = [cat.strip() for cat in categories.split(",") if cat.strip()]
        click.echo(f"Categories to populate: {', '.join(category_list)}")

    # Get the vendor population service
    population_service = get_vendor_population_service()

    # Check service availability
    if not population_service.vendor_data:
        click.echo("❌ Error: Vendor dataset not available")
        click.echo("   Please ensure comprehensive_vendor_dataset.py is properly configured")
        return 1

    click.echo("✅ Vendor population service is available")

    # Get current statistics
    current_stats = population_service.get_population_status()
    click.echo(f"📊 Current Database Status:")
    click.echo(
        f"   - Vendors in DB: {current_stats.get('database_status', {}).get('vendors_in_db', 0)}"
    )
    click.echo(
        f"   - Products in DB: {current_stats.get('database_status', {}).get('products_in_db', 0)}"
    )

    # Confirm population
    if force_update:
        click.echo("⚠️  Force update mode - existing vendors will be updated")
    else:
        click.echo("📝 Incremental mode - only new vendors will be added")

    if not click.confirm("Proceed with vendor population?"):
        click.echo("Population cancelled by user")
        return 0

    # Perform population
    click.echo("\n📦 Populating Vendor Data...")

    try:
        result = population_service.populate_all_vendors(force_update=force_update)

        if result.get("success"):
            stats = result["stats"]
            click.echo(f"   ✅ Vendors created: {stats['vendors_created']}")
            click.echo(f"   ✅ Vendors updated: {stats['vendors_updated']}")
            click.echo(f"   ✅ Products created: {stats['products_created']}")
            click.echo(f"   ✅ Products updated: {stats['products_updated']}")
            click.echo(f"   ✅ Capabilities mapped: {stats['capabilities_mapped']}")
            click.echo(f"   ✅ Pricing models created: {stats['pricing_models_created']}")
            click.echo(f"   ⏱️  Processing time: {stats['processing_time_seconds']}s")

            if stats["errors_count"] > 0:
                click.echo(f"   ⚠️  Errors encountered: {stats['errors_count']}")
                for error in result.get("errors", [])[:5]:  # Show first 5 errors
                    click.echo(f"      - {error}")
        else:
            click.echo(f"   ❌ Population failed: {result.get('error', 'Unknown error')}")
            return 1

    except Exception as e:
        click.echo(f"❌ Error during population: {str(e)}")
        return 1

    # Final statistics
    final_stats = population_service.get_population_status()
    click.echo(f"\n📊 Final Database Status:")
    click.echo(
        f"   - Vendors in DB: {final_stats.get('database_status', {}).get('vendors_in_db', 0)}"
    )
    click.echo(
        f"   - Products in DB: {final_stats.get('database_status', {}).get('products_in_db', 0)}"
    )
    click.echo(
        f"   - Vendor coverage: {final_stats.get('coverage_percentages', {}).get('vendor_coverage', 0):.1f}%"
    )
    click.echo(
        f"   - Product coverage: {final_stats.get('coverage_percentages', {}).get('product_coverage', 0):.1f}%"
    )

    click.echo("\n🎉 Vendor data population completed successfully!")
    return 0


@click.command()
@click.option("--fix-issues", is_flag=True, help="Attempt to fix minor issues automatically")
@with_appcontext
def validate_vendor_data(fix_issues):
    """Validate the integrity of vendor data."""

    click.echo("🔍 Validating Vendor Data Integrity...")

    population_service = get_vendor_population_service()

    try:
        validation_results = population_service.validate_data_integrity()

        click.echo(f"\n📊 Validation Results:")
        click.echo(f"   - Status: {validation_results['status']}")
        click.echo(f"   - Total issues: {validation_results['total_issues']}")

        if validation_results["issues"]:
            click.echo(f"\n⚠️  Issues Found:")
            for issue in validation_results["issues"]:
                click.echo(f"   - {issue['type']}: {issue['message']} (count: {issue['count']})")

        if validation_results["warnings"]:
            click.echo(f"\n⚠️  Warnings:")
            for warning in validation_results["warnings"]:
                click.echo(
                    f"   - {warning['type']}: {warning['message']} (count: {warning['count']})"
                )

        if fix_issues and validation_results.get("issues"):
            click.echo(f"\n🔧 Attempting to fix issues...")
            # Note: Auto-fix functionality would need to be implemented
            click.echo(f"   Auto-fix not yet implemented")

        if validation_results["status"] == "passed":
            click.echo("\n✅ All validation checks passed!")
            return 0
        else:
            click.echo("\n❌ Validation failed - issues need to be addressed")
            return 1

    except Exception as e:
        click.echo(f"❌ Error during validation: {str(e)}")
        return 1


@click.command()
@click.option("--include-details", is_flag=True, help="Include detailed vendor information")
@with_appcontext
def vendor_population_status(include_details):
    """Show vendor data population status."""

    click.echo("📊 Vendor Data Population Status")
    click.echo("=" * 40)

    population_service = get_vendor_population_service()

    try:
        status = population_service.get_population_status()

        # Database status
        db_status = status.get("database_status", {})
        click.echo(f"🗄️  Database Status:")
        click.echo(f"   - Vendors: {db_status.get('vendors_in_db', 0)}")
        click.echo(f"   - Products: {db_status.get('products_in_db', 0)}")
        click.echo(f"   - Capability mappings: {db_status.get('capability_mappings', 0)}")
        click.echo(f"   - Pricing models: {db_status.get('pricing_models', 0)}")

        # Dataset info
        dataset_info = status.get("dataset_info", {})
        if dataset_info:
            click.echo(f"\n📚 Dataset Information:")
            click.echo(
                f"   - Total vendors in dataset: {dataset_info.get('total_vendors_in_dataset', 0)}"
            )
            click.echo(
                f"   - Total products in dataset: {dataset_info.get('total_products_in_dataset', 0)}"
            )
            click.echo(f"   - Categories: {dataset_info.get('categories_in_dataset', 0)}")
            click.echo(f"   - Last updated: {dataset_info.get('last_updated', 'Unknown')}")

        # Coverage percentages
        coverage = status.get("coverage_percentages", {})
        if coverage:
            click.echo(f"\n📈 Coverage Analysis:")
            click.echo(f"   - Vendor coverage: {coverage.get('vendor_coverage', 0):.1f}%")
            click.echo(f"   - Product coverage: {coverage.get('product_coverage', 0):.1f}%")

        # Vendor categories
        categories = status.get("vendor_categories", {})
        if categories and include_details:
            click.echo(f"\n📂 Vendor Categories:")
            for category, count in sorted(categories.items()):
                click.echo(f"   - {category}: {count} vendors")

        # Overall status
        vendor_coverage = coverage.get("vendor_coverage", 0)
        product_coverage = coverage.get("product_coverage", 0)

        if vendor_coverage >= 95 and product_coverage >= 95:
            click.echo(f"\n✅ Status: COMPLETE - Excellent coverage achieved")
        elif vendor_coverage >= 80 and product_coverage >= 80:
            click.echo(f"\n⚠️  Status: GOOD - Most data populated")
        else:
            click.echo(f"\n❌ Status: INCOMPLETE - Run 'python manage.py populate-vendors'")

    except Exception as e:
        click.echo(f"❌ Error getting status: {str(e)}")
        return 1

    return 0


@click.command()
@click.option("--category", help="Filter by category")
@click.option("--tier", help="Filter by strategic tier")
@click.option("--limit", default=20, help="Number of vendors to show")
@with_appcontext
def list_vendors(category, tier, limit):
    """List vendors with optional filtering."""

    click.echo(f"🏢 Vendor Listing")
    if category:
        click.echo(f"   Category: {category}")
    if tier:
        click.echo(f"   Tier: {tier}")
    click.echo(f"   Limit: {limit}")
    click.echo("=" * 50)

    try:
        from sqlalchemy import and_

        query = VendorOrganization.query

        # Apply filters
        if category:
            query = query.filter(VendorOrganization.category == category)
        if tier:
            query = query.filter(VendorOrganization.strategic_tier == tier)

        vendors = query.limit(limit).all()

        if not vendors:
            click.echo("No vendors found matching the criteria")
            return 0

        click.echo(f"\nFound {len(vendors)} vendors:\n")

        for vendor in vendors:
            product_count = len(vendor.products) if vendor.products else 0
            click.echo(f"📋 {vendor.name}")
            click.echo(f"   Category: {vendor.category}")
            click.echo(f"   Tier: {vendor.strategic_tier or 'N/A'}")
            click.echo(f"   Gartner MQ: {vendor.gartner_magic_quadrant or 'N/A'}")
            click.echo(f"   G2 Rating: {vendor.g2_rating or 'N/A'}")
            click.echo(f"   Products: {product_count}")
            click.echo(f"   Website: {vendor.website or 'N/A'}")
            click.echo()

    except Exception as e:
        click.echo(f"❌ Error listing vendors: {str(e)}")
        return 1

    return 0


@click.command()
@with_appcontext
def vendor_categories():
    """Show vendor categories with statistics."""

    click.echo("📂 Vendor Categories")
    click.echo("=" * 30)

    try:
        from sqlalchemy import func

        # Get category statistics
        categories = (
            db.session.query(
                VendorOrganization.category,
                func.count(VendorOrganization.id).label("vendor_count"),
                func.count(VendorProduct.id).label("product_count"),
            )
            .outerjoin(VendorProduct)
            .group_by(VendorOrganization.category)
            .all()
        )

        if not categories:
            click.echo("No categories found")
            return 0

        total_vendors = sum(cat[1] for cat in categories)
        total_products = sum(cat[2] or 0 for cat in categories)

        click.echo(
            f"\nTotal: {total_vendors} vendors, {total_products} products across {len(categories)} categories\n"
        )

        # Sort by vendor count
        categories_sorted = sorted(categories, key=lambda x: x[1], reverse=True)

        for category, vendor_count, product_count in categories_sorted:
            avg_products = round((product_count or 0) / vendor_count, 2) if vendor_count > 0 else 0
            click.echo(f"📊 {category}")
            click.echo(f"   Vendors: {vendor_count}")
            click.echo(f"   Products: {product_count or 0}")
            click.echo(f"   Avg products/vendor: {avg_products}")
            click.echo()

    except Exception as e:
        click.echo(f"❌ Error getting categories: {str(e)}")
        return 1

    return 0


# Register commands with Flask CLI
def register_commands(cli):
    """Register vendor population commands with Flask CLI."""
    cli.add_command(populate_vendors)
    cli.add_command(validate_vendor_data)
    cli.add_command(vendor_population_status)
    cli.add_command(list_vendors)
    cli.add_command(vendor_categories)
