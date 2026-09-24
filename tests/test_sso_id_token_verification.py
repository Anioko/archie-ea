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


@pytest.fixture(autouse=True)
def _fresh_jwks_cache():
    """The key set is cached in-process; every test starts with it empty."""
    from app.services.sso_service import SSOService

    SSOService._jwks_cache.clear()
    yield
    SSOService._jwks_cache.clear()


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
_NONCE = "nonce-issued-for-this-login"


def _make_jwks():
    """Return a JWKS dict containing our test public key."""
    from authlib.jose import JsonWebKey

    jwk = JsonWebKey.import_key(
        _PUBLIC_KEY,
        {"kid": _KID, "use": "sig", "alg": "RS256", "kty": "RSA"},
    ).as_dict()
    return {"keys": [jwk]}


def _make_token(claims=None, headers=None, key=None, drop=()):
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
        "nonce": _NONCE,
    }
    if claims:
        base.update(claims)
    for name in drop:
        base.pop(name, None)
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
            claims = svc._verify_id_token(token, config, discovery, _NONCE)

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
                svc._verify_id_token(token, config, discovery, _NONCE)

    def test_wrong_issuer_is_refused(self):
        token = _make_token({"iss": "https://evil-idp.example.com"})
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(token, config, discovery, _NONCE)

    def test_wrong_audience_is_refused(self):
        token = _make_token({"aud": "wrong-client-id"})
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(token, config, discovery, _NONCE)

    def test_expired_token_is_refused(self):
        token = _make_token({"exp": int(time.time()) - 3600})
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(token, config, discovery, _NONCE)

    def test_missing_jwks_uri_is_refused(self):
        token = _make_token()
        discovery = {"issuer": _ISSUER}  # no jwks_uri
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with pytest.raises(SSONotConfiguredError):
            svc._verify_id_token(token, config, discovery, _NONCE)

    def test_missing_issuer_in_discovery_is_refused(self):
        token = _make_token()
        discovery = {"jwks_uri": _JWKS_URI}  # no issuer
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with pytest.raises(SSONotConfiguredError):
            svc._verify_id_token(token, config, discovery, _NONCE)

    def test_jwks_fetch_failure_is_refused(self):
        token = _make_token()
        discovery = _make_discovery()
        config = _make_config()

        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.side_effect = OSError("connection refused")
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(token, config, discovery, _NONCE)


def _verify(token, *, config=None, nonce=_NONCE, jwks_get=None):
    from app.services.sso_service import SSOService

    svc = SSOService()
    with mock.patch("requests.get") as mock_get:
        mock_get.return_value = _mock_jwks_response()
        if jwks_get is not None:
            mock_get.side_effect = jwks_get
        return svc._verify_id_token(token, config or _make_config(), _make_discovery(), nonce)


def _refused(token, **kwargs):
    from app.services.sso_service import SSONotConfiguredError

    with pytest.raises(SSONotConfiguredError):
        _verify(token, **kwargs)


class TestNonceBinding:
    def test_matching_nonce_passes(self):
        assert _verify(_make_token())["nonce"] == _NONCE

    def test_token_without_a_nonce_claim_is_refused(self):
        _refused(_make_token(drop=("nonce",)))

    def test_token_from_another_login_is_refused(self):
        _refused(_make_token({"nonce": "nonce-of-someone-elses-login"}))

    def test_no_nonce_issued_for_this_login_refuses_even_a_valid_token(self):
        _refused(_make_token(), nonce="")
        _refused(_make_token(), nonce=None)


class TestClaimEdgeCases:
    def test_audience_as_an_array_containing_the_client_id_passes(self):
        claims = _verify(_make_token({"aud": ["other-client", _CLIENT_ID]}))
        assert _CLIENT_ID in claims["aud"]

    def test_audience_array_without_the_client_id_is_refused(self):
        _refused(_make_token({"aud": ["other-client", "another-client"]}))

    def test_not_before_in_the_future_is_refused(self):
        _refused(_make_token({"nbf": int(time.time()) + 3600}))

    def test_issued_at_in_the_future_is_refused(self):
        _refused(_make_token({"iat": int(time.time()) + 3600}))

    def test_missing_issuer_and_missing_audience_are_refused(self):
        _refused(_make_token(drop=("iss",)))
        _refused(_make_token(drop=("aud",)))

    @pytest.mark.parametrize("token", ["", "abc", "a.b", "a.b.c.d", "not.base64!.at-all"])
    def test_malformed_tokens_are_refused(self, token):
        _refused(token)

    def test_a_config_without_a_client_id_refuses_every_token(self):
        from app.models.sso_config import SSOConfig

        for client_id in (None, ""):
            config = SSOConfig(organization_id=1, protocol="oidc", client_id=client_id)
            _refused(_make_token(), config=config)


class TestKeyCacheAndErrors:
    def test_the_key_set_is_fetched_once_within_the_ttl(self):
        from app.services.sso_service import SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            for _ in range(3):
                svc._verify_id_token(_make_token(), _make_config(), _make_discovery(), _NONCE)
        assert mock_get.call_count == 1

    def test_an_expired_cache_entry_is_refetched(self):
        from app.services.sso_service import SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            svc._verify_id_token(_make_token(), _make_config(), _make_discovery(), _NONCE)
            fetched_at, jwks = SSOService._jwks_cache[_JWKS_URI]
            SSOService._jwks_cache[_JWKS_URI] = (fetched_at - SSOService._JWKS_TTL_SECONDS - 1, jwks)
            svc._verify_id_token(_make_token(), _make_config(), _make_discovery(), _NONCE)
        assert mock_get.call_count == 2

    def test_a_rotated_signing_key_is_picked_up_without_waiting_for_the_ttl(self):
        from authlib.jose import JsonWebKey

        from app.services.sso_service import SSOService

        new_private = rsa.generate_private_key(65537, 2048)
        new_jwks = {
            "keys": [
                JsonWebKey.import_key(
                    new_private.public_key(),
                    {"kid": "rotated-kid", "use": "sig", "alg": "RS256", "kty": "RSA"},
                ).as_dict()
            ]
        }
        rotated = mock.MagicMock()
        rotated.json.return_value = new_jwks
        rotated.raise_for_status = lambda: None

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            svc._verify_id_token(_make_token(), _make_config(), _make_discovery(), _NONCE)
            mock_get.return_value = rotated
            token = _make_token(key=new_private, headers={"alg": "RS256", "kid": "rotated-kid"})
            claims = svc._verify_id_token(token, _make_config(), _make_discovery(), _NONCE)
        assert claims["sub"] == "user-1"

    def test_a_bad_signature_refreshes_the_keys_once_and_stops(self):
        bad_key = rsa.generate_private_key(65537, 2048)
        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        with mock.patch("requests.get") as mock_get:
            mock_get.return_value = _mock_jwks_response()
            with pytest.raises(SSONotConfiguredError):
                svc._verify_id_token(_make_token(key=bad_key), _make_config(), _make_discovery(), _NONCE)
        assert mock_get.call_count == 2  # the first fetch, then one refresh

    def test_errors_do_not_reveal_the_key_set_address_or_the_library_text(self):
        from app.services.sso_service import SSONotConfiguredError

        with pytest.raises(SSONotConfiguredError) as fetch_failure:
            _verify(_make_token(), jwks_get=OSError("connection refused at 10.0.0.5"))
        assert _JWKS_URI not in str(fetch_failure.value)
        assert "10.0.0.5" not in str(fetch_failure.value)

        with pytest.raises(SSONotConfiguredError) as bad_token:
            _verify(_make_token({"iss": "https://evil-idp.example.com"}))
        assert str(bad_token.value) == "id_token verification failed"


class TestFlowWiring:
    def _config(self):
        from app.models.sso_config import SSOConfig

        return SSOConfig(
            organization_id=1, protocol="oidc", client_id=_CLIENT_ID,
            idp_metadata_url="https://idp.example.com/.well-known",
        )

    def test_the_authorization_request_carries_a_fresh_nonce_that_is_returned(self):
        from urllib.parse import parse_qs, urlparse

        from app.services.sso_service import SSOService

        svc = SSOService()
        discovery = {"authorization_endpoint": "https://idp.example.com/authorize"}
        with mock.patch.object(SSOService, "_fetch_oidc_discovery", return_value=discovery):
            first = svc.initiate_oidc_flow(self._config(), "https://app.example.com/cb")
            second = svc.initiate_oidc_flow(self._config(), "https://app.example.com/cb")

        query = parse_qs(urlparse(first["redirect_url"]).query)
        assert query["nonce"] == [first["nonce"]] and len(first["nonce"]) >= 32
        assert first["nonce"] != second["nonce"] and first["nonce"] != first["state"]

    def test_the_callback_passes_the_expected_nonce_to_the_token_check(self):
        from app.services.sso_service import SSONotConfiguredError, SSOService

        svc = SSOService()
        discovery = {
            "token_endpoint": "https://idp.example.com/token",
            "jwks_uri": _JWKS_URI,
            "issuer": _ISSUER,
        }
        token_response = mock.MagicMock()
        token_response.json.return_value = {"id_token": _make_token()}
        token_response.raise_for_status = lambda: None
        with mock.patch.object(SSOService, "_fetch_oidc_discovery", return_value=discovery), mock.patch(
            "requests.post", return_value=token_response
        ), mock.patch("requests.get", return_value=_mock_jwks_response()):
            claims = svc.handle_oidc_callback(
                self._config(), "code", "state", "https://app.example.com/cb", expected_nonce=_NONCE
            )
            assert claims["sub"] == "user-1"

            with pytest.raises(SSONotConfiguredError):
                svc.handle_oidc_callback(self._config(), "code", "state", "https://app.example.com/cb")

    def test_the_callback_refuses_a_config_without_a_client_id(self):
        from app.models.sso_config import SSOConfig
        from app.services.sso_service import SSONotConfiguredError, SSOService

        config = SSOConfig(organization_id=1, protocol="oidc", client_id=None, idp_metadata_url="https://x")
        with pytest.raises(SSONotConfiguredError):
            SSOService().handle_oidc_callback(config, "code", "state", "https://app.example.com/cb")
