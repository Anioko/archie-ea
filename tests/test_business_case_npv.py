"""Business case NPV — un-orphans the DCF capability the transformation-gap
audit found (SolutionCostService.calculate_npv existed, was wired to zero
routes). BusinessCase gets its OWN computed NPV instead of borrowing that
unrelated Solution-scoped cost-model service — different system of record
(ADR-0008) — derived from its own capex/opex/financial_benefit_annual, never
stored so it can never go stale when any one of those three is edited alone.
"""

from decimal import Decimal

from app.modules.business_case.service import calculate_npv


def test_calculate_npv_matches_hand_computed_value():
    # -100000 + sum_{t=1..3} (60000-20000)/(1.10)^t = -525.92... (hand-computed)
    npv = calculate_npv(Decimal("100000"), Decimal("20000"), Decimal("60000"))
    assert npv is not None
    assert round(npv, 2) == Decimal("-525.92")


def test_no_costs_no_benefit_returns_none_not_zero():
    """A business case with nothing costed has no NPV to report — never a
    fabricated zero (CLAUDE.md null-display rule)."""
    assert calculate_npv(None, None, None) is None
    assert calculate_npv(None, Decimal("5000"), None) is None  # opex alone, no capex/benefit


def test_capex_only_is_negative_npv():
    npv = calculate_npv(Decimal("50000"), None, None)
    assert npv is not None
    assert npv < 0
    assert round(npv, 2) == Decimal("-50000.00")  # no cash flows to discount


def test_benefit_only_no_capex_is_positive():
    npv = calculate_npv(None, None, Decimal("40000"))
    assert npv is not None
    assert npv > 0


def test_model_property_matches_service_function(db_session, make_org, tenant_ctx):
    from app.models.business_case import BusinessCase

    org = make_org("npv")
    with tenant_ctx(org.id):
        bc = BusinessCase(
            organization_id=org.id, title="NPV test case",
            capex=Decimal("100000"), opex_annual=Decimal("20000"),
            financial_benefit_annual=Decimal("60000"),
        )
        db_session.add(bc)
        db_session.flush()

        assert bc.npv is not None
        assert round(bc.npv, 2) == -525.92
        assert bc.to_dict()["npv"] == bc.npv  # to_dict exposes the same computed value


def test_model_property_none_when_nothing_costed(db_session, make_org, tenant_ctx):
    from app.models.business_case import BusinessCase

    org = make_org("npv")
    with tenant_ctx(org.id):
        bc = BusinessCase(organization_id=org.id, title="Empty case")
        db_session.add(bc)
        db_session.flush()
        assert bc.npv is None
        assert bc.to_dict()["npv"] is None
