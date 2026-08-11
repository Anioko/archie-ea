"""The Capability Frameworks page must be able to show a number.

``frameworks_overview()`` initialised ``framework_stats = {}``, ran a loop that
built a bind-parameter list and a params dict, threw both away, and passed the
still-empty dict to the template. Every card and every table row in
``capability_maturity/frameworks_overview.html`` is wrapped in
``{% if stats and stats[0] > 0 %}``, so all of them were suppressed: the page
rendered as a title, a "Framework Comparison" heading and a row of column
headers over nothing. There was no way to tell that from an empty model, and
the page's only action was a "Back to Overview" button pointing at itself.

The second defect is subtler and is why the averages are computed the way they
are. ``BusinessCapability.current_maturity_level`` is declared
``db.Column(db.Integer, default=1)``. It is therefore never NULL, and a
capability nobody has ever assessed is indistinguishable from one deliberately
assessed at level 1. Averaging the raw column would have reported "Avg Current
1.0" and a 20% progress bar for a model containing zero assessments — a
measurement that was never taken, presented as one. On the live dev database
all 529 capabilities read exactly like that: ``current_maturity_level`` is 1 for
every row and ``maturity_assessment_date`` is NULL for every row.

So "assessed" means ``maturity_assessment_date IS NOT NULL``, which every write
path that sets a level also stamps, and the averages are ``None`` — rendered as
an em dash — until something really has been assessed.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.modules.capabilities.routes.maturity_routes import _framework_stats
from app.utils.framework_classifier import FrameworkClassifier

# Categories that FrameworkClassifier maps onto the "customer" framework.
CUSTOMER_CATEGORIES = FrameworkClassifier.get_framework_categories("customer")


@pytest.fixture
def client(app):
    """Test client with ``@login_required`` off; restored because ``app`` is session-scoped."""
    previous = app.config.get("LOGIN_DISABLED", False)
    app.config["LOGIN_DISABLED"] = True
    try:
        yield app.test_client()
    finally:
        app.config["LOGIN_DISABLED"] = previous


def _capability(db_session, name, category, *, current=None, target=None, assessed=False):
    from app.models.business_capabilities import BusinessCapability

    cap = BusinessCapability(name=name, category=category, level=1)
    if current is not None:
        cap.current_maturity_level = current
    if target is not None:
        cap.target_maturity_level = target
    if assessed:
        cap.maturity_assessment_date = datetime.utcnow()
    db_session.add(cap)
    db_session.flush()
    return cap


# ---------------------------------------------------------------------------
# The statistics themselves
# ---------------------------------------------------------------------------


def test_capabilities_are_counted_into_their_framework(db_session, make_org, tenant_ctx):
    org = make_org("framework-count")
    with tenant_ctx(org.id):
        _capability(db_session, "Complaints Handling", CUSTOMER_CATEGORIES[0])
        _capability(db_session, "Case Triage", CUSTOMER_CATEGORIES[0])
        _capability(db_session, "Ledger Close", "Accounting")

        total, _with_current, _with_target, _assessed, _avg_c, _avg_t = _framework_stats(
            CUSTOMER_CATEGORIES
        )

    assert total == 2, (
        "the customer framework should count only the two capabilities whose "
        f"category is one of {CUSTOMER_CATEGORIES}"
    )


def test_category_match_is_case_insensitive(db_session, make_org, tenant_ctx):
    """Imported data does not preserve the capitalisation of an authored list."""
    org = make_org("framework-case")
    with tenant_ctx(org.id):
        _capability(db_session, "Retention Desk", CUSTOMER_CATEGORIES[0].lower())
        total = _framework_stats(CUSTOMER_CATEGORIES)[0]

    assert total == 1


def test_unassessed_capabilities_do_not_produce_an_average(db_session, make_org, tenant_ctx):
    """The regression that matters: a default of 1 must not read as a measurement.

    Both rows below carry ``current_maturity_level = 1`` exactly as the column
    default leaves them, and neither has been assessed. Averaging the column
    would report 1.0; the honest answer is that there is no average.
    """
    org = make_org("framework-unassessed")
    with tenant_ctx(org.id):
        _capability(db_session, "Onboarding", CUSTOMER_CATEGORIES[0])
        _capability(db_session, "Offboarding", CUSTOMER_CATEGORIES[0])

        total, with_current, with_target, assessed, avg_current, avg_target = (
            _framework_stats(CUSTOMER_CATEGORIES)
        )

    assert total == 2
    assert assessed == 0
    assert with_current == 0, "an unstamped default is not an assessment"
    assert with_target == 0
    assert avg_current is None, (
        "current_maturity_level defaults to 1, so averaging it over unassessed "
        "rows fabricates a maturity score of 1.0 that nobody measured"
    )
    assert avg_target is None


def test_assessed_capabilities_average_only_over_the_assessed(
    db_session, make_org, tenant_ctx
):
    org = make_org("framework-assessed")
    with tenant_ctx(org.id):
        _capability(
            db_session, "Service Desk", CUSTOMER_CATEGORIES[0],
            current=2, target=4, assessed=True,
        )
        _capability(
            db_session, "Field Service", CUSTOMER_CATEGORIES[0],
            current=4, target=4, assessed=True,
        )
        # Present in the framework, never assessed — must not drag the average
        # down towards its default of 1.
        _capability(db_session, "Loyalty", CUSTOMER_CATEGORIES[0])

        total, with_current, with_target, assessed, avg_current, avg_target = (
            _framework_stats(CUSTOMER_CATEGORIES)
        )

    assert (total, assessed, with_current, with_target) == (3, 2, 2, 2)
    assert avg_current == pytest.approx(3.0)
    assert avg_target == pytest.approx(4.0)


def test_a_framework_with_no_categories_is_not_an_error():
    assert _framework_stats([]) == (0, 0, 0, 0, None, None)


# ---------------------------------------------------------------------------
# What the route hands the template
# ---------------------------------------------------------------------------


def test_route_populates_stats_for_every_framework(app, client):
    """The original bug: the template got ``{}`` and suppressed the whole page."""
    from unittest.mock import patch

    from app.modules.capabilities.routes import maturity_routes as mod

    captured = {}

    def _fake_render(template_name, **context):
        captured["template"] = template_name
        captured.update(context)
        return ""

    with patch.object(mod, "render_template", _fake_render):
        resp = client.get("/capability-maturity/frameworks")

    assert resp.status_code == 200, (
        "the overview redirects away on any exception, so a non-200 here means "
        "the page failed to build rather than rendered empty"
    )
    assert captured["template"] == "capability_maturity/frameworks_overview.html"

    stats = captured["framework_stats"]
    assert stats, "framework_stats was empty — every card and row is suppressed"
    assert set(stats) == set(captured["all_frameworks"]), (
        "a framework with no entry in framework_stats renders as nothing at all"
    )
    for key, row in stats.items():
        assert len(row) == 6, f"{key}: the template indexes stats[0] through stats[5]"
        assert isinstance(row[0], int)


def test_page_reports_when_no_capability_sits_in_any_framework(app, client):
    """The empty state has to be distinguishable from the old blank page."""
    from unittest.mock import patch

    from app.modules.capabilities.routes import maturity_routes as mod

    captured = {}

    with patch.object(mod, "_framework_stats", lambda _c: (0, 0, 0, 0, None, None)):
        with patch.object(
            mod, "render_template",
            lambda t, **c: (captured.update(c), "")[1],
        ):
            resp = client.get("/capability-maturity/frameworks")

    assert resp.status_code == 200
    assert captured["any_framework_populated"] is False


# ---------------------------------------------------------------------------
# The CSV import must mark what it assessed
# ---------------------------------------------------------------------------


def test_csv_import_stamps_the_assessment_date(app, db_session, make_org, tenant_ctx):
    """Without the stamp, a CSV-assessed capability still reads as unassessed.

    Logged in as a real user of the organisation rather than through
    LOGIN_DISABLED: the import matches capabilities by name against a
    tenant-scoped query, so a request with no authenticated user has no
    ``g.current_org_id``, matches nothing, and the test passes or fails
    depending on what ran before it.
    """
    import io
    import uuid

    from app.models.business_capabilities import BusinessCapability
    from app.models.user import User

    org = make_org(f"framework-csv-{uuid.uuid4().hex[:6]}")
    name = f"Quote Management {uuid.uuid4().hex[:8]}"
    with tenant_ctx(org.id):
        cap = _capability(db_session, name, CUSTOMER_CATEGORIES[0])
        assessor = User(
            email=f"assessor-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Assessor",
            last_name="Tester",
            organization_id=org.id,
            confirmed=True,
            enterprise_role="business_architect",
        )
        db_session.add(assessor)
        db_session.commit()
        cap_id, assessor_id = cap.id, assessor.id

    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["_user_id"] = str(assessor_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)

    payload = f"capability_name,current_maturity,target_maturity\n{name},3,5\n".encode()
    resp = test_client.post(
        "/capability-maturity/import-csv",
        data={"file": (io.BytesIO(payload), "maturity.csv")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200, resp.data[:400]
    assert resp.get_json()["updated"] == 1, resp.get_json()

    db_session.expire_all()
    refreshed = db_session.get(BusinessCapability, cap_id)
    assert refreshed.current_maturity_level == 3
    assert refreshed.maturity_assessment_date is not None, (
        "the import set a level without recording that an assessment happened, "
        "so the frameworks overview would still count this row as unassessed"
    )
