"""Exercise the shared rollback fixture against the explicit PostgreSQL test DB."""

import os
import uuid

import pytest
import sqlalchemy as sa

from tests.conftest import db_session as shared_db_session


pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Rollback integration requires an explicit TEST_DATABASE_URL",
)


@pytest.mark.parametrize("raise_inside", [False, True])
def test_committed_organization_is_removed_by_fixture_teardown(app, _schema, raise_inside):
    from app import db
    from app.models.organization import Organization

    slug = "rollback-probe-" + uuid.uuid4().hex
    statement = sa.select(Organization.id).where(Organization.slug == slug)
    with app.app_context():
        engine = db.engine
        assert engine.dialect.name == "postgresql"
        original_class = db.session.session_factory.class_
        original_options = dict(db.session.session_factory.kw)
        with engine.connect() as check:
            assert check.execute(statement).first() is None

    # Drive the real shared fixture lifecycle explicitly so the post-teardown
    # assertion is in the same test and cannot depend on test execution order.
    fixture = shared_db_session.__wrapped__(app, _schema)
    session = next(fixture)
    try:
        connection = session.get_bind()
        assert isinstance(connection, sa.engine.Connection)
        assert connection.in_transaction()
        assert session.get_bind(mapper=Organization) is connection
        assert session.get_bind(clause=Organization.__table__) is connection
        session.add(Organization(name="Synthetic rollback probe", slug=slug))
        session.commit()
        assert connection.in_transaction()
        assert session.execute(statement).first() is not None
        with engine.connect() as observer:
            assert observer.execute(statement).first() is None
        session.remove()
        with app.app_context():
            assert db.session.get_bind() is connection
            assert db.session.execute(statement).first() is not None
            db.session.commit()
    finally:
        if raise_inside:
            with pytest.raises(RuntimeError, match="synthetic body failure"):
                fixture.throw(RuntimeError("synthetic body failure"))
        else:
            fixture.close()

    with app.app_context():
        assert db.engine is engine
        assert db.session.session_factory.class_ is original_class
        assert db.session.session_factory.kw == original_options
        with engine.connect() as check:
            assert check.execute(statement).first() is None
