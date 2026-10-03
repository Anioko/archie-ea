"""
ConnectorConfig model — per-organisation connector credentials and settings.

Stores encrypted credentials for external connectors (ServiceNow, Jira, M365).
Unique per (organization_id, connector_type).

``OrgConnectorCredential`` is the sole credential store. All connector routes
and services read from and write to this model via ``OrgCredentialVault``.
Legacy models (``OrgConnectorConfig``, ``DevOpsConnectorConfig``,
``LucidchartConnectorConfig``) are retired: their setters raise so no new
credentials can be written, and a ``migrate-connector-credentials`` CLI command
exists to copy existing rows into the new store.

``ExternalSystem`` (platform-wide, no organisation) is scoped separately and
is not migrated; it remains as-is for platform-level system configurations.
"""

import logging
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declared_attr

from app.extensions import db
from app.models.mixins.core import TenantMixin
from app.modules.codegen.services.credential_encryption import (
    decrypt_credential,
    encrypt_credential,
)

logger = logging.getLogger(__name__)

# All Fernet tokens start with this byte (same check as app/models/models.py's
# EncryptedAPIKey type). The setters below used to store plaintext whenever
# no key was configured -- which, since nothing in this codebase ever set
# FERNET_KEY, was the only path any of them ever took -- so every existing
# stored value predates this fix and is plaintext, not a Fernet token.
_FERNET_PREFIX = b"gAAAAA"


def _decrypt_or_legacy_plaintext(encrypted: str) -> str | None:
    """Decrypt a stored credential, tolerating a pre-fix plaintext value.

    A value that doesn't look like a Fernet token is returned as-is (it
    predates this fix); one that does but fails to decrypt (corrupted, or
    encrypted under a since-rotated key) is also returned as-is rather than
    silently discarded, with a warning logged, matching the same tolerance
    app/models/models.py's EncryptedAPIKey already applies. Either way the
    value is re-encrypted correctly the next time its setter runs.
    """
    raw = encrypted.encode() if isinstance(encrypted, str) else encrypted
    if not raw.startswith(_FERNET_PREFIX):
        return encrypted
    decrypted = decrypt_credential(raw)
    if decrypted is None:
        logger.warning(
            "Failed to decrypt a stored connector credential — returning the "
            "raw value (may be legacy plaintext or encrypted under a "
            "different key)."
        )
        return encrypted
    return decrypted


class ConnectorType(str, Enum):
    """Supported connector types."""

    CMDB = "cmdb"
    ALM = "alm"
    APM = "apm"
    CLM = "clm"  # Kept for future use
    ERP = "erp"
    CRM = "crm"
    ITSM = "itsm"
    EA_TOOL = "ea_tool"  # Enterprise Architecture tools (Abacus, Ardoq, LeanIX, etc.)


class SyncMode(str, Enum):
    """Synchronization modes."""

    BATCH = "batch"
    EVENT = "event"
    HYBRID = "hybrid"


class ConnectorStatus(str, Enum):
    """Connector operational status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class ConnectorConfig(TenantMixin, db.Model):
    """Connector configuration storage, scoped to the organisation that saved it.

    Inherits ``TenantMixin`` so the ORM tenant filter (do_orm_execute) and
    the before_flush auto-set both apply, but overrides its
    ``organization_id`` column to be nullable: existing rows had no
    organisation column at all, and a row whose origin cannot be determined
    (no audit trail recorded who saved it) is backfilled to NULL rather
    than guessed. NULL is not "shared" here -- the mixin's equality filter
    (``WHERE organization_id = g.current_org_id``) never matches NULL, so
    such a row is invisible to every organisation, not visible to all of
    them. A row assigned to the wrong organisation is worse than a row
    nobody can load.
    """

    __tablename__ = "connector_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    @declared_attr
    def organization_id(cls):
        from app.models.mixins.core import _default_org_id

        return Column(
            Integer,
            ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
            # Same belt-and-suspenders as TenantMixin's own column: an insert
            # that bypasses the before_flush listener (raw Table.insert(),
            # a seeder, a background thread with no request context) still
            # gets an org when one can be inferred. Nullable, unlike the
            # mixin's own column, because an existing row whose origin
            # cannot be determined is backfilled to NULL, not guessed.
            default=_default_org_id,
        )

    connector_type = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    config = Column(JSON, nullable=False)  # API endpoints, credentials, etc.
    field_mappings = Column(JSON)  # Field mapping DSL
    sync_schedule = Column(JSON)  # Cron expressions for batch sync
    webhook_config = Column(JSON)  # Webhook endpoints and secrets
    status = Column(String(20), default=ConnectorStatus.INACTIVE.value)
    last_sync = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ConnectorConfig {self.connector_type} org={self.organization_id}>"


class SyncLog(db.Model):
    """Synchronization log entries for :class:`ConnectorConfig`."""

    __tablename__ = "sync_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connector_id = Column(String(36), ForeignKey("connector_configs.id"))
    sync_type = Column(String(20), nullable=False)  # batch, event, manual
    status = Column(String(20), nullable=False)  # success, error, partial
    records_processed = Column(Integer, default=0)
    records_created = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_deleted = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class OrgConnectorConfig(db.Model):
    """Per-organisation connector configuration with encrypted credentials.

    RETIRED. Use ``OrgConnectorCredential`` via ``OrgCredentialVault`` for
    new credentials. Kept for backward compatibility with existing rows.
    Writers raise ``RuntimeError``. Run ``flask migrate-connector-credentials``
    to copy existing rows to the new store and then drop this table.
    """

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
    # Encrypted credential property — RETIRED, raises on write
    # ------------------------------------------------------------------

    @property
    def client_secret(self) -> str | None:
        """Return the decrypted client secret."""
        if not self._client_secret_encrypted:
            return None
        return _decrypt_or_legacy_plaintext(self._client_secret_encrypted)

    @client_secret.setter
    def client_secret(self, value: str | None) -> None:
        """Encrypt and store client secret. RETIRED — raises RuntimeError."""
        logger.warning(
            "OrgConnectorConfig is RETIRED. Use OrgCredentialVault instead."
        )
        raise RuntimeError(
            "OrgConnectorConfig is RETIRED — new credentials must use "
            "OrgConnectorCredential via OrgCredentialVault. "
            "Run `flask migrate-connector-credentials` to migrate existing rows."
        )

    def __repr__(self) -> str:
        return f"<ConnectorConfig {self.connector_type} org={self.organization_id}>"


class DevOpsConnectorConfig(db.Model):  # migration-exempt — COM-018
    """Per-org GitHub / Azure DevOps connector configuration.

    RETIRED. Use ``OrgConnectorCredential`` via ``OrgCredentialVault``.
    Kept for backward compatibility with existing rows.
    Writers raise ``RuntimeError``.

    One record per organisation. Access token is Fernet-encrypted using
    ``CREDENTIAL_ENCRYPTION_KEY``; the setter raises if no key is configured.
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
    # Fernet-encrypted access_token property — RETIRED, raises on write
    # ------------------------------------------------------------------

    @property
    def access_token(self) -> str | None:
        """Decrypt and return the stored access token."""
        if not self._access_token_encrypted:
            return None
        return _decrypt_or_legacy_plaintext(self._access_token_encrypted)

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        """Encrypt and store the access token. RETIRED — raises RuntimeError."""
        logger.warning(
            "DevOpsConnectorConfig is RETIRED. Use OrgCredentialVault instead."
        )
        raise RuntimeError(
            "DevOpsConnectorConfig is RETIRED — new credentials must use "
            "OrgConnectorCredential via OrgCredentialVault. "
            "Run `flask migrate-connector-credentials` to migrate existing rows."
        )

    def __repr__(self) -> str:
        return f"<DevOpsConnectorConfig {self.provider} org={self.organization_id}>"


class LucidchartConnectorConfig(db.Model):  # migration-exempt — LUC-001
    """Per-org Lucidchart OAuth configuration with encrypted token storage.

    RETIRED. Use ``OrgConnectorCredential`` via ``OrgCredentialVault``.
    Kept for backward compatibility with existing rows.
    Writers raise ``RuntimeError``.
    """

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
        return _decrypt_or_legacy_plaintext(self._client_secret_encrypted)

    @client_secret.setter
    def client_secret(self, value: str | None) -> None:
        """Encrypt and store the OAuth client secret. RETIRED — raises RuntimeError."""
        logger.warning(
            "LucidchartConnectorConfig is RETIRED. Use OrgCredentialVault instead."
        )
        raise RuntimeError(
            "LucidchartConnectorConfig is RETIRED — new credentials must use "
            "OrgConnectorCredential via OrgCredentialVault. "
            "Run `flask migrate-connector-credentials` to migrate existing rows."
        )

    @property
    def access_token(self) -> str | None:
        """Decrypt and return the stored Lucidchart access token."""
        if not self._access_token_encrypted:
            return None
        return _decrypt_or_legacy_plaintext(self._access_token_encrypted)

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        """Encrypt and store the Lucidchart access token. RETIRED — raises RuntimeError."""
        logger.warning(
            "LucidchartConnectorConfig is RETIRED. Use OrgCredentialVault instead."
        )
        raise RuntimeError(
            "LucidchartConnectorConfig is RETIRED — new credentials must use "
            "OrgConnectorCredential via OrgCredentialVault. "
            "Run `flask migrate-connector-credentials` to migrate existing rows."
        )

    @property
    def refresh_token(self) -> str | None:
        """Decrypt and return the stored Lucidchart refresh token."""
        if not self._refresh_token_encrypted:
            return None
        return _decrypt_or_legacy_plaintext(self._refresh_token_encrypted)

    @refresh_token.setter
    def refresh_token(self, value: str | None) -> None:
        """Encrypt and store the Lucidchart refresh token. RETIRED — raises RuntimeError."""
        logger.warning(
            "LucidchartConnectorConfig is RETIRED. Use OrgCredentialVault instead."
        )
        raise RuntimeError(
            "LucidchartConnectorConfig is RETIRED — new credentials must use "
            "OrgConnectorCredential via OrgCredentialVault. "
            "Run `flask migrate-connector-credentials` to migrate existing rows."
        )

    def token_is_expired(self, now: datetime | None = None) -> bool:
        """Return True when the stored access token is missing or expired."""
        if self.token_expires_at is None:
            return True
        now = now or datetime.utcnow()
        return self.token_expires_at <= now

    def __repr__(self) -> str:
        return f"<LucidchartConnectorConfig org={self.organization_id} enabled={self.enabled}>"


# ============================================================================
# Per-organisation encryption key store
# ============================================================================

class OrganizationEncryptionKey(TenantMixin, db.Model):  # migration-exempt — per-org key store
    """One Fernet encryption key per organisation, itself encrypted with a
    master key from ``ORG_ENCRYPTION_MASTER_KEY``.

    ``key_version`` supports zero-downtime rotation: after re-encrypting every
    credential row with the new key, increment the version. Old credentials
    encrypted under a previous version must be re-encrypted by the rotation
    service before the old key is discarded.
    """

    __tablename__ = "organization_encryption_keys"
    __table_args__ = (
        db.UniqueConstraint("organization_id", name="uq_org_encryption_key"),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    @declared_attr
    def organization_id(cls):
        return db.Column(
            db.Integer,
            db.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        )
    # The org's Fernet key, encrypted with the master key
    encrypted_key = db.Column(db.LargeBinary, nullable=False)
    key_version = db.Column(db.Integer, nullable=False, default=1)
    previous_encrypted_key = db.Column(db.LargeBinary, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    organization = db.relationship(
        "Organization",
        backref=db.backref("encryption_key", uselist=False),
    )

    def __repr__(self) -> str:
        return (
            f"<OrganizationEncryptionKey org={self.organization_id} "
            f"version={self.key_version}>"
        )


class OrgConnectorCredential(TenantMixin, db.Model):  # migration-exempt — per-org credential store
    """Single credential store for all connector types, encrypted with the
    organisation's own Fernet key (see ``OrganizationEncryptionKey``).

    Replaces the retired per-model stores (``OrgConnectorConfig``,
    ``DevOpsConnectorConfig``, ``LucidchartConnectorConfig``). New credentials
    must be stored here via ``OrgCredentialVault``.
    """

    __tablename__ = "org_connector_credentials"
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "connector_type", "credential_type",
            name="uq_org_connector_credential",
        ),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    @declared_attr
    def organization_id(cls):
        return db.Column(
            db.Integer,
            db.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    connector_type = db.Column(db.String(50), nullable=False)
    # Distinguishes credential kinds: "api_key", "client_secret", "access_token",
    # "refresh_token", "credentials" (full JSON blob)
    credential_type = db.Column(db.String(50), nullable=False, default="credentials")
    # Fernet-encrypted JSON blob or single value, encrypted with the org's key
    encrypted_value = db.Column(db.LargeBinary, nullable=False)
    # Tracks which encryption key version was used; enables per-row key lookup
    # and MultiFernet fallthrough during rotation
    key_version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    organization = db.relationship(
        "Organization",
        backref=db.backref("connector_credentials", lazy="dynamic"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrgConnectorCredential org={self.organization_id} "
            f"type={self.connector_type}/{self.credential_type}>"
        )