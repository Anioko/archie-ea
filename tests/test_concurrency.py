"""Two people editing the same record must not silently overwrite each other.

OptimisticLockMixin declares version_id_col, so SQLAlchemy should append
`WHERE version = <read value>` to every UPDATE and raise StaleDataError when that
matches no row. Whether it actually does is not something you can tell by reading
the model - the mixin is declarative, and a mapper misconfiguration produces a
class that looks correct and silently last-write-wins.

That failure mode is quiet and expensive. Two architects open the same
application, both save, and the second overwrites the first with no error shown
to anyone. Nothing appears in the log, and the data is simply wrong afterwards.

These tests use two independent sessions against one row - the same shape as two
browser tabs - and assert the second write is refused.
"""

import uuid

import pytest

pytestmark = pytest.mark.journey


@pytest.fixture(scope="module")
def app():
    import os

    os.environ.setdefault("SECRET_KEY", "x" * 32)
    from app import create_app, db

    application = create_app("testing")
    with application.app_context():
        db.create_all()
    return application


def _lock_attr(cls):
    """The attribute SQLAlchemy actually increments, whatever it is called.

    ApplicationComponent cannot use the mixin's `version`: that name is already
    taken by the application's own release string ("2.1.0"), which a user edits.
    Asking the mapper avoids hard-coding either name and keeps the test honest
    if a model renames its lock column later.
    """
    from sqlalchemy import inspect as sa_inspect

    col = sa_inspect(cls).version_id_col
    assert col is not None, (
        "%s maps without version_id_col, so concurrent writes are "
        "last-write-wins" % cls.__name__)
    return col.name


@pytest.fixture
def component(app):
    """A row to fight over, plus its organisation."""
    from app import db
    from app.models.application_portfolio import ApplicationComponent
    from app.models.organization import Organization

    marker = uuid.uuid4().hex[:8]
    with app.app_context():
        org = Organization(name="Lock %s" % marker, slug="lock-%s" % marker)
        db.session.add(org)
        db.session.commit()
        row = ApplicationComponent(name="Contended %s" % marker, organization_id=org.id)
        db.session.add(row)
        db.session.commit()
        return {"id": row.id, "org_id": org.id, "marker": marker}


def test_the_version_column_exists_and_starts_populated(app, component):
    """A NULL version silently disables the whole mechanism."""
    from app.models.application_portfolio import ApplicationComponent

    with app.app_context():
        attr = _lock_attr(ApplicationComponent)
        row = ApplicationComponent.query.get(component["id"])
        assert getattr(row, attr, None) is not None, (
            "%s is NULL - SQLAlchemy compares it with `= NULL`, which matches no "
            "row, so every save on this application would be refused" % attr)


def test_a_concurrent_update_is_refused(app, component):
    """The core guarantee, exercised with two real sessions."""
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.orm.exc import StaleDataError

    from app import db
    from app.models.application_portfolio import ApplicationComponent

    with app.app_context():
        Session = sessionmaker(bind=db.engine)
        first, second = Session(), Session()
        try:
            # Both read the row at the same version - two tabs, one record.
            attr = _lock_attr(ApplicationComponent)
            a = first.get(ApplicationComponent, component["id"])
            b = second.get(ApplicationComponent, component["id"])
            assert getattr(a, attr) == getattr(b, attr), (
                "the two sessions did not start level")

            a.description = "written by the first editor"
            first.commit()

            b.description = "written by the second editor"
            with pytest.raises(StaleDataError):
                second.commit()
        finally:
            first.close()
            second.close()


def test_the_first_writer_survives(app, component):
    """A refused write must not be a partially applied one."""
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.orm.exc import StaleDataError

    from app import db
    from app.models.application_portfolio import ApplicationComponent

    with app.app_context():
        Session = sessionmaker(bind=db.engine)
        first, second = Session(), Session()
        try:
            a = first.get(ApplicationComponent, component["id"])
            b = second.get(ApplicationComponent, component["id"])
            a.description = "kept"
            first.commit()
            b.description = "lost"
            try:
                second.commit()
            except StaleDataError:
                second.rollback()
        finally:
            first.close()
            second.close()

        db.session.expire_all()
        row = ApplicationComponent.query.get(component["id"])
        assert row.description == "kept", (
            "the second writer overwrote the first - optimistic locking is not "
            "protecting this row")


def test_the_version_advances_on_write(app, component):
    """If version never moves, the guard is inert even when configured."""
    from sqlalchemy.orm import sessionmaker

    from app import db
    from app.models.application_portfolio import ApplicationComponent

    with app.app_context():
        Session = sessionmaker(bind=db.engine)
        attr = _lock_attr(ApplicationComponent)
        session = Session()
        try:
            row = session.get(ApplicationComponent, component["id"])
            before = getattr(row, attr)
            row.description = "bumped"
            session.commit()
            after = getattr(row, attr)
        finally:
            session.close()

    assert after > before, (
        "version did not advance on UPDATE (%s -> %s), so a later writer reading "
        "the old value would be accepted" % (before, after))


def test_every_optimistically_locked_model_is_wired_up(app):
    """Inheriting the mixin is not the same as being configured by it.

    A model can carry OptimisticLockMixin and still map without version_id_col if
    __mapper_args__ is overridden downstream - which looks entirely correct in the
    class definition.
    """
    from sqlalchemy import inspect as sa_inspect

    from app.models.mixins import OptimisticLockMixin

    unwired = []
    with app.app_context():
        from app import db

        for mapper in db.Model.registry.mappers:
            cls = mapper.class_
            if not issubclass(cls, OptimisticLockMixin):
                continue
            if sa_inspect(cls).version_id_col is None:
                unwired.append(cls.__name__)

    assert not unwired, (
        "%d model(s) inherit OptimisticLockMixin but map without version_id_col, "
        "so concurrent writes are silently last-write-wins: %s"
        % (len(unwired), sorted(unwired)))
