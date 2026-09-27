"""Real PostgreSQL catalog queries through both authenticated Flask endpoints.

Requires explicit TEST_DATABASE_URL. Shared db_session owns the rollback: the
temporary deactivation of any existing catalog is never committed. All inserted
templates are synthetic custom test data, not production framework content.
"""

import os
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Framework database tests require an explicit TEST_DATABASE_URL",
)

ENDPOINTS = (
    "/dashboard/api/templates/frameworks",
    "/applications/api/templates/frameworks",
)


@pytest.fixture
def catalog_session(db_session):
    from app.models.element_templates import ElementTemplate

    # The shared fixture binds this session to its rollback-owned connection.
    # Never commit: reference rows may predate this test and must be restored.
    connection = db_session.get_bind()
    assert connection.in_transaction(), "catalog setup requires the shared rollback transaction"
    ElementTemplate.query.filter_by(is_active=True).update(
        {ElementTemplate.is_active: False}, synchronize_session="fetch")
    db_session.flush()
    assert ElementTemplate.query.filter_by(is_active=True).count() == 0
    yield db_session


@pytest.fixture
def catalog_user(catalog_session, make_org):
    from app.models.user import Permission, Role, User

    suffix = uuid.uuid4().hex[:10]
    org = make_org("framework-catalog")
    role = Role(name="Framework reader %s" % suffix, permissions=Permission.GENERAL)
    user = User(email="framework-%s@example.com" % suffix, role=role,
                organization_id=org.id, confirmed=True,
                enterprise_role="enterprise_architect")
    catalog_session.add_all([role, user])
    catalog_session.flush()
    return user


def _template(framework, name, active=True):
    from app.models.element_templates import ElementTemplate

    return ElementTemplate(
        framework=framework, name=name, element_type="BusinessProcess", layer="business",
        is_active=active, is_custom=True, description="Synthetic catalog regression fixture.",
    )


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_catalog_empty_active_collection_returns_array(
    endpoint, catalog_session, catalog_user, client, login_as
):
    login_as(client, catalog_user)
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.get_json() == []


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_catalog_inactive_templates_do_not_expose_frameworks(
    endpoint, catalog_session, catalog_user, client, login_as
):
    catalog_session.add(_template("TEST CUSTOM INACTIVE", "Inactive fixture", active=False))
    catalog_session.flush()
    login_as(client, catalog_user)
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.get_json() == []


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_catalog_returns_only_distinct_sorted_active_frameworks(
    endpoint, catalog_session, catalog_user, client, login_as
):
    suffix = uuid.uuid4().hex[:10]
    catalog_session.add_all([
        _template("TEST CUSTOM Z", "Z fixture %s" % suffix),
        _template("TEST CUSTOM A", "A first %s" % suffix),
        _template("TEST CUSTOM A", "A second %s" % suffix),
        _template("TEST CUSTOM INACTIVE", "Inactive %s" % suffix, active=False),
    ])
    catalog_session.flush()
    login_as(client, catalog_user)
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.get_json() == ["TEST CUSTOM A", "TEST CUSTOM Z"]
