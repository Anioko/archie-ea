"""The Risk Register table's own tiles and per-row badges must be accurate.

Both from live production checks on 6 Sep 2026:

- E2E-N: the CRITICAL tile counted risk_level alone with no status filter,
  so a risk that had already been closed still inflated the count a viewer
  reads as current exposure (TOTAL 1, OPEN 0, CRITICAL 1 - confirmed live).
- F6: a risk with risk_level "high" or "medium" was reported to render an
  empty Level cell, with every seed risk happening to be critical/low so it
  only surfaced once a user created a high/medium risk in normal use.
"""
from bs4 import BeautifulSoup
from flask import render_template


def _make_risk(organization_id, title, likelihood, impact, status="open"):
    from app.models.risk import Risk, RiskStatus

    return Risk(
        organization_id=organization_id, title=title,
        likelihood=likelihood, impact=impact,
        status=RiskStatus[status.upper()],
    )


def test_critical_tile_excludes_closed_and_mitigated_risks(app, db_session, make_org, tenant_ctx):
    org = make_org("risk-register-tiles")
    with tenant_ctx(org.id):
        db_session.add_all([
            _make_risk(org.id, "Closed critical (must not count)", 5, 5, status="closed"),
            _make_risk(org.id, "Open critical (must count)", 5, 5, status="open"),
            _make_risk(org.id, "Mitigated critical (must not count)", 5, 5, status="mitigated"),
        ])
        db_session.flush()

        from app.models.risk import Risk
        risks = Risk.query.order_by(Risk.id).all()
        with app.test_request_context("/"):
            html = render_template(
                "governance/risk_register.html", risks=risks, grid=[],
                total=len(risks), current_sort="id", current_dir="asc",
                raid_items=[], raid_kinds=[], programmes=[],
            )
        page = BeautifulSoup(html, "html.parser")
        tiles = page.select(".text-2xl.font-semibold.tabular-nums")
        # Order in the template: Total, Open, Critical, Mitigated.
        values = [t.get_text(strip=True) for t in tiles]
        assert values[0] == "3"   # Total
        assert values[1] == "1"   # Open
        assert values[2] == "1"   # Critical: only the open one
        assert values[3] == "1"   # Mitigated


def test_high_and_medium_risks_render_a_level_badge(app, db_session, make_org, tenant_ctx):
    org = make_org("risk-register-levels")
    with tenant_ctx(org.id):
        db_session.add_all([
            _make_risk(org.id, "High risk", 3, 3),    # score 9 -> high
            _make_risk(org.id, "Medium risk", 2, 3),  # score 6 -> medium
        ])
        db_session.flush()

        from app.models.risk import Risk
        risks = Risk.query.order_by(Risk.id).all()
        with app.test_request_context("/"):
            html = render_template(
                "governance/risk_register.html", risks=risks, grid=[],
                total=len(risks), current_sort="id", current_dir="asc",
                raid_items=[], raid_kinds=[], programmes=[],
            )
        for risk, expected_label in zip(risks, ("High", "Medium")):
            assert expected_label in html, f"{risk.title} did not render a '{expected_label}' badge"
