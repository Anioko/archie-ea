"""ARCH-126 CLI: surface traceability gaps (orphaned elements, unlinked solutions).

    flask --app manage traceability-report
"""

import click


def register_traceability_report_command(app):
    @app.cli.command("traceability-report")
    def traceability_report():
        """Print counts of ArchiMate elements with no relationships and
        solutions with no capability links (ARCH-126).

        Run outside a request context, so there is no ``g.current_org_id`` and
        the counts are computed across every organization in the database —
        the report says so explicitly rather than silently scoping to one.
        """
        from app.services.traceability_report_service import compute_traceability_report

        report = compute_traceability_report()

        def _fmt_pct(v):
            return "—" if v is None else f"{v}%"

        click.echo("Traceability report (all organizations — no tenant scope outside a request)")
        click.echo("-" * 70)
        click.echo(
            f"ArchiMate elements: {report['elements_total']} total, "
            f"{report['elements_with_zero_relationships']} with zero relationships "
            f"({_fmt_pct(report['elements_with_zero_relationships_pct'])})"
        )
        click.echo(
            f"Solutions: {report['solutions_total']} total, "
            f"{report['solutions_with_zero_capability_links']} with zero capability links "
            f"({_fmt_pct(report['solutions_with_zero_capability_links_pct'])})"
        )
