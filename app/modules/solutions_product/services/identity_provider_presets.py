"""
Identity Provider Presets — OIDC-compliant IdP configurations for generated auth.

Each preset contains URL templates, default scopes, and role claim paths for
the five most common enterprise identity providers. Templates use Python
str.format() placeholders that are filled from user-supplied parameters.
"""
import copy
import logging

logger = logging.getLogger(__name__)


IDENTITY_PROVIDER_PRESETS = {
    "okta": {
        "display_name": "Okta",
        "issuer_url_template": "https://{domain}.okta.com/oauth2/default",
        "jwks_uri_template": "https://{domain}.okta.com/oauth2/default/v1/keys",
        "token_endpoint_template": "https://{domain}.okta.com/oauth2/default/v1/token",
        "role_claim": "groups",
        "default_scopes": ["openid", "profile", "email"],
        "required_params": ["domain"],
    },
    "azure_ad": {
        "display_name": "Azure Active Directory",
        "issuer_url_template": "https://login.microsoftonline.com/{tenant_id}/v2.0",
        "jwks_uri_template": "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
        "token_endpoint_template": "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        "role_claim": "roles",
        "default_scopes": ["openid", "profile"],
        "required_params": ["tenant_id"],
    },
    "keycloak": {
        "display_name": "Keycloak",
        "issuer_url_template": "https://{host}/realms/{realm}",
        "jwks_uri_template": "https://{host}/realms/{realm}/protocol/openid-connect/certs",
        "token_endpoint_template": "https://{host}/realms/{realm}/protocol/openid-connect/token",
        "role_claim": "realm_access.roles",
        "default_scopes": ["openid", "profile"],
        "required_params": ["host", "realm"],
    },
    "auth0": {
        "display_name": "Auth0",
        "issuer_url_template": "https://{domain}.auth0.com/",
        "jwks_uri_template": "https://{domain}.auth0.com/.well-known/jwks.json",
        "token_endpoint_template": "https://{domain}.auth0.com/oauth/token",
        "role_claim": "permissions",
        "default_scopes": ["openid", "profile", "email"],
        "required_params": ["domain"],
    },
    "cognito": {
        "display_name": "AWS Cognito",
        "issuer_url_template": "https://cognito-idp.{region}.amazonaws.com/{user_pool_id}",
        "jwks_uri_template": "https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json",
        "token_endpoint_template": "https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/oauth2/token",
        "role_claim": "cognito:groups",
        "default_scopes": ["openid", "profile"],
        "required_params": ["region", "user_pool_id"],
    },
}


def get_preset(provider_type):
    """Return a deep copy of the preset for the given provider type, or None."""
    preset = IDENTITY_PROVIDER_PRESETS.get(provider_type)
    if preset is None:
        return None
    return copy.deepcopy(preset)


def list_presets():
    """Return a list of available preset summaries."""
    return [
        {
            "type": k,
            "display_name": v["display_name"],
            "required_params": v["required_params"],
            "default_scopes": v["default_scopes"],
            "role_claim": v["role_claim"],
        }
        for k, v in IDENTITY_PROVIDER_PRESETS.items()
    ]


def expand_preset(provider_type, params):
    """Expand a preset's URL templates with user-supplied parameters.

    Args:
        provider_type: One of the IDENTITY_PROVIDER_PRESETS keys.
        params: Dict of template parameters (e.g. {"domain": "company"}).

    Returns:
        Dict with expanded URLs, or None if provider_type is unknown.

    Raises:
        ValueError: If required parameters are missing.
    """
    preset = get_preset(provider_type)
    if preset is None:
        return None

    required = preset.get("required_params", [])
    missing = [p for p in required if p not in params or not params[p]]
    if missing:
        raise ValueError(
            f"Missing required parameters for {provider_type}: {', '.join(missing)}"
        )

    return {
        "type": provider_type,
        "display_name": preset["display_name"],
        "issuer_url": preset["issuer_url_template"].format(**params),
        "jwks_uri": preset["jwks_uri_template"].format(**params),
        "token_endpoint": preset["token_endpoint_template"].format(**params),
        "role_claim": preset["role_claim"],
        "scopes": preset["default_scopes"],
    }


def build_identity_provider_config(body):
    """Build a validated identity provider config from API request body.

    Accepts either:
    1. A preset type + params: {"type": "okta", "params": {"domain": "company"}, ...}
    2. A custom config: {"type": "custom", "issuer_url": "...", "jwks_uri": "...", ...}

    Returns a normalized config dict suitable for storage in spec_data.

    Raises:
        ValueError: On invalid input.
    """
    provider_type = body.get("type")
    if not provider_type:
        raise ValueError("identity provider 'type' is required")

    if provider_type == "custom":
        # Custom provider — require explicit URLs
        issuer_url = body.get("issuer_url")
        jwks_uri = body.get("jwks_uri")
        if not issuer_url or not jwks_uri:
            raise ValueError(
                "Custom provider requires 'issuer_url' and 'jwks_uri'"
            )
        config = {
            "type": "custom",
            "display_name": body.get("display_name", "Custom OIDC Provider"),
            "issuer_url": issuer_url,
            "jwks_uri": jwks_uri,
            "token_endpoint": body.get("token_endpoint", ""),
            "role_claim": body.get("role_claim", "roles"),
            "scopes": body.get("scopes", ["openid", "profile"]),
        }
    else:
        # Preset-based — expand templates
        params = body.get("params", {})
        config = expand_preset(provider_type, params)
        if config is None:
            raise ValueError(
                f"Unknown provider type: {provider_type}. "
                f"Available: {', '.join(IDENTITY_PROVIDER_PRESETS.keys())}, custom"
            )

    # Common fields
    config["client_id_env"] = body.get("client_id_env", "OAUTH_CLIENT_ID")
    config["audience"] = body.get("audience", "")
    config["role_mapping"] = body.get("role_mapping", {})

    # Override scopes if explicitly provided
    if "scopes" in body and body["scopes"]:
        config["scopes"] = body["scopes"]

    return config
