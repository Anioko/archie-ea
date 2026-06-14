"""CLI command to sync computed maturity scores back to Solution.maturity_current.

The health-score dashboard uses Solution.maturity_current / maturity_target when set.
All solutions currently have NULL maturity_current, so the dashboard falls back to
ADM phase percentage (phase A = 12%). This command computes the real section-completion
score by querying the actual lifecycle tables (solution_drivers, solution_goals, etc.)
and persists the results so the dashboard shows accurate health data.

Usage:
    flask solutions sync-maturity          # dry-run (print scores, no DB write)
    flask solutions sync-maturity --apply  # write scores to DB
"""

import click
import logging

logger = logging.getLogger(__name__)


@click.group("solutions")
def solutions_cli():
    """Solution management commands."""


def _compute_solution_maturity(solution, db) -> int:
    """Compute the section-completion maturity score (0-100) for a single solution.

    Queries the actual lifecycle tables (solution_drivers, solution_goals, etc.) directly
    instead of relying on lifecycle_json which is built dynamically in route context.
    """
    TOTAL_WEIGHT = 87  # 8+7+5+10+8+7+10+8+5+7+5+7
    sid = solution.id

    # Resolve analysis session for session-linked tables (drivers, goals, constraints, recommendations)
    sess_id = getattr(solution, "analysis_session_id", None)
    problem_ids = []
    if sess_id:
        try:
            from app.models.solution_architect_models import SolutionProblemDefinition
            problem_ids = [
                r[0] for r in
                db.session.query(SolutionProblemDefinition.id)
                .filter_by(session_id=sess_id)
                .all()
            ]
        except Exception as exc:
            logger.debug("suppressed error in _compute_solution_maturity (app/commands/solution_maturity_commands.py): %s", exc)

    def _has_in_problems(model):
        if not problem_ids:
            return False
        try:
            return db.session.query(model).filter(
                model.problem_id.in_(problem_ids)
            ).limit(1).count() > 0
        except Exception:
            return False

    def _has_by_solution(model, fk_col):
        try:
            return db.session.query(model).filter(fk_col == sid).limit(1).count() > 0
        except Exception:
            return False

    # Lifecycle checks via direct DB queries
    has_drivers = has_goals = has_constraints = has_recommendations = False
    has_requirements = has_risks = has_plateaus = has_metrics = False
    try:
        from app.models.solution_architect_models import (
            SolutionDriver, SolutionGoal, SolutionConstraint, SolutionRequirement,
            SolutionRecommendation,
        )
        has_drivers = _has_in_problems(SolutionDriver)
        has_goals = _has_in_problems(SolutionGoal)
        has_constraints = _has_in_problems(SolutionConstraint)
        # requirements link via solution_id OR problem_id
        has_requirements = _has_by_solution(SolutionRequirement, SolutionRequirement.solution_id)
        if not has_requirements and problem_ids:
            has_requirements = _has_in_problems(SolutionRequirement)
        # recommendations link via session_id
        if sess_id:
            try:
                has_recommendations = (
                    db.session.query(SolutionRecommendation)
                    .filter_by(session_id=sess_id).limit(1).count() > 0
                )
            except Exception as exc:
                has_recommendations = _has_in_problems(SolutionRecommendation)
    except Exception:
        logger.debug("suppressed error in _compute_solution_maturity (app/commands/solution_maturity_commands.py): %s", exc)

    try:
        from app.models.solution_lifecycle_models import SolutionRisk, SolutionPlateau, SolutionMetric
        has_risks = _has_by_solution(SolutionRisk, SolutionRisk.solution_id)
        has_plateaus = _has_by_solution(SolutionPlateau, SolutionPlateau.solution_id)
        has_metrics = _has_by_solution(SolutionMetric, SolutionMetric.solution_id)
    except Exception as exc:
        logger.debug("suppressed error in _compute_solution_maturity (app/commands/solution_maturity_commands.py): %s", exc)

    # ArchiMate elements linked to this solution
    has_archimate = False
    cross_layer_ok = False
    try:
        from app.models.solution_element import SolutionElement
        from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship

        sol_elem_ids = {
            r[0] for r in
            db.session.query(SolutionElement.archimate_element_id)
            .filter_by(solution_id=sid)
            .all()
        }
        # Also check solution_archimate_elements junction (used by blueprint page)
        # when solution_elements is empty — both tables are valid sources for this check.
        if not sol_elem_ids:
            try:
                from app.models.solution_archimate_element import SolutionArchiMateElement
                ae_ids = {
                    r[0] for r in
                    db.session.query(SolutionArchiMateElement.element_id)
                    .filter(
                        SolutionArchiMateElement.solution_id == sid,
                        SolutionArchiMateElement.element_table == "archimate_elements",
                    )
                    .all()
                }
                sol_elem_ids = ae_ids
            except Exception as exc:
                logger.debug("suppressed error in _compute_solution_maturity (app/commands/solution_maturity_commands.py): %s", exc)
        has_archimate = bool(sol_elem_ids)

        if sol_elem_ids:
            cross_layer_count = 0
            rels = (
                ArchiMateRelationship.query
                .filter(
                    ArchiMateRelationship.source_id.in_(sol_elem_ids),
                    ArchiMateRelationship.target_id.in_(sol_elem_ids),
                )
                .limit(200)
                .all()
            )
            elem_cache = {}
            for rel in rels:
                for eid in (rel.source_id, rel.target_id):
                    if eid not in elem_cache:
                        elem_cache[eid] = ArchiMateElement.query.get(eid)
                src = elem_cache.get(rel.source_id)
                tgt = elem_cache.get(rel.target_id)
                if src and tgt and (src.layer or "").lower() != (tgt.layer or "").lower():
                    cross_layer_count += 1
            cross_layer_ok = cross_layer_count >= 5
    except Exception as exc:
        logger.debug("suppressed error in _compute_solution_maturity (app/commands/solution_maturity_commands.py): %s", exc)

    earned = 0
    if has_drivers:          earned += 8
    if has_goals:            earned += 7
    if has_constraints:      earned += 5
    if has_requirements:     earned += 10
    if has_archimate:        earned += 8
    if has_risks:            earned += 7
    if has_recommendations:  earned += 10
    if has_plateaus:         earned += 5
    if (solution.governance_status or "draft") not in (None, "draft"):
                             earned += 7
    if has_metrics:          earned += 5
    if cross_layer_ok:       earned += 7

    return round((earned / TOTAL_WEIGHT) * 100)


@solutions_cli.command("sync-maturity")
@click.option("--apply", is_flag=True, default=False,
              help="Write scores to DB (default: dry run).")
@click.option("--solution-id", default=None, type=int,
              help="Sync a single solution by ID instead of all.")
def cmd_sync_maturity(apply, solution_id):
    """Compute and persist maturity scores to Solution.maturity_current.

    Dry run by default — pass --apply to write to DB.
    """
    from app.extensions import db
    from app.models.solution_models import Solution

    query = Solution.query
    if solution_id:
        query = query.filter_by(id=solution_id)
    solutions = query.all()

    if not solutions:
        click.echo("No solutions found.")
        return

    click.echo(f"{'DRY RUN — ' if not apply else ''}Syncing maturity scores for {len(solutions)} solutions...")

    updated = 0
    unchanged = 0
    errors = 0
    score_distribution = {}

    for sol in solutions:
        try:
            score = _compute_solution_maturity(sol, db)
            bucket = (score // 10) * 10
            score_distribution[bucket] = score_distribution.get(bucket, 0) + 1

            old_current = getattr(sol, "maturity_current", None)
            old_target = getattr(sol, "maturity_target", None)

            if old_current == score and old_target == 100:
                unchanged += 1
                continue

            if apply:
                sol.maturity_current = score
                sol.maturity_target = 100
                updated += 1
            else:
                click.echo(
                    f"  [{sol.id}] {(sol.name or 'unnamed')[:40]:<40} "
                    f"score={score:3d}  (was current={old_current} target={old_target})"
                )
                updated += 1
        except Exception as exc:
            click.echo(f"  ERROR solution {sol.id}: {exc}", err=True)
            errors += 1

    if apply and updated > 0:
        try:
            db.session.commit()
            click.echo(f"Committed {updated} score updates.")
        except Exception as exc:
            db.session.rollback()
            click.echo(f"DB commit failed: {exc}", err=True)
            raise SystemExit(1)

    click.echo(
        f"\nDone. Updated={updated}  Unchanged={unchanged}  Errors={errors}"
    )
    if score_distribution:
        click.echo("Score distribution (bucket: count):")
        for bucket in sorted(score_distribution):
            bar = "█" * score_distribution[bucket]
            click.echo(f"  {bucket:3d}-{bucket+9}: {bar} ({score_distribution[bucket]})")


def register_solution_maturity_commands(app):
    """Register solution maturity CLI commands with Flask app."""
    app.cli.add_command(solutions_cli)
