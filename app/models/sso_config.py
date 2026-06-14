"""
SSOConfig model — per-organisation SSO federation config (COM-005).

One record per organisation. Stores OIDC client credentials (encrypted)
and SAML IdP metadata URL. Email-domain matching routes login to IdP.
"""

import logging
import os

from app import db

logger = logging.getLogger(__name__)


class SSOConfig(db.Model):  # migration-exempt
    """Per-organisation SSO configuration for SAML 2.0 / OIDC federation."""

    __tablename__ = "sso_configs"

    id = db.Column(db.Integer, primary_key=True)
    # One SSO config per organisation
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    # 'saml' or 'oidc'
    protocol = db.Column(db.String(10), nullable=False, default="oidc")
    # SAML: IdP metadata URL; OIDC: OpenID Connect discovery document URL
    idp_metadata_url = db.Column(db.String(500))
    # OIDC client credentials
    client_id = db.Column(db.String(255))
    # Encrypted with Fernet; use the client_secret property for access
    _client_secret_encrypted = db.Column("client_secret_encrypted", db.String(1000))
    # JSON map of IdP claim names → platform attribute names (optional override)
    attribute_mapping = db.Column(db.JSON, default=dict)
    # Comma-separated email domains that trigger this config, e.g. "acme.com,acme.co.uk"
    email_domain = db.Column(db.String(500))
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    organization = db.relationship(
        "Organization", backref=db.backref("sso_config", uselist=False)
    )

    # ------------------------------------------------------------------
    # Fernet-encrypted client_secret property
    # ------------------------------------------------------------------

    @property
    def client_secret(self):
        """Decrypt and return the OIDC client secret."""
        if not self._client_secret_encrypted:
            return None
        key = os.environ.get("FERNET_KEY")
        if not key:
            # No encryption key — value was stored as plaintext
            return self._client_secret_encrypted
        try:
            from cryptography.fernet import Fernet

            f = Fernet(key.encode())
            return f.decrypt(self._client_secret_encrypted.encode()).decode()
        except Exception as exc:
            logger.error("Failed to decrypt client_secret: %s", exc)
            return self._client_secret_encrypted

    @client_secret.setter
    def client_secret(self, value):
        """Encrypt and store the OIDC client secret."""
        if not value:
            self._client_secret_encrypted = None
            return
        key = os.environ.get("FERNET_KEY")
        if not key:
            logger.warning(
                "FERNET_KEY not set; storing SSO client_secret as plaintext. "
                "Set FERNET_KEY for production use."
            )
            self._client_secret_encrypted = value
            return
        try:
            from cryptography.fernet import Fernet

            f = Fernet(key.encode())
            self._client_secret_encrypted = f.encrypt(value.encode()).decode()
        except Exception as exc:
            logger.error(
                "Failed to encrypt client_secret (storing plaintext): %s", exc
            )
            self._client_secret_encrypted = value

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def email_domains(self):
        """Return list of configured email domains (supports comma-separated)."""
        if not self.email_domain:
            return []
        return [d.strip().lower() for d in self.email_domain.split(",") if d.strip()]

    def __repr__(self):
        return (
            f"<SSOConfig org={self.organization_id} protocol={self.protocol} "
            f"enabled={self.enabled}>"
        )
