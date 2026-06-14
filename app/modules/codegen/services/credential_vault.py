"""Encrypted credential storage for connector secrets.

Reuses Phase 1's credential_encryption.py Fernet pattern.
Credentials stored in codegen_connector_credentials table, encrypted at rest.
Never in generated code, never in n8n storage, never in logs.
"""
import json
import logging
from datetime import datetime

from app.extensions import db
from app.modules.codegen.services.credential_encryption import encrypt_credential, decrypt_credential

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
