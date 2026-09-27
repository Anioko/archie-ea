"""Shared helper for hand-rolled test login fixtures.

``session-invalidation-on-logout`` made every authenticated request check a
server-side registry record (``app.services.session_registry``) keyed by a
``_sid`` in the signed session, failing CLOSED when it is missing. Dozens of
test modules pre-date that and build a session by writing ``_user_id``/
``_fresh`` directly into ``client.session_transaction()``, bypassing
``login_user()``/``session_registry.issue()`` entirely -- which this fix
would otherwise reject as an unregistered session on every request.

``mint_test_sid`` mints the same kind of registry row the real login path
does, so those hand-rolled helpers keep working. It needs an open app/db
context, or an ``app=`` to open one, and its result must be written into
``sess["_sid"]`` inside the ``client.session_transaction()`` block. It never
returns ``None``: a login that cannot be registered is an error, because an
unregistered session is rejected as revoked on the first request and the
failure would otherwise surface far from its cause.
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

    Raises ``RuntimeError`` when the row cannot be written: either no app
    context is open and no ``app`` was passed, or the insert itself failed.
    A missing sid is never returned, because a session without one is
    rejected by the fail-closed revocation check on its first request.

    ``app``: pass this whenever the caller may run with no app context open
    -- a test that logs in after its ``with app.app_context():`` blocks have
    closed (the test client's own ``client.application`` is always at hand),
    or a worker thread spawned by ``ThreadPoolExecutor`` in a concurrency
    test, where Flask's context is thread-local and simply isn't there.
    Flask-SQLAlchemy's session factory is patched process-wide by the
    ``db_session`` fixture, so a session opened in a fresh app context here
    still resolves to the same wrapped, rolled-back connection.
    """
    from flask import has_app_context

    if has_app_context():
        context = None
    elif app is not None:
        context = app.app_context()
    else:
        raise RuntimeError(
            "mint_test_sid(user_id=%r) was called with no app context open and "
            "no app= argument, so no session row can be registered and the "
            "login would be rejected as revoked. Pass app=client.application "
            "(or app=app) when logging in outside a `with app.app_context():` "
            "block." % (user_id,)
        )

    try:
        if context is None:
            return _do_mint(user_id, organization_id)
        with context:
            return _do_mint(user_id, organization_id)
    except Exception as exc:
        raise RuntimeError(
            "mint_test_sid could not register a session row for user_id=%r: "
            "%s: %s" % (user_id, type(exc).__name__, exc)
        ) from exc
