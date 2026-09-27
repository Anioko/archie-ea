"""H7: /applications/rationalization showed "Plan: 2/0 (0%)" -- a numerator
bigger than its denominator. Root cause: the Plan stage's denominator was
stats.time_scored_count (from ApplicationRationalizationScore), a table with
no subset relationship to stats.consolidation_count (from
ConsolidationListEntry) -- two independent populations compared as if one
contained the other. Fixed in
app/templates/applications/rationalization/dashboard.html by sharing
total_apps as every stage's denominator, matching Detect and Score, and in
app/modules/applications/routes/rationalization_api_routes.py by logging a
warning if a stage count ever still exceeds total_apps.
"""

from __future__ import annotations

import re

from flask import render_template


def _render(app, stats):
    with app.test_request_context("/applications/rationalization"):
        return render_template(
            "applications/rationalization/dashboard.html",
            stats=stats,
            groups=[],
            runs=[],
            latest_run=None,
            currency_symbol="£",
            active_tab="dashboard",
            data_quality=None,
            insufficient_count=0,
        )


def _plan_fraction(body: str) -> tuple[int, int]:
    # The Plan step prints "<count>/<total> (<pct>%)" right after its label.
    match = re.search(r"Plan</span>\s*<span[^>]*>(\d+)/(\d+)", body)
    assert match, "could not find the Plan step's count/total in rendered output"
    return int(match.group(1)), int(match.group(2))


def test_plan_fraction_never_has_numerator_exceeding_denominator(app):
    """The exact reported scenario: consolidation entries exist (2) but zero
    applications have been TIME-scored yet -- the old code compared these two
    unrelated counts directly and produced 2/0."""
    stats = {
        "total_applications": 50,
        "duplicate_groups": 3,
        "estimated_savings": 1000.0,
        "consolidation_count": 2,
        "time_scored_count": 0,
        "roadmap_count": 1,
    }
    body = _render(app, stats)
    count, total = _plan_fraction(body)
    assert total >= count, f"Plan rendered {count}/{total} -- numerator exceeds denominator"
    assert total == 50, "Plan's denominator should be total_applications (shared with Detect/Score)"


def test_plan_fraction_stays_sane_across_arbitrary_counts(app):
    for consolidation_count, time_scored_count, total_apps in [
        (0, 0, 10),
        (5, 5, 10),
        (10, 0, 10),
        (1, 100, 10),
    ]:
        stats = {
            "total_applications": total_apps,
            "duplicate_groups": 0,
            "estimated_savings": 0.0,
            "consolidation_count": consolidation_count,
            "time_scored_count": time_scored_count,
            "roadmap_count": 0,
        }
        body = _render(app, stats)
        count, total = _plan_fraction(body)
        assert total == total_apps
        assert count == consolidation_count
