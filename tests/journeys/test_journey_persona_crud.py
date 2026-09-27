"""Journey: can the two write-capable personas actually change anything?

Until 2026-07-31 they could not. Procurement exposed seven routes and
Application Manager five, every one of them GET, and neither VendorContract nor
LicenseEntitlement was constructed anywhere in the codebase - so both personas
were named for work the product did not let them do, and both dashboards
rendered permanently empty on a new tenant.

These assert the write paths over real HTTP, and - equally important - that they
refuse to touch another tenant's rows. A create path that works but is not scoped
is worse than no create path at all.
"""

import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def _contract(db, org_id, name="Acme MSA"):
    from datetime import date

    from app.models.application_portfolio import VendorContract

    contract = VendorContract(
        organization_id=org_id,
        contract_name="%s %s" % (name, uuid.uuid4().hex[:6]),
        start_date=date.today(),
    )
    db.session.add(contract)
    db.session.commit()
    return contract.id


# ── Procurement ─────────────────────────────────────────────────────────────

def test_procurement_can_create_a_contract(app, client):
    from app import db
    from app.models.application_portfolio import VendorContract

    with app.app_context():
        org_id = make_org(db, "Proc")
        user_id = make_user(db, org_id, "proc", enterprise_role="procurement")

    login(client, user_id)
    name = "Vendor Agreement %s" % uuid.uuid4().hex[:6]
    response = client.post(
        "/procurement/contracts/new",
        data={
            "contract_name": name,
            "contract_type": "subscription",
            "status": "active",
            "contract_value": "125000",
            "currency": "EUR",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        saved = VendorContract.query.filter_by(contract_name=name).first()
        assert saved is not None, "contract was not persisted"
        assert saved.organization_id == org_id, "contract landed in the wrong tenant"
        assert saved.contract_value == 125000
        assert saved.status == "active"


def test_a_contract_status_outside_the_vocabulary_is_rejected(app, client):
    """Free text here disappears from every dashboard that groups on status.

    The submission is refused outright rather than cleaned up. Mapping an
    unrecognised value to None looks tidier but is worse: VendorContract.status
    carries default="active", so assigning None lets the column default fire and
    the contract is filed as ACTIVE. Inventing a meaningful status from nonsense
    is a worse outcome than storing the nonsense would have been - which is
    exactly what the first version of this code did, and what this test caught.
    """
    from app import db
    from app.models.application_portfolio import VendorContract

    with app.app_context():
        org_id = make_org(db, "Vocab")
        user_id = make_user(db, org_id, "vocab", enterprise_role="procurement")

    login(client, user_id)
    name = "Odd Status %s" % uuid.uuid4().hex[:6]
    response = client.post(
        "/procurement/contracts/new",
        data={"contract_name": name, "status": "whatever-i-typed", "start_date": "2026-01-01"},
    )
    assert response.status_code == 400, "an unrecognised status was accepted"

    with app.app_context():
        assert VendorContract.query.filter_by(contract_name=name).first() is None, (
            "the contract was persisted despite an invalid status"
        )


def test_procurement_cannot_edit_another_tenants_contract(app, client):
    from app import db

    with app.app_context():
        victim_org = make_org(db, "Victim")
        attacker_org = make_org(db, "Attacker")
        contract_id = _contract(db, victim_org)
        attacker_id = make_user(db, attacker_org, "attacker", enterprise_role="procurement")

    login(client, attacker_id)
    response = client.post(
        "/procurement/contracts/%d/edit" % contract_id,
        data={"contract_name": "Owned", "start_date": "2026-01-01"},
    )
    assert response.status_code == 404, (
        "a user from another organisation could edit this contract"
    )


def test_procurement_cannot_delete_another_tenants_contract(app, client):
    from app import db
    from app.models.application_portfolio import VendorContract

    with app.app_context():
        victim_org = make_org(db, "Victim2")
        attacker_org = make_org(db, "Attacker2")
        contract_id = _contract(db, victim_org)
        attacker_id = make_user(db, attacker_org, "attacker2", enterprise_role="procurement")

    login(client, attacker_id)
    response = client.post("/procurement/contracts/%d/delete" % contract_id)
    assert response.status_code == 404

    with app.app_context():
        assert VendorContract.query.get(contract_id) is not None, (
            "another tenant's contract was deleted"
        )


def test_a_licence_cannot_be_hung_off_another_tenants_contract(app, client):
    """contract_id arrives from the client, so it has to be re-checked."""
    from app import db

    with app.app_context():
        victim_org = make_org(db, "Victim3")
        attacker_org = make_org(db, "Attacker3")
        contract_id = _contract(db, victim_org)
        attacker_id = make_user(db, attacker_org, "attacker3", enterprise_role="procurement")

    login(client, attacker_id)
    response = client.post(
        "/procurement/licenses/new",
        data={
            "contract_id": str(contract_id),
            "product_name": "Smuggled",
            "license_type": "named_user",
            "quantity_entitled": "10",
            "quantity_deployed": "5",
        },
    )
    assert response.status_code == 404


def test_compliance_is_derived_not_accepted_from_the_form(app, client):
    """The compliance dashboard is what an auditor reads.

    Accepting compliance_status from the client would let an over-deployed licence
    be filed as compliant - the exact condition the screen exists to surface.
    """
    from app import db
    from app.models.license_entitlement import LicenseEntitlement

    with app.app_context():
        org_id = make_org(db, "Comply")
        contract_id = _contract(db, org_id)
        user_id = make_user(db, org_id, "comply", enterprise_role="procurement")

    login(client, user_id)
    product = "Overdeployed %s" % uuid.uuid4().hex[:6]
    client.post(
        "/procurement/licenses/new",
        data={
            "contract_id": str(contract_id),
            "product_name": product,
            "license_type": "named_user",
            "quantity_entitled": "10",
            "quantity_deployed": "50",      # plainly over-deployed
            "compliance_status": "compliant",  # ... and claiming otherwise
        },
        follow_redirects=True,
    )
    with app.app_context():
        saved = LicenseEntitlement.query.filter_by(product_name=product).first()
        assert saved is not None, "licence was not persisted"
        assert saved.compliance_status == "over_deployed", (
            "the posted compliance_status was trusted over the quantities"
        )


def test_the_procurement_section_root_resolves(app, client):
    """/procurement had no route: every page beneath it worked, the section did not."""
    from app import db

    with app.app_context():
        org_id = make_org(db, "Root")
        user_id = make_user(db, org_id, "root", enterprise_role="procurement")

    login(client, user_id)
    assert client.get("/procurement/").status_code in (200, 302)


# ── Application Manager ─────────────────────────────────────────────────────

def _owned_application(db, org_id, user_id):
    """An ApplicationComponent this user owns.

    ApplicationOwner.application_id is a foreign key to application_components.
    An earlier version of this helper created a Solution instead and the insert
    failed on that constraint - which is how the read path was found to be
    resolving those same ids against the solutions table, matching on nothing
    more than two id sequences colliding.
    """
    from app.models.application_owner import ApplicationOwner
    from app.models.application_portfolio import ApplicationComponent

    component = ApplicationComponent(
        name="Owned App %s" % uuid.uuid4().hex[:6], organization_id=org_id
    )
    db.session.add(component)
    db.session.flush()
    db.session.add(
        ApplicationOwner(
            user_id=user_id, application_id=component.id, organization_id=org_id
        )
    )
    db.session.commit()
    return component.id


def test_an_application_manager_can_update_an_application_they_own(app, client):
    from app import db
    from app.models.application_portfolio import ApplicationComponent

    with app.app_context():
        org_id = make_org(db, "AppMgr")
        user_id = make_user(db, org_id, "appmgr", enterprise_role="application_manager")
        app_id = _owned_application(db, org_id, user_id)

    login(client, user_id)
    response = client.post(
        "/my-applications/app/%d/edit" % app_id,
        data={
            "description": "Now maintained by its owner.",
            "lifecycle_status": "operational",
            "health_status": "at_risk",
            "technical_owner": "R. Patel",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        saved = ApplicationComponent.query.get(app_id)
        assert saved.lifecycle_status == "operational"
        # health_status did not exist as a column, so the health overview could
        # only ever report "unknown" for every application.
        assert saved.health_status == "at_risk"
        assert saved.technical_owner == "R. Patel"


def test_an_application_manager_cannot_edit_an_application_they_do_not_own(app, client):
    """Same organisation is not sufficient - the persona is scoped by ownership."""
    from app import db
    from app.models.application_portfolio import ApplicationComponent

    with app.app_context():
        org_id = make_org(db, "SameOrg")
        owner_id = make_user(db, org_id, "owner", enterprise_role="application_manager")
        other_id = make_user(db, org_id, "other", enterprise_role="application_manager")
        app_id = _owned_application(db, org_id, owner_id)

    login(client, other_id)
    response = client.post(
        "/my-applications/app/%d/edit" % app_id,
        data={"description": "Not mine to change.", "lifecycle_status": "retired"},
    )
    assert response.status_code == 404

    with app.app_context():
        # Read the DATABASE, not the identity map. ApplicationComponent.query.get()
        # returns the cached object without emitting SQL on a hit (CLAUDE.md), so
        # it would report the pre-request value and pass even if the unauthorised
        # edit HAD been applied -- a false pass on the exact thing under test.
        db.session.expunge_all()
        saved = db.session.execute(
            db.select(ApplicationComponent).filter_by(id=app_id)
        ).scalar_one()
        assert saved.lifecycle_status != "retired"


def test_licence_entitlement_is_tenant_scoped():
    """It carried organization_id but not the mixin, so nothing filtered it."""
    from app.models.license_entitlement import LicenseEntitlement
    from app.models.mixins import TenantMixin

    assert issubclass(LicenseEntitlement, TenantMixin), (
        "LicenseEntitlement lost TenantMixin - isolation is back to depending on "
        "every caller remembering an organization_id filter"
    )
