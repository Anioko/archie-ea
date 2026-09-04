"""Rendered contracts for capability and enterprise screens.

These pages are analysis and register views.  A visible control must either
reach a workflow that operates on the same model or not be presented as an
action at all.
"""

from types import SimpleNamespace

from flask import render_template


def _render(app, template_name, **context):
    with app.test_request_context("/"):
        return render_template(template_name, **context)


def test_unmapped_capability_analysis_does_not_offer_cross_model_actions(app):
    """Unified-capability rows must not promise unsupported per-row actions.

    The production change this catches is reintroducing a Map Application or
    View Details control before a UnifiedCapability mapping/detail workflow
    exists.  Those controls previously passed a UnifiedCapability id to the
    BusinessCapability mapping flow, where it could identify a different row
    or return not found.
    """
    capability = SimpleNamespace(
        id=91,
        name="Claims Intake",
        strategic_importance="high",
        domain_name="Operations",
        current_maturity_level=2,
        target_maturity_level=4,
        status="active",
        description="",
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

    assert "Map Application" not in html
    assert "View Details" not in html


def test_plateau_register_does_not_advertise_unimplemented_create_or_detail_actions(app):
    """The register must not render controls without matching enterprise routes.

    The production change this catches is restoring the New Plateau or arrow
    buttons without implementing an enterprise create/detail workflow.  The
    available plateau API belongs to the roadmap experience, not this register.
    """
    plateau = SimpleNamespace(
        id=17,
        name="Target State",
        description="A stable transition state.",
        status="Planned",
        target_date="2027-03-31",
    )

    html = _render(app, "enterprise/plateaus.html", plateaus=[plateau])

    assert "New Plateau" not in html
    assert 'data-lucide="arrow-right"' not in html


def test_plateau_register_does_not_fabricate_missing_values(app):
    plateau = SimpleNamespace(
        id=18,
        name=None,
        description=None,
        status=None,
        target_date=None,
    )

    html = _render(app, "enterprise/plateaus.html", plateaus=[plateau])

    assert "TBD" not in html
    assert "Unnamed Plateau" not in html
    assert "No description" not in html
    assert "Target: —" in html
