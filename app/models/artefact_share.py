"""Revocable, read-only share links for business-architecture artefacts (BA-B1).

Senior leadership will not log into an EA tool. If a capability framework cannot
travel to them, it is shelf-ware. This model is the credential that lets exactly
one artefact, belonging to exactly one organisation, be read without a login.

Deliberately **not** a ``TenantMixin`` model. The whole point of the row is to be
resolvable from an unauthenticated request, where ``g.current_org_id`` is None and
the automatic tenant filter is a documented no-op — so a mixin here would give the
false impression of protection on the one path that actually needs it. Instead the
``organization_id`` column is explicit and mandatory, every owner-side query filters
on it by hand, and the public route derives its tenant scope *from the row itself*.
"""

from __future__ import annotations

import secrets

from app.datetime_helpers import utcnow

from .. import db

#: Artefacts that may be shared. The token carries no other authority, so this
#: allow-list is what bounds a public request — a type outside it is a 404.
SHAREABLE_ARTEFACTS = {
    "maturity_heatmap": "Capability Maturity Heatmap",
    "capability_map": "Capability Map",
    "capability_roadmap": "Capability Roadmap",
}


def generate_share_token() -> str:
    """A cryptographically secure 32-char URL-safe token.

    Same construction as the Code Workbench share links
    (``app/modules/codegen/routes/share_routes.py``): ``secrets.token_urlsafe(24)``
    is 192 bits of entropy rendered as 32 URL-safe characters. Never a sequential id.
    """
    return secrets.token_urlsafe(24)


class ArtefactShareLink(db.Model):
    """One revocable read-only link to one artefact of one organisation."""

    __tablename__ = "artefact_share_links"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)

    #: One of SHAREABLE_ARTEFACTS.
    artefact_type = db.Column(db.String(64), nullable=False, index=True)

    #: The single organisation this token may ever read. Not nullable: a link with
    #: no org would be a cross-tenant read waiting to happen.
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    label = db.Column(db.String(200))

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    #: Set to revoke. Non-NULL means the token stops resolving immediately.
    revoked_at = db.Column(db.DateTime)
    last_viewed_at = db.Column(db.DateTime)
    view_count = db.Column(db.Integer, default=0, nullable=False)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    @property
    def artefact_title(self) -> str:
        return SHAREABLE_ARTEFACTS.get(self.artefact_type, "Architecture Artefact")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        state = "active" if self.is_active else "revoked"
        return f"<ArtefactShareLink {self.artefact_type} org={self.organization_id} {state}>"
