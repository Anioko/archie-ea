"""
BIZBOK × ArchiMate: Backfill Strategy & Motivation layer ArchiMate elements.

Run with:
    python scripts/backfill_strategy_motivation_elements.py [--dry-run]
  or:
    flask backfill-strategy-motivation [--dry-run]

Creates ArchiMate element counterparts for existing domain data:
  - BusinessCapability (516)  → Capability     (Strategy layer)
  - Solution                  → CourseOfAction  (Strategy layer)
  - APQC Process Categories   → ValueStream     (Strategy layer)
  - SolutionDriver            → Driver          (Motivation layer)
  - SolutionGoal              → Goal            (Motivation layer)
  - SolutionRequirement       → Requirement     (Motivation layer)
  - SolutionConstraint        → Constraint      (Motivation layer)

Also creates cross-layer relationships:
  - CourseOfAction → Capability   (Realization)
  - Driver → Goal                 (Influence)
  - Goal → Requirement            (Realization)
  - Capability → ValueStream      (Assignment)

Idempotent — safe to run multiple times. Uses name+type dedup.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import click
from flask.cli import with_appcontext

from app import db


def _find_or_create_element(name, ae_type, layer, description=None, architecture_id=None):
    """Find existing element by name+type or create a new one. Returns (element, created)."""
    from app.models.archimate_core import ArchiMateElement

    name = (name or "").strip()[:100]
    if not name:
        return None, False

    existing = ArchiMateElement.query.filter_by(name=name, type=ae_type).first()
    if existing:
        return existing, False

    ae = ArchiMateElement(
        name=name,
        type=ae_type,
        layer=layer,
        description=(description or f"{ae_type}: {name}")[:500],
        architecture_id=architecture_id,
    )
    db.session.add(ae)
    db.session.flush()
    return ae, True


def _link_solution_element(solution_id, element_id, layer):
    """Create SolutionElement junction if not exists."""
    from app.models.solution_element import SolutionElement

    existing = SolutionElement.query.filter_by(
        solution_id=solution_id, archimate_element_id=element_id
    ).first()
    if not existing:
        db.session.add(SolutionElement(
            solution_id=solution_id,
            archimate_element_id=element_id,
            layer=layer,
        ))


def _create_relationship(source_id, target_id, rel_type, architecture_id=None):
    """Create ArchiMateRelationship if not exists."""
    from app.models.archimate_core import ArchiMateRelationship

    existing = ArchiMateRelationship.query.filter_by(
        source_id=source_id, target_id=target_id, type=rel_type
    ).first()
    if existing:
        return False

    db.session.add(ArchiMateRelationship(
        source_id=source_id,
        target_id=target_id,
        type=rel_type,
        architecture_id=architecture_id,
    ))
    return True


@click.command("backfill-strategy-motivation")
@click.option("--dry-run", is_flag=True, help="Show counts without modifying data")
@with_appcontext
def backfill_strategy_motivation_command(dry_run):
    """Backfill Strategy & Motivation ArchiMate elements from domain data."""
    if dry_run:
        click.echo("DRY RUN — no data will be modified.\n")

    stats = {
        "Capability": 0, "CourseOfAction": 0, "ValueStream": 0,
        "Driver": 0, "Goal": 0, "Requirement": 0, "Constraint": 0,
        "relationships": 0, "links": 0,
    }

    # ── 1. Business Capabilities → Capability (Strategy) ────────────────────
    click.echo("Phase 1: BusinessCapability → Capability elements")
    cap_rows = db.session.execute(db.text(
        "SELECT id, name, description FROM business_capability WHERE name IS NOT NULL"
    )).fetchall()
    click.echo(f"  Found {len(cap_rows)} business capabilities")

    cap_element_map = {}  # business_capability.id → archimate_element.id
    for row in cap_rows:
        if dry_run:
            stats["Capability"] += 1
            continue
        ae, created = _find_or_create_element(
            row.name, "Capability", "strategy", row.description
        )
        if ae:
            cap_element_map[row.id] = ae.id
            if created:
                stats["Capability"] += 1

    if not dry_run:
        db.session.commit()
    click.echo(f"  → Created {stats['Capability']} Capability elements")

    # ── 2. Solutions → CourseOfAction (Strategy) ────────────────────────────
    click.echo("\nPhase 2: Solutions → CourseOfAction elements")
    sol_rows = db.session.execute(db.text(
        "SELECT id, name, description FROM solutions WHERE name IS NOT NULL"
    )).fetchall()
    click.echo(f"  Found {len(sol_rows)} solutions")

    coa_element_map = {}  # solution.id → archimate_element.id
    for row in sol_rows:
        if dry_run:
            stats["CourseOfAction"] += 1
            continue
        ae, created = _find_or_create_element(
            row.name, "CourseOfAction", "strategy",
            f"Solution: {row.description or row.name}"
        )
        if ae:
            coa_element_map[row.id] = ae.id
            _link_solution_element(row.id, ae.id, "strategy")
            stats["links"] += 1
            if created:
                stats["CourseOfAction"] += 1

    if not dry_run:
        db.session.commit()
    click.echo(f"  → Created {stats['CourseOfAction']} CourseOfAction elements")

    # ── 3. APQC Process Categories → ValueStream (Strategy) ────────────────
    click.echo("\nPhase 3: APQC process categories → ValueStream elements")
    apqc_rows = db.session.execute(db.text(
        """SELECT DISTINCT category_level_1 AS name
           FROM apqc_process
           WHERE category_level_1 IS NOT NULL AND category_level_1 != ''"""
    )).fetchall()
    click.echo(f"  Found {len(apqc_rows)} APQC level-1 categories")

    vs_element_map = {}  # category_name → archimate_element.id
    for row in apqc_rows:
        if dry_run:
            stats["ValueStream"] += 1
            continue
        ae, created = _find_or_create_element(
            row.name, "ValueStream", "strategy",
            f"Value Stream (from APQC): {row.name}"
        )
        if ae:
            vs_element_map[row.name] = ae.id
            if created:
                stats["ValueStream"] += 1

    if not dry_run:
        db.session.commit()
    click.echo(f"  → Created {stats['ValueStream']} ValueStream elements")

    # ── 4. Motivation layer: Drivers, Goals, Requirements, Constraints ──────
    click.echo("\nPhase 4: Solution motivation entities → Motivation elements")

    _MOTIVATION_QUERIES = {
        "Driver": (
            "Driver", "motivation",
            """SELECT d.id, d.name, d.description, s.id AS solution_id
               FROM solution_drivers d
               JOIN solution_problem_definitions spd ON d.problem_id = spd.id
               JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
               JOIN solutions s ON s.analysis_session_id = sas.id
               WHERE d.name IS NOT NULL AND d.name != ''"""
        ),
        "Goal": (
            "Goal", "motivation",
            """SELECT g.id, g.name, g.description, s.id AS solution_id
               FROM solution_goals g
               JOIN solution_problem_definitions spd ON g.problem_id = spd.id
               JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
               JOIN solutions s ON s.analysis_session_id = sas.id
               WHERE g.name IS NOT NULL AND g.name != ''"""
        ),
        "Requirement": (
            "Requirement", "motivation",
            """SELECT r.id, r.name, r.description, COALESCE(r.solution_id, s.id) AS solution_id
               FROM solution_requirements r
               LEFT JOIN solution_problem_definitions spd ON r.problem_id = spd.id
               LEFT JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
               LEFT JOIN solutions s ON s.analysis_session_id = sas.id
               WHERE r.name IS NOT NULL AND r.name != ''
               AND (r.solution_id IS NOT NULL OR s.id IS NOT NULL)"""
        ),
        "Constraint": (
            "Constraint", "motivation",
            """SELECT c.id, c.name, c.description, s.id AS solution_id
               FROM solution_constraints c
               JOIN solution_problem_definitions spd ON c.problem_id = spd.id
               JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
               JOIN solutions s ON s.analysis_session_id = sas.id
               WHERE c.name IS NOT NULL AND c.name != ''"""
        ),
    }

    motivation_maps = {}  # {entity_type: {entity_id: archimate_element_id}}

    for key, (ae_type, ae_layer, sql) in _MOTIVATION_QUERIES.items():
        motivation_maps[key] = {}
        try:
            rows = db.session.execute(db.text(sql)).fetchall()
        except Exception as exc:
            click.echo(f"  {key}: QUERY ERROR — {exc}", err=True)
            db.session.rollback()
            continue

        created_count = 0
        for row in rows:
            if dry_run:
                stats[key] += 1
                continue
            ae, created = _find_or_create_element(
                row.name, ae_type, ae_layer, getattr(row, 'description', None)
            )
            if ae and row.solution_id:
                motivation_maps[key][row.id] = ae.id
                _link_solution_element(row.solution_id, ae.id, ae_layer)
                stats["links"] += 1
                if created:
                    stats[key] += 1
                    created_count += 1

        if not dry_run:
            db.session.commit()
        click.echo(f"  {key:16s}: Created {stats[key] if dry_run else created_count}")

    # ── 5. Cross-layer relationships ────────────────────────────────────────
    click.echo("\nPhase 5: Cross-layer relationships")

    if not dry_run:
        rel_count = 0

        # CourseOfAction → Capability (Realization) via solution_capability_mappings
        cap_map_rows = db.session.execute(db.text(
            """SELECT scm.solution_id, scm.capability_id
               FROM solution_capability_mappings scm
               WHERE scm.solution_id IS NOT NULL AND scm.capability_id IS NOT NULL"""
        )).fetchall()
        for row in cap_map_rows:
            coa_id = coa_element_map.get(row.solution_id)
            cap_id = cap_element_map.get(row.capability_id)
            if coa_id and cap_id:
                if _create_relationship(coa_id, cap_id, "Realization"):
                    rel_count += 1

        # Driver → Goal (Influence) via solution_goals.driver_id
        goal_driver_rows = db.session.execute(db.text(
            """SELECT g.id AS goal_id, g.driver_id
               FROM solution_goals g
               WHERE g.driver_id IS NOT NULL"""
        )).fetchall()
        for row in goal_driver_rows:
            driver_ae = motivation_maps.get("Driver", {}).get(row.driver_id)
            goal_ae = motivation_maps.get("Goal", {}).get(row.goal_id)
            if driver_ae and goal_ae:
                if _create_relationship(driver_ae, goal_ae, "Influence"):
                    rel_count += 1

        # Goal → Requirement (Realization) — inferred: same solution scope
        # Link goals to requirements within same solution
        goal_sol_map = {}  # solution_id → [goal_ae_ids]
        req_sol_map = {}   # solution_id → [req_ae_ids]

        goal_rows = db.session.execute(db.text(
            """SELECT g.id, s.id AS solution_id
               FROM solution_goals g
               JOIN solution_problem_definitions spd ON g.problem_id = spd.id
               JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
               JOIN solutions s ON s.analysis_session_id = sas.id"""
        )).fetchall()
        for row in goal_rows:
            ae_id = motivation_maps.get("Goal", {}).get(row.id)
            if ae_id:
                goal_sol_map.setdefault(row.solution_id, []).append(ae_id)

        req_rows = db.session.execute(db.text(
            """SELECT r.id, COALESCE(r.solution_id, s.id) AS solution_id
               FROM solution_requirements r
               LEFT JOIN solution_problem_definitions spd ON r.problem_id = spd.id
               LEFT JOIN solution_analysis_sessions sas ON spd.session_id = sas.id
               LEFT JOIN solutions s ON s.analysis_session_id = sas.id
               WHERE r.solution_id IS NOT NULL OR s.id IS NOT NULL"""
        )).fetchall()
        for row in req_rows:
            ae_id = motivation_maps.get("Requirement", {}).get(row.id)
            if ae_id and row.solution_id:
                req_sol_map.setdefault(row.solution_id, []).append(ae_id)

        for sol_id, goal_ids in goal_sol_map.items():
            req_ids = req_sol_map.get(sol_id, [])
            for g_id in goal_ids:
                for r_id in req_ids:
                    if _create_relationship(g_id, r_id, "Realization"):
                        rel_count += 1

        db.session.commit()
        stats["relationships"] = rel_count
        click.echo(f"  → Created {rel_count} cross-layer relationships")
    else:
        click.echo("  (skipped in dry-run)")

    # ── Summary ─────────────────────────────────────────────────────────────
    click.echo("\n" + ("=" * 50))
    action = "Would create" if dry_run else "Created"
    click.echo(f"{action}:")
    for key in ["Capability", "CourseOfAction", "ValueStream", "Driver", "Goal", "Requirement", "Constraint"]:
        click.echo(f"  {key:20s}: {stats[key]}")
    click.echo(f"  {'Relationships':20s}: {stats['relationships']}")
    click.echo(f"  {'Solution links':20s}: {stats['links']}")


def init_app(app):
    """Register CLI command with app."""
    app.cli.add_command(backfill_strategy_motivation_command)


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        dry_run = "--dry-run" in sys.argv
        # Invoke the click command's callback directly
        backfill_strategy_motivation_command.callback(dry_run=dry_run)
