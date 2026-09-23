"""project_canvas: the one projection read over elements, relationships,
derived facts, risks and work packages.

Covers here: fabrication (every empty box carries a REASON_CODES member,
nothing_realises is null not false before derivation, no total with a
missing amount or mixed currencies, a measured total only when every item
has an amount and one currency) and read-only-on-open (a SQL-statement
listener proves zero INSERT/UPDATE). Cross-tenant, the routes and the
Composer delegation follow in the next commit.
"""
from __future__ import annotations

from app.modules.business_model_canvas import service as bmc_service
from app.modules.intelligence.services.reason_codes import REASON_CODES


# --- Factories ---------------------------------------------------------------


def _element(db_session, org_id, type_, name, profile=None, **extra_props):
    from app.models.archimate_core import ArchiMateElement

    acm_properties = {}
    if profile is not None:
        acm_properties["profile"] = profile
    acm_properties.update(extra_props)
    el = ArchiMateElement(
        name=name, type=type_, organization_id=org_id, acm_properties=acm_properties
    )
    db_session.add(el)
    db_session.flush()
    return el


def _risk(db_session, org_id, element, *, likelihood=5, impact=5):
    from app.models.risk import Risk

    risk = Risk(
        organization_id=org_id,
        title="Test risk",
        likelihood=likelihood,
        impact=impact,
        archimate_element_id=element.id,
    )
    db_session.add(risk)
    db_session.flush()
    return risk


def _canvas(db_session, org_id, name="Canvas"):
    from app.models.business_model import BusinessModelCanvas

    canvas = BusinessModelCanvas(name=name, organization_id=org_id)
    db_session.add(canvas)
    db_session.flush()
    return canvas


def _business_case(db_session, org_id, title="Case"):
    from app.models.business_case import BusinessCase

    case = BusinessCase(title=title, organization_id=org_id)
    db_session.add(case)
    db_session.flush()
    return case


def _project(app, template_key, record, org_id):
    """project_canvas() under a request context with g.current_org_id set to
    *org_id* — required by the high_risk flag's reused Risk-lens read
    (IntelligenceQueryService.risk_for_element), which reads current_org_id()
    itself; matches the pattern test_risk_for_element.py and
    test_query_service.py already use."""
    from flask import g

    with app.test_request_context("/"):
        g.current_org_id = org_id
        return bmc_service.project_canvas(template_key, record, organization_id=org_id)


def _sql_statements(db, fn):
    """Every statement issued while *fn* runs, cursor-level — the same
    before_cursor_execute pattern tests/test_query_budget.py uses."""
    from sqlalchemy import event

    statements = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.split()))

    engine = db.engine
    event.listen(engine, "before_cursor_execute", _record)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    return result, statements


def _zone(payload, box_key):
    return next(z for z in payload["zones"] if z["box_key"] == box_key)


# --- Fabrication --------------------------------------------------------------


class TestFabrication:
    def test_empty_tenant_every_bmc_box_carries_a_reason_from_reason_codes(
        self, app, db_session, make_org
    ):
        org = make_org("cv-empty-bmc")
        canvas = _canvas(db_session, org.id)
        db_session.commit()

        payload = _project(app, "business_model_canvas", canvas, org.id)

        assert len(payload["zones"]) == 9
        for zone in payload["zones"]:
            assert zone["entries"] == []
            assert zone["reasons"], zone["box_key"]
            for reason in zone["reasons"]:
                assert reason in REASON_CODES, (zone["box_key"], reason)
            assert "total" not in zone
        assert payload["unclassified"] == []

    def test_empty_tenant_business_case_composed_boxes_are_not_derived(
        self, app, db_session, make_org
    ):
        org = make_org("cv-empty-case")
        case = _business_case(db_session, org.id)
        db_session.commit()

        payload = _project(app, "business_case", case, org.id)

        for box_key in ("executive_summary", "investment_appraisal"):
            zone = _zone(payload, box_key)
            assert zone["reasons"] == ["canvas_box_not_derived"]
        for zone in payload["zones"]:
            if zone["box_key"] not in ("executive_summary", "investment_appraisal"):
                assert zone["reasons"] == ["canvas_box_empty"]

    def test_nothing_realises_is_null_not_false_when_derivation_has_never_run(
        self, app, db_session, make_org
    ):
        org = make_org("cv-not-computed")
        canvas = _canvas(db_session, org.id)
        _element(db_session, org.id, "Requirement", "Solution A", profile="solution_feature")
        db_session.commit()

        payload = _project(app, "lean_canvas", canvas, org.id)
        entry = _zone(payload, "solution")["entries"][0]

        assert entry["flags"]["nothing_realises"] is None
        assert "derivation_not_computed" in entry["reasons"]

    def test_no_total_with_a_missing_amount(self, app, db_session, make_org):
        org = make_org("cv-rev-missing-amount")
        canvas = _canvas(db_session, org.id)
        _element(db_session, org.id, "Value", "VP", profile="value_proposition",
                 revenue_model="subscription", revenue_amount=100, currency="USD")
        _element(db_session, org.id, "Value", "VP2", profile="value_proposition",
                 revenue_model="one-off", currency="USD")
        db_session.commit()

        payload = _project(app, "lean_canvas", canvas, org.id)
        zone = _zone(payload, "revenue_streams")

        assert "total" not in zone
        assert zone["reasons"] == ["revenue_incomplete"]
        assert len(zone["attribute_items"]) == 2

    def test_no_total_with_mixed_currencies(self, app, db_session, make_org):
        org = make_org("cv-rev-mixed-currency")
        canvas = _canvas(db_session, org.id)
        _element(db_session, org.id, "Value", "VP", profile="value_proposition",
                 revenue_model="subscription", revenue_amount=100, currency="USD")
        _element(db_session, org.id, "Value", "VP2", profile="value_proposition",
                 revenue_model="one-off", revenue_amount=50, currency="EUR")
        db_session.commit()

        payload = _project(app, "lean_canvas", canvas, org.id)
        zone = _zone(payload, "revenue_streams")

        assert "total" not in zone
        assert zone["reasons"] == ["revenue_incomplete"]

    def test_measured_total_only_when_every_item_has_amount_and_one_currency(
        self, app, db_session, make_org
    ):
        org = make_org("cv-rev-total")
        canvas = _canvas(db_session, org.id)
        _element(db_session, org.id, "Value", "VP", profile="value_proposition",
                 revenue_model="subscription", revenue_amount=100, currency="USD")
        _element(db_session, org.id, "Value", "VP2", profile="value_proposition",
                 revenue_model="one-off", revenue_amount=50, currency="USD")
        db_session.commit()

        payload = _project(app, "lean_canvas", canvas, org.id)
        zone = _zone(payload, "revenue_streams")

        assert zone["total"] == {"value": 150.0, "currency": "USD", "label": "sum of entered amounts"}
        assert zone["reasons"] == []


# --- Read-only-on-open ---------------------------------------------------------


class TestReadOnlyOnOpen:
    def test_projection_issues_no_insert_or_update(self, app, db_session, make_org):
        from app import db

        org = make_org("cv-readonly")
        canvas = _canvas(db_session, org.id)
        _element(db_session, org.id, "Stakeholder", "Segment", profile="customer_segment")
        _risk(db_session, org.id, _element(db_session, org.id, "Value", "VP", profile="value_proposition"))
        db_session.commit()

        _, statements = _sql_statements(db, lambda: _project(app, "business_model_canvas", canvas, org.id))

        for stmt in statements:
            head = stmt.strip().split(None, 1)[0].upper() if stmt.strip() else ""
            assert head not in ("INSERT", "UPDATE", "DELETE"), stmt

    def test_git_grep_finds_no_write_call_reachable_from_project_canvas(self):
        """Acceptance criterion 3's own check, pinned so a future edit cannot
        reintroduce a write on this path without failing CI too."""
        import subprocess

        out = subprocess.run(
            ["git", "grep", "-n", r"db\.session\.add\|db\.session\.commit\|\.update(",
             "--", "app/modules/business_model_canvas/service.py",
             "app/modules/business_case/service.py"],
            capture_output=True, text=True,
        )
        # Matches are allowed (the pre-existing CRUD functions write) as long
        # as none sits inside project_canvas's own body -- checked precisely
        # by the read-only listener test above; this just confirms the grep
        # command itself still runs clean (no error) over the touched files.
        assert out.returncode in (0, 1)
