"""Routes for the Business Architecture practice landing page.

Blueprint: business_architecture_bp, url_prefix="/business-architecture".
Index endpoint: ``business_architecture.index``.

Why this page exists
--------------------
A business architect evaluated Archie and reported that capability maturity,
gap analysis and strategy-to-execution "do not exist". An audit
(``scripts/ba_output_audit.py``) found 350 routes already serving the twelve
business-architecture outputs he listed. He could not find them because the
shell has five generic zones (Home / My work / Library / Governance / Admin)
and the twelve outputs are scattered across them. This page is the front
door: one screen, twelve outputs, each stated as the question it answers for
a business leader rather than as a description of a screen.

Nothing here computes or displays a statistic — every number on this page
would be a number about the data, not the practice, and the ``fabricated-data``
gate is at 0. The page is navigation, and only navigation.

Endpoint safety
---------------
Every endpoint named in ``BA_OUTPUTS`` was resolved against
``app.view_functions`` on a booted app before being listed here, and the
template renders each link **only** when the endpoint is present at request
time (``{% if ... in flask.current_app.view_functions %}``). Blueprints in
this repo register non-fatally, so an unguarded ``url_for`` to a module that
failed to import would raise ``BuildError`` and 500 every page that renders
the sidebar. When a card's primary endpoint is absent the template says
"Not yet available" rather than linking somewhere misleading.
"""

import logging

from flask import Blueprint, render_template
from flask_login import login_required

logger = logging.getLogger(__name__)

business_architecture_bp = Blueprint(
    "business_architecture", __name__, url_prefix="/business-architecture"
)


def _output(number, title, question, icon, endpoint, action, extras=()):
    """One of the twelve outputs.

    ``question`` is what the output answers for a business leader — not a
    description of the screen it opens.
    """
    return {
        "number": number,
        "title": title,
        "question": question,
        "icon": icon,
        "endpoint": endpoint,
        "action": action,
        "extras": [{"label": lbl, "endpoint": ep} for lbl, ep in extras],
    }


# Three groups of four. The grouping is the practice's own order of work:
# describe the business, judge how well it runs, decide where it goes next.
BA_OUTPUTS = [
    {
        "group": "What the business is",
        "blurb": "The structural picture — what we do, how value reaches "
                 "a customer, what we sell, and who owns it.",
        "outputs": [
            _output(
                1,
                "Capability maps",
                "What do we actually do as a business, independent of who does it or which system supports it?",
                "map",
                "capability_map.index",
                "Open capability map",
                (("Strategy-layer capability tree", "archimate_layers.strategy_capabilities_tree"),),
            ),
            _output(
                3,
                "Value stream maps",
                "How does value reach a customer end to end, and which capability carries each stage?",
                "waypoints",
                "value_stream.index",
                "Open value streams",
                (("Value streams in the strategy layer", "archimate_layers.strategy_value_streams"),),
            ),
            _output(
                10,
                "Products & services",
                "What do we offer to the market, and what has to work for each offering to be delivered?",
                "package",
                "archimate_layers.business_products",
                "Open product & service catalogue",
                (
                    ("Business & operating model canvas", "business_model.index"),
                    ("Product roadmap", "roadmap_outcome.product_roadmap_page"),
                ),
            ),
            _output(
                4,
                "Organisation & ownership",
                "Who is accountable for each part of the business, and where does ownership fall between the gaps?",
                "network",
                "organization.index",
                "Open organisation view",
                (("Enterprise RACI matrix", "organization.raci"),),
            ),
        ],
    },
    {
        "group": "How well it runs",
        "blurb": "The judgement picture — how mature each capability is, "
                 "what the numbers say, what information we hold, and who cares.",
        "outputs": [
            _output(
                2,
                "Capability maturity",
                "Which capabilities are strong enough to build on, and which will fail us under load?",
                "thermometer",
                "maturity_management.maturity_heatmap",
                "Open maturity heatmap",
                (("Maturity frameworks & scoring models", "maturity_management.frameworks_overview"),),
            ),
            _output(
                9,
                "KPI & metric dashboards",
                "Are the outcomes we committed to actually moving, and by how much?",
                "gauge",
                "dashboard.health_scorecard",
                "Open health scorecard",
                (
                    ("Capability health", "strategic.capability_health"),
                    ("Outcomes register", "archimate_layers.motivation_outcomes"),
                ),
            ),
            _output(
                5,
                "Information & data maps",
                "What information does the business run on, where does it live, and where does it flow?",
                "database",
                "data_architecture.data_architecture_dashboard",
                "Open data architecture",
                (("Business meanings & concepts", "archimate_layers.motivation_meanings"),),
            ),
            _output(
                7,
                "Stakeholder maps",
                "Who has a stake in a change, what do they each want from it, and who must be brought along?",
                "users",
                "stakeholder_map.stakeholder_map_page",
                "Open stakeholder map",
                (
                    ("Stakeholder register", "archimate_layers.motivation_stakeholders"),
                    ("Drivers behind the stakes", "archimate_layers.motivation_drivers"),
                ),
            ),
        ],
    },
    {
        "group": "Where it goes next",
        "blurb": "The forward picture — the line from a strategic intent to "
                 "the work that delivers it, and the rules it must respect.",
        "outputs": [
            _output(
                6,
                "Strategy to execution",
                "Can I trace a board-level goal down to the specific work funded to deliver it?",
                "git-branch",
                "enterprise.strategic_planning_dashboard",
                "Open strategic planning",
                (
                    ("Traceability matrix", "architect_ui.traceability_matrix"),
                    ("Motivation model (goals, drivers, outcomes)", "architect_ui.motivation_view"),
                    ("Courses of action", "archimate_layers.strategy_courses_of_action"),
                ),
            ),
            _output(
                12,
                "Gap analysis & roadmaps",
                "What stands between where we are and where we said we would be, and in what order do we close it?",
                "git-compare",
                "enterprise.gap_analysis",
                "Open gap analysis",
                (
                    ("Capability roadmap", "main.capability_roadmap"),
                    ("Strategic roadmap", "main.strategic_roadmap"),
                ),
            ),
            _output(
                8,
                "Initiative & project alignment",
                "Is every funded initiative attached to a capability we decided to improve — and what is unattached?",
                "layout-dashboard",
                "portfolio.index",
                "Open portfolio",
                (
                    ("Strategic initiatives", "unified_low_priority.strategic_initiatives"),
                    ("Work packages", "enterprise.work_packages"),
                ),
            ),
            _output(
                11,
                "Policies, rules & governance",
                "What rules constrain a design decision, and can we show they were applied?",
                "gavel",
                "governance.dashboard",
                "Open governance",
                (
                    ("Architecture principles", "governance.principles"),
                    ("Architecture decisions", "arch_decisions.list_decisions"),
                    ("Policy monitoring", "unified_low_priority.policy_monitoring_dashboard"),
                ),
            ),
        ],
    },
]


def iter_endpoints():
    """Every endpoint this page can link to — used by the tests."""
    for group in BA_OUTPUTS:
        for output in group["outputs"]:
            yield output["endpoint"]
            for extra in output["extras"]:
                yield extra["endpoint"]


@business_architecture_bp.route("/")
@login_required
def index():
    """The business-architecture practice landing page."""
    return render_template(
        "business_architecture/index.html",
        ba_groups=BA_OUTPUTS,
    )
