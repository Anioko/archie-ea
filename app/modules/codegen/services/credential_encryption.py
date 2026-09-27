"""Fernet symmetric encryption for credentials stored in Entelim's database.

Used by:
- SolutionInstance.database_url_encrypted (Phase 1)
- CredentialVault for connector secrets (Phase 3b)
- OrgCredentialVault for per-organisation encrypted credentials

Single-key functions use ``CREDENTIAL_ENCRYPTION_KEY`` from app config.
Per-organisation functions use ``ORG_ENCRYPTION_MASTER_KEY`` from app config to
unwrap each organisation's Fernet key stored in ``OrganizationEncryptionKey``.
"""
import logging

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

logger = logging.getLogger(__name__)

# Sentinel: any test that removes the master key mid-session needs a fresh
# one for org A vs org B independence, so we cache org Fernet instances
# per-app-instance rather than globally.
_org_fernet_cache: dict = {}


def _get_fernet() -> Fernet:
    """Build Fernet instance from app config key."""
    key = current_app.config.get("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY not set in app config. "
            "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    if isinstance(key, str):
        key = key.encode()
    try:
        return Fernet(key)
    except Exception as exc:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key. "
            "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from exc


def encrypt_credential(plaintext: str) -> bytes:
    """Encrypt a credential string. Returns Fernet token as bytes."""
    if not plaintext:
        return b""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8"))


def decrypt_credential(ciphertext: bytes | None) -> str | None:
    """Decrypt a Fernet token back to string. Returns None if input is empty/None."""
    if not ciphertext:
        return None
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt credential — invalid token or wrong key")
        return None


# ---------------------------------------------------------------------------
# Per-organisation encryption
# ---------------------------------------------------------------------------

def _get_master_fernet() -> Fernet:
    """Build Fernet from the per-org master key."""
    key = current_app.config.get("ORG_ENCRYPTION_MASTER_KEY")
    if not key:
        raise RuntimeError(
            "ORG_ENCRYPTION_MASTER_KEY not set in app config. "
            "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    if isinstance(key, str):
        key = key.encode()
    try:
        return Fernet(key)
    except Exception as exc:
        raise RuntimeError(
            "ORG_ENCRYPTION_MASTER_KEY is not a valid Fernet key. "
            "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from exc


def _get_or_create_org_fernet(org_id: int) -> Fernet:
    """Return the Fernet instance for an organisation, creating the key row
    if none exists yet.

    The org's raw Fernet key is generated fresh and encrypted under the master
    key before storage. Subsequent calls return the cached Fernet instance.
    """
    from app.models.connector_config import OrganizationEncryptionKey

    cache_key = (id(current_app._get_current_object()), org_id)
    if cache_key in _org_fernet_cache:
        return _org_fernet_cache[cache_key]

    master = _get_master_fernet()
    record = OrganizationEncryptionKey.query.filter_by(
        organization_id=org_id
    ).first()

    if record is None:
        raw_key = Fernet.generate_key()
        encrypted = master.encrypt(raw_key)
        record = OrganizationEncryptionKey(
            organization_id=org_id,
            encrypted_key=encrypted,
            key_version=1,
        )
        from app.extensions import db
        db.session.add(record)
        db.session.flush()
        org_fernet = Fernet(raw_key)
    else:
        raw_key = master.decrypt(record.encrypted_key)
        org_fernet = Fernet(raw_key)

    _org_fernet_cache[cache_key] = org_fernet
    return org_fernet


def encrypt_for_org(org_id: int, plaintext: str) -> bytes:
    """Encrypt plaintext with the organisation's Fernet key."""
    if not plaintext:
        return b""
    f = _get_or_create_org_fernet(org_id)
    return f.encrypt(plaintext.encode("utf-8"))


def decrypt_for_org(org_id: int, ciphertext: bytes | None) -> str | None:
    """Decrypt a token with the organisation's Fernet key."""
    if not ciphertext:
        return None
    f = _get_or_create_org_fernet(org_id)
    try:
        return f.decrypt(ciphertext).decode("utf-8")
    except InvalidToken:
        logger.error(
            "Failed to decrypt org credential for org %s — invalid token or wrong key",
            org_id,
        )
        return None


def rotate_org_encryption_key(org_id: int) -> int:
    """Rotate the encryption key for one organisation.

    Generates a new Fernet key, stores it encrypted under the master key,
    increments ``key_version``, and clears the cache. The caller is
    responsible for re-encrypting every credential row (see
    ``OrgCredentialVault.rotate_all_credentials``).

    Returns the new ``key_version``.
    """
    from app.models.connector_config import OrganizationEncryptionKey
    from app.extensions import db

    master = _get_master_fernet()
    raw_key = Fernet.generate_key()
    encrypted = master.encrypt(raw_key)

    record = OrganizationEncryptionKey.query.filter_by(
        organization_id=org_id
    ).first()
    if record is None:
        record = OrganizationEncryptionKey(
            organization_id=org_id,
            encrypted_key=encrypted,
            key_version=1,
        )
        db.session.add(record)
    else:
        record.encrypted_key = encrypted
        record.key_version = (record.key_version or 0) + 1
    db.session.flush()

    cache_key = (id(current_app._get_current_object()), org_id)
    _org_fernet_cache.pop(cache_key, None)

    return record.key_version


def clear_org_fernet_cache() -> None:
    """Clear the org Fernet cache (useful between tests)."""
    _org_fernet_cache.clear()