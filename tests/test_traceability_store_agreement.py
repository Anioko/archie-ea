"""ADR-0008 store-agreement for /architecture/traceability.

The page had three surfaces counting three different stores: the pivot-type
dropdown and the cross-layer matrix read the ArchiMate backbone
(archimate_elements + archimate_relationships), while the coverage tiles read
the enterprise DOMAIN tables (motivation.Driver, requirements.Requirement, …).
A tenant whose motivation entities exist only as ArchiMate elements therefore
saw the dropdown count 3 Drivers while the coverage tile read "0 of 0".

get_archimate_gap_analysis() makes the coverage tiles read the SAME store the
matrix reads, so the numbers agree. These tests pin that agreement.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _el(db_session, name, type_, layer):
    from app.models.archimate_core import ArchiMateElement

    e = ArchiMateElement(name=name, type=type_, layer=layer)
    db_session.add(e)
    db_session.flush()
    return e


def _rel(db_session, src, tgt, rtype="RealizationRelationship"):
    from app.models.archimate_core import ArchiMateRelationship

    r = ArchiMateRelationship(source_id=src.id, target_id=tgt.id, type=rtype)
    db_session.add(r)
    db_session.flush()
    return r


def test_archimate_gap_analysis_counts_the_backbone(make_org, tenant_ctx, db_session):
    from app.services.archimate_traceability_service import (
        get_archimate_gap_analysis,
        ArchiMateTraceabilityService,
    )

    org = make_org("trc")
    tag = uuid.uuid4().hex[:6]
    with tenant_ctx(org.id):
        driver = _el(db_session, f"Drv {tag}", "Driver", "Motivation")
        goal = _el(db_session, f"Goal {tag}", "Goal", "Motivation")
        orphan_goal = _el(db_session, f"LoneGoal {tag}", "Goal", "Motivation")
        cap = _el(db_session, f"Cap {tag}", "Capability", "Strategy")
        app_el = _el(db_session, f"App {tag}", "ApplicationComponent", "Application")

        # Driver -> Goal (connected); Capability -> Application (connected).
        _rel(db_session, driver, goal)
        _rel(db_session, cap, app_el)
        db_session.flush()

        gap = get_archimate_gap_analysis()

        cov = gap["coverage"]
        # Driver is connected to a Goal.
        assert cov["drivers_with_goals"] == {"count": 1, "total": 1}
        # Two goals exist, neither reaches a Requirement -> 0 of 2.
        assert cov["goals_with_requirements"]["total"] == 2
        assert cov["goals_with_requirements"]["count"] == 0
        # Capability is connected to an application.
        assert cov["capabilities_with_apps"] == {"count": 1, "total": 1}

        # Orphan lists carry ArchiMateElement ids (used by the element links).
        orphan_goal_ids = {g["id"] for g in gap["orphaned_goals"]}
        assert goal.id in orphan_goal_ids
        assert orphan_goal.id in orphan_goal_ids
        assert not gap["orphaned_drivers"]

        # Store agreement: the matrix (same backbone) shows the app aligned to
        # the capability, so a non-zero coverage tile can never sit above an
        # empty matrix for this tenant.
        matrix = ArchiMateTraceabilityService().get_full_matrix(
            pivot_type="ApplicationComponent"
        )
        app_row = next(r for r in matrix if r["application"]["id"] == app_el.id)
        strategy_ids = {e["id"] for e in app_row["strategy"]}
        assert cap.id in strategy_ids


def test_gap_analysis_empty_tenant_is_all_zero(make_org, tenant_ctx, db_session):
    from app.services.archimate_traceability_service import get_archimate_gap_analysis

    org = make_org("trcempty")
    with tenant_ctx(org.id):
        gap = get_archimate_gap_analysis()
        for key in (
            "drivers_with_goals",
            "goals_with_requirements",
            "requirements_with_capabilities",
            "capabilities_with_apps",
        ):
            assert gap["coverage"][key] == {"count": 0, "total": 0}
        assert gap["orphaned_drivers"] == []
