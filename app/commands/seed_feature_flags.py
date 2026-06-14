"""
Flask CLI command for seeding feature flags.
Run with: flask seed-feature-flags
"""
import click
from flask.cli import with_appcontext


@click.command("seed-feature-flags")
@click.option("--clear", is_flag=True, help="Clear existing feature flags first")
@with_appcontext
def seed_feature_flags_command(clear):
    """Seed database with initial feature flags for existing sidebar sections."""
    # Import inside function to avoid circular import and ensure app context
    from flask import current_app

    # Get db from app extensions
    db = current_app.extensions["sqlalchemy"]
    from sqlalchemy import text

    from app.models import FeatureFlag, FeatureState, FeatureType

    if clear:
        if click.confirm("⚠️  This will delete all feature flags. Continue?"):
            # Use raw SQL for deletion to avoid model configuration issues
            db.session.execute(text("DELETE FROM feature_flags"))  # tenant-exempt: CLI command
            db.session.commit()
            click.echo("🗑️  Existing feature flags cleared")

    # Define initial feature flags based on sidebar structure
    feature_flags = [
        # Applications Section
        {
            "key": "applications_management",
            "name": "Applications Management",
            "description": "Application portfolio and rationalization features",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.STABLE.value,
            "enabled": True,
            "sidebar_label": "Applications Management",
            "sidebar_icon": "package",
            "routes": [
                "/applications/*",
                "/unified-applications/*",
                "/application-mgmt/*",
            ],
            "sort_order": 10,
        },
        # Vendor Management Section
        {
            "key": "vendor_management",
            "name": "Vendor Management",
            "description": "Vendor portfolio and analysis features",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.STABLE.value,
            "enabled": True,
            "sidebar_label": "Vendor Management",
            "sidebar_icon": "building - 2",
            "routes": ["/vendors/*", "/unified-applications/vendors*"],
            "sort_order": 20,
        },
        # ArchiMate Section
        {
            "key": "archimate_management",
            "name": "ArchiMate Management",
            "description": "Enterprise architecture modeling with ArchiMate 3.2",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.STABLE.value,
            "enabled": True,
            "sidebar_label": "ArchiMate",
            "sidebar_icon": "network",
            "routes": ["/architecture/*", "/archimate/*"],
            "sort_order": 30,
        },
        # Capabilities Section
        {
            "key": "capabilities_management",
            "name": "Capabilities Management",
            "description": "Business and technical capability modeling",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.STABLE.value,
            "enabled": True,
            "sidebar_label": "Capabilities",
            "sidebar_icon": "layers",
            "routes": ["/capabilities/*", "/business-capabilities/*"],
            "sort_order": 40,
        },
        # Solutions Management Section
        {
            "key": "solutions_management",
            "name": "Solutions Management",
            "description": "Solution architecture and design workflows",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.STABLE.value,
            "enabled": True,
            "sidebar_label": "Solutions Management",
            "sidebar_icon": "lightbulb",
            "routes": ["/solutions/*", "/solution-architect/*"],
            "sort_order": 50,
        },
        # Architecture Review Board Section
        {
            "key": "arb_workflows",
            "name": "Architecture Review Board",
            "description": "ARB governance and decision workflows",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.BETA.value,
            "enabled": True,
            "sidebar_label": "ARB Workflows",
            "sidebar_icon": "shield-check",
            "routes": ["/arb/*"],
            "sort_order": 60,
        },
        # ADM Kanban Section
        {
            "key": "adm_kanban",
            "name": "ADM Kanban",
            "description": "TOGAF ADM phase management with Kanban boards",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.STABLE.value,
            "enabled": True,
            "sidebar_label": "ADM Kanban",
            "sidebar_icon": "kanban",
            "routes": ["/adm-kanban/*"],
            "sort_order": 70,
        },
        # AI Chat Section
        {
            "key": "ai_assistant",
            "name": "AI Assistant",
            "description": "AI-powered architecture assistant and chat",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.ALPHA.value,
            "enabled": True,
            "sidebar_label": "AI Assistant",
            "sidebar_icon": "bot",
            "routes": ["/ai-chat/*", "/ai-assistance/*"],
            "sort_order": 80,
        },
        # Reports Section
        {
            "key": "reports",
            "name": "Reports & Analytics",
            "description": "Dashboards, reports, and analytics",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.STABLE.value,
            "enabled": True,
            "sidebar_label": "Reports",
            "sidebar_icon": "bar-chart",
            "routes": ["/reports/*", "/analytics/*", "/dashboard/*"],
            "sort_order": 90,
        },
        # Administration Section
        {
            "key": "administration",
            "name": "Administration",
            "description": "System administration and configuration",
            "feature_type": FeatureType.SIDEBAR_SECTION.value,
            "state": FeatureState.STABLE.value,
            "enabled": True,
            "sidebar_label": "Administration",
            "sidebar_icon": "settings",
            "routes": ["/admin/*"],
            "sort_order": 100,
        },
    ]

    # Insert feature flags
    created_count = 0
    skipped_count = 0

    for flag_data in feature_flags:
        # Check if already exists using raw SQL to avoid model configuration issues
        result = db.session.execute(  # tenant-exempt: CLI command
            text("SELECT 1 FROM feature_flags WHERE key = :key"), {"key": flag_data["key"]}
        )
        existing = result.scalar()

        if existing:
            click.echo(f"⏭️  Skipping {flag_data['key']} (already exists)")
            skipped_count += 1
            continue

        flag = FeatureFlag(**flag_data)
        db.session.add(flag)
        created_count += 1
        click.echo(f"✅ Created feature flag: {flag_data['key']}")

    db.session.commit()

    click.echo("\n" + "=" * 60)
    click.echo(f"✅ Feature flag seeding complete!")
    click.echo(f"   Created: {created_count}")
    click.echo(f"   Skipped: {skipped_count}")
    click.echo(f"   Total: {created_count + skipped_count}")
    click.echo("=" * 60)
    click.echo("\n📍 Manage feature flags at: /admin/feature-flags")


def init_app(app):
    """Register CLI command with app."""
    app.cli.add_command(seed_feature_flags_command)
