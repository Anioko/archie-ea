"""The data-models page must show measured counts, not a silent zero.

`enterprise.data_models` and `enterprise.data_architecture_dashboard` render the
SAME template, `enterprise/data_architecture_dashboard.html`, whose tiles read
`conceptual_count` / `logical_count` / `physical_count`. `data_models` passed
`conceptual_models` / `logical_models` / `physical_models` instead — three lists
the template never reads — so every tile fell through `value=... or 0` and
rendered **0 regardless of the real counts**.

That is the failure CLAUDE.md singles out: a `0` meaning "not computed" is
indistinguishable from a measured zero, and the user cannot tell the difference.

The route is asserted at the render boundary rather than through a rendered
page: this repo deliberately avoids rendering full `layouts/admin_base.html`
pages via test_client (see the note in tests/test_ba_tenant_and_authz.py), so
the template context is the honest seam. The counts asserted are real values
read back from the database, not stubs.
"""

from unittest.mock import patch

import pytest

TEMPLATE = "enterprise/data_architecture_dashboard.html"

# The variables the template's three metric tiles actually read.
TILE_VARS = ("conceptual_count", "logical_count", "physical_count")


@pytest.fixture
def one_of_each(db_session):
    """Insert one model of each kind so a correct count is non-zero."""
    from app.models.all_missing_models import (
        ConceptualDataModel,
        LogicalDataModel,
        PhysicalDataModel,
    )

    db_session.add(ConceptualDataModel(name="Customer Domain Model"))
    db_session.add(LogicalDataModel(name="Customer Logical Model"))
    db_session.add(PhysicalDataModel(name="Customer Physical Model"))
    db_session.flush()


def _render_context(app, view_name):
    """Call a view and capture the kwargs it hands to render_template.

    ``LOGIN_DISABLED`` is the documented Flask-Login test switch; without it the
    ``@login_required`` wrapper returns a redirect and the view body — the thing
    under test — never runs. Restored afterwards because ``app`` is session-scoped.
    """
    captured = {}

    def _fake_render(template_name, **context):
        captured["template"] = template_name
        captured.update(context)
        return ""

    from app.routes import unified_enterprise_routes as mod

    view = getattr(mod, view_name)
    previous = app.config.get("LOGIN_DISABLED", False)
    app.config["LOGIN_DISABLED"] = True
    try:
        with patch.object(mod, "render_template", _fake_render):
            with app.test_request_context("/"):
                view()
    finally:
        app.config["LOGIN_DISABLED"] = previous
    return captured


def test_data_models_page_passes_the_counts_the_template_reads(app, one_of_each):
    """`data_models` must supply the tile variables, not unread lists."""
    context = _render_context(app, "data_models")

    assert context["template"] == TEMPLATE
    missing = [v for v in TILE_VARS if v not in context]
    assert not missing, (
        "data_models does not pass %s; the template reads those and falls back "
        "to `or 0`, so every tile renders 0 no matter the real count" % (missing,)
    )
    for var in TILE_VARS:
        assert context[var] == 1, f"{var} was {context[var]!r}, expected the measured 1"


def test_data_architecture_dashboard_still_passes_counts(app, one_of_each):
    """The sibling route already worked; pin it so a shared-template edit can't break it."""
    context = _render_context(app, "data_architecture_dashboard")

    assert context["template"] == TEMPLATE
    for var in TILE_VARS:
        assert context[var] == 1, f"{var} was {context[var]!r}, expected the measured 1"
