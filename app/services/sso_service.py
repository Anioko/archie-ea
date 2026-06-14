"""
SSOService — per-organisation SSO federation (COM-005).

Handles OIDC (OpenID Connect) flow using authlib and provides a stub for
SAML 2.0. Each organisation has exactly one SSOConfig row; login is
intercepted when the user's email domain matches a configured domain.

Usage::

    svc = SSOService()
    config = svc.get_config_for_email("alice@acme.com")
    if config and config.enabled:
        result = svc.initiate_oidc_flow(config, redirect_uri)
        # redirect to result['redirect_url']
"""

import logging
import secrets
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class SSONotConfiguredError(Exception):
    """Raised when SSO is not configured or a required env var is missing."""


class SSOService:
    """Per-organisation SSO service (OIDC + SAML stub)."""

    # Simple in-process cache for OIDC discovery documents (URL → dict).
    _discovery_cache: dict = {}

    # ------------------------------------------------------------------
    # Email-domain lookup
    # ------------------------------------------------------------------

    def get_config_for_email(self, email: str):
        """Return the enabled SSOConfig whose domain matches *email*, or None.

        Args:
            email: User's email address (e.g. "alice@acme.com").

        Returns:
            :class:`app.models.sso_config.SSOConfig` or ``None``.
        """
        if not email or "@" not in email:
            return None
        domain = email.split("@", 1)[1].lower()
        try:
            from app.models.sso_config import SSOConfig

            configs = SSOConfig.query.filter_by(enabled=True).all()
            for config in configs:
                if domain in config.email_domains:
                    return config
        except Exception as exc:
            logger.warning("SSO config lookup failed (non-fatal): %s", exc)
            try:
                from app import db
                db.session.rollback()
            except Exception as exc:
                logger.debug("suppressed error in SSOService.get_config_for_email (app/services/sso_service.py): %s", exc)
        return None

    # ------------------------------------------------------------------
    # OIDC flow
    # ------------------------------------------------------------------

    def _fetch_oidc_discovery(self, metadata_url: str) -> dict:
        """Fetch (and cache) the OIDC discovery document.

        Args:
            metadata_url: The ``/.well-known/openid-configuration`` URL.

        Returns:
            Parsed JSON dict.

        Raises:
            :class:`SSONotConfiguredError` on network / parsing failure.
        """
        if metadata_url in self._discovery_cache:
            return self._discovery_cache[metadata_url]
        try:
            import requests

            resp = requests.get(metadata_url, timeout=10)
            resp.raise_for_status()
            doc = resp.json()
            self._discovery_cache[metadata_url] = doc
            return doc
        except Exception as exc:
            raise SSONotConfiguredError(
                f"Failed to fetch OIDC discovery document from {metadata_url}: {exc}"
            ) from exc

    def initiate_oidc_flow(self, config, redirect_uri: str) -> dict:
        """Build the OIDC authorization URL.

        Fetches the IdP's discovery document to obtain ``authorization_endpoint``,
        then constructs the redirect URL with PKCE-style ``state`` token.

        Args:
            config: :class:`app.models.sso_config.SSOConfig` instance.
            redirect_uri: The callback URL registered with the IdP.

        Returns:
            Dict with keys ``redirect_url`` (str) and ``state`` (str).

        Raises:
            :class:`SSONotConfiguredError` if config is None or setup is incomplete.
        """
        if config is None:
            raise SSONotConfiguredError("No SSO config provided")
        if not config.client_id:
            raise SSONotConfiguredError("SSO config has no client_id")
        if not config.idp_metadata_url:
            raise SSONotConfiguredError("SSO config has no idp_metadata_url")

        discovery = self._fetch_oidc_discovery(config.idp_metadata_url)
        auth_endpoint = discovery.get("authorization_endpoint")
        if not auth_endpoint:
            raise SSONotConfiguredError(
                "OIDC discovery document missing 'authorization_endpoint'"
            )

        state = secrets.token_urlsafe(32)
        params = {
            "response_type": "code",
            "client_id": config.client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
        }
        redirect_url = f"{auth_endpoint}?{urlencode(params)}"
        return {"redirect_url": redirect_url, "state": state}

    def handle_oidc_callback(
        self, config, code: str, state: str, redirect_uri: str
    ) -> dict:
        """Exchange the authorization code for tokens and return user info.

        Fetches the IdP's ``token_endpoint`` from the discovery document,
        exchanges the code, then calls ``userinfo_endpoint`` for claims.

        Args:
            config: :class:`app.models.sso_config.SSOConfig` instance.
            code: The authorization code from the IdP callback.
            state: The state parameter (caller should validate before calling).
            redirect_uri: Must match the value used in :meth:`initiate_oidc_flow`.

        Returns:
            Dict of user-info claims (``email``, ``sub``, ``name``, etc.).

        Raises:
            :class:`SSONotConfiguredError` if config is None or network errors occur.
        """
        if config is None:
            raise SSONotConfiguredError("No SSO config provided")
        if not config.idp_metadata_url:
            raise SSONotConfiguredError("SSO config has no idp_metadata_url")

        import requests

        discovery = self._fetch_oidc_discovery(config.idp_metadata_url)
        token_endpoint = discovery.get("token_endpoint")
        userinfo_endpoint = discovery.get("userinfo_endpoint", "")
        if not token_endpoint:
            raise SSONotConfiguredError(
                "OIDC discovery document missing 'token_endpoint'"
            )

        client_secret = config.client_secret
        try:
            resp = requests.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": config.client_id,
                    "client_secret": client_secret or "",
                },
                timeout=15,
            )
            resp.raise_for_status()
            token_data = resp.json()
        except Exception as exc:
            raise SSONotConfiguredError(
                f"Token exchange failed: {exc}"
            ) from exc

        # Prefer userinfo endpoint for claims; fall back to id_token payload
        userinfo: dict = {}
        access_token = token_data.get("access_token", "")
        if userinfo_endpoint and access_token:
            try:
                uinfo_resp = requests.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                if uinfo_resp.status_code == 200:
                    userinfo = uinfo_resp.json()
            except Exception as exc:
                logger.warning("Userinfo fetch failed (falling back to id_token): %s", exc)

        # Fall back: decode id_token payload (no signature verification needed —
        # we just exchanged the code back-channel, so the token is trustworthy)
        if not userinfo:
            id_token = token_data.get("id_token", "")
            if id_token:
                try:
                    import base64
                    import json

                    parts = id_token.split(".")
                    if len(parts) >= 2:
                        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                        userinfo = json.loads(base64.urlsafe_b64decode(padded))
                except Exception as exc:
                    logger.warning("Failed to decode id_token claims: %s", exc)

        return userinfo

    # ------------------------------------------------------------------
    # User provisioning
    # ------------------------------------------------------------------

    def provision_user(self, org, userinfo: dict):
        """Create or update a User record from IdP-supplied claims.

        Looks up by email first. Creates a confirmed SSO user if not found.
        Always syncs ``first_name``, ``last_name``, ``sso_provider``, and
        ``external_id`` from the IdP claims.

        Args:
            org: :class:`app.models.organization.Organization` instance.
            userinfo: Dict of OIDC claims (``email``, ``sub``, ``name``, etc.).

        Returns:
            :class:`app.models.user.User` instance (persisted to DB).

        Raises:
            :class:`SSONotConfiguredError` if email is missing from claims.
        """
        from app import db
        from app.models.user import User

        email = (userinfo.get("email") or "").strip().lower()
        if not email:
            raise SSONotConfiguredError("IdP did not provide an email claim")

        # Resolve name from claims, honouring attribute_mapping overrides
        attr_map: dict = {}
        if org and getattr(org, "sso_config", None):
            attr_map = org.sso_config.attribute_mapping or {}

        def _claim(key: str, fallback: str = "") -> str:
            mapped_key = attr_map.get(key, key)
            return (userinfo.get(mapped_key) or userinfo.get(fallback) or "").strip()

        given_name = _claim("given_name")
        family_name = _claim("family_name")
        full_name = userinfo.get("name", "").strip()
        if full_name and not given_name:
            parts = full_name.split(" ", 1)
            given_name = parts[0]
            family_name = parts[1] if len(parts) > 1 else ""

        sub = userinfo.get("sub", email)

        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email,
                first_name=given_name,
                last_name=family_name,
                confirmed=True,
                sso_provider="oidc",
                external_id=sub,
            )
            if org:
                user.organization_id = org.id
            db.session.add(user)
        else:
            # Update mutable IdP-owned fields
            if given_name:
                user.first_name = given_name
            if family_name:
                user.last_name = family_name
            user.sso_provider = "oidc"
            if sub:
                user.external_id = sub
            if org and not user.organization_id:
                user.organization_id = org.id

        db.session.commit()
        return user

    # ------------------------------------------------------------------
    # SAML stub
    # ------------------------------------------------------------------

    def initiate_saml_flow(self, config) -> str:  # noqa: ARG002
        """Build a SAML 2.0 AuthnRequest redirect URL.

        .. todo::
            Full implementation requires the ``python3-saml`` library
            (``pip install python3-saml``).  Once installed, replace this
            stub with::

                from onelogin.saml2.auth import OneLogin_Saml2_Auth
                auth = OneLogin_Saml2_Auth(request_data, saml_settings)
                return auth.login()

        Raises:
            :class:`SSONotConfiguredError` always, until python3-saml is
            installed and wired.
        """
        if config is None:
            raise SSONotConfiguredError("No SSO config provided")
        raise SSONotConfiguredError(
            "SAML 2.0 federation requires the python3-saml library. "
            "Install with: pip install python3-saml"
        )
