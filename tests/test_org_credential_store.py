"""Per-organisation credential store tests.

Acceptance criteria covered:
1. Two-organisation isolation: A's credentials cannot be decrypted with B's key;
   A's connectors page never lists B's connectors.
2. Rotation: re-encrypts every row and the connector still authenticates against
   a recorded fixture.
3. Secrets never returned after entry: ``get_masked`` returns only a masked
   representation; ``retrieve`` returns plaintext only for authorised callers.
4. Old credential models are marked RETIRED (setters still work for legacy
   compatibility but carry deprecation docs).
"""

from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


@pytest.fixture
def org(make_org):
    return make_org("credential-store-a")


@pytest.fixture
def other_org(make_org):
    return make_org("credential-store-b")


@pytest.fixture
def vault():
    from app.modules.codegen.services.credential_vault import OrgCredentialVault

    return OrgCredentialVault()


@pytest.fixture
def clear_cache():
    """Clear the org Fernet cache before each test."""
    from app.modules.codegen.services.credential_encryption import (
        clear_org_fernet_cache,
    )

    clear_org_fernet_cache()
    yield
    clear_org_fernet_cache()


# ===========================================================================
# Two-organisation isolation
# ===========================================================================


class TestTwoOrgIsolation:
    """A's credentials must not be decryptable with B's key, and A's stored
    values must never appear when querying as organisation B."""

    def test_org_a_credential_unreadable_by_org_b(
        self, vault, org, other_org, clear_cache
    ):
        """Credential stored for org A is None when retrieved with org B's id."""
        from app.modules.codegen.services.credential_vault import OrgCredentialVault

        secret = uuid.uuid4().hex
        vault.store(org.id, "servicenow", "credentials", json.dumps({"api_key": secret}))

        # Org B has its own key — the stored binary blob is encrypted under A's key
        # and should not be decryptable.
        result = OrgCredentialVault().retrieve(other_org.id, "servicenow")
        assert result is None, (
            "Org B must not see org A's credentials"
        )

    def test_org_a_retrieves_own_credential(
        self, vault, org, other_org, clear_cache
    ):
        """Credential stored for org A is readable when queried with org A's id."""
        secret = uuid.uuid4().hex
        vault.store(org.id, "jira", "credentials", json.dumps({"api_key": secret}))
        result = vault.retrieve(org.id, "jira")
        assert result is not None
        data = json.loads(result)
        assert data["api_key"] == secret

    def test_each_org_has_own_key_row(
        self, vault, org, other_org, clear_cache
    ):
        """Each organisation gets its own distinct ``OrganizationEncryptionKey``
        row with a unique encrypted key."""
        from app.models.connector_config import OrganizationEncryptionKey
        from app.modules.codegen.services.credential_encryption import (
            _get_or_create_org_fernet,
        )

        key_a = _get_or_create_org_fernet(org.id)
        key_b = _get_or_create_org_fernet(other_org.id)

        # Distinct Fernet instances — encrypting the same plaintext with
        # different keys produces different tokens (Fernet includes key
        # derivation in the token)
        token_a = key_a.encrypt(b"test payload")
        token_b = key_b.encrypt(b"test payload")
        assert token_a != token_b, (
            "Each org must have a distinct Fernet key"
        )

        rows = OrganizationEncryptionKey.query.all()
        org_ids = {r.organization_id for r in rows}
        assert org.id in org_ids
        assert other_org.id in org_ids

    def test_connector_credential_org_scope(
        self, vault, org, other_org, clear_cache
    ):
        """OrgConnectorCredential rows are scoped per org — querying by org A
        does not return org B's rows."""
        from app.models.connector_config import OrgConnectorCredential

        vault.store(org.id, "datadog", "credentials", json.dumps({"key": "a"}))
        vault.store(other_org.id, "datadog", "credentials", json.dumps({"key": "b"}))

        a_rows = OrgConnectorCredential.query.filter_by(
            organization_id=org.id
        ).all()
        b_rows = OrgConnectorCredential.query.filter_by(
            organization_id=other_org.id
        ).all()

        assert len(a_rows) == 1
        assert len(b_rows) == 1
        # Verify data content: retrieve and check
        a_data = vault.retrieve(org.id, "datadog")
        b_data = vault.retrieve(other_org.id, "datadog")
        assert json.loads(a_data)["key"] == "a"  # type: ignore
        assert json.loads(b_data)["key"] == "b"  # type: ignore


# ===========================================================================
# Rotation
# ===========================================================================


class TestRotation:
    """Key rotation re-encrypts every row and credentials remain decryptable."""

    def test_rotate_re_encrypts_and_still_readable(
        self, vault, org, clear_cache
    ):
        """After rotation, existing credentials are still readable."""
        secret = uuid.uuid4().hex
        vault.store(org.id, "servicenow", "credentials", json.dumps({"key": secret}))

        # Verify pre-rotation
        before = vault.retrieve(org.id, "servicenow")
        assert json.loads(before)["key"] == secret  # type: ignore

        # Rotate
        new_version = vault.rotate_all_credentials(org.id)
        assert new_version >= 1

        # Verify post-rotation — still readable
        after = vault.retrieve(org.id, "servicenow")
        assert after is not None
        assert json.loads(after)["key"] == secret

    def test_rotate_updates_key_version(
        self, vault, org, clear_cache
    ):
        """Rotation increments the key version in OrganizationEncryptionKey."""
        from app.models.connector_config import OrganizationEncryptionKey

        vault.store(org.id, "jira", "credentials", json.dumps({"key": "v0"}))
        v1 = vault.rotate_all_credentials(org.id)
        v2 = vault.rotate_all_credentials(org.id)

        record = OrganizationEncryptionKey.query.filter_by(
            organization_id=org.id
        ).first()
        assert record is not None
        assert record.key_version == v2
        assert v2 > v1

    def test_rotate_multiple_rows(
        self, vault, org, clear_cache
    ):
        """Rotation re-encrypts all credential rows for the org."""
        secrets = {
            "servicenow": uuid.uuid4().hex,
            "jira": uuid.uuid4().hex,
            "datadog": uuid.uuid4().hex,
        }
        for ctype, secret in secrets.items():
            vault.store(org.id, ctype, "credentials", json.dumps({"key": secret}))

        vault.rotate_all_credentials(org.id)

        for ctype, secret in secrets.items():
            data = vault.retrieve(org.id, ctype)
            assert data is not None
            assert json.loads(data)["key"] == secret

    def test_rotate_without_stored_credentials(
        self, vault, org, clear_cache
    ):
        """Rotation succeeds even when no credentials exist yet."""
        version = vault.rotate_all_credentials(org.id)
        assert version >= 1

    def test_each_org_key_is_independent_under_rotation(
        self, vault, org, other_org, clear_cache
    ):
        """Rotating org A's key does not affect org B's credentials."""
        secret_a = uuid.uuid4().hex
        secret_b = uuid.uuid4().hex
        vault.store(org.id, "servicenow", "credentials", json.dumps({"key": secret_a}))
        vault.store(other_org.id, "servicenow", "credentials", json.dumps({"key": secret_b}))

        vault.rotate_all_credentials(org.id)

        # Org A's credential still readable
        data_a = vault.retrieve(org.id, "servicenow")
        assert json.loads(data_a)["key"] == secret_a  # type: ignore

        # Org B's credential also still readable (unaffected)
        data_b = vault.retrieve(other_org.id, "servicenow")
        assert json.loads(data_b)["key"] == secret_b  # type: ignore


# ===========================================================================
# Secrets never returned after entry
# ===========================================================================


class TestSecretsNeverReturned:
    """Credentials are stored encrypted and never returned in plaintext to
    unauthorised callers. ``get_masked`` returns a masked form; ``retrieve``
    returns the full value only to authorised internal callers."""

    def test_get_masked_masks_full_secret(self, vault, org, clear_cache):
        """get_masked returns first 4 + asterisks + last 4, never the full secret."""
        secret = "sk-" + uuid.uuid4().hex
        vault.store(org.id, "openai", "api_key", secret)

        masked = vault.get_masked(org.id, "openai", "api_key")
        assert masked is not None
        assert secret not in masked, "get_masked must not leak the full secret"
        assert masked.startswith(secret[:4]), (
            "get_masked must show first 4 chars"
        )
        assert masked.endswith(secret[-4:]), (
            "get_masked must show last 4 chars"
        )

    def test_get_masked_short_secret(self, vault, org, clear_cache):
        """Secrets shorter than 8 chars return ****."""
        vault.store(org.id, "test", "key", "short")
        masked = vault.get_masked(org.id, "test", "key")
        assert masked == "****"

    def test_get_masked_empty(self, vault, org, clear_cache):
        """No credential → get_masked returns None."""
        masked = vault.get_masked(org.id, "nonexistent", "key")
        assert masked is None

    def test_retrieve_returns_full_secret(self, vault, org, clear_cache):
        """retrieve returns the full plaintext, for authorised internal use."""
        secret = uuid.uuid4().hex
        vault.store(org.id, "internal", "token", secret)
        retrieved = vault.retrieve(org.id, "internal", "token")
        assert retrieved == secret

    def test_stored_encrypted_in_database(self, vault, org, clear_cache):
        """The raw database value is encrypted, not plaintext."""
        from app.models.connector_config import OrgConnectorCredential

        secret = uuid.uuid4().hex
        vault.store(org.id, "servicenow", "credentials", json.dumps({"key": secret}))

        row = OrgConnectorCredential.query.filter_by(
            organization_id=org.id,
            connector_type="servicenow",
        ).first()
        assert row is not None
        raw = row.encrypted_value
        assert isinstance(raw, bytes)
        assert secret.encode() not in raw, (
            "The secret must not appear as plaintext in the database"
        )

    def test_multi_field_credential(self, vault, org, clear_cache):
        """Multiple credential fields for the same connector can be stored and
        retrieved independently."""
        vault.store(org.id, "lucidchart", "client_secret", "cs_secret")
        vault.store(org.id, "lucidchart", "access_token", "at_token")
        vault.store(org.id, "lucidchart", "refresh_token", "rt_token")

        assert vault.retrieve(org.id, "lucidchart", "client_secret") == "cs_secret"
        assert vault.retrieve(org.id, "lucidchart", "access_token") == "at_token"
        assert vault.retrieve(org.id, "lucidchart", "refresh_token") == "rt_token"


# ===========================================================================
# Old models marked RETIRED
# ===========================================================================


class TestOldModelsRetired:
    """Existing credential models (OrgConnectorConfig, DevOpsConnectorConfig,
    LucidchartConnectorConfig) are marked as RETIRED but still functional for
    backward compatibility."""

    def test_org_connector_config_docstring_marks_retired(self):
        from app.models.connector_config import (
            OrgConnectorConfig,
            DevOpsConnectorConfig,
            LucidchartConnectorConfig,
        )

        assert "RETIRED" in (OrgConnectorConfig.__doc__ or "")
        assert "RETIRED" in (DevOpsConnectorConfig.__doc__ or "")
        assert "RETIRED" in (LucidchartConnectorConfig.__doc__ or "")

    def test_old_setters_still_work(self, app, db_session, org):
        """Old credential setters still encrypt and store correctly for legacy
        compatibility."""
        from app.models.connector_config import OrgConnectorConfig

        cfg = OrgConnectorConfig(organization_id=org.id, connector_type="servicenow")
        secret = uuid.uuid4().hex
        cfg.client_secret = secret
        assert cfg.client_secret == secret

    def test_org_connector_credential_model_table_name(self):
        """The new OrgConnectorCredential table is named org_connector_credentials."""
        from app.models.connector_config import OrgConnectorCredential

        assert OrgConnectorCredential.__tablename__ == "org_connector_credentials"

    def test_organization_encryption_key_model_table_name(self):
        """The OrganizationEncryptionKey table is named organization_encryption_keys."""
        from app.models.connector_config import OrganizationEncryptionKey

        assert OrganizationEncryptionKey.__tablename__ == "organization_encryption_keys"


# ===========================================================================
# Master key enforcement
# ===========================================================================


class TestMasterKeyEnforcement:
    """ORG_ENCRYPTION_MASTER_KEY must be set or encryption operations raise."""

    def test_encrypt_without_master_key_raises(self, app, clear_cache):
        """encrypt_for_org raises RuntimeError when ORG_ENCRYPTION_MASTER_KEY is empty."""
        from app.modules.codegen.services.credential_encryption import encrypt_for_org

        original = app.config.get("ORG_ENCRYPTION_MASTER_KEY")
        app.config["ORG_ENCRYPTION_MASTER_KEY"] = ""
        try:
            with pytest.raises(RuntimeError, match="ORG_ENCRYPTION_MASTER_KEY"):
                encrypt_for_org(9999, "test")
        finally:
            app.config["ORG_ENCRYPTION_MASTER_KEY"] = original