"""
ConnectorConfig model — per-organisation connector credentials and settings.

Stores encrypted credentials for external connectors (ServiceNow, Jira, M365).
Unique per (organization_id, connector_type).
"""

import logging
import os
import uuid
from datetime import datetime

from app.extensions import db

logger = logging.getLogger(__name__)


def _fernet():
    """Return a Fernet instance using FERNET_KEY env var, or None if absent."""
    key = os.environ.get("FERNET_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        logger.warning("Failed to initialise Fernet for credential encryption: %s", exc)
        return None


class OrgConnectorConfig(db.Model):
    """Per-organisation connector configuration with encrypted credentials."""

    __tablename__ = "org_connector_configs"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "connector_type", name="uq_org_connector_type"),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_type = db.Column(db.String(50), nullable=False)  # 'servicenow', 'jira', 'm365'
    instance_url = db.Column(db.String(512))
    client_id = db.Column(db.String(255))
    _client_secret_encrypted = db.Column("client_secret_encrypted", db.String(1024))
    field_mapping = db.Column(db.JSON, default=dict)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    last_sync_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    organization = db.relationship("Organization", backref="connector_configs")

    # ------------------------------------------------------------------
    # Encrypted credential property
    # ------------------------------------------------------------------

    @property
    def client_secret(self) -> str | None:
        """Return decrypted client secret, or plaintext if no FERNET_KEY."""
        if not self._client_secret_encrypted:
            return None
        f = _fernet()
        if f is None:
            return self._client_secret_encrypted
        try:
            return f.decrypt(self._client_secret_encrypted.encode()).decode()
        except Exception as exc:
            logger.error("Failed to decrypt client_secret: %s", exc)
            return None

    @client_secret.setter
    def client_secret(self, value: str | None) -> None:
        """Encrypt and store client secret.  Falls back to plaintext + warning."""
        if value is None:
            self._client_secret_encrypted = None
            return
        f = _fernet()
        if f is None:
            logger.warning(
                "FERNET_KEY not set — storing connector client_secret as plaintext. "
                "Set FERNET_KEY in production."
            )
            self._client_secret_encrypted = value
        else:
            self._client_secret_encrypted = f.encrypt(value.encode()).decode()

    def __repr__(self) -> str:
        return f"<ConnectorConfig {self.connector_type} org={self.organization_id}>"


class DevOpsConnectorConfig(db.Model):  # migration-exempt — COM-018
    """Per-org GitHub / Azure DevOps connector configuration.

    One record per organisation.  Access token is Fernet-encrypted using
    the ``FERNET_KEY`` environment variable (graceful plaintext fallback
    when the key is absent, e.g. in development).
    """

    __tablename__ = "devops_connector_configs"
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "connector_type",
            name="uq_devops_connector_org_type",
        ),
        {"extend_existing": True},
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_type = db.Column(db.String(50), nullable=False, default="devops")
    # 'github' or 'azure_devops'
    provider = db.Column(db.String(50), nullable=False, default="github")
    # GitHub Enterprise base URL or Azure DevOps org URL; leave blank for cloud
    instance_url = db.Column(db.String(512), nullable=True)
    client_id = db.Column(db.String(255), nullable=True)
    # Fernet-encrypted PAT / OAuth token — use the access_token property
    _access_token_encrypted = db.Column("access_token_encrypted", db.String(2000), nullable=True)
    # Full repo URL, e.g. https://github.com/acme/myrepo
    repo_url = db.Column(db.String(512), nullable=True)
    default_base_branch = db.Column(db.String(100), nullable=True, default="main")
    field_mapping = db.Column(db.JSON, default=dict)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    organization = db.relationship(
        "Organization", backref=db.backref("devops_connector_config", uselist=False)
    )

    # ------------------------------------------------------------------
    # Fernet-encrypted access_token property
    # ------------------------------------------------------------------

    @property
    def access_token(self) -> str | None:
        """Decrypt and return the stored access token."""
        if not self._access_token_encrypted:
            return None
        f = _fernet()
        if f is None:
            return self._access_token_encrypted
        try:
            return f.decrypt(self._access_token_encrypted.encode()).decode("utf-8")
        except Exception as exc:
            logger.error("DevOpsConnectorConfig: failed to decrypt access_token: %s", exc)
            return self._access_token_encrypted

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        """Encrypt and store the access token."""
        if not value:
            self._access_token_encrypted = None
            return
        f = _fernet()
        if f is None:
            logger.warning(
                "FERNET_KEY not set — storing DevOps access_token as plaintext. "
                "Set FERNET_KEY for production use."
            )
            self._access_token_encrypted = value
        else:
            self._access_token_encrypted = f.encrypt(value.encode("utf-8")).decode("ascii")

    def __repr__(self) -> str:
        return f"<DevOpsConnectorConfig {self.provider} org={self.organization_id}>"


class LucidchartConnectorConfig(db.Model):  # migration-exempt — LUC-001
    """Per-org Lucidchart OAuth configuration with encrypted token storage."""

    __tablename__ = "lucidchart_connector_configs"
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            name="uq_lucidchart_connector_org",
        ),
        {"extend_existing": True},
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_type = db.Column(db.String(50), nullable=False, default="lucidchart")
    client_id = db.Column(db.String(255), nullable=True)
    _client_secret_encrypted = db.Column(
        "client_secret_encrypted",
        db.String(2000),
        nullable=True,
    )
    _access_token_encrypted = db.Column(
        "access_token_encrypted",
        db.String(4000),
        nullable=True,
    )
    _refresh_token_encrypted = db.Column(
        "refresh_token_encrypted",
        db.String(4000),
        nullable=True,
    )
    token_expires_at = db.Column(db.DateTime, nullable=True)
    scope = db.Column(db.String(1000), nullable=True)
    lucid_account_id = db.Column(db.String(255), nullable=True)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    organization = db.relationship(
        "Organization",
        backref=db.backref("lucidchart_connector_config", uselist=False),
    )

    @property
    def client_secret(self) -> str | None:
        """Decrypt and return the stored OAuth client secret."""
        if not self._client_secret_encrypted:
            return None
        f = _fernet()
        if f is None:
            return self._client_secret_encrypted
        try:
            return f.decrypt(self._client_secret_encrypted.encode()).decode("utf-8")
        except Exception as exc:
            logger.error("LucidchartConnectorConfig: failed to decrypt client_secret: %s", exc)
            return self._client_secret_encrypted

    @client_secret.setter
    def client_secret(self, value: str | None) -> None:
        """Encrypt and store the OAuth client secret."""
        if not value:
            self._client_secret_encrypted = None
            return
        f = _fernet()
        if f is None:
            logger.warning(
                "FERNET_KEY not set — storing Lucidchart client_secret as plaintext. "
                "Set FERNET_KEY for production use."
            )
            self._client_secret_encrypted = value
        else:
            self._client_secret_encrypted = f.encrypt(value.encode("utf-8")).decode("ascii")

    @property
    def access_token(self) -> str | None:
        """Decrypt and return the stored Lucidchart access token."""
        if not self._access_token_encrypted:
            return None
        f = _fernet()
        if f is None:
            return self._access_token_encrypted
        try:
            return f.decrypt(self._access_token_encrypted.encode()).decode("utf-8")
        except Exception as exc:
            logger.error("LucidchartConnectorConfig: failed to decrypt access_token: %s", exc)
            return self._access_token_encrypted

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        """Encrypt and store the Lucidchart access token."""
        if not value:
            self._access_token_encrypted = None
            return
        f = _fernet()
        if f is None:
            logger.warning(
                "FERNET_KEY not set — storing Lucidchart access_token as plaintext. "
                "Set FERNET_KEY for production use."
            )
            self._access_token_encrypted = value
        else:
            self._access_token_encrypted = f.encrypt(value.encode("utf-8")).decode("ascii")

    @property
    def refresh_token(self) -> str | None:
        """Decrypt and return the stored Lucidchart refresh token."""
        if not self._refresh_token_encrypted:
            return None
        f = _fernet()
        if f is None:
            return self._refresh_token_encrypted
        try:
            return f.decrypt(self._refresh_token_encrypted.encode()).decode("utf-8")
        except Exception as exc:
            logger.error("LucidchartConnectorConfig: failed to decrypt refresh_token: %s", exc)
            return self._refresh_token_encrypted

    @refresh_token.setter
    def refresh_token(self, value: str | None) -> None:
        """Encrypt and store the Lucidchart refresh token."""
        if not value:
            self._refresh_token_encrypted = None
            return
        f = _fernet()
        if f is None:
            logger.warning(
                "FERNET_KEY not set — storing Lucidchart refresh_token as plaintext. "
                "Set FERNET_KEY for production use."
            )
            self._refresh_token_encrypted = value
        else:
            self._refresh_token_encrypted = f.encrypt(value.encode("utf-8")).decode("ascii")

    def token_is_expired(self, now: datetime | None = None) -> bool:
        """Return True when the stored access token is missing or expired."""
        if self.token_expires_at is None:
            return True
        now = now or datetime.utcnow()
        return self.token_expires_at <= now

    def __repr__(self) -> str:
        return f"<LucidchartConnectorConfig org={self.organization_id} enabled={self.enabled}>"
