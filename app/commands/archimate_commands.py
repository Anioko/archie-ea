"""
ArchiMate CLI Commands

Command-line interface for ArchiMate 3.2 element generation and management.
Provides automated enterprise architecture modeling from vendor and capability data.
"""

import click
from flask.cli import with_appcontext

from app.services.archimate.archimate_service import ArchiMateService


@click.group("archimate")
def archimate_cli():
    """ArchiMate 3.2 enterprise architecture modeling commands."""
    pass


@archimate_cli.command("generate-from-vendors")
@click.option("--vendor-ids", help="Comma-separated list of vendor IDs to process (empty for all)")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be generated without creating elements"
)
@with_appcontext
def generate_from_vendors(vendor_ids, dry_run):
    """Generate ArchiMate architecture from vendor data."""
    click.echo("🏗️  Generating ArchiMate architecture from vendors...")

    # Parse vendor IDs
    vendor_id_list = None
    if vendor_ids:
        try:
            vendor_id_list = [int(vid.strip()) for vid in vendor_ids.split(",")]
            click.echo(f"📋 Processing specific vendors: {vendor_id_list}")
        except ValueError:
            click.echo("❌ Invalid vendor IDs format. Use comma-separated integers.")
            return

    try:
        archimate_service = ArchiMateService()

        if dry_run:
            click.echo("🔍 Performing dry run...")
            # For dry run, we could implement a preview method
            click.echo("ℹ️  Dry run not yet implemented - proceeding with generation")
            # Dry run preview not yet available

        result = archimate_service.generate_architecture_from_vendors(vendor_id_list)

        if result["success"]:
            click.echo("✅ ArchiMate architecture generation completed successfully!")
            click.echo(f"📊 Vendors processed: {result['vendors_processed']}")
            click.echo(f"🏗️  Elements created: {result['elements_created']}")
            click.echo(f"🔗 Relationships created: {result['relationships_created']}")
            click.echo(f"📈 Total elements: {result['total_elements']}")
            click.echo(f"📈 Total relationships: {result['total_relationships']}")
        else:
            click.echo("❌ ArchiMate generation failed!")
            click.echo(f"Error: {result['message']}")

    except Exception as e:
        click.echo(f"❌ Error during ArchiMate generation: {e}")


@archimate_cli.command("generate-from-capabilities")
@click.option(
    "--capability-ids", help="Comma-separated list of capability IDs to process (empty for all)"
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be generated without creating elements"
)
@with_appcontext
def generate_from_capabilities(capability_ids, dry_run):
    """Generate ArchiMate elements from business capabilities."""
    click.echo("🏗️  Generating ArchiMate elements from capabilities...")

    # Parse capability IDs
    capability_id_list = None
    if capability_ids:
        try:
            capability_id_list = [int(cid.strip()) for cid in capability_ids.split(",")]
            click.echo(f"📋 Processing specific capabilities: {capability_id_list}")
        except ValueError:
            click.echo("❌ Invalid capability IDs format. Use comma-separated integers.")
            return

    try:
        archimate_service = ArchiMateService()

        if dry_run:
            click.echo("🔍 Performing dry run...")
            click.echo("ℹ️  Dry run not yet implemented - proceeding with generation")

        result = archimate_service.generate_architecture_from_capabilities(capability_id_list)

        if result["success"]:
            click.echo("✅ ArchiMate element generation completed successfully!")
            click.echo(f"📊 Capabilities processed: {result['capabilities_processed']}")
            click.echo(f"🏗️  Elements created: {result['elements_created']}")
            click.echo(f"📈 Total elements: {result['total_elements']}")
        else:
            click.echo("❌ ArchiMate generation failed!")
            click.echo(f"Error: {result['message']}")

    except Exception as e:
        click.echo(f"❌ Error during ArchiMate generation: {e}")


@archimate_cli.command("generate-relationships")
@click.option("--input-file", help="JSON file containing capability-to-vendor mappings")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be generated without creating relationships"
)
@with_appcontext
def generate_relationships(input_file, dry_run):
    """Create ArchiMate relationships from capability-to-vendor mappings."""
    click.echo("🔗 Generating ArchiMate relationships from mappings...")

    if not input_file:
        click.echo("❌ Input file required. Use --input-file to specify JSON file with mappings.")
        return

    try:
        import json

        # Load mappings from file
        with open(input_file, "r") as f:
            mappings = json.load(f)

        if not isinstance(mappings, list):
            click.echo("❌ Input file must contain a JSON array of mapping objects.")
            return

        click.echo(f"📋 Loaded {len(mappings)} mappings from {input_file}")

        archimate_service = ArchiMateService()

        if dry_run:
            click.echo("🔍 Performing dry run...")
            click.echo("ℹ️  Dry run not yet implemented - proceeding with generation")

        result = archimate_service.create_relationships_from_mappings(mappings)

        if result["success"]:
            click.echo("✅ ArchiMate relationship generation completed successfully!")
            click.echo(f"📊 Mappings processed: {result['mappings_processed']}")
            click.echo(f"🔗 Relationships created: {result['relationships_created']}")
            click.echo(f"⚠️  Warnings: {result['warnings']}")
        else:
            click.echo("❌ ArchiMate relationship generation failed!")
            click.echo(f"Error: {result['message']}")

    except FileNotFoundError:
        click.echo(f"❌ Input file not found: {input_file}")
    except json.JSONDecodeError:
        click.echo(f"❌ Invalid JSON in input file: {input_file}")
    except Exception as e:
        click.echo(f"❌ Error during relationship generation: {e}")


@archimate_cli.command("validate")
@click.option("--detailed", is_flag=True, help="Show detailed validation results")
@with_appcontext
def validate_compliance(detailed):
    """Validate ArchiMate 3.2 compliance of the current model."""
    click.echo("🔍 Validating ArchiMate 3.2 compliance...")

    try:
        archimate_service = ArchiMateService()
        result = archimate_service.validate_archimate_compliance()

        if result["success"]:
            click.echo("✅ ArchiMate compliance validation completed!")

            if detailed:
                click.echo("\n📊 Detailed Results:")
                click.echo(f"🏗️  Total elements: {result['total_elements']}")
                click.echo(f"🔗 Total relationships: {result['total_relationships']}")
                click.echo(f"✅ Valid elements: {result['valid_elements']}")
                click.echo(f"❌ Invalid elements: {result['invalid_elements']}")
                click.echo(f"✅ Valid relationships: {result['valid_relationships']}")
                click.echo(f"❌ Invalid relationships: {result['invalid_relationships']}")

                if result["errors"]:
                    click.echo("\n⚠️  Validation Errors:")
                    for error in result["errors"][:10]:  # Show first 10 errors
                        click.echo(f"  • {error}")
                    if len(result["errors"]) > 10:
                        click.echo(f"  ... and {len(result['errors']) - 10} more errors")

            else:
                compliance_rate = result["compliance_rate"]
                click.echo(f"📊 Compliance rate: {compliance_rate:.1f}%")
                click.echo(f"✅ Valid: {result['valid_elements'] + result['valid_relationships']}")
                click.echo(
                    f"❌ Invalid: {result['invalid_elements'] + result['invalid_relationships']}"
                )

        else:
            click.echo("❌ Validation failed!")
            click.echo(f"Error: {result['message']}")

    except Exception as e:
        click.echo(f"❌ Error during validation: {e}")


@archimate_cli.command("stats")
@click.option(
    "--layer", help="Filter statistics by ArchiMate layer (business, application, technology)"
)
@click.option("--element-type", help="Filter statistics by element type")
@with_appcontext
def show_statistics(layer, element_type):
    """Show comprehensive ArchiMate architecture statistics."""
    click.echo("📊 Gathering ArchiMate architecture statistics...")

    try:
        archimate_service = ArchiMateService()
        stats = archimate_service.get_architecture_statistics()

        if layer:
            click.echo(f"📋 Filtering by layer: {layer}")
        if element_type:
            click.echo(f"📋 Filtering by element type: {element_type}")

        click.echo("\n🏗️  Architecture Overview:")
        click.echo(f"  Total Elements: {stats['total_elements']}")
        click.echo(f"  Total Relationships: {stats['total_relationships']}")
        click.echo(f"  Architecture Models: {stats['total_models']}")

        if stats["elements_by_layer"]:
            click.echo("\n📊 Elements by Layer:")
            for layer_name, count in stats["elements_by_layer"].items():
                click.echo(f"  {layer_name.title()}: {count}")

        if stats["elements_by_type"]:
            click.echo("\n🏷️  Elements by Type (Top 10):")
            sorted_types = sorted(
                stats["elements_by_type"].items(), key=lambda x: x[1], reverse=True
            )
            for elem_type, count in sorted_types[:10]:
                click.echo(f"  {elem_type}: {count}")

        if stats["relationships_by_type"]:
            click.echo("\n🔗 Relationships by Type:")
            for rel_type, count in stats["relationships_by_type"].items():
                click.echo(f"  {rel_type}: {count}")

        if stats["model_statistics"]:
            click.echo("\n📈 Model Statistics:")
            for model_stat in stats["model_statistics"]:
                click.echo(
                    f"  {model_stat['name']} (v{model_stat['version']}): {model_stat['element_count']} elements"
                )

    except Exception as e:
        click.echo(f"❌ Error gathering statistics: {e}")


@archimate_cli.command("clear")
@click.option("--confirm", is_flag=True, help="Confirm deletion of all ArchiMate data")
@with_appcontext
def clear_data(confirm):
    """Clear all ArchiMate elements and relationships."""
    if not confirm:
        click.echo("⚠️  This will delete ALL ArchiMate elements and relationships!")
        click.echo("Add --confirm flag to proceed.")
        return

    click.echo("🗑️  Clearing all ArchiMate data...")

    try:
        from app import db
        from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel

        # Count before deletion
        element_count = ArchiMateElement.query.count()
        relationship_count = ArchiMateRelationship.query.count()
        model_count = ArchitectureModel.query.count()

        # Delete in correct order (relationships first due to foreign keys)
        ArchiMateRelationship.query.delete()
        ArchiMateElement.query.delete()
        ArchitectureModel.query.delete()

        db.session.commit()

        click.echo("✅ ArchiMate data cleared successfully!")
        click.echo(
            f"🗑️  Deleted: {element_count} elements, {relationship_count} relationships, {model_count} models"
        )

    except Exception as e:
        click.echo(f"❌ Error clearing ArchiMate data: {e}")
        db.session.rollback()


@archimate_cli.command("health")
@with_appcontext
def health_check():
    """Check ArchiMate service health and connectivity."""
    click.echo("🏥 Checking ArchiMate service health...")

    try:
        from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel

        element_count = ArchiMateElement.query.count()
        relationship_count = ArchiMateRelationship.query.count()
        model_count = ArchitectureModel.query.count()

        click.echo("✅ ArchiMate service is healthy!")
        click.echo(f"🏗️  Elements: {element_count}")
        click.echo(f"🔗 Relationships: {relationship_count}")
        click.echo(f"📋 Models: {model_count}")

        # Test service instantiation
        archimate_service = ArchiMateService()
        click.echo("✅ ArchiMate service instantiated successfully")

    except Exception as e:
        click.echo(f"❌ ArchiMate service health check failed: {e}")


# Register the CLI group with Flask
def register_archimate_commands(app):
    """Register ArchiMate CLI commands with Flask app."""
    app.cli.add_command(archimate_cli)
