"""``flask purge-cross-tenant-copilot-insights`` — delete derived insight rows.

``portfolio_duplicate`` and ``pattern_available`` insights quote other solutions
by name. Before the tenant-scope fix (T-RR-4) they could name solutions from
other organisations. This command deletes those two insight types so they are
regenerated correctly on the next blueprint page load.

It is a one-off housekeeping command, not a scheduled job. Dry-run by default;
deletes only with ``--apply``.
"""

import click


def init_app(app):
    @app.cli.command("purge-cross-tenant-copilot-insights")
    @click.option(
        "--apply",
        is_flag=True,
        default=False,
        help="Actually delete rows. Without this flag the command prints counts only.",
    )
    def purge_cross_tenant_copilot_insights(apply):
        """Delete portfolio_duplicate and pattern_available CopilotInsight rows."""
        from app.models.copilot_insight import CopilotInsight

        target_types = ["portfolio_duplicate", "pattern_available"]
        counts = {}
        for insight_type in target_types:
            counts[insight_type] = CopilotInsight.query.filter_by(
                insight_type=insight_type
            ).count()

        for insight_type, count in counts.items():
            click.echo(f"{insight_type}: {count} row(s)")

        if apply:
            total = 0
            for insight_type in target_types:
                deleted = CopilotInsight.query.filter_by(
                    insight_type=insight_type
                ).delete()
                total += deleted
            from app import db
            db.session.commit()
            click.echo(f"Deleted {total} row(s).")
        else:
            click.echo("Dry run — use --apply to delete.")