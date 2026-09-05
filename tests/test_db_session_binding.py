"""Narrow real-library fixture checks, not SQLite application qualification.

No Archie app factory runs here. SQLite only supplies disposable connections to
exercise Flask-SQLAlchemy routing and our fixture's transaction ownership.
"""

import sys
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy

from tests.conftest import db_session as shared_db_session


@pytest.mark.parametrize("raise_inside", [False, True])
def test_fixture_owns_mapped_commits_and_restores_context(monkeypatch, raise_inside):
    application = Flask(__name__)
    application.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_BINDS={"secondary": "sqlite://"},
    )
    extension = SQLAlchemy(application)

    class Probe(extension.Model):
        id = sa.Column(sa.Integer, primary_key=True)
        listener_seen = sa.Column(sa.Boolean, default=False)

    class SecondaryProbe(extension.Model):
        __bind_key__ = "secondary"
        id = sa.Column(sa.Integer, primary_key=True)

    @sa.event.listens_for(extension.session, "before_flush")
    def mark_new_rows(session, flush_context, instances):
        # Tenant middleware installs listeners on this same scoped-session
        # target. Replacing its class must preserve their effects on new rows.
        for row in session.new:
            if isinstance(row, Probe):
                row.listener_seen = True

    # Substitute only the fixture's lazy import; all session/engine APIs are real.
    monkeypatch.setitem(sys.modules, "app", SimpleNamespace(db=extension))
    with application.app_context():
        engines = dict(extension.engines)
        # Python sqlite3 legacy mode does not BEGIN before SAVEPOINT. Explicit
        # BEGIN makes this narrow harness transactional without claiming PG parity.
        for engine in engines.values():
            sa.event.listen(engine, "begin", lambda conn: conn.exec_driver_sql("BEGIN"))
        extension.create_all()
        original_class = extension.session.session_factory.class_
        original_options = dict(extension.session.session_factory.kw)
        existing_session = extension.session()
        fixture = shared_db_session.__wrapped__(application, True)
        session = next(fixture)
        try:
            connection = session.get_bind()
            assert isinstance(connection, sa.engine.Connection)
            assert connection.in_transaction()
            assert session.get_bind(mapper=Probe) is connection
            assert session.get_bind(clause=Probe.__table__) is connection
            secondary = session.get_bind(mapper=SecondaryProbe)
            assert isinstance(secondary, sa.engine.Connection)
            assert secondary.in_transaction()
            assert extension.engines == engines
            session.add_all([Probe(id=1), SecondaryProbe(id=1)])
            session.commit()
            session.remove()
            # A newly scoped session in a nested app context must still be bound.
            with application.app_context():
                assert extension.session.get_bind() is connection
                assert extension.session.get(Probe, 1) is not None
                assert extension.session.get(Probe, 1).listener_seen is True
                extension.session.add(Probe(id=2))
                extension.session.commit()
                extension.session.add(Probe(id=3))
                extension.session.flush()
                extension.session.rollback()
                assert extension.session.get(Probe, 3) is None
            assert connection.in_transaction()
        finally:
            if raise_inside:
                with pytest.raises(RuntimeError, match="test body failed"):
                    fixture.throw(RuntimeError("test body failed"))
            else:
                fixture.close()
        assert current_app._get_current_object() is application
        assert extension.session() is existing_session
        assert extension.session.session_factory.class_ is original_class
        assert extension.session.session_factory.kw == original_options
        assert extension.engines == engines
        for model, key in ((Probe, None), (SecondaryProbe, "secondary")):
            with engines[key].connect() as check:
                assert check.scalar(sa.select(sa.func.count()).select_from(model.__table__)) == 0
