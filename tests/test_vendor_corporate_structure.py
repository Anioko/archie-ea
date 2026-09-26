"""A vendor record carries its parent group and legal entities, and stays single.

The group structure cannot become circular, a registry identifier cannot be
kept without the entity's name, and the standalone create form refuses a
second record whose name differs only in letter case or spacing.
"""

import uuid

import pytest
from werkzeug.datastructures import MultiDict

pytestmark = pytest.mark.usefixtures("db_session")


def _vendor(db_session, name):
    from app.models.vendor.vendor_organization import VendorOrganization

    vendor = VendorOrganization(name=f"{name} {uuid.uuid4().hex[:8]}")
    db_session.add(vendor)
    db_session.flush()
    return vendor


def test_parent_group_and_legal_entities_are_recorded(db_session):
    holding, cloud = _vendor(db_session, "Holding"), _vendor(db_session, "Cloud")
    cloud.apply_corporate_structure(MultiDict([
        ("parent_vendor_id", str(holding.id)),
        ("legal_entity_name", "Cloud Ltd"), ("legal_entity_identifier", "GB-1"),
        ("legal_entity_name", "  "), ("legal_entity_identifier", ""),
        ("legal_entity_name", "Cloud Inc"), ("legal_entity_identifier", ""),
    ]))
    db_session.flush()
    assert cloud.parent_vendor is holding and holding.group_members == [cloud]
    assert cloud.legal_entities == [{"name": "Cloud Ltd", "identifier": "GB-1"},
                                    {"name": "Cloud Inc", "identifier": None}]

    cloud.apply_corporate_structure(MultiDict([("parent_vendor_id", "")]))
    assert cloud.parent_vendor_id is None and cloud.legal_entities is None


def test_group_structure_cannot_become_circular(db_session):
    holding, cloud = _vendor(db_session, "Holding"), _vendor(db_session, "Cloud")
    cloud.apply_corporate_structure(MultiDict([("parent_vendor_id", str(holding.id))]))
    db_session.flush()
    with pytest.raises(ValueError, match="cannot be its own parent group"):
        holding.apply_corporate_structure(MultiDict([("parent_vendor_id", str(cloud.id))]))
    with pytest.raises(ValueError, match="cannot be its own parent group"):
        holding.apply_corporate_structure(MultiDict([("parent_vendor_id", str(holding.id))]))


def test_an_identifier_needs_a_name_and_a_parent_must_exist(db_session):
    cloud = _vendor(db_session, "Cloud")
    with pytest.raises(ValueError, match="Give the legal entity with identifier GB-9 a name"):
        cloud.apply_corporate_structure(MultiDict([
            ("legal_entity_name", ""), ("legal_entity_identifier", "GB-9")]))
    with pytest.raises(ValueError, match="no longer exists"):
        cloud.apply_corporate_structure(MultiDict([("parent_vendor_id", "999999999")]))


def test_create_form_refuses_a_name_differing_only_in_case(app, db_session, make_org, login_as):
    from app.models.user import Role, User
    from app.models.vendor.vendor_organization import VendorOrganization

    existing = _vendor(db_session, "Launch Vendor")
    org = make_org("vendor-dup")
    Role.insert_roles()
    user = User(email=f"vendor-dup-{uuid.uuid4().hex[:8]}@example.com", first_name="Test", last_name="User",
                organization_id=org.id, confirmed=True, enterprise_role="procurement",
                role=Role.query.filter_by(name="Architect").first())
    user.password = uuid.uuid4().hex
    db_session.add(user)
    db_session.flush()
    client = app.test_client()
    login_as(client, user)
    response = client.post("/applications/vendors/create", data={"name": "  " + existing.name.upper() + " "})
    assert response.status_code == 409
    assert b"already in the vendor catalogue" in response.data
    matches = VendorOrganization.query.filter(
        VendorOrganization.name.ilike(existing.name)).count()
    assert matches == 1
