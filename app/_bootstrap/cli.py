"""
CLI command registration.
"""


def init_cli(app):
    """Register all CLI commands."""

    # Seed CLI commands
    try:
        from app.commands.seed_commands import register_commands
        register_commands(app)
        app.logger.info("\u2705 Seed CLI commands registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register seed CLI commands: {e}")

    # ArchiMate CLI commands
    try:
        from app.commands.archimate_commands import register_archimate_commands
        register_archimate_commands(app)
        app.logger.info("\u2705 ArchiMate CLI commands registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register ArchiMate CLI commands: {e}")

    # Capabilities seed CLI commands
    try:
        from app.commands.seed_capabilities import register_capabilities_commands
        register_capabilities_commands(app)
        app.logger.info("\u2705 Capabilities seed CLI commands registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register capabilities seed CLI commands: {e}")

    # ACM CLI commands
    try:
        from app.commands.acm_commands import register_commands as register_acm_commands
        register_acm_commands(app)
        app.logger.info("\u2705 ACM CLI commands registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register ACM CLI commands: {e}")

    # Feature Flags seed CLI command
    try:
        from app.commands import seed_feature_flags
        seed_feature_flags.init_app(app)
        app.logger.info("\u2705 Feature flags seed CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register feature flags seed CLI command: {e}")

    # ADM Deliverables seed CLI command
    try:
        from app.commands import seed_adm_deliverables
        seed_adm_deliverables.init_app(app)
        app.logger.info("\u2705 ADM deliverables seed CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register ADM deliverables seed CLI command: {e}")

    # ArchiMate backfill CLI command
    try:
        from app.commands import backfill_archimate_elements
        backfill_archimate_elements.init_app(app)
        app.logger.info("\u2705 ArchiMate backfill CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register ArchiMate backfill CLI: {e}")

    # BIZBOK Strategy & Motivation backfill CLI command
    try:
        from scripts.backfill_strategy_motivation_elements import init_app as init_strat_backfill
        init_strat_backfill(app)
        app.logger.info("\u2705 Strategy/Motivation backfill CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register Strategy/Motivation backfill CLI: {e}")

    # Vendor Seed Management CLI commands
    try:
        from app.commands.seed_vendors_cli import register_seed_commands
        register_seed_commands(app)
        app.logger.info("\u2705 Vendor seed management CLI commands registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register vendor seed CLI commands: {e}")

    # ArchiMate Viewpoint seed CLI command
    try:
        from app.commands import seed_viewpoints
        seed_viewpoints.init_app(app)
        app.logger.info("\u2705 ArchiMate viewpoint seed CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register viewpoint seed CLI command: {e}")

    # RATA-003: Rationalization scoring CLI commands
    try:
        from app.commands.rationalization_commands import register_rationalization_commands
        register_rationalization_commands(app)
        app.logger.info("\u2705 Rationalization CLI commands registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register rationalization CLI commands: {e}")

    # Data profile + read-only query CLI commands
    try:
        from app.commands.data_profile_commands import register_data_profile_commands
        register_data_profile_commands(app)
        app.logger.info("\u2705 Data profile CLI commands registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register data profile CLI commands: {e}")

    # PLT-009: Data maturity digest CLI command
    import click

    @app.cli.command("send-maturity-digest")
    def send_maturity_digest_cmd():
        """PLT-009: Send the weekly data maturity digest email now."""
        from app._bootstrap._digest_emails import send_data_maturity_digest
        from flask import current_app

        click.echo("Generating data maturity digest...")
        data = send_data_maturity_digest(current_app._get_current_object())
        click.echo(
            f"Done: {data['total']} solutions, "
            f"{data['avg_score']}% avg completeness, "
            f"{len(data['zero_connections'])} with zero connections."
        )

    # PLT-031: Executive summary CLI command
    @app.cli.command("send-executive-summary")
    def send_executive_summary_cmd():
        """PLT-031: Send the weekly executive summary email now."""
        from app._bootstrap._digest_emails import send_executive_summary
        from flask import current_app

        click.echo("Generating executive summary...")
        data = send_executive_summary(current_app._get_current_object())
        click.echo(
            f"Done: {data['total_solutions']} solutions, "
            f"{data['new_solutions_count']} new this week, "
            f"{data['arb_decisions_count']} ARB decisions."
        )

    # ACM-001: Cloud pricing API sync CLI commands
    try:
        from app.commands.cloud_pricing_commands import register_commands as register_cloud_pricing
        register_cloud_pricing(app)
        app.logger.info("\u2705 Cloud pricing CLI commands registered")
    except ImportError:
        pass

    # Solution maturity sync CLI commands
    try:
        from app.commands.solution_maturity_commands import register_solution_maturity_commands
        register_solution_maturity_commands(app)
        app.logger.info("\u2705 Solution maturity sync CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register solution maturity CLI: {e}")

    # SAP BTP: Vendor ArchiMate template seed CLI command + domain entity schema seeds
    try:
        from app.commands import seed_vendor_archimate_templates
        seed_vendor_archimate_templates.init_app(app)
        app.logger.info("\u2705 Vendor ArchiMate template seed CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register vendor ArchiMate template seed CLI: {e}")

    # Vendor seed column migration (add spec_data_seed to vendor_archimate_templates)
    try:
        from app.commands.add_vendor_seed_column import init_app as init_vendor_seed_col
        init_vendor_seed_col(app)
        app.logger.info("\u2705 Vendor seed column CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register vendor seed column CLI: {e}")

    # INTARCH-001: Integration pattern catalogue seed + schema extension commands
    try:
        from app.commands import seed_integration_patterns
        seed_integration_patterns.init_app(app)
        app.logger.info("\u2705 Integration pattern seed CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register integration pattern seed CLI: {e}")

    try:
        from app.commands.add_integration_flow_columns import init_app as init_flow_columns
        init_flow_columns(app)
        app.logger.info("\u2705 Integration flow columns CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register integration flow columns CLI: {e}")

    try:
        from app.commands.seed_minimal_vendor_products import seed_minimal_vendor_products
        app.cli.add_command(seed_minimal_vendor_products)
        app.logger.info("\u2705 Minimal vendor products seed CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register minimal vendor products seed CLI: {e}")

    try:
        from app.commands.codegen_drift_commands import register_codegen_drift_commands
        register_codegen_drift_commands(app)
        app.logger.info("\u2705 Codegen drift detection CLI command registered")
    except Exception as e:
        app.logger.warning(f"\u26a0\ufe0f  Failed to register codegen drift CLI: {e}")
