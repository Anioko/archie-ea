"""Encrypted credential storage for connector secrets.

Reuses phase 1's credential_encryption.py Fernet pattern.

``CredentialVault`` (existing): stores credentials in ``codegen_connector_credentials``
table encrypted with the shared ``CREDENTIAL_ENCRYPTION_KEY``.

``OrgCredentialVault``: stores credentials in
``org_connector_credentials`` table encrypted per-organisation with that org's
own Fernet key. Never returns secrets after entry; retrieves only for sync
operations and returns a masked representation on read.
"""

import json
import logging
from datetime import datetime

from app.extensions import db
from app.modules.codegen.services.credential_encryption import (
    decrypt_credential,
    encrypt_credential,
    encrypt_for_org,
    decrypt_for_org,
    rotate_org_encryption_key,
)

logger = logging.getLogger(__name__)


class ConnectorCredential(db.Model):
    """Encrypted credential storage. migration-exempt — db.create_all()"""
    __tablename__ = "codegen_connector_credentials"

    id = db.Column(db.Integer, primary_key=True)
    solution_id = db.Column(db.Integer, nullable=False, index=True)
    connector_type = db.Column(db.String(50), nullable=False)
    encrypted_data = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("solution_id", "connector_type", name="uq_solution_connector_cred"),)


class CredentialVault:
    """Encrypted CRUD for connector credentials."""

    def store(self, solution_id: int, connector_type: str, credentials: dict) -> None:
        """Store credentials encrypted. Upserts if already exists."""
        encrypted = encrypt_credential(json.dumps(credentials))
        existing = ConnectorCredential.query.filter_by(
            solution_id=solution_id, connector_type=connector_type
        ).first()
        if existing:
            existing.encrypted_data = encrypted
            existing.updated_at = datetime.utcnow()
        else:
            db.session.add(ConnectorCredential(
                solution_id=solution_id,
                connector_type=connector_type,
                encrypted_data=encrypted,
            ))
        db.session.commit()

    def retrieve(self, solution_id: int, connector_type: str) -> dict | None:
        """Retrieve and decrypt credentials. Returns None if not found."""
        cred = ConnectorCredential.query.filter_by(
            solution_id=solution_id, connector_type=connector_type
        ).first()
        if not cred:
            return None
        decrypted = decrypt_credential(cred.encrypted_data)
        return json.loads(decrypted) if decrypted else None

    def delete(self, solution_id: int, connector_type: str) -> None:
        """Delete credentials for a connector."""
        ConnectorCredential.query.filter_by(
            solution_id=solution_id, connector_type=connector_type
        ).delete()
        db.session.commit()


# ---------------------------------------------------------------------------
# Per-organisation credential vault
# ---------------------------------------------------------------------------

def _mask_value(value: str) -> str:
    """Return a masked version of a credential value: show first 4 and last 4
    characters, mask the rest with asterisks. Returns '****' for short values."""
    if not value:
        return ""
    value = value.strip()
    if len(value) < 8:
        return "****"
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


class OrgCredentialVault:
    """Per-organisation credential store.

    Credentials are encrypted with the organisation's own Fernet key and
    stored in ``org_connector_credentials``. Secrets are never returned after
    entry — ``store`` accepts plaintext, ``retrieve`` returns decrypted data
    only for authorised internal callers, and ``get_masked`` returns a masked
    representation for display.
    """

    def store(
        self,
        org_id: int,
        connector_type: str,
        credential_type: str,
        value: str,
    ) -> None:
        """Store a credential value encrypted with the organisation's key.

        Upserts if a row with the same (org_id, connector_type, credential_type)
        already exists.
        """
        from app.models.connector_config import OrgConnectorCredential

        encrypted = encrypt_for_org(org_id, value)
        existing = OrgConnectorCredential.query.filter_by(
            organization_id=org_id,
            connector_type=connector_type,
            credential_type=credential_type,
        ).first()
        if existing:
            existing.encrypted_value = encrypted
            existing.updated_at = datetime.utcnow()
        else:
            db.session.add(OrgConnectorCredential(
                organization_id=org_id,
                connector_type=connector_type,
                credential_type=credential_type,
                encrypted_value=encrypted,
            ))
        db.session.commit()

    def store_credentials(
        self,
        org_id: int,
        connector_type: str,
        credentials: dict,
    ) -> None:
        """Store multiple credential fields as a JSON blob under
        credential_type='credentials'."""
        self.store(org_id, connector_type, "credentials", json.dumps(credentials))

    def retrieve(
        self,
        org_id: int,
        connector_type: str,
        credential_type: str = "credentials",
    ) -> str | None:
        """Retrieve and decrypt a credential. Returns the plaintext value
        (caller must ensure authorised use). Returns None if not found."""
        from app.models.connector_config import OrgConnectorCredential

        cred = OrgConnectorCredential.query.filter_by(
            organization_id=org_id,
            connector_type=connector_type,
            credential_type=credential_type,
        ).first()
        if not cred:
            return None
        return decrypt_for_org(org_id, cred.encrypted_value)

    def retrieve_credentials(
        self,
        org_id: int,
        connector_type: str,
    ) -> dict | None:
        """Retrieve and decrypt the full credentials JSON blob."""
        raw = self.retrieve(org_id, connector_type, "credentials")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Failed to parse credentials JSON for org %s connector %s",
                org_id,
                connector_type,
            )
            return None

    def get_masked(
        self,
        org_id: int,
        connector_type: str,
        credential_type: str = "credentials",
    ) -> str | None:
        """Return a masked version of the credential (first 4 + last 4,
        middle replaced by asterisks). Never returns the full secret."""
        value = self.retrieve(org_id, connector_type, credential_type)
        if value is None:
            return None
        return _mask_value(value)

    def delete(
        self,
        org_id: int,
        connector_type: str,
        credential_type: str = "credentials",
    ) -> None:
        """Delete credentials for a connector."""
        from app.models.connector_config import OrgConnectorCredential

        OrgConnectorCredential.query.filter_by(
            organization_id=org_id,
            connector_type=connector_type,
            credential_type=credential_type,
        ).delete()
        db.session.commit()

    def rotate_all_credentials(self, org_id: int) -> int:
        """Rotate the organisation's encryption key and re-encrypt every
        credential row.

        Returns the new ``key_version``.

        Steps:
        1. Derive old Fernet from the current cache (still valid).
        2. Rotate the key in ``OrganizationEncryptionKey`` (generates new key,
           clears cache).
        3. Re-encrypt every ``OrgConnectorCredential`` row with the new key.
        4. Commit.

        This is zero-downtime: the cache clear means the next read will fetch
        the new key, and re-encryption happens atomically.
        """
        from app.models.connector_config import OrgConnectorCredential
        from app.modules.codegen.services.credential_encryption import (
            _get_or_create_org_fernet,
            _get_master_fernet,
        )

        # 1. Get old key to decrypt existing rows
        old_fernet = _get_or_create_org_fernet(org_id)

        # 2. Rotate the org's stored key
        new_version = rotate_org_encryption_key(org_id)

        # 3. Get new key
        new_fernet = _get_or_create_org_fernet(org_id)

        # 4. Re-encrypt every row
        rows = OrgConnectorCredential.query.filter_by(
            organization_id=org_id
        ).all()
        for row in rows:
            if row.encrypted_value:
                plaintext = old_fernet.decrypt(row.encrypted_value).decode("utf-8")
                row.encrypted_value = new_fernet.encrypt(plaintext.encode("utf-8"))

        db.session.commit()
        return new_version