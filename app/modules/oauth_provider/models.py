"""OAuth 2.0 authorization server models — the one system of record for MCP
connector clients, authorization codes, and tokens.

Nothing here stores a usable secret: access tokens, refresh tokens and
authorization codes are hashed (SHA-256) before they are written, and looked
up by hash. The plaintext value is returned to the caller exactly once, at
issuance, and never persisted or logged.

``organization_id`` on ``OAuthAuthorizationCode`` and ``OAuthToken`` overrides
``TenantMixin``'s default NOT NULL column to be nullable
(tenant-scoping-ok: a code/token row is written inside the same request that
authenticates its user, before the tenant-context middleware has necessarily
resolved an organization for every code path that can reach here — e.g. a
`resource` mismatch or an admin re-running `flask oauth prune-clients`
against orphaned rows). Every runtime read filters explicitly by the
resource-owning user's organization_id rather than relying on the implicit
tenant query filter, so a NULL value here can only ever under-scope a write,
never leak a read across organizations.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from app.extensions import db
from app.models.mixins import TenantMixin


def generate_client_id() -> str:
    return "mcp_" + secrets.token_urlsafe(24)


def generate_token() -> str:
    """A high-entropy, URL-safe plaintext token (never stored as-is)."""
    return secrets.token_urlsafe(32)


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


class OAuthClient(db.Model):
    """A registered OAuth client (an assistant/agent connecting to /mcp).

    Not tenant-scoped: a single client (e.g. one Claude installation) is
    shared across whichever organizations its holder is a member of. Reads
    of this table are safe without a tenant filter because it holds no
    business data — only public client metadata — but call sites still
    annotate the read (tenant-scoping-ok: <reason>) so a reviewer never has
    to re-derive that from scratch.
    """

    __tablename__ = "oauth_clients"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    client_name = db.Column(db.String(100), nullable=False)
    redirect_uris = db.Column(db.JSON, nullable=False, default=list)
    token_endpoint_auth_method = db.Column(db.String(32), nullable=False, default="none")
    grant_types = db.Column(
        db.JSON, nullable=False, default=lambda: ["authorization_code", "refresh_token"]
    )
    response_types = db.Column(db.JSON, nullable=False, default=lambda: ["code"])
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_token_exchange_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def register(cls, client_name: str, redirect_uris: list[str]) -> "OAuthClient":
        """The one path that creates an OAuthClient row.

        Raises ``ValueError`` with a message safe to surface as
        ``invalid_client_metadata`` on any input that fails validation.
        """
        from app.utils.text_sanitization import neutralize_untrusted_text
        from app.modules.oauth_provider.validation import validate_redirect_uris

        if not client_name or not str(client_name).strip():
            raise ValueError("client_name is required")
        clean_name = neutralize_untrusted_text(client_name, max_len=100).strip()
        if not clean_name:
            raise ValueError("client_name is required")

        clean_uris = validate_redirect_uris(redirect_uris)

        client = cls(
            client_id=generate_client_id(),
            client_name=clean_name,
            redirect_uris=clean_uris,
            token_endpoint_auth_method="none",
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
        )
        db.session.add(client)
        db.session.commit()
        return client


class OAuthAuthorizationCode(TenantMixin, db.Model):
    """A single-use authorization code, hashed at rest."""

    __tablename__ = "oauth_authorization_codes"

    id = db.Column(db.Integer, primary_key=True)

    # tenant-scoping-ok: see module docstring — nullable override of TenantMixin.
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("oauth_clients.id", ondelete="CASCADE"), nullable=False)

    code_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    redirect_uri = db.Column(db.String(2048), nullable=False)
    scope = db.Column(db.String(255), nullable=False, default="")
    resource = db.Column(db.String(2048), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    client = db.relationship("OAuthClient")

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None


class OAuthToken(TenantMixin, db.Model):
    """One access/refresh token pair issued from a single grant.

    A refresh exchange rotates the pair: the old row is revoked and a brand
    new row (new access + refresh hash) is written, rather than mutating the
    existing row's hashes in place, so a stolen, already-used refresh token
    is easy to notice (its row is revoked, not silently updated).
    """

    __tablename__ = "oauth_tokens"

    id = db.Column(db.Integer, primary_key=True)

    # tenant-scoping-ok: see module docstring — nullable override of TenantMixin.
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("oauth_clients.id", ondelete="CASCADE"), nullable=False)

    access_token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    refresh_token_hash = db.Column(db.String(64), unique=True, nullable=True, index=True)

    scope = db.Column(db.String(255), nullable=False, default="")
    resource = db.Column(db.String(2048), nullable=False)
    grant_type = db.Column(db.String(32), nullable=False)  # authorization_code | refresh_token | personal

    issued_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    access_token_expires_at = db.Column(db.DateTime, nullable=False)
    refresh_token_expires_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)

    # Slice 3 (self-hosted personal token): a human label for tokens minted
    # from the account panel rather than an OAuth grant. Unused by the
    # authorization-code/refresh flows.
    label = db.Column(db.String(100), nullable=True)

    client = db.relationship("OAuthClient")
    user = db.relationship("User")

    @property
    def is_access_token_expired(self) -> bool:
        return datetime.utcnow() >= self.access_token_expires_at

    @property
    def is_refresh_token_expired(self) -> bool:
        if self.refresh_token_expires_at is None:
            return True
        return datetime.utcnow() >= self.refresh_token_expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def scopes(self) -> list[str]:
        return [s for s in (self.scope or "").split(" ") if s]

    def revoke(self) -> None:
        self.revoked_at = datetime.utcnow()
