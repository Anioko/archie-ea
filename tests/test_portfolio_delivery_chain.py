"""
Tests for the delivery chain: demand -> initiative -> work package -> project,
with benefits and RAID hanging off the initiative.

Context: the architecture repository and the delivery repository could not join.
`projects.capability_id` was a bare Integer with a comment where a foreign key
belonged, so nothing could traverse it; `EnterpriseInitiative` carried budget,
spend, forecast and RAG health but had zero templates and no tenant isolation;
benefits were a JSON blob on a Text column; and there was no Demand or Assumption
model at all.

These tests pin the structural facts, because they are what make the chain
queryable — a broken FK here silently returns to "the architecture cannot see
what is being built".
"""
import pytest


@pytest.fixture(scope="module")
def app():
    from app import create_app, db

    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        db.create_all()
    return app


def _fk_targets(model, column):
    col = model.__table__.c[column]
    return {fk.target_fullname for fk in col.foreign_keys}


# --------------------------------------------------------------------------
# 1. The join that did not exist
# --------------------------------------------------------------------------

def test_project_links_to_work_package(app):
    """The link that lets a capability gap reach the work delivering it."""
    from app.models.project_models import Project

    assert _fk_targets(Project, "work_package_id") == {"work_packages.id"}


def test_project_architecture_links_are_real_foreign_keys(app):
    """capability_id/requirement_id were bare Integers with a comment.

    projects.id being a UUID is irrelevant — a FK column only has to match the
    *target* primary key's type.
    """
    from app.models.project_models import Project

    assert _fk_targets(Project, "capability_id") == {"unified_capabilities.id"}
    assert _fk_targets(Project, "requirement_id") == {"requirements.id"}


def test_project_has_an_owner_relationship(app):
    """project_manager was free text, so there was no ownership graph."""
    from app.models.project_models import Project

    assert _fk_targets(Project, "project_manager_id") == {"users.id"}
    assert "project_manager_user" in {r.key for r in Project.__mapper__.relationships}


def test_project_new_columns_are_nullable(app):
    """projects is an existing table; reconcile-schema can only ADD nullable."""
    from app.models.project_models import Project

    for col in ("work_package_id", "capability_id", "requirement_id", "project_manager_id"):
        assert Project.__table__.c[col].nullable is True, col


def test_traces_to_architecture_flags_orphaned_projects(app):
    from app.models.project_models import Project

    assert Project(name="orphan", code="O-1").traces_to_architecture is False
    assert Project(name="linked", code="L-1", work_package_id=1).traces_to_architecture is True


# --------------------------------------------------------------------------
# 2. Tenant isolation — the leak found while building the portfolio view
# --------------------------------------------------------------------------

def test_initiative_is_tenant_scoped(app):
    """EnterpriseInitiative held every tenant's programmes with no org column.

    Nothing surfaced it, which is the only reason it had not leaked. The
    portfolio view surfaces it, so isolation must exist first.
    """
    from app.models.mixins import TenantMixin
    from app.models.vendor.vendor_organization import EnterpriseInitiative

    assert issubclass(EnterpriseInitiative, TenantMixin)
    assert EnterpriseInitiative.__table__.c.organization_id.nullable is True


@pytest.mark.parametrize("model_path,cls_name", [
    ("app.models.benefit", "Benefit"),
    ("app.models.demand", "Demand"),
    ("app.models.demand", "Assumption"),
])
def test_new_models_are_tenant_scoped(app, model_path, cls_name):
    import importlib

    from app.models.mixins import TenantMixin

    model = getattr(importlib.import_module(model_path), cls_name)
    assert issubclass(model, TenantMixin)


# --------------------------------------------------------------------------
# 3. Benefits — measurable, not declared
# --------------------------------------------------------------------------

def test_benefit_realisation_is_none_not_zero_when_unmeasured(app):
    """A measured zero and an absent measurement are different facts.

    Returning 0 here is exactly the bug this codebase's fabricated-data gate
    exists to prevent — it renders as "0% realised" about something never
    measured.
    """
    from app.models.benefit import Benefit

    assert Benefit(name="b").realisation_percentage is None
    assert Benefit(name="b", baseline_value=100).realisation_percentage is None
    assert Benefit(name="b", baseline_value=100, target_value=50).realisation_percentage is None


def test_benefit_realisation_computes_against_the_baseline(app):
    """Realisation is a delta from baseline, not a raw ratio of actual/target."""
    from app.models.benefit import Benefit

    # baseline 100 -> target 50 (seeking -50); actual 75 means half achieved.
    b = Benefit(name="licence spend", baseline_value=100, target_value=50, actual_value=75)
    assert b.realisation_percentage == 50.0


def test_benefit_separates_financial_from_non_financial(app):
    """Summing a monetary saving with an NPS point is meaningless."""
    from app.models.benefit import Benefit

    assert Benefit(name="x", benefit_type="cost_saving").is_financial is True
    assert Benefit(name="x", benefit_type="customer").is_financial is False


def test_benefit_links_to_initiative_and_capability(app):
    from app.models.benefit import Benefit

    assert _fk_targets(Benefit, "initiative_id") == {"enterprise_initiatives.id"}
    assert _fk_targets(Benefit, "capability_id") == {"unified_capabilities.id"}


def test_initiative_can_traverse_to_its_benefits_and_raid(app):
    """The traversal the portfolio detail page depends on."""
    from app.models.vendor.vendor_organization import EnterpriseInitiative

    rels = {r.key for r in EnterpriseInitiative.__mapper__.relationships}
    assert {"benefits", "demands", "assumptions"}.issubset(rels)


# --------------------------------------------------------------------------
# 4. Demand and Assumption
# --------------------------------------------------------------------------

def test_demand_priority_is_none_when_inputs_missing(app):
    from app.models.demand import Demand

    assert Demand(title="t").priority_score is None
    assert Demand(title="t", business_value_score=4, urgency_score=3).priority_score == 12


def test_assumption_exposure_ranks_low_confidence_higher(app):
    """impact x (6 - confidence): the same impact is worse when less certain."""
    from app.models.demand import Assumption

    certain = Assumption(statement="s", impact_if_false=4, confidence=5)
    unsure = Assumption(statement="s", impact_if_false=4, confidence=1)
    assert unsure.exposure > certain.exposure
    assert Assumption(statement="s").exposure is None


def test_assumption_can_convert_to_a_risk(app):
    """An invalidated assumption is a risk that arrived late; keep the link."""
    from app.models.demand import Assumption

    assert _fk_targets(Assumption, "converted_to_risk_id") == {"risks.id"}


# --------------------------------------------------------------------------
# 5. Effort actuals
# --------------------------------------------------------------------------

def test_kanban_card_carries_effort_actuals(app):
    """Nothing could observe consumed effort, so spend was never computable."""
    from app.models.adm_kanban import KanbanCard

    for col in ("time_spent_seconds", "time_estimate_seconds", "effort_synced_at"):
        assert col in KanbanCard.__table__.c, col
        assert KanbanCard.__table__.c[col].nullable is True


def test_effort_hours_and_variance_are_none_when_unknown(app):
    """"No worklog" must stay distinguishable from "zero effort"."""
    from app.models.adm_kanban import KanbanCard

    assert KanbanCard(title="c").time_spent_hours is None
    assert KanbanCard(title="c", time_spent_seconds=7200).time_spent_hours == 2.0
    assert KanbanCard(title="c", time_spent_seconds=7200).effort_variance_pct is None
    card = KanbanCard(title="c", time_spent_seconds=7200, time_estimate_seconds=3600)
    assert card.effort_variance_pct == 100.0


# --------------------------------------------------------------------------
# 6. Routes
# --------------------------------------------------------------------------

@pytest.mark.parametrize("url", ["/portfolio/", "/portfolio/1"])
def test_portfolio_routes_resolve(app, url):
    assert app.url_map.bind("localhost").test(url, "GET")


@pytest.mark.parametrize("url", ["/portfolio/", "/portfolio/1"])
def test_portfolio_requires_login(app, url):
    """Portfolio holds budgets and sponsors — never anonymous."""
    resp = app.test_client().get(url)
    assert resp.status_code in (301, 302, 401, 403)


# --------------------------------------------------------------------------
# 7. Effort -> spend rollup
# --------------------------------------------------------------------------

def test_card_reaches_the_canonical_work_package(app):
    """Effort could not reach an initiative before this link existed.

    KanbanCard.work_package_id points at roadmap_work_packages, which stores
    business_capability as a String and carries no foreign keys — a dead end.
    The canonical WorkPackage is the one that links to the initiative.
    """
    from app.models.adm_kanban import KanbanCard

    assert _fk_targets(KanbanCard, "implementation_work_package_id") == {"work_packages.id"}


def test_rate_card_is_tenant_scoped(app):
    from app.models.mixins import TenantMixin
    from app.models.rate_card import RateCard

    assert issubclass(RateCard, TenantMixin)


def test_spend_is_none_not_zero_when_no_effort_logged(app):
    """"Nobody recorded effort" and "zero effort" are different facts.

    Returning 0.0 here would render as "£0 spent" on the portfolio page about an
    initiative nobody has measured — the exact lie the fabricated-data gate exists
    to prevent.
    """
    from app.services.initiative_spend_service import compute_initiative_spend

    with app.app_context():
        result = compute_initiative_spend(999_999)

    assert result["amount"] is None
    assert result["hours"] is None
    assert result["reason_unavailable"]


def test_spend_result_declares_itself_an_estimate(app):
    """A rate-card figure must never be mistaken for booked cost."""
    from app.services.initiative_spend_service import compute_initiative_spend

    with app.app_context():
        assert compute_initiative_spend(999_999)["is_estimate"] is True


def test_rate_card_currency_of_the_period(app):
    """A rate outside its effective window is not current and must not be used."""
    import datetime as dt

    from app.models.rate_card import RateCard

    past = RateCard(role="dev", hourly_rate=100, effective_to=dt.date(2000, 1, 1))
    assert past.is_current is False
    assert RateCard(role="dev", hourly_rate=100).is_current is True
