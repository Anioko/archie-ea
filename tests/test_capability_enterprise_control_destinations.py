"""Rendered navigation contracts for capability and enterprise controls."""

from __future__ import annotations

from types import SimpleNamespace

from flask import render_template


def _render(app, template: str, **context) -> str:
    with app.test_request_context("/"):
        return render_template(template, **context)


def test_unmapped_capability_actions_open_existing_capability_workspaces(app):
    capability = SimpleNamespace(
        id=41,
        name="Order Management",
        description="",
        strategic_importance="high",
        domain_name="Operations",
        current_maturity_level=2,
        target_maturity_level=4,
        status="active",
    )

    html = _render(
        app,
        "capability_analysis/unmapped_capabilities.html",
        unmapped_capabilities=[capability],
        total_capabilities=1,
        mapped_capabilities=0,
        unmapped_count=1,
        mapping_coverage=0,
        domain_stats=[],
        priority_breakdown=[],
    )

    assert 'href="/enterprise/capability-map/mapping"' in html
    assert 'href="/enterprise/capability-map/capabilities#capability-41"' in html


def test_business_capability_cards_and_rows_navigate_to_canonical_capability_view(app):
    capability = SimpleNamespace(
        id=17,
        name="Customer Service",
        description="Handles customer requests",
        domain="Customer",
        strategic_importance="high",
        business_owner="Ada",
    )
    info = SimpleNamespace(
        color="blue",
        icon="users",
        name="Customer",
        description="Customer capabilities",
        subcategory_count=0,
        subcategories={},
    )
    classification = SimpleNamespace(subcategory_name="Engagement")

    html = _render(
        app,
        "business_capability/overview.html",
        classified_capabilities={
            "customer": SimpleNamespace(
                info=info,
                capabilities=[SimpleNamespace(capability=capability, classification=classification)],
            )
        },
        total_capabilities=1,
        classified_count=1,
    )

    assert 'href="/capability-map/simple#grouping-customer"' in html
    assert 'href="/enterprise/capability-map/capabilities#capability-17"' in html


def test_enterprise_plateau_controls_open_create_and_record_detail(app):
    plateau = SimpleNamespace(
        id=9,
        name="Target State",
        description="",
        status="Planned",
        target_date=None,
    )

    html = _render(app, "enterprise/plateaus.html", plateaus=[plateau])

    assert 'href="/architecture/implementation/Plateau/new"' in html
    assert 'href="/architecture/implementation/Plateau/9"' in html


def test_enterprise_gap_action_opens_the_gap_record(app):
    gap = SimpleNamespace(
        id=23,
        name="Coverage gap",
        description="",
        gap_type="coverage",
        priority="high",
        resolution_status="identified",
        impact="high",
    )

    html = _render(app, "enterprise/gap_analysis.html", gaps=[gap])

    assert 'href="/architecture/implementation/Gap/23"' in html
