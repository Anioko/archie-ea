"""
flask bridge-motivation — promote AI solution-design journey motivation
elements (SolutionDriver/SolutionGoal/SolutionOutcome/SolutionPrinciple) into
the enterprise motivation layer (Driver/Goal/Outcome/Principle) so journey
motivation becomes visible/traceable in the enterprise traceability matrix.

This is an explicit, opt-in promotion — it does NOT hook into the live
journey creation path, so it cannot destabilize the journey. It is:
  - NON-DESTRUCTIVE: only ever INSERTs new enterprise rows plus
    MotivationBridgeLink rows (a new table). Never deletes, renames, or
    retypes anything; never touches Solution* rows.
  - IDEMPOTENT: re-running is a no-op for elements already bridged
    (see app.models.motivation.MotivationBridgeLink's unique constraint).

Usage:
    flask --app manage bridge-motivation                     # promote all solutions
    flask --app manage bridge-motivation --solution-id 42     # promote one solution
    flask --app manage bridge-motivation --dry-run            # preview, write nothing
    flask --app manage bridge-motivation --solution-id 42 --dry-run
"""
import click
from flask.cli import with_appcontext


@click.command("bridge-motivation")
@click.option(
    "--solution-id",
    default=None,
    type=int,
    help="Promote a single solution by ID instead of all solutions.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview what would be created/linked without writing to the database.",
)
@with_appcontext
def bridge_motivation_cmd(solution_id, dry_run):
    """Promote solution-scoped motivation elements to the enterprise motivation layer."""
    from app.services.motivation_bridge_service import promote_all, promote_solution_motivation

    if solution_id is not None:
        summary = promote_solution_motivation(solution_id, dry_run=dry_run)
    else:
        summary = promote_all(dry_run=dry_run)

    click.echo(f"{'DRY RUN — ' if dry_run else ''}bridge-motivation summary:")
    if "solutions_processed" in summary:
        click.echo(f"  solutions processed: {summary['solutions_processed']}")
    click.echo(f"  created (new enterprise entity + link): {summary.get('created', 0)}")
    click.echo(f"  linked (matched existing enterprise entity by name): {summary.get('linked', 0)}")
    click.echo(f"  skipped (already bridged): {summary.get('skipped', 0)}")

    errors = summary.get("errors", [])
    if errors:
        click.echo(f"  errors: {len(errors)}")
        for err in errors[:20]:
            click.echo(f"    ! {err.get('element_type')} {err.get('element_id')}: {err.get('error')}")
        if len(errors) > 20:
            click.echo(f"    ... and {len(errors) - 20} more")


def init_app(app):
    """Register the bridge-motivation CLI command with the Flask app."""
    app.cli.add_command(bridge_motivation_cmd)
