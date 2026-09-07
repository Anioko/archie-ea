"""H1/H2: the Risk Register had no way to link a risk to an Application,
Solution or Programme, no full edit, and no delete -- rows opened nothing and
the "Action" column had no working control once a risk was mitigated/closed.

Covers:
- Risk full CRUD (GET single, PATCH full edit, DELETE) -- previously PATCH
  only supported {"status": ...}.
- RiskEntityLink CRUD (app/models/risk_entity_link.py), the new table behind
  H1's entity picker.
- links_for_entity(), the parent-side read for "Linked risks" sections.
"""

import pytest

from app.services import risk_service


@pytest.mark.usefixtures("db_session")
def test_risk_full_edit_updates_all_editable_fields(app, db_session, make_org, tenant_ctx):
    org = make_org("h2-edit")
    with tenant_ctx(org.id):
        risk = risk_service.create_risk(
            solution_id=None, title="Original title", description="orig",
            likelihood=2, impact=2, owner="Alice", mitigation_plan="orig plan",
        )
        updated = risk_service.update_risk(
            risk.id,
            title="Updated title",
            description="updated description",
            likelihood=5,
            impact=5,
            owner="Bob",
            mitigation_plan="updated plan",
        )
        assert updated.title == "Updated title"
        assert updated.description == "updated description"
        assert updated.likelihood == 5
        assert updated.impact == 5
        assert updated.owner == "Bob"
        assert updated.mitigation_plan == "updated plan"
        assert updated.risk_score == 25  # recomputed from the new likelihood/impact


@pytest.mark.usefixtures("db_session")
def test_risk_delete_removes_the_row_and_its_links(app, db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent
    from app.models.risk import Risk
    from app.models.risk_entity_link import RiskEntityLink

    org = make_org("h2-delete")
    with tenant_ctx(org.id):
        component = ApplicationComponent(name="Doomed App", organization_id=org.id)
        db_session.add(component)
        db_session.flush()

        risk = risk_service.create_risk(
            solution_id=None, title="Will be deleted", description=None,
            likelihood=3, impact=3, owner=None, mitigation_plan=None,
        )
        risk_service.add_risk_link(risk.id, "application", component.id)

        risk_id = risk.id
        risk_service.delete_risk(risk_id)

        assert Risk.query.get(risk_id) is None
        assert RiskEntityLink.query.filter_by(risk_id=risk_id).count() == 0


@pytest.mark.usefixtures("db_session")
def test_add_and_remove_risk_entity_link(app, db_session, make_org, tenant_ctx):
    from app.models.application_portfolio import ApplicationComponent

    org = make_org("h1-link")
    with tenant_ctx(org.id):
        component = ApplicationComponent(name="Linked App", organization_id=org.id)
        db_session.add(component)
        db_session.flush()

        risk = risk_service.create_risk(
            solution_id=None, title="Vendor risk", description=None,
            likelihood=3, impact=4, owner=None, mitigation_plan=None,
        )

        link = risk_service.add_risk_link(risk.id, "application", component.id)
        assert link.entity_type == "application"
        assert link.entity_id == component.id

        links = risk_service.list_risk_links(risk.id)
        assert len(links) == 1

        # Idempotent: mapping the same risk to the same entity twice does not
        # duplicate the row.
        again = risk_service.add_risk_link(risk.id, "application", component.id)
        assert again.id == link.id
        assert len(risk_service.list_risk_links(risk.id)) == 1

        risk_service.remove_risk_link(risk.id, link.id)
        assert risk_service.list_risk_links(risk.id) == []


@pytest.mark.usefixtures("db_session")
def test_add_risk_link_rejects_unknown_entity_type(app, db_session, make_org, tenant_ctx):
    org = make_org("h1-badtype")
    with tenant_ctx(org.id):
        risk = risk_service.create_risk(
            solution_id=None, title="Some risk", description=None,
            likelihood=1, impact=1, owner=None, mitigation_plan=None,
        )
        with pytest.raises(ValueError):
            risk_service.add_risk_link(risk.id, "vendor", 1)


@pytest.mark.usefixtures("db_session")
def test_links_for_entity_surfaces_risks_on_the_parent_side(app, db_session, make_org, tenant_ctx):
    """The read that backs an Application/Solution/Programme detail page's
    own "Linked risks" section (H1's second half: showing linked risks on
    the parent entity, not just recording the link from the risk side)."""
    from app.models.application_portfolio import ApplicationComponent

    org = make_org("h1-parent-read")
    with tenant_ctx(org.id):
        component = ApplicationComponent(name="Watched App", organization_id=org.id)
        db_session.add(component)
        db_session.flush()

        risk_a = risk_service.create_risk(
            solution_id=None, title="Risk A", description=None,
            likelihood=2, impact=2, owner=None, mitigation_plan=None,
        )
        risk_b = risk_service.create_risk(
            solution_id=None, title="Risk B", description=None,
            likelihood=4, impact=4, owner=None, mitigation_plan=None,
        )
        risk_service.add_risk_link(risk_a.id, "application", component.id)
        risk_service.add_risk_link(risk_b.id, "application", component.id)

        linked = risk_service.links_for_entity("application", component.id)
        assert {r["title"] for r in linked} == {"Risk A", "Risk B"}

        # A different application sees none of these.
        other = ApplicationComponent(name="Unrelated App", organization_id=org.id)
        db_session.add(other)
        db_session.flush()
        assert risk_service.links_for_entity("application", other.id) == []
