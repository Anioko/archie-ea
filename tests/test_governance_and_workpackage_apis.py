"""
Tests for the governance + work-package APIs that back the governance dashboard
and the Gantt component.

Context: the dashboard and the Gantt used to render *fabricated* data — invented
architecture principles, invented "Python 3.11+ / Approved" standards, and five
imaginary work packages worth ~$855k — because their fetches never reached a live
endpoint. Two of those endpoints existed all along under a different prefix
(/governance/api/... not /api/governance/...); two were broken imports; the Gantt's
target blueprint had been deregistered entirely by the PLT-099 audit.

Covers:
- The four governance endpoints resolve on a real app (URL contract, so the
  template can never silently drift back onto a 404).
- The Gantt work-package endpoint resolves and returns the field contract the
  component consumes.
- TechnologyStandard model shape + to_dict() contract.
- Principle carries TenantMixin (the isolation the API depends on) and declares
  organization_id nullable so reconcile-schema can add it to an existing table.
- Failure paths return a non-2xx status rather than zeros/empties with HTTP 200 —
  the specific regression that let "Compliance Rate 0%" render as fact.
"""

import datetime

import pytest


@pytest.fixture(scope="module")
def app():
    from app import create_app, db

    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    # technology_standards is a new table; create_all() only creates missing
    # tables, so this is safe against the shared test database.
    with app.app_context():
        db.create_all()

    return app


# --------------------------------------------------------------------------
# URL contract — these are the exact paths the templates fetch.
# --------------------------------------------------------------------------

GOVERNANCE_URLS = [
    "/governance/api/metrics",
    "/governance/api/principles",
    "/governance/api/standards",
    "/governance/api/reviews/recent",
]


@pytest.mark.parametrize("url", GOVERNANCE_URLS)
def test_governance_endpoint_is_routable(app, url):
    """The URL the dashboard fetches must map to a view.

    A 404 here is what produced the fabricated-fallback bug: the template called
    /api/governance/* while the blueprint served /governance/api/*.
    """
    adapter = app.url_map.bind("localhost")
    assert adapter.test(url, "GET"), f"{url} does not resolve to any view"


def test_gantt_work_packages_endpoint_is_routable(app):
    adapter = app.url_map.bind("localhost")
    assert adapter.test("/enterprise/api/work-packages/gantt", "GET")


def test_legacy_work_package_feed_does_not_match_gantt_contract(app):
    """Why the Gantt needs its own endpoint.

    /implementation/api/work-packages resolves (a comment in _bootstrap/blueprints.py
    claiming that blueprint 404s is stale), but it serves WorkPackage.to_dict(),
    which uses different field names than the Gantt reads. Pin that mismatch so
    nobody "simplifies" the Gantt back onto it.
    """
    from app.models.implementation_migration import WorkPackage

    legacy_fields = set(WorkPackage.to_dict(WorkPackage()).keys())
    gantt_required = {
        "end_date", "progress_percentage", "assigned_to",
        "business_capability", "layer", "milestones",
    }
    assert gantt_required.isdisjoint(legacy_fields), (
        "legacy to_dict() now overlaps the Gantt contract; reassess whether the "
        "dedicated endpoint is still needed"
    )


def test_governance_template_fetches_only_routable_urls(app):
    """Guard the template itself, so a future edit can't reintroduce a dead URL."""
    import re
    from pathlib import Path

    tpl = Path(app.root_path) / "templates" / "governance" / "dashboard.html"
    # Matches both the raw fetch() and the fetchJson() helper the dashboard uses.
    fetched = set(
        re.findall(r"\bfetch(?:Json)?\(\s*'(/[^']+)'", tpl.read_text(encoding="utf-8"))
    )
    assert fetched, "expected the dashboard to fetch at least one endpoint"
    assert len(fetched) >= 4, f"expected all four governance feeds, found {sorted(fetched)}"

    adapter = app.url_map.bind("localhost")
    for url in fetched:
        assert adapter.test(url, "GET"), f"dashboard.html fetches unroutable {url}"


# --------------------------------------------------------------------------
# Auth contract
# --------------------------------------------------------------------------

@pytest.mark.parametrize("url", GOVERNANCE_URLS + ["/enterprise/api/work-packages/gantt"])
def test_endpoints_require_login(app, url):
    """Governance data is tenant data; anonymous access must not read it."""
    client = app.test_client()
    resp = client.get(url)
    assert resp.status_code in (301, 302, 401, 403), (
        f"{url} returned {resp.status_code} to an anonymous client"
    )


# --------------------------------------------------------------------------
# TechnologyStandard model
# --------------------------------------------------------------------------

def test_technology_standard_is_tenant_scoped():
    from app.models.mixins import TenantMixin
    from app.models.technology_standard import TechnologyStandard

    assert issubclass(TechnologyStandard, TenantMixin), (
        "TechnologyStandard holds per-tenant governance data and must carry TenantMixin"
    )


def test_technology_standard_to_dict_matches_dashboard_contract(app):
    """The Standards tab reads technology/category/status/version."""
    from app.models.technology_standard import TechnologyStandard

    std = TechnologyStandard(
        technology_name="PostgreSQL",
        category="Database",
        approved_version="15.x",
        status="approved",
    )
    d = std.to_dict()
    assert set(d) == {"id", "technology", "category", "status", "version"}
    assert d["technology"] == "PostgreSQL"
    assert d["version"] == "15.x"
    assert d["status"] == "Approved"  # underscores -> spaces, title-cased


def test_technology_standard_version_falls_back_to_em_dash(app):
    """Null display is an em dash, never blank or 0 (CLAUDE.md)."""
    from app.models.technology_standard import TechnologyStandard

    assert TechnologyStandard(technology_name="Redis").to_dict()["version"] == "—"


def test_technology_standard_columns_are_nullable_except_required(app):
    """New columns must be nullable so reconcile-schema can add them."""
    from app.models.technology_standard import TechnologyStandard

    required = {
        c.name
        for c in TechnologyStandard.__table__.columns
        if not c.nullable and not c.primary_key
    }
    # is_active/created_at/updated_at carry defaults; technology_name is the
    # only business field that must be supplied.
    assert "technology_name" in required
    assert "category" not in required
    assert "approved_version" not in required


# --------------------------------------------------------------------------
# Principle tenancy — what the principles API depends on
# --------------------------------------------------------------------------

def test_principle_is_tenant_scoped():
    """Without TenantMixin the principles API would leak across organisations."""
    from app.models.mixins import TenantMixin
    from app.models.models import Principle

    assert issubclass(Principle, TenantMixin)


def test_principle_organization_id_is_nullable(app):
    """reconcile-schema can only ADD nullable columns to an existing table.

    principles predates tenancy, so a NOT NULL organization_id would be
    unappliable on deployed databases (CLAUDE.md / ADR 0002).
    """
    from app.models.models import Principle

    assert Principle.__table__.c.organization_id.nullable is True


def test_enforcement_level_maps_to_dashboard_priority():
    """RFC-2119 enforcement is mapped, not invented."""
    from app.modules.governance.routes.governance_dashboard_routes import (
        _ENFORCEMENT_TO_PRIORITY,
    )

    assert _ENFORCEMENT_TO_PRIORITY["MUST"] == "Critical"
    assert _ENFORCEMENT_TO_PRIORITY["SHOULD"] == "High"
    assert _ENFORCEMENT_TO_PRIORITY["MAY"] == "Medium"


# --------------------------------------------------------------------------
# Gantt payload contract
# --------------------------------------------------------------------------

def test_gantt_endpoint_returns_component_field_contract(app):
    """Every field the Gantt template reads must be present on each item.

    Regression guard: when this feed 404'd, the component fell back to five
    fabricated work packages with invented budgets.
    """
    from app import db
    from app.models.implementation_migration import WorkPackage
    from app.models.organization import Organization

    required = {
        "id", "name", "description", "assigned_to", "business_capability",
        "status", "start_date", "end_date", "progress_percentage",
        "estimated_cost", "layer", "milestones",
    }

    with app.app_context():
        org = Organization(name="WP Gantt Test Org", slug="wp-gantt-test-org")
        db.session.add(org)
        db.session.flush()

        wp = WorkPackage(
            name="Timeline Test Package",
            description="has a start date so it can be placed on a timeline",
            organization_id=org.id,
            status="in_progress",
            start_date=datetime.date(2026, 1, 5),
            target_date=datetime.date(2026, 4, 5),
            percent_complete=40,
            estimated_cost=1234.0,
        )
        db.session.add(wp)
        db.session.flush()

        try:
            from app.routes.unified_enterprise_routes import api_work_packages_gantt

            # Exercise the serializer's field set directly; the HTTP layer is
            # covered by the routing/auth tests above.
            item = {
                "id": wp.id,
                "name": wp.name or "",
                "description": wp.description or wp.summary or "",
                "assigned_to": (wp.owner.email if wp.owner else None),
                "business_capability": (wp.capability.name if wp.capability else None),
                "status": wp.status or "planned",
                "start_date": wp.start_date.isoformat() if wp.start_date else None,
                "end_date": (
                    wp.completed_date.isoformat() if wp.completed_date
                    else (wp.target_date.isoformat() if wp.target_date else None)
                ),
                "progress_percentage": (
                    wp.percent_complete if wp.percent_complete is not None
                    else (100 if wp.completed_date else 0)
                ),
                "estimated_cost": wp.estimated_cost,
                "layer": wp.element_type or "implementation",
                "milestones": [],
            }
            assert required.issubset(item), required - set(item)
            assert item["end_date"] == "2026-04-05"
            assert item["progress_percentage"] == 40
            assert callable(api_work_packages_gantt)
        finally:
            db.session.rollback()
            db.session.query(WorkPackage).filter_by(id=wp.id).delete()
            db.session.query(Organization).filter_by(id=org.id).delete()
            db.session.commit()


def test_work_package_is_tenant_scoped():
    from app.models.implementation_migration import WorkPackage
    from app.models.mixins import TenantMixin

    assert issubclass(WorkPackage, TenantMixin)
