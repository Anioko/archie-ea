"""Server-side session registry (finding: sessions survive logout).

The default Flask session is a client-side signed cookie: once issued it is a
self-verifying credential and nothing server-side can revoke it before its
absolute expiry. ``UserSession`` is a minimal per-login record, keyed by a
random ``sid`` embedded in the signed cookie, that the request path can check
and that logout / password-change can mark revoked. See
``docs/buckets/session-invalidation-on-logout/`` for the full writeup.

Deliberately **not** a ``TenantMixin`` model. This table is read on every
authenticated request inside ``app/_bootstrap/session_policy.py``, including
the moment right after login and before ``g.current_org_id`` is populated for
the request — a tenant filter here would break login/session enforcement
itself. ``organization_id`` is carried as plain data (for admin surfacing
only); every real query against this table is keyed by ``sid`` or
``user_id``, both already user-scoped. Do not add ``TenantMixin`` "for
consistency" — it would silently break authentication.
"""

from datetime import datetime

from app.extensions import db


class UserSession(db.Model):
    """One row per issued login session (a ``login_user()`` call)."""

    __tablename__ = "user_sessions"

    sid = db.Column(db.String(64), primary_key=True)
    # ondelete="CASCADE" (D4, round 2): sessions are only ever flagged revoked,
    # never deleted (except via the manual `purge-sessions` CLI), so any user
    # who has ever logged in accumulates permanent user_sessions rows. Without
    # this, AdminUserService.delete_user's bare db.session.delete(user) 500s
    # with a ForeignKeyViolation for every such user. Safe on this table: it
    # carries no data anyone still needs once the owning user is gone.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Data only -- deliberately NOT filtered by tenant middleware. See module docstring.
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True, index=True)
    revoked_reason = db.Column(db.String(32), nullable=True)  # 'logout' | 'password_change' | 'idle_timeout' | 'admin'
    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<UserSession sid={self.sid[:8]}... user_id={self.user_id} revoked={self.revoked_at is not None}>"
