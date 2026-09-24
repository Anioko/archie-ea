"""Verify id_token signature, issuer, audience and expiry in SSO fallback.

Covers the _verify_id_token method added to SSOService: a token with a bad
signature, wrong issuer, wrong audience or past expiry is refused; a valid
token passes and returns its claims.
"""

from __future__ import annotations

import json
import time
from unittest import mock

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


# ---------------------------------------------------------------------------
# Test key material (one RSA key pair, shared across tests)
# ---------------------------------------------------------------------------

from cryptography.hazmat.primitives.asymmetric import rsa

_PRIVATE_KEY = rsa.generate_private_key(65537, 2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_ISSUER = "https://idp.example.com"
_CLIENT_ID = "test-client-id"
_KID = "test-kid-1"
_JWKS_URI = "https://idp.example.com/jwks"


def _make_jwks():
    """Return a JWKS dict containing our test public key."""
    from authlib.jose import JsonWebKey

    jwk = JsonWebKey.import_key(
        _PUBLIC_KEY,
        {"kid": _KID, "use": "sig", "alg": "RS256", "kty": "RSA"},
    ).as_dict()
    return {"keys": [jwk]}


def _make_token(claims=None, headers=None, key=None):
    """Build and return a signed id_token string."""
    from authlib.jose import jwt

    if key is None:
        key = _PRIVATE_KEY
    if headers is None:
        headers = {"alg": "RS256", "kid": _KID}
    base = {
        "iss": _ISSUER,
        "aud": _CLIENT_ID,
        "sub": "user-1",
        "email": "test@example.com",
        "exp": int(time.time()) + 3600,
    }
    if claims:
        base.update(claims)
    token = jwt.encode(headers, base, key)
    return token.decode() if isinstance(token, bytes) else token


def _make_discovery():
    return {
        "jwks_uri": _JWKS_URI,
        "issuer": _ISSUER,
    }


def _make_config():
    from app.models.sso_config import SSOConfig

    return SSOConfig(
        organization_id=1,
        protocol="oidc",
        client_id=_CLIENT_ID,
    )


def _mock_jwks_response():
    """Return a mock requests.get that returns our JWKS."""
    mock_resp = mock.MagicMock()
    mock_resp.json.return_value = _make_jwks()
    mock_resp.raise_for_status = lambda: None
    return mock_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIdTokenVerification:
    def test_valid_token_passes_verification(self):
        token = _make_token()
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            claims = svc._verify_id_token(token, config, discovery)

        assert claims["sub"] == "user-1"
        assert claims["email"] == "test@example.com"
        assert claims["iss"] == _ISSUER
        assert claims["aud"] == _CLIENT_ID

    def test_bad_signature_is_refused(self):
        bad_key = rsa.generate_private_key(65537, 2048)
        token = _make_token(key=bad_key)
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(token, config, discovery)

    def test_wrong_issuer_is_refused(self):
        token = _make_token({"iss": "https://evil-idp.example.com"})
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(token, config, discovery)

    def test_wrong_audience_is_refused(self):
        token = _make_token({"aud": "wrong-client-id"})
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(token, config, discovery)

    def test_expired_token_is_refused(self):
        token = _make_token({"exp": int(time.time()) - 3600})
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(token, config, discovery)

    def test_missing_jwks_uri_is_refused(self):
        token = _make_token()
        discovery = {"issuer": _ISSUER}  # no jwks_uri
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with pytest.raises(SSONotConfiguredError):
            svc._verify_id_token(token, config, discovery)

    def test_missing_issuer_in_discovery_is_refused(self):
        token = _make_token()
        discovery = {"jwks_uri": _JWKS_URI}  # no issuer
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with pytest.raises(SSONotConfiguredError):
            svc._verify_id_token(token, config, discovery)

    def test_jwks_fetch_failure_is_refused(self):
        token = _make_token()
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.side_effect = OSError("connection refused")
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(token, config, discovery)