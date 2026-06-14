"""
FieldEncryption — Fernet-based field-level encryption for SOC 2 compliance.

Usage
-----
Symmetric encryption with a 32-byte URL-safe base64 key stored in the
``FERNET_KEY`` environment variable.  If the key is not set the helpers
return the value unchanged *and* emit a WARNING so that misconfigured
environments are visible in logs.

Applying to a model column
--------------------------
    from app.utils.field_encryption import EncryptedField

    class User(db.Model):
        email = db.Column(EncryptedField(db.String(500)))

The ``EncryptedField`` TypeDecorator transparently encrypts on INSERT/UPDATE
and decrypts on SELECT so no change is required at the call site.

NOTE: Do NOT apply ``EncryptedField`` to any existing column in this
task — that would require a migration.  The type is provided so that
COM-011 / COM-012 can use it on new columns.
"""

import base64
import logging
import os

from sqlalchemy import types

logger = logging.getLogger(__name__)

_FERNET_KEY_ENV = "FERNET_KEY"
_MISSING_KEY_WARNING_LOGGED = False  # emit once per process


def _get_fernet():
    """Return a ``Fernet`` instance or ``None`` when the key is absent."""
    global _MISSING_KEY_WARNING_LOGGED  # noqa: PLW0603

    key = os.environ.get(_FERNET_KEY_ENV)
    if not key:
        if not _MISSING_KEY_WARNING_LOGGED:
            logger.warning(
                "FERNET_KEY environment variable is not set. "
                "Field-level encryption is DISABLED. "
                "Set FERNET_KEY to enable SOC 2 field encryption."
            )
            _MISSING_KEY_WARNING_LOGGED = True
        return None

    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        logger.error("FERNET_KEY is invalid: %s", exc)
        return None


def encrypt(value: str) -> str:
    """Encrypt *value* using Fernet symmetric encryption.

    Returns the value unchanged (with a WARNING) when ``FERNET_KEY`` is
    not set so that the application degrades gracefully in dev/test.
    """
    if value is None:
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value
    try:
        token = fernet.encrypt(value.encode("utf-8"))
        return base64.urlsafe_b64encode(token).decode("ascii")
    except Exception as exc:
        logger.error("encrypt() failed: %s", exc)
        return value


def decrypt(value: str) -> str:
    """Decrypt a Fernet-encrypted *value*.

    Returns the value unchanged when ``FERNET_KEY`` is not set or when the
    value does not look like a Fernet token (e.g. plain-text legacy data).
    """
    if value is None:
        return value
    fernet = _get_fernet()
    if fernet is None:
        return value
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        return fernet.decrypt(raw).decode("utf-8")
    except Exception:
        # Value may be unencrypted legacy data — return as-is.
        return value


class EncryptedField(types.TypeDecorator):
    """SQLAlchemy TypeDecorator that transparently encrypts/decrypts values.

    Usage::

        class User(db.Model):
            ssn = db.Column(EncryptedField(db.String(500)))

    The column must be wide enough to hold the base64-encoded Fernet token
    (roughly ``len(plaintext) * 2 + 60`` bytes).
    """

    impl = types.String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encrypt before writing to the database."""
        if value is None:
            return value
        return encrypt(str(value))

    def process_result_value(self, value, dialect):
        """Decrypt when reading from the database."""
        if value is None:
            return value
        return decrypt(value)
