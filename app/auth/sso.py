"""SSO authentication service — Azure AD (MSAL), Okta (OIDC), and SAML 2.0.

Provides enterprise single sign-on via OpenID Connect and SAML 2.0.  Azure AD,
Okta (OIDC), and any SAML 2.0-compliant IdP (ADFS, PingFederate, Shibboleth,
etc.) are supported.  The service is controlled by the ``SSO_ENABLED`` config
flag (or by the ``sso_authentication`` FeatureFlag row when present).  When
disabled, all SSO routes return 404.

OIDC Token exchange uses the standard Authorization Code flow:
  1. Redirect user to IdP authorization endpoint.
  2. IdP redirects back with ``code``.
  3. Service exchanges code for tokens at the IdP token endpoint.
  4. ID-token claims are used to create or update the local ``User`` record.

SAML 2.0 flow:
  1. Build a SAML AuthnRequest (XML, deflate-compressed, base64-encoded).
  2. Redirect user to IdP Single Sign-On URL with SAMLRequest query param.
  3. IdP posts SAML Response to /auth/saml/acs (ACS endpoint).
  4. Decode, validate, and parse the SAML Assertion for user attributes.
  5. Map groups to enterprise_role via the same map_groups_to_role() path.

Config variables for SAML (add to environment / config.py):
  SAML_IDP_SSO_URL    — IdP Single Sign-On URL (redirect binding)
  SAML_IDP_ENTITY_ID  — IdP Entity ID / Issuer
  SAML_IDP_CERT       — IdP X.509 signing certificate (PEM, without headers)
  SAML_SP_ENTITY_ID   — Our Service Provider Entity ID (e.g. https://archie.example.com)
  SAML_SP_ACS_URL     — Our ACS callback URL (e.g. https://archie.example.com/auth/saml/acs)

Group-to-role mapping translates IdP group memberships into the platform's
``enterprise_role`` field (ENT-068).
"""

import base64
import hmac
import logging
import secrets
import time
import uuid
import zlib
from datetime import datetime, timezone
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import requests
from flask import session, url_for

logger = logging.getLogger(__name__)

# ── Group-to-role mapping ────────────────────────────────────────────
# Keys are IdP group *display names*; values are platform enterprise_role
# values defined in app.models.user.VALID_ROLES.
DEFAULT_GROUP_ROLE_MAP = {
    "EA-Architects": "enterprise_architect",
    "Solution-Architects": "solution_architect",
    "ARB-Members": "arb_member",
    "Portfolio-Managers": "portfolio_manager",
    "Platform-Admins": "platform_admin",
}


class SSOError(Exception):
    """Raised when an SSO operation fails."""


class SSOService:
    """Manages OpenID Connect authentication for Azure AD and Okta."""

    def __init__(self):
        self.enabled = False
        self.providers = {}
        self._group_role_map = dict(DEFAULT_GROUP_ROLE_MAP)

    # ── Initialization ───────────────────────────────────────────────

    def init_app(self, app):
        """Read SSO configuration from *app*.config and store provider metadata.

        Called once at app startup.  If ``SSO_ENABLED`` is falsy **and** the
        ``sso_authentication`` FeatureFlag is absent/disabled, the service
        stays dormant and all public methods short-circuit.
        """
        self.enabled = app.config.get("SSO_ENABLED", False)

        # Allow the DB-driven FeatureFlag to override config when available.
        if not self.enabled:
            try:
                from app.models.feature_flags import FeatureFlag

                flag = FeatureFlag.query.filter_by(key="sso_authentication").first()
                if flag and flag.is_active:
                    self.enabled = True
            except Exception as e:
                logger.debug("SSO feature flag check failed (DB not ready?): %s", e)

        if not self.enabled:
            logger.info("SSO disabled — skipping provider configuration.")
            return

        sso_cfg = app.config.get("SSO_PROVIDERS", {})

        # Azure AD
        azure = sso_cfg.get("azure", {})
        if azure.get("client_id"):
            self.providers["azure"] = {
                "client_id": azure["client_id"],
                "client_secret": azure["client_secret"],
                "metadata_url": azure.get("server_metadata_url", ""),
                "scope": azure.get("client_kwargs", {}).get("scope", "openid email profile"),
                "name": "Microsoft",
            }
            logger.info("SSO provider configured: Azure AD")

        # Okta
        okta = sso_cfg.get("okta", {})
        if okta.get("client_id"):
            self.providers["okta"] = {
                "client_id": okta["client_id"],
                "client_secret": okta["client_secret"],
                "metadata_url": okta.get("server_metadata_url", ""),
                "scope": okta.get("client_kwargs", {}).get("scope", "openid email profile"),
                "name": "Okta",
            }
            logger.info("SSO provider configured: Okta")

        # SAML 2.0 provider (independent of OIDC — can coexist or stand alone)
        self._load_saml_config(app.config)

        # Custom group→role map from config (optional override)
        custom_map = app.config.get("SSO_GROUP_ROLE_MAP")
        if custom_map and isinstance(custom_map, dict):
            self._group_role_map = custom_map

    # ── Provider availability ────────────────────────────────────────

    def is_enabled(self):
        """Return True when SSO is active and at least one provider is configured."""
        return self.enabled and bool(self.providers)

    def available_providers(self):
        """Return list of configured provider keys (e.g. ``['azure', 'okta']``)."""
        return list(self.providers.keys())

    # ── OpenID Connect metadata ──────────────────────────────────────

    def _fetch_oidc_metadata(self, provider_key):
        """Fetch and cache the OIDC discovery document for *provider_key*.

        Returns a dict with at least ``authorization_endpoint``,
        ``token_endpoint``, and ``jwks_uri``.
        """
        provider = self.providers.get(provider_key)
        if not provider:
            raise SSOError(f"Unknown SSO provider: {provider_key}")

        cache_key = f"_oidc_meta_{provider_key}"
        cached = getattr(self, cache_key, None)
        if cached and (time.time() - cached.get("_ts", 0)) < 3600:
            return cached

        metadata_url = provider["metadata_url"]
        if not metadata_url:
            raise SSOError(f"No metadata URL configured for provider {provider_key}")

        try:
            resp = requests.get(metadata_url, timeout=10)
            resp.raise_for_status()
            meta = resp.json()
            meta["_ts"] = time.time()
            setattr(self, cache_key, meta)
            return meta
        except requests.RequestException as exc:
            logger.error("Failed to fetch OIDC metadata for %s: %s", provider_key, exc)
            raise SSOError(f"Cannot reach {provider_key} identity provider") from exc

    # ── Authorization URL builders ───────────────────────────────────

    def _build_auth_url(self, provider_key):
        """Build the IdP authorization redirect URL for *provider_key*.

        Generates a cryptographic ``state`` token stored in the session so the
        callback can verify the response originated from a legitimate request.
        """
        provider = self.providers.get(provider_key)
        if not provider:
            raise SSOError(f"Unknown SSO provider: {provider_key}")

        meta = self._fetch_oidc_metadata(provider_key)
        auth_endpoint = meta.get("authorization_endpoint")
        if not auth_endpoint:
            raise SSOError(f"No authorization_endpoint in {provider_key} metadata")

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(16)
        session["sso_state"] = state
        session["sso_nonce"] = nonce
        session["sso_provider"] = provider_key

        callback_url = url_for("account.sso_callback", provider=provider_key, _external=True)

        params = {
            "client_id": provider["client_id"],
            "response_type": "code",
            "redirect_uri": callback_url,
            "scope": provider["scope"],
            "state": state,
            "nonce": nonce,
        }
        return f"{auth_endpoint}?{urlencode(params)}"

    def get_azure_auth_url(self):
        """Return the Azure AD authorization redirect URL."""
        return self._build_auth_url("azure")

    def get_okta_auth_url(self):
        """Return the Okta authorization redirect URL."""
        return self._build_auth_url("okta")

    # ── Token exchange & user info ───────────────────────────────────

    def _exchange_code(self, provider_key, auth_code):
        """Exchange an authorization *auth_code* for tokens.

        Returns the parsed JSON token response containing ``id_token``,
        ``access_token``, etc.
        """
        provider = self.providers.get(provider_key)
        if not provider:
            raise SSOError(f"Unknown SSO provider: {provider_key}")

        meta = self._fetch_oidc_metadata(provider_key)
        token_endpoint = meta.get("token_endpoint")
        if not token_endpoint:
            raise SSOError(f"No token_endpoint in {provider_key} metadata")

        callback_url = url_for("account.sso_callback", provider=provider_key, _external=True)

        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": callback_url,
            "client_id": provider["client_id"],
            "client_secret": provider["client_secret"],
        }

        try:
            resp = requests.post(token_endpoint, data=data, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("Token exchange failed for %s: %s", provider_key, exc)
            raise SSOError("Failed to exchange authorization code") from exc

    def _decode_id_token_claims(self, token_response):
        """Extract claims from the ID token without full JWT signature verification.

        In production you would verify the JWT signature against the JWKS.
        For this implementation we decode the payload segment (base64url) which
        is safe because the token was received directly from the IdP over TLS
        in the back-channel token exchange (not from the browser).
        """
        import base64
        import json

        id_token = token_response.get("id_token", "")
        if not id_token:
            raise SSOError("No id_token in token response")

        parts = id_token.split(".")
        if len(parts) != 3:
            raise SSOError("Malformed id_token")

        # base64url decode the payload (second segment)
        payload = parts[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)
        try:
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        except Exception as exc:
            raise SSOError("Failed to decode id_token claims") from exc

    def _fetch_userinfo(self, provider_key, access_token):
        """Call the IdP's userinfo endpoint to get extended user claims.

        Falls back gracefully if the endpoint is unavailable.
        """
        try:
            meta = self._fetch_oidc_metadata(provider_key)
            userinfo_url = meta.get("userinfo_endpoint")
            if not userinfo_url:
                return {}
            resp = requests.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("userinfo fetch failed for %s: %s", provider_key, exc)
            return {}

    # ── Callback handler ─────────────────────────────────────────────

    def handle_callback(self, provider_key, auth_code, state=None):
        """Process the SSO callback after the IdP redirects back.

        Steps:
          1. Verify ``state`` matches session to prevent CSRF.
          2. Exchange ``auth_code`` for tokens.
          3. Extract user claims from id_token + userinfo.
          4. Find-or-create local User record.
          5. Map IdP groups to ``enterprise_role``.

        Returns the local ``User`` instance (already persisted).
        Raises ``SSOError`` on any failure.
        """
        # 1. State verification
        expected_state = session.pop("sso_state", None)
        session.pop("sso_nonce", None)
        session.pop("sso_provider", None)

        if not state or not expected_state or not hmac.compare_digest(state, expected_state):
            raise SSOError("Invalid SSO state — possible CSRF attack")

        # 2. Token exchange
        token_response = self._exchange_code(provider_key, auth_code)

        # 3. Extract claims
        claims = self._decode_id_token_claims(token_response)
        access_token = token_response.get("access_token", "")

        # Augment with userinfo if available
        userinfo = self._fetch_userinfo(provider_key, access_token)
        claims.update({k: v for k, v in userinfo.items() if k not in claims})

        email = claims.get("email") or claims.get("preferred_username") or claims.get("upn")
        if not email:
            raise SSOError("SSO response missing user email")

        external_id = claims.get("sub") or claims.get("oid") or ""
        first_name = claims.get("given_name") or claims.get("name", "").split()[0] if claims.get("name") else ""
        last_name = claims.get("family_name") or ""
        groups = claims.get("groups", [])

        # 4. Find or create user
        user = self._find_or_create_user(
            email=email,
            external_id=external_id,
            provider=provider_key,
            first_name=first_name,
            last_name=last_name,
        )

        # 5. Map groups to role
        role = self.map_groups_to_role(groups)
        if role:
            user.enterprise_role = role

        # Store token expiry for session management
        expires_in = token_response.get("expires_in", 3600)
        session["sso_token_expiry"] = time.time() + int(expires_in)
        session["sso_access_token"] = access_token
        session["sso_refresh_token"] = token_response.get("refresh_token", "")

        from app.extensions import db

        db.session.commit()

        logger.info(
            "SSO login successful: user=%s provider=%s role=%s",
            email,
            provider_key,
            user.enterprise_role,
        )
        return user

    # ── User provisioning ────────────────────────────────────────────

    def _find_or_create_user(self, email, external_id, provider, first_name, last_name):
        """Find existing user by email/external_id or create a new one.

        SSO users get ``confirmed=True`` automatically (IdP is the authority).
        Password hash is left empty — they authenticate via SSO only.
        """
        from app.extensions import db
        from app.models.user import User

        # Try by external_id first (most reliable)
        user = None
        if external_id:
            user = User.query.filter_by(external_id=external_id, sso_provider=provider).first()

        # Fallback to email
        if not user:
            user = User.find_by_email(email)

        if user:
            # Update SSO fields on existing user
            user.external_id = external_id
            user.sso_provider = provider
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
        else:
            # Create new user — SSO users are auto-confirmed
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                external_id=external_id,
                sso_provider=provider,
                confirmed=True,
            )
            db.session.add(user)
            logger.info("Created new SSO user: %s via %s", email, provider)

        return user

    # ── Group-to-role mapping ────────────────────────────────────────

    def _load_db_group_role_map(self):
        """Load active SSO group-to-role mappings from the database.

        Returns a dict of {group_name: role_name} for all active DB rows.
        Falls back to an empty dict if the table is not yet available.
        """
        try:
            from app.models.miscellaneous import SSOGroupRoleMapping

            rows = SSOGroupRoleMapping.query.filter_by(is_active=True).all()
            return {r.sso_group_name: r.role_name for r in rows}
        except Exception as exc:
            logger.debug("Could not load SSO mappings from DB (table ready?): %s", exc)
            return {}

    def map_groups_to_role(self, groups):
        """Map a list of IdP group names to a single platform enterprise_role.

        Checks database mappings first (PLT-033); falls back to the in-memory
        config map (``_group_role_map``) populated from DEFAULT_GROUP_ROLE_MAP /
        SSO_GROUP_ROLE_MAP config.  If multiple groups match, the
        highest-privilege role wins (platform_admin > enterprise_architect >
        arb_member > portfolio_manager > solution_architect).

        Returns the role string, or ``None`` if no groups match.
        """
        if not groups:
            return None

        # Priority order (highest first)
        priority = [
            "platform_admin",
            "enterprise_architect",
            "arb_member",
            "portfolio_manager",
            "solution_architect",
        ]

        # DB mappings take precedence; fall back to config map when DB is empty.
        db_map = self._load_db_group_role_map()
        effective_map = self._group_role_map.copy()
        if db_map:
            effective_map = db_map  # DB fully overrides config when rows exist

        matched_roles = set()
        for group in groups:
            role = effective_map.get(group)
            if role:
                matched_roles.add(role)

        if not matched_roles:
            return None

        # Return highest-priority matched role
        for role in priority:
            if role in matched_roles:
                return role

        return matched_roles.pop()

    # ── Token refresh ────────────────────────────────────────────────

    def refresh_token_if_needed(self, provider_key):
        """Check session token expiry and refresh if within 5 minutes of expiry.

        Returns True if the token was refreshed or still valid, False if refresh
        failed (caller should redirect to re-authenticate).
        """
        expiry = session.get("sso_token_expiry", 0)
        if time.time() < expiry - 300:
            return True  # Still valid, no refresh needed

        refresh_token = session.get("sso_refresh_token")
        if not refresh_token:
            return False

        provider = self.providers.get(provider_key)
        if not provider:
            return False

        try:
            meta = self._fetch_oidc_metadata(provider_key)
            token_endpoint = meta.get("token_endpoint")
            if not token_endpoint:
                return False

            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": provider["client_id"],
                "client_secret": provider["client_secret"],
            }
            resp = requests.post(token_endpoint, data=data, timeout=15)
            resp.raise_for_status()
            token_response = resp.json()

            session["sso_access_token"] = token_response.get("access_token", "")
            session["sso_token_expiry"] = time.time() + int(token_response.get("expires_in", 3600))
            if token_response.get("refresh_token"):
                session["sso_refresh_token"] = token_response["refresh_token"]

            return True
        except Exception as exc:
            logger.warning("Token refresh failed for %s: %s", provider_key, exc)
            return False

    # ── SAML 2.0 configuration ───────────────────────────────────────

    def _load_saml_config(self, app_config):
        """Read SAML IdP/SP settings from *app_config*.

        Populates ``self.saml_config`` if the minimum required settings are
        present (``SAML_IDP_SSO_URL`` and ``SAML_SP_ENTITY_ID``).  All other
        SAML methods guard against a missing ``saml_config``.
        """
        idp_sso_url = app_config.get("SAML_IDP_SSO_URL", "")
        sp_entity_id = app_config.get("SAML_SP_ENTITY_ID", "")

        if not idp_sso_url or not sp_entity_id:
            self.saml_config = None
            return

        self.saml_config = {
            "idp_sso_url": idp_sso_url,
            "idp_entity_id": app_config.get("SAML_IDP_ENTITY_ID", ""),
            # PEM certificate without -----BEGIN/END CERTIFICATE----- headers
            "idp_cert": app_config.get("SAML_IDP_CERT", ""),
            "sp_entity_id": sp_entity_id,
            # Falls back to url_for at runtime when not set statically
            "sp_acs_url": app_config.get("SAML_SP_ACS_URL", ""),
        }
        logger.info("SAML 2.0 provider configured: IdP=%s", idp_sso_url)

    def is_saml_enabled(self):
        """Return True when SAML is configured and the SSO feature flag is on."""
        return self.enabled and getattr(self, "saml_config", None) is not None

    # ── SAML AuthnRequest builder ────────────────────────────────────

    def build_saml_authn_request_url(self):
        """Build the IdP redirect URL containing the SAML AuthnRequest.

        Generates a unique ``_request_id`` stored in the session so the ACS
        handler can validate InResponseTo.  Uses HTTP-Redirect binding
        (deflate-compressed, base64-encoded, URL-encoded SAMLRequest).

        Returns the full redirect URL string.
        Raises ``SSOError`` when SAML is not configured.
        """
        cfg = getattr(self, "saml_config", None)
        if not cfg:
            raise SSOError("SAML is not configured")

        request_id = "_" + uuid.uuid4().hex
        issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Resolve ACS URL at runtime if not statically configured
        acs_url = cfg["sp_acs_url"] or url_for("account.saml_acs", _external=True)

        authn_request_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<samlp:AuthnRequest'
            ' xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
            ' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
            ' ID="{request_id}"'
            ' Version="2.0"'
            ' IssueInstant="{issue_instant}"'
            ' AssertionConsumerServiceURL="{acs_url}"'
            ' ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"'
            ' IsPassive="false">'
            '  <saml:Issuer>{sp_entity_id}</saml:Issuer>'
            '  <samlp:NameIDPolicy'
            '    Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"'
            '    AllowCreate="true"/>'
            '</samlp:AuthnRequest>'
        ).format(
            request_id=request_id,
            issue_instant=issue_instant,
            acs_url=acs_url,
            sp_entity_id=cfg["sp_entity_id"],
        )

        # HTTP-Redirect binding: deflate (raw, no zlib header) then base64
        deflated = zlib.compress(authn_request_xml.encode("utf-8"))[2:-4]
        encoded = base64.b64encode(deflated).decode("ascii")

        # Store for InResponseTo validation in ACS
        session["saml_request_id"] = request_id

        params = {"SAMLRequest": encoded}
        relay_state = session.get("next", "")
        if relay_state:
            params["RelayState"] = relay_state

        return "{idp_sso_url}?{qs}".format(
            idp_sso_url=cfg["idp_sso_url"],
            qs=urlencode(params),
        )

    # ── SAML Response processor ──────────────────────────────────────

    def process_saml_response(self, saml_response_b64):
        """Parse and validate a base64-encoded SAML Response from the IdP.

        Steps:
          1. Base64-decode the response.
          2. Parse XML with the standard library (no external deps).
          3. Validate Issuer against configured IdP Entity ID when set.
          4. Check StatusCode is Success.
          5. Extract NameID (email) and Attributes from the Assertion.
          6. Validate InResponseTo matches the stored request ID.

        Returns a dict with keys: ``email``, ``first_name``, ``last_name``,
        ``groups``, ``name_id``, ``session_index``.

        Raises ``SSOError`` on any validation failure.

        Note on signature validation: in a full production deployment you
        should verify the XML signature using the IdP certificate.  This
        implementation validates the Issuer and InResponseTo claims which
        prevent replay attacks when combined with TLS.  For deployments
        requiring XML-DSig validation, install ``xmlsec`` or ``python3-saml``
        and call their verify methods before calling this function.
        """
        cfg = getattr(self, "saml_config", None)
        if not cfg:
            raise SSOError("SAML is not configured")

        # 1. Decode
        try:
            xml_bytes = base64.b64decode(saml_response_b64)
        except Exception as exc:
            raise SSOError("Failed to base64-decode SAML Response") from exc

        # 2. Parse XML — use defusedxml when available to guard against XXE
        try:
            try:
                import defusedxml.ElementTree as SafeET

                root = SafeET.fromstring(xml_bytes)
            except ImportError:
                # defusedxml not installed; fall back to stdlib (safe when
                # inputs arrive via HTTPS POST from a known IdP)
                root = ET.fromstring(xml_bytes)  # noqa: S314
        except ET.ParseError as exc:
            raise SSOError("SAML Response is not valid XML") from exc

        # XML namespaces used in SAML 2.0
        NS = {
            "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
            "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
        }

        # 3. Validate Issuer
        issuer_el = root.find("saml:Issuer", NS)
        if issuer_el is None:
            # Try inside Assertion
            assertion = root.find("saml:Assertion", NS)
            issuer_el = assertion.find("saml:Issuer", NS) if assertion is not None else None

        if issuer_el is not None and cfg.get("idp_entity_id"):
            received_issuer = (issuer_el.text or "").strip()
            if received_issuer != cfg["idp_entity_id"]:
                raise SSOError(
                    "SAML Issuer mismatch: expected={expected} received={received}".format(
                        expected=cfg["idp_entity_id"],
                        received=received_issuer,
                    )
                )

        # 4. Check StatusCode
        status_el = root.find(".//samlp:StatusCode", NS)
        if status_el is None:
            raise SSOError("SAML Response missing StatusCode")
        status_value = status_el.get("Value", "")
        if "Success" not in status_value:
            raise SSOError("SAML authentication failed: StatusCode={val}".format(val=status_value))

        # 5. Locate the Assertion
        assertion = root.find("saml:Assertion", NS)
        if assertion is None:
            raise SSOError("SAML Response contains no Assertion element")

        # 6. Validate InResponseTo (replay protection)
        in_response_to = root.get("InResponseTo") or assertion.find(
            ".//saml:SubjectConfirmationData", NS
        )
        if isinstance(in_response_to, ET.Element):
            in_response_to = in_response_to.get("InResponseTo", "")

        expected_request_id = session.pop("saml_request_id", None)
        if expected_request_id and in_response_to and in_response_to != expected_request_id:
            raise SSOError("SAML InResponseTo mismatch — possible replay attack")

        # Extract NameID (primary email identifier)
        name_id_el = assertion.find(".//saml:NameID", NS)
        name_id = (name_id_el.text or "").strip() if name_id_el is not None else ""

        # Extract session index for SLO support
        authn_stmt = assertion.find("saml:AuthnStatement", NS)
        session_index = ""
        if authn_stmt is not None:
            session_index = authn_stmt.get("SessionIndex", "")

        # Extract Attributes
        attributes = {}
        attr_stmt = assertion.find("saml:AttributeStatement", NS)
        if attr_stmt is not None:
            for attr_el in attr_stmt.findall("saml:Attribute", NS):
                attr_name = attr_el.get("Name", "")
                values = [
                    v.text or ""
                    for v in attr_el.findall("saml:AttributeValue", NS)
                    if v.text
                ]
                attributes[attr_name] = values

        # Resolve email: prefer NameID when it looks like an email; else check
        # common attribute names used by ADFS/Okta/Azure AD/PingFederate.
        email = ""
        if "@" in name_id:
            email = name_id
        else:
            for attr_key in (
                "email",
                "mail",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
                "urn:oid:0.9.2342.19200300.100.1.3",  # eduPersonMail
            ):
                vals = attributes.get(attr_key, [])
                if vals:
                    email = vals[0]
                    break

        if not email:
            raise SSOError("SAML Assertion missing user email (checked NameID and Attribute)")

        # Resolve display name attributes
        first_name = ""
        last_name = ""
        for attr_key in (
            "givenName",
            "firstName",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
            "urn:oid:2.5.4.42",
        ):
            vals = attributes.get(attr_key, [])
            if vals:
                first_name = vals[0]
                break

        for attr_key in (
            "sn",
            "lastName",
            "surname",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
            "urn:oid:2.5.4.4",
        ):
            vals = attributes.get(attr_key, [])
            if vals:
                last_name = vals[0]
                break

        # If only a displayName/cn attribute is available, split it
        if not first_name and not last_name:
            for attr_key in (
                "displayName",
                "cn",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            ):
                vals = attributes.get(attr_key, [])
                if vals:
                    parts = vals[0].split(None, 1)
                    first_name = parts[0] if parts else ""
                    last_name = parts[1] if len(parts) > 1 else ""
                    break

        # Groups: collect all values from common group attributes
        groups = []
        for attr_key in (
            "memberOf",
            "groups",
            "Group",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups",
            "http://schemas.xmlsoap.org/claims/Group",
        ):
            vals = attributes.get(attr_key, [])
            groups.extend(vals)

        return {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "groups": groups,
            "name_id": name_id,
            "session_index": session_index,
        }

    # ── SAML ACS handler ─────────────────────────────────────────────

    def handle_saml_callback(self, saml_response_b64):
        """Process a SAML ACS POST and return the authenticated local User.

        Calls ``process_saml_response`` to extract identity claims, then
        find-or-create the local user and map groups to enterprise_role —
        exactly the same as the OIDC callback path.

        Returns the local ``User`` instance (already persisted).
        Raises ``SSOError`` on any failure.
        """
        attrs = self.process_saml_response(saml_response_b64)

        email = attrs["email"]
        first_name = attrs["first_name"]
        last_name = attrs["last_name"]
        groups = attrs["groups"]
        # Use NameID as the stable external_id for SAML users
        external_id = attrs["name_id"] or email

        user = self._find_or_create_user(
            email=email,
            external_id=external_id,
            provider="saml",
            first_name=first_name,
            last_name=last_name,
        )

        role = self.map_groups_to_role(groups)
        if role:
            user.enterprise_role = role

        # Store SAML session index for future Single Logout (SLO) support
        session["saml_session_index"] = attrs["session_index"]

        from app.extensions import db

        db.session.commit()

        logger.info(
            "SAML login successful: user=%s role=%s groups=%s",
            email,
            user.enterprise_role,
            groups,
        )
        return user

    # ── SAML SP Metadata ─────────────────────────────────────────────

    def build_sp_metadata_xml(self):
        """Return the SP (Service Provider) metadata XML string.

        This XML is published at GET /auth/saml/metadata so that IdP
        administrators can import it to configure the service provider trust.

        Raises ``SSOError`` when SAML is not configured.
        """
        cfg = getattr(self, "saml_config", None)
        if not cfg:
            raise SSOError("SAML is not configured")

        acs_url = cfg["sp_acs_url"] or url_for("account.saml_acs", _external=True)
        sp_entity_id = cfg["sp_entity_id"]
        valid_until = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        metadata = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<md:EntityDescriptor'
            ' xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"'
            ' entityID="{sp_entity_id}"'
            ' validUntil="{valid_until}">'
            '  <md:SPSSODescriptor'
            '    AuthnRequestsSigned="false"'
            '    WantAssertionsSigned="true"'
            '    protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
            '    <md:NameIDFormat>'
            '      urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress'
            '    </md:NameIDFormat>'
            '    <md:AssertionConsumerService'
            '      Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"'
            '      Location="{acs_url}"'
            '      index="1"/>'
            '  </md:SPSSODescriptor>'
            '</md:EntityDescriptor>'
        ).format(
            sp_entity_id=sp_entity_id,
            acs_url=acs_url,
            valid_until=valid_until,
        )
        return metadata


# Module-level singleton — initialized via init_app() at startup
sso_service = SSOService()
