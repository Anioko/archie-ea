"""Shared helper for hand-rolled test login fixtures.

``session-invalidation-on-logout`` made every authenticated request check a
server-side registry record (``app.services.session_registry``) keyed by a
``_sid`` in the signed session, failing CLOSED when it is missing. Dozens of
test modules pre-date that and build a session by writing ``_user_id``/
``_fresh`` directly into ``client.session_transaction()``, bypassing
``login_user()``/``session_registry.issue()`` entirely -- which this fix
would otherwise reject as an unregistered session on every request.

``mint_test_sid`` mints the same kind of registry row the real login path
does, so those hand-rolled helpers keep working. It must be called inside an
open app/db context (the same one ``client.session_transaction()`` is used
in), before opening the session transaction, and its result written into
``sess["_sid"]`` inside that transaction.
"""

import secrets


def _do_mint(user_id, organization_id):
    from app.extensions import db
    from app.models.user_session import UserSession

    sid = secrets.token_urlsafe(32)
    db.session.add(UserSession(sid=sid, user_id=int(user_id), organization_id=organization_id))
    db.session.commit()
    return sid


def mint_test_sid(user_id, organization_id=None, app=None):
    """Insert a ``user_sessions`` row for ``user_id`` and return its sid.

    Best-effort: returns ``None`` (never raises) if it cannot run, so a
    caller with no DB/app context available degrades to the pre-fix
    behaviour rather than erroring the whole test.

    ``app``: pass this when the caller may run with no app context already
    active -- notably a worker thread spawned by ``ThreadPoolExecutor`` in a
    concurrency test, where Flask's context is thread-local and simply isn't
    there. A missing sid there isn't a silent degrade: it makes every
    request in that thread fail the fail-closed revocation check this fix
    added, which is a false failure in the test, not a real one. Flask-
    SQLAlchemy's session factory is patched process-wide by the ``db_session``
    fixture, so a session opened in a fresh app context here still resolves
    to the same wrapped, rolled-back connection.
    """
    from flask import has_app_context

    try:
        if has_app_context():
            return _do_mint(user_id, organization_id)
        if app is not None:
            with app.app_context():
                return _do_mint(user_id, organization_id)
        return None
    except Exception:
        return None
