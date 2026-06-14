import os
from datetime import timedelta

# Optional raygun import
try:
    from raygun4py.middleware import flask as flask_raygun

    HAS_RAYGUN = True
except ImportError:
    HAS_RAYGUN = False
    flask_raygun = None

# Python 3 only (Python 2 is no longer supported)
import urllib.parse

basedir = os.path.abspath(os.path.dirname(__file__))

# Canonical module configuration. The v2 ("guardrail") modules are the active code
# path (see CLAUDE.md), and the navigation/templates reference their endpoints, so
# they MUST be registered by default. Without these flags a fresh install registers
# only legacy/partial blueprints and every authenticated page 500s on a sidebar
# url_for to an unregistered endpoint (e.g. solution_design.list_solutions). Using
# setdefault means an explicit env value (true/false) is still respected.
for _canonical_flag in (
    "USE_SOLUTIONS_STRATEGIC_GUARDRAILS",
    "USE_NEW_SOLUTIONS_STRATEGIC",
    "USE_CAPABILITIES_GUARDRAILS",
    "USE_NEW_CAPABILITIES",
    "USE_DASHBOARD_GUARDRAILS",
    "USE_NEW_DASHBOARD",
    "USE_APPLICATIONS_GUARDRAILS",
    "USE_NEW_APPLICATIONS",
    "USE_ARCHITECTURE_GUARDRAILS",
    "USE_NEW_ARCHITECTURE",
    "USE_AI_CHAT_GUARDRAILS",
    "USE_NEW_AI_CHAT",
    "USE_VENDORS_GUARDRAILS",
    "USE_NEW_VENDORS",
):
    os.environ.setdefault(_canonical_flag, "true")


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Load environment variables from .env file
from dotenv import load_dotenv

# Load from .env file using explicit path (ensures it works regardless of working directory)
env_path = os.path.join(basedir, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"Loaded environment from: {env_path}")
else:
    # Fallback to default behavior
    load_dotenv()
    print("Loaded environment from default location")

# Verify critical API keys are loaded
_api_keys_loaded = []
for key in [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "HUGGINGFACE_API_KEY",
]:
    if os.getenv(key):
        _api_keys_loaded.append(key)
if _api_keys_loaded:
    print(f"API keys loaded: {', '.join(_api_keys_loaded)}")
else:
    print("WARNING: No LLM API keys found in environment!")


class Config:
    APP_NAME = os.environ.get("APP_NAME", "A.R.C.H.I.E.")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        import secrets

        SECRET_KEY = secrets.token_hex(32)
        print(
            "WARNING: SECRET_KEY env var not set. A random key has been generated "
            "for this session. Sessions will NOT persist across restarts. "
            "Set SECRET_KEY in your .env file for production use."
        )
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True

    # Session security — 8-hour session lifetime, 30-day remember-me cookie
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    SESSION_REFRESH_EACH_REQUEST = True  # FAR-012: Ensure session is refreshed on every request
    REMEMBER_COOKIE_REFRESH_EACH_REQUEST = True  # FAR-012: Refresh remember-me cookie on activity

    # JWT Configuration
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)

    # Email
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.sendgrid.net")
    MAIL_PORT = os.environ.get("MAIL_PORT", 587)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", True)
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

    # Analytics
    GOOGLE_ANALYTICS_ID = os.environ.get("GOOGLE_ANALYTICS_ID", "")
    SEGMENT_API_KEY = os.environ.get("SEGMENT_API_KEY", "")

    # Admin account
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    if not ADMIN_PASSWORD:
        import secrets

        ADMIN_PASSWORD = secrets.token_urlsafe(16)
        print(
            "WARNING: ADMIN_PASSWORD env var not set. Generated random password. "
            "Set ADMIN_PASSWORD in your .env file for production use."
        )
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "flask-base-admin@example.com")
    EMAIL_SUBJECT_PREFIX = "[{}]".format(APP_NAME)
    EMAIL_SENDER = "{app_name} Admin <{email}>".format(
        app_name=APP_NAME, email=MAIL_USERNAME
    )

    # ARCHIE Deploy: Credential encryption + Coolify PaaS + n8n connector sync
    CREDENTIAL_ENCRYPTION_KEY = os.environ.get("CREDENTIAL_ENCRYPTION_KEY", "")
    COOLIFY_API_URL = os.environ.get("COOLIFY_API_URL", "http://localhost:8000")
    COOLIFY_API_TOKEN = os.environ.get("COOLIFY_API_TOKEN", "")
    COOLIFY_DOMAIN_SUFFIX = os.environ.get("COOLIFY_DOMAIN_SUFFIX", "archie.example.com")
    N8N_API_URL = os.environ.get("N8N_API_URL", "http://localhost:5678")
    N8N_API_TOKEN = os.environ.get("N8N_API_TOKEN", "")

    REDIS_URL = os.getenv("REDIS_URL") or os.getenv(
        "REDISTOGO_URL", "redis://localhost:6379/0"
    )

    RAYGUN_APIKEY = os.environ.get("RAYGUN_APIKEY")

    # Stripe Billing (COM-001) — platform works without these; set in production .env
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_PRO = os.environ.get("STRIPE_PRICE_PRO", "")
    STRIPE_PRICE_ENTERPRISE = os.environ.get("STRIPE_PRICE_ENTERPRISE", "")

    # Parse the REDIS_URL to set RQ config variables
    urllib.parse.uses_netloc.append("redis")
    url = urllib.parse.urlparse(REDIS_URL)

    RQ_DEFAULT_HOST = url.hostname
    RQ_DEFAULT_PORT = url.port
    RQ_DEFAULT_PASSWORD = url.password
    RQ_DEFAULT_DB = 0

    # Celery configuration (async task queue)
    # Feature-flagged: set CELERY_ENABLED=true to enable async batch import
    CELERY_ENABLED = os.environ.get("CELERY_ENABLED", "false").lower() == "true"
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)
    CELERY_TASK_SERIALIZER = "json"
    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_TIMEZONE = "UTC"
    CELERY_ENABLE_UTC = True

    # SSO / Enterprise Identity (S0-01)
    # Supports Azure AD, Okta (OIDC) and any SAML 2.0 IdP (PLT-030).
    # Feature-flagged: SSO routes only active when FeatureFlag(key='sso_authentication') is enabled.
    SSO_PROVIDERS = {
        "azure": {
            "client_id": os.environ.get("AZURE_AD_CLIENT_ID", ""),
            "client_secret": os.environ.get("AZURE_AD_CLIENT_SECRET", ""),
            "server_metadata_url": os.environ.get(
                "AZURE_AD_METADATA_URL",
                "https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration".format(
                    tenant=os.environ.get("AZURE_AD_TENANT_ID", "common")
                ),
            ),
            "client_kwargs": {"scope": "openid email profile"},
        },
        "okta": {
            "client_id": os.environ.get("OKTA_CLIENT_ID", ""),
            "client_secret": os.environ.get("OKTA_CLIENT_SECRET", ""),
            "server_metadata_url": os.environ.get("OKTA_METADATA_URL", ""),
            "client_kwargs": {"scope": "openid email profile"},
        },
    }

    # SAML 2.0 IdP configuration (PLT-030)
    # Set SAML_IDP_SSO_URL + SAML_SP_ENTITY_ID to enable SAML alongside OIDC.
    # Supported IdPs: ADFS, PingFederate, Shibboleth, Okta (SAML), Azure AD (SAML).
    # Routes registered at /account/saml/login, /account/saml/acs, /account/saml/metadata.
    SAML_IDP_SSO_URL = os.environ.get("SAML_IDP_SSO_URL", "")
    # IdP Entity ID / Issuer URI (validated against Assertion Issuer element)
    SAML_IDP_ENTITY_ID = os.environ.get("SAML_IDP_ENTITY_ID", "")
    # IdP X.509 signing certificate — PEM body without -----BEGIN/END----- headers.
    # Required for production signature validation (via xmlsec / python3-saml).
    SAML_IDP_CERT = os.environ.get("SAML_IDP_CERT", "")
    # SP Entity ID — typically the platform's base URL
    SAML_SP_ENTITY_ID = os.environ.get("SAML_SP_ENTITY_ID", "")
    # SP ACS URL — leave empty to auto-derive from url_for('account.saml_acs')
    SAML_SP_ACS_URL = os.environ.get("SAML_SP_ACS_URL", "")

    # Internationalization (S2-01) — date/number/currency formatting
    # Full string translation (gettext) is Phase 2.
    BABEL_DEFAULT_LOCALE = os.environ.get("BABEL_DEFAULT_LOCALE", "en")
    BABEL_DEFAULT_TIMEZONE = os.environ.get("BABEL_DEFAULT_TIMEZONE", "UTC")

    # Read Replica Configuration (ENH-012)
    # Set DATABASE_READ_REPLICA_URL to a replica DB connection string to offload
    # dashboard and portfolio GET queries from the primary. When not configured,
    # all queries use the default SQLALCHEMY_DATABASE_URI (no-op).
    DATABASE_READ_REPLICA_URL = os.environ.get("DATABASE_READ_REPLICA_URL", "")
    USE_READ_REPLICA_FOR_DASHBOARD = (
        os.environ.get("USE_READ_REPLICA_FOR_DASHBOARD", "false").lower() == "true"
    )

    # AI-originated CRUD approval gate (A95-008)
    # When true, AI CRUD endpoints return 202 pending_approval instead of writing directly.
    REQUIRE_AI_APPROVAL = os.environ.get("REQUIRE_AI_APPROVAL", "false").lower() == "true"

    # North Star Navigation (NORTH-STAR-001)
    # Enterprise-grade navigation for Fortune 500 TOGAF/ArchiMate practitioners.
    # When enabled: renamed navigation items, persona-based filtering, hidden admin items.
    # Rollback: set to false and restart service (zero risk, instant revert).
    # ENABLED 2026-04-02: Quick wins from NORTH_STAR_ASSESSMENT.md Part 10
    ENABLE_NORTH_STAR_NAV = _env_bool("ENABLE_NORTH_STAR_NAV", True)

    # North Star Navigation Phase 2 (NORTH-STAR-002)
    # Complete ArchiMate 3.2 layer-based navigation with all 55 element types.
    # When enabled: 6-section IA, layer-first architecture, Portfolio/Architecture separation.
    # Depends on: ENABLE_NORTH_STAR_NAV=True (Phase 1 must be active)
    # Rollback: set to false and restart service.
    ENABLE_NORTH_STAR_PHASE2 = _env_bool("ENABLE_NORTH_STAR_PHASE2", False)

    # Page-aware AI guide is fail-closed by default and only activates when
    # this flag is explicitly enabled and an LLM provider is configured.
    AI_PAGE_GUIDE_ENABLED = _env_bool("AI_PAGE_GUIDE_ENABLED", False)

    # File Upload Settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {
        "pdf",
        "docx",
        "doc",
        "xlsx",
        "xls",
        "png",
        "jpg",
        "jpeg",
        "vsdx",
        "txt",
        "csv",
        "md",
    }
    UPLOAD_FOLDER = os.path.join(basedir, "uploads", "documents")

    @staticmethod
    def init_app(app):
        """Base class hook — subclasses override to customize app initialization."""
        return


class DevelopmentConfig(Config):
    DEBUG = True
    ASSETS_DEBUG = True

    # N+1 query detection — set SQLALCHEMY_ECHO=true in .env to enable query logging
    SQLALCHEMY_ECHO = os.environ.get("SQLALCHEMY_ECHO", "false").lower() == "true"
    JIRA_AUTO_PUSH = os.environ.get("JIRA_AUTO_PUSH", "false").lower() == "true"

    # PostgreSQL configuration (REQUIRED - validated at runtime)
    # Default to a local Postgres instance for development when DATABASE_URL is not set.
    # Standard port 5432; set DATABASE_URL in .env to override (e.g. Windows installs
    # that run Postgres on 5439).
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/archie",  # secrets-safety-ok
    )

    # SERVER_NAME must NOT be hardcoded — Flask-WTF CSRF validates the Referer
    # header against SERVER_NAME, so a hardcoded value causes "CSRF token is missing"
    # when the browser omits the Referer header (privacy settings, extensions, etc.).
    # Only set when explicitly provided via environment variable.
    SERVER_NAME = os.environ.get("SERVER_NAME") or None
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "http")
    APPLICATION_ROOT = os.environ.get("APPLICATION_ROOT", "/")

    # PostgreSQL connection options (optimized for local development)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "connect_args": {
            "client_encoding": "utf8",
            "options": "-c client_encoding=utf8",
        },
        "pool_reset_on_return": "commit",
    }

    @classmethod
    def init_app(cls, app):
        # Ensure a sensible default exists for development (Postgres is the standard)
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            app.logger.warning(
                "No DATABASE_URL provided; falling back to local Postgres default."
            )


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False

    # PostgreSQL REQUIRED for tests (matches production behavior)
    # SQLite is NOT supported - tests must use PostgreSQL for consistency
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/archie_test",  # secrets-safety-ok
    )

    # PostgreSQL connection options for testing
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }

    @classmethod
    def init_app(cls, app):
        # Validate PostgreSQL is being used (not SQLite)
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if "sqlite" in db_uri.lower():
            raise ValueError(
                "TEST_DATABASE_URL must be PostgreSQL, not SQLite. "
                "Set TEST_DATABASE_URL to a PostgreSQL connection string. "
                "Example: postgresql://postgres:postgres@localhost:5432/flask_test"  # secrets-safety-ok
            )

        if not db_uri:
            app.logger.warning(
                "No TEST_DATABASE_URL provided; using default local PostgreSQL test database."
            )

        print("THIS APP IS IN TESTING MODE. YOU SHOULD NOT SEE THIS IN PRODUCTION.")


class ProductionConfig(Config):
    DEBUG = False
    USE_RELOADER = False

    # Session cookie security
    _cookie_secure_default = os.environ.get("PREFERRED_URL_SCHEME", "http").lower() == "https"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", _cookie_secure_default)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = _env_bool("REMEMBER_COOKIE_SECURE", _cookie_secure_default)
    REMEMBER_COOKIE_HTTPONLY = True

    # PostgreSQL for production (REQUIRED - validated at runtime)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SSL_DISABLE = os.environ.get("SSL_DISABLE", "False") == "True"
    JIRA_AUTO_PUSH = os.environ.get("JIRA_AUTO_PUSH", "false").lower() == "true"

    # PostgreSQL connection options (optimized for production)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 20,
        "max_overflow": 30,
        "pool_timeout": 30,
        "connect_args": {
            "client_encoding": "utf8",
            "options": "-c client_encoding=utf8",
        },
        "pool_reset_on_return": "commit",
    }

    @classmethod
    def init_app(cls, app):
        # Validate DATABASE_URL is set
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            raise ValueError(
                "DATABASE_URL environment variable is required. PostgreSQL must be configured for production."
            )

        Config.init_app(app)
        assert os.environ.get("SECRET_KEY"), "SECRET_KEY IS NOT SET!"

        # Trust the nginx reverse proxy's forwarded headers (X-Forwarded-Proto /
        # -For) so request.scheme/host reflect the real client-facing protocol.
        # Without this, behind TLS the app still builds http:// external URLs
        # (breaking OAuth redirect URIs, email links) and treats requests as
        # insecure. nginx is the single trusted hop. Idempotent so a subclass
        # (Heroku/Unix) re-running init_app cannot double-wrap.
        if not getattr(app, "_proxyfix_applied", False):
            from werkzeug.middleware.proxy_fix import ProxyFix

            app.wsgi_app = ProxyFix(
                app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
            )
            app._proxyfix_applied = True

        if HAS_RAYGUN and flask_raygun and app.config.get("RAYGUN_APIKEY"):
            flask_raygun.Provider(app, app.config["RAYGUN_APIKEY"]).attach()


class HerokuConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        # ProductionConfig.init_app applies ProxyFix (idempotently); no need to
        # re-wrap here.
        ProductionConfig.init_app(app)


class UnixConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # Log to syslog
        import logging
        from logging.handlers import SysLogHandler

        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)


# Currency Configuration System
class CurrencyConfig:
    """Centralized currency configuration for the application"""

    DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "GBP")

    SUPPORTED_CURRENCIES = {
        "GBP": {
            "symbol": "£",
            "code": "GBP",
            "position": "prefix",  # prefix or suffix
            "decimal_places": 2,
            "thousands_separator": ",",
            "name": "British Pound Sterling",
        },
        "USD": {
            "symbol": "$",
            "code": "USD",
            "position": "prefix",
            "decimal_places": 2,
            "thousands_separator": ",",
            "name": "United States Dollar",
        },
        "EUR": {
            "symbol": "€",
            "code": "EUR",
            "position": "suffix",
            "decimal_places": 2,
            "thousands_separator": ".",
            "name": "Euro",
        },
        "JPY": {
            "symbol": "¥",
            "code": "JPY",
            "position": "prefix",
            "decimal_places": 0,
            "thousands_separator": ",",
            "name": "Japanese Yen",
        },
        "CAD": {
            "symbol": "C$",
            "code": "CAD",
            "position": "prefix",
            "decimal_places": 2,
            "thousands_separator": ",",
            "name": "Canadian Dollar",
        },
        "AUD": {
            "symbol": "A$",
            "code": "AUD",
            "position": "prefix",
            "decimal_places": 2,
            "thousands_separator": ",",
            "name": "Australian Dollar",
        },
    }

    @classmethod
    def get_currency_config(cls, currency_code=None):
        """Get currency configuration for specified currency code"""
        if not currency_code:
            currency_code = cls.DEFAULT_CURRENCY

        config = cls.SUPPORTED_CURRENCIES.get(currency_code)
        if not config:
            # Fallback to default currency instead of crashing
            config = cls.SUPPORTED_CURRENCIES.get(cls.DEFAULT_CURRENCY)

        return config

    @classmethod
    def is_supported(cls, currency_code):
        """Check if currency is supported"""
        return currency_code in cls.SUPPORTED_CURRENCIES

    @classmethod
    def get_all_supported_codes(cls):
        """Get list of all supported currency codes"""
        return list(cls.SUPPORTED_CURRENCIES.keys())


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
    "heroku": HerokuConfig,
    "unix": UnixConfig,
}
