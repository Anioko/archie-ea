"""
Flask CLI command for backfilling ArchiMateElement records.
Run with: flask backfill-archimate-elements [--dry-run] [--motivation-only]

Covers:
  - ApplicationComponent  (Application layer)
  - BusinessCapability    (Strategy layer)
  - SolutionDriver        → Driver        (Motivation)
  - SolutionGoal          → Goal          (Motivation)
  - SolutionConstraint    → Constraint    (Motivation)
  - SolutionRequirement   → Requirement   (Motivation)
  - SolutionRisk          → Assessment    (Motivation)
  - SolutionMetric        → Outcome       (Motivation)
  - SolutionPlateau       → Plateau       (Implementation)
"""

import click
from flask.cli import with_appcontext

# SQL to fetch (entity_id, name, solution_id) for each motivation entity type.
# All queries avoid ORM to prevent column-drift errors from unapplied migrations.
_ENTITY_QUERIES = {
    # via solution.analysis_session_id chain
    "Driver": (
        "Driver", "Motivation",
        """
        SELECT d.id, d.name, s.id AS solution_id
        FROM solution_drivers d
        JOIN solution_problem_definitions spd ON d.problem_id = spd.id
        JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
        JOIN solutions s ON s.analysis_session_id = sas.id
        """,
    ),
    "Goal": (
        "Goal", "Motivation",
        """
        SELECT g.id, g.name, s.id AS solution_id
        FROM solution_goals g
        JOIN solution_problem_definitions spd ON g.problem_id = spd.id
        JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
        JOIN solutions s ON s.analysis_session_id = sas.id
        """,
    ),
    "Constraint": (
        "Constraint", "Motivation",
        """
        SELECT c.id, c.name, s.id AS solution_id
        FROM solution_constraints c
        JOIN solution_problem_definitions spd ON c.problem_id = spd.id
        JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
        JOIN solutions s ON s.analysis_session_id = sas.id
        """,
    ),
    "Requirement": (
        "Requirement", "Motivation",
        """
        SELECT r.id, r.name, s.id AS solution_id
        FROM solution_requirements r
        JOIN solutions s ON (
            r.solution_id = s.id
            OR (r.solution_id IS NULL AND r.problem_id IN (
                SELECT spd.id FROM solution_problem_definitions spd
                JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
                WHERE s.analysis_session_id = sas.id
            ))
        )
        WHERE r.name IS NOT NULL AND r.name != ''
        """,
    ),
    # direct solution_id
    "Assessment": (
        "Assessment", "Motivation",
        "SELECT id, risk_description AS name, solution_id FROM solution_risks",
    ),
    "Outcome": (
        "Outcome", "Motivation",
        "SELECT id, name, solution_id FROM solution_metrics",
    ),
    "Plateau": (
        "Plateau", "Implementation",
        "SELECT id, name, solution_id FROM solution_plateaus",
    ),
}


def _already_linked_sql(db, solution_id, ae_type, name):
    """True if (solution_id, ae_type, name) already has a join record."""
    row = db.session.execute(db.text(  # tenant-exempt: CLI command
    """
        SELECT 1 FROM solution_elements se
        JOIN archimate_elements ae ON se.archimate_element_id = ae.id
        WHERE se.solution_id = :sol AND ae.type = :t AND ae.name = :n
        LIMIT 1
    """), {"sol": solution_id, "t": ae_type, "n": name}).fetchone()
    return row is not None


@click.command("backfill-archimate-elements")
@click.option("--dry-run", is_flag=True, help="Show counts without modifying data")
@click.option("--motivation-only", is_flag=True, help="Skip ApplicationComponent/Capability")
@with_appcontext
def backfill_archimate_elements_command(dry_run, motivation_only):
    """Backfill ArchiMateElement for all solution entity types (ARCH-LINK-4)."""
    from app import db
    from app.models.archimate_core import ArchiMateElement
    from app.models.solution_element import SolutionElement

    if dry_run:
        click.echo("DRY RUN — no data will be modified.\n")

    total_created = 0

    # ── Legacy: ApplicationComponent and BusinessCapability ──────────────────
    if not motivation_only:
        from app.models.application_portfolio import ApplicationComponent
        from app.models.business_capabilities import BusinessCapability

        apps_missing = ApplicationComponent.query.filter(
            ApplicationComponent.archimate_element_id.is_(None)
        ).count()
        caps_missing = BusinessCapability.query.filter(
            BusinessCapability.archimate_element_id.is_(None)
        ).count()
        click.echo(f"ApplicationComponents missing element: {apps_missing}")
        click.echo(f"BusinessCapabilities missing element:  {caps_missing}")

        if not dry_run:
            batch_size = 100
            app_created = 0
            while True:
                batch = ApplicationComponent.query.filter(
                    ApplicationComponent.archimate_element_id.is_(None)
                ).limit(batch_size).all()
                if not batch:
                    break
                for app_comp in batch:
                    ae = ArchiMateElement(
                        name=app_comp.name,
                        type="ApplicationComponent",
                        layer="Application",
                        description=app_comp.description or f"Application: {app_comp.name}",
                    )
                    db.session.add(ae)
                    db.session.flush()
                    app_comp.archimate_element_id = ae.id
                    app_created += 1
                db.session.commit()
            click.echo(f"  → Created {app_created} ApplicationComponent elements")
            total_created += app_created

            cap_created = 0
            while True:
                batch = BusinessCapability.query.filter(
                    BusinessCapability.archimate_element_id.is_(None)
                ).limit(batch_size).all()
                if not batch:
                    break
                for cap in batch:
                    ae = ArchiMateElement(
                        name=cap.name,
                        type="Capability",
                        layer="Strategy",
                        description=cap.description or f"Capability: {cap.name}",
                    )
                    db.session.add(ae)
                    db.session.flush()
                    cap.archimate_element_id = ae.id
                    cap_created += 1
                db.session.commit()
            click.echo(f"  → Created {cap_created} Capability elements")
            total_created += cap_created

    # ── Motivation + Implementation layer entities ───────────────────────────
    click.echo("\nMotivation / Implementation entity backfill:")
    for key, (ae_type, ae_layer, sql) in _ENTITY_QUERIES.items():
        try:
            rows = db.session.execute(db.text(sql)).fetchall()  # tenant-exempt: CLI command
        except Exception as exc:
            click.echo(f"  {key:16s}: QUERY ERROR — {exc}", err=True)
            db.session.rollback()
            continue

        created = skipped = errors = 0
        for row in rows:
            name = ((row.name or "").strip() or f"{ae_type}-{row.id}")[:100]
            sol_id = row.solution_id
            if not sol_id:
                skipped += 1
                continue
            if _already_linked_sql(db, sol_id, ae_type, name):
                skipped += 1
                continue
            if not dry_run:
                try:
                    ae = ArchiMateElement(
                        name=name, type=ae_type, layer=ae_layer,
                        description=f"{ae_type}: {name}",
                    )
                    db.session.add(ae)
                    db.session.flush()
                    db.session.add(SolutionElement(
                        solution_id=sol_id,
                        archimate_element_id=ae.id,
                        layer=ae_layer,
                    ))
                    db.session.commit()
                except Exception as exc:
                    db.session.rollback()
                    errors += 1
                    continue
            created += 1

        action = "Would create" if dry_run else "Created    "
        click.echo(
            f"  {key:16s} ({ae_type:14s}): {action} {created:3d}  "
            f"skip {skipped:3d}  err {errors:2d}"
        )
        total_created += created

    action = "Would create" if dry_run else "Total created"
    click.echo(f"\n{action}: {total_created} ArchiMate elements")


def init_app(app):
    """Register CLI command with app."""
    app.cli.add_command(backfill_archimate_elements_command)
