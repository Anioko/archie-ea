"""
AABL Compiler — ArchiMate Architecture Blueprint Language

Transforms accepted ArchiMate elements from the journey wizard (Step 3)
into an Architectural Genome YAML/dict that code generators consume.

The genome is the single intermediate representation between architecture
design and code generation. It preserves traceability (every genome field
links back to its source ArchiMateElement.id) and design rationale.

Pipeline position:
  ArchiMate elements → AABL Compiler → Genome → GenomeToBundle → DeterministicCodeGenerator → Code

Genome schema: agents/schemas/architectural_genome_schema.json
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app import db

logger = logging.getLogger(__name__)

# Current genome schema version. Generators declare compatibility ranges.
GENOME_VERSION = "1.0.0"

# G17: genome schema migration table.
# When the AABL compiler adds new required keys, add a migration step here so
# that stored genomes compiled under an older version are upgraded on load.
_GENOME_MIGRATIONS = {
    # "0.9.0" → "1.0.0": 'security' key was renamed from 'auth_config'
    # Only add entries here when a breaking schema change is made to GENOME_VERSION.
}


def migrate_genome(genome: dict) -> dict:
    """Normalise a stored genome dict to the current GENOME_VERSION schema.

    Safe to call on already-current genomes — returns the dict unchanged.
    """
    if not isinstance(genome, dict):
        return genome
    stored_version = genome.get("genome_version", "1.0.0")
    if stored_version == GENOME_VERSION:
        return genome
    # Apply incremental migrations in version order
    for _from_ver, _migrator in _GENOME_MIGRATIONS.items():
        if stored_version == _from_ver:
            genome = _migrator(genome)
            stored_version = genome.get("genome_version", GENOME_VERSION)
    # Ensure version stamp is current after migrations
    genome["genome_version"] = GENOME_VERSION
    logger.info("Genome migrated from %s → %s", stored_version, GENOME_VERSION)
    return genome

# ArchiMate element types → genome mapping layer
_LAYER_MAP = {
    # Motivation layer
    "stakeholder": "motivation",
    "driver": "motivation",
    "assessment": "motivation",
    "goal": "motivation",
    "outcome": "motivation",
    "principle": "motivation",
    "requirement": "motivation",
    "constraint": "motivation",
    "meaning": "motivation",
    "value": "motivation",
    # Strategy layer
    "resource": "strategy",
    "capability": "strategy",
    "value_stream": "strategy",
    "course_of_action": "strategy",
    # Business layer
    "business_actor": "business",
    "business_role": "business",
    "business_collaboration": "business",
    "business_interface": "business",
    "business_process": "business",
    "business_function": "business",
    "business_interaction": "business",
    "business_event": "business",
    "business_service": "business",
    "business_object": "business",
    "contract": "business",
    "representation": "business",
    "product": "business",
    "location": "business",
    # Application layer
    "application_component": "application",
    "application_collaboration": "application",
    "application_interface": "application",
    "application_function": "application",
    "application_interaction": "application",
    "application_process": "application",
    "application_event": "application",
    "application_service": "application",
    "data_object": "application",
    # Technology layer
    "node": "technology",
    "device": "technology",
    "system_software": "technology",
    "technology_collaboration": "technology",
    "technology_interface": "technology",
    "path": "technology",
    "communication_network": "technology",
    "technology_function": "technology",
    "technology_process": "technology",
    "technology_interaction": "technology",
    "technology_event": "technology",
    "technology_service": "technology",
    "artifact": "technology",
    "technology_object": "technology",
    # Implementation & Migration
    "work_package": "implementation",
    "deliverable": "implementation",
    "implementation_event": "implementation",
    "plateau": "implementation",
    "gap": "implementation",
}

# Element types that become modules (bounded contexts) in the genome
_MODULE_TYPES = {"application_component", "application_service", "application_function"}

# Element types that become entities (data objects) in the genome
_ENTITY_TYPES = {"data_object", "business_object", "location", "technology_object"}

# ArchiMate type suffixes to strip from element names to get clean domain names.
# "Workspace Data Object" → "Workspace", "Order Application Component" → "Order"
_ARCHIMATE_SUFFIXES = re.compile(
    r"\s*(?:Data\s*Object|Business\s*Object|Application\s*Component|"
    r"Application\s*Service|Application\s*Function|Application\s*Interface|"
    r"Business\s*Process|Business\s*Service|Business\s*Function|"
    r"Technology\s*Object|Technology\s*Service|Node|Artifact|"
    r"DataObject|BusinessObject|ApplicationComponent|"
    r"ApplicationService|ApplicationFunction|ApplicationInterface|"
    r"BusinessProcess|BusinessService|BusinessFunction|"
    r"TechnologyObject|TechnologyService)\s*$",
    re.IGNORECASE,
)


def _strip_archimate_suffix(name: str) -> str:
    """Strip ArchiMate type suffixes from element names to get clean domain names.

    "Workspace Data Object" → "Workspace"
    "Order Application Component" → "Order"
    "Customer" → "Customer" (no suffix to strip)
    """
    stripped = _ARCHIMATE_SUFFIXES.sub("", name).strip()
    return stripped if stripped else name

# Element types that become business rules / constraints
_RULE_TYPES = {"constraint", "requirement", "principle"}

# Element types that become state machine sources
_PROCESS_TYPES = {
    "business_process", "business_function", "application_process",
    "technology_process", "technology_interaction", "technology_event",
}

# Element types in the Motivation layer (goals, drivers, values)
_MOTIVATION_TYPES = {"meaning", "value"}

# ── Technical Capability Model ────────────────────────────────────────────────
# Maps business domain patterns and entity types to codegen capability flags.
# Used to infer cross-cutting concerns when the architect doesn't explicitly select them.
#
# Domain keywords → capabilities inferred from business domain
_DOMAIN_CAPABILITY_MAP = {
    "finance": {"audit_trail", "encryption_at_rest", "export", "mfa", "multi_tenancy"},
    "banking": {"audit_trail", "encryption_at_rest", "export", "mfa", "multi_tenancy", "notifications"},
    "insurance": {"audit_trail", "export", "file_storage", "notifications", "webhooks"},
    "healthcare": {"audit_trail", "encryption_at_rest", "mfa", "file_storage"},
    "ecommerce": {"webhooks", "notifications", "export", "search", "file_storage"},
    "retail": {"export", "search", "notifications"},
    "manufacturing": {"export", "webhooks", "audit_trail"},
    "logistics": {"webhooks", "notifications", "export", "search"},
    "hr": {"audit_trail", "export", "notifications", "file_storage", "encryption_at_rest"},
    "crm": {"search", "export", "notifications", "webhooks"},
    "erp": {"audit_trail", "export", "search", "multi_tenancy", "webhooks"},
    "saas": {"multi_tenancy", "api_keys", "webhooks", "notifications", "export"},
    "marketplace": {"multi_tenancy", "search", "notifications", "webhooks", "file_storage"},
    "government": {"audit_trail", "encryption_at_rest", "mfa", "export"},
    "education": {"notifications", "file_storage", "export"},
    "field service": {"notifications", "file_storage", "export", "search"},
}

# Entity name patterns → capabilities inferred from what entities exist
_ENTITY_CAPABILITY_MAP = {
    "user": {"notifications"},
    "order": {"audit_trail", "export", "webhooks", "notifications"},
    "invoice": {"audit_trail", "export", "notifications"},
    "payment": {"audit_trail", "encryption_at_rest", "webhooks", "notifications"},
    "document": {"file_storage", "search", "export"},
    "contract": {"audit_trail", "file_storage", "export"},
    "report": {"export"},
    "notification": {"notifications"},
    "webhook": {"webhooks"},
    "audit": {"audit_trail"},
    "tenant": {"multi_tenancy"},
    "subscription": {"webhooks", "notifications"},
    "workflow": {"audit_trail", "notifications", "webhooks"},
    "approval": {"audit_trail", "notifications"},
    "ticket": {"notifications", "search", "webhooks"},
    "message": {"notifications", "search"},
    "file": {"file_storage"},
    "attachment": {"file_storage"},
    "email": {"notifications"},
    "import": {"file_storage", "export"},
}

# ── Universal mandatory capability baseline ────────────────────────────────────
# Applied to EVERY solution before domain-specific augmentation.
# These capabilities are non-negotiable for production-readiness.
_UNIVERSAL_BASELINE: set = {
    "auth_rbac",         # JWT + role-based access control always enforced
    "health_endpoints",  # /health + /ready probes always present
    "account_settings",  # /api/v1/account/* routes always generated
    "error_handling",    # Typed error responses always generated
    "api_versioning",    # /api/v1/ prefix always used
    "seed_data",         # Demo data seeded on first boot
    "soft_delete",       # deleted_at on all models; hard DELETE forbidden
    "security_headers",  # CORS + CSP + HSTS middleware always registered
    "audit_trail",       # Mutation audit log always generated
    "rate_limiting",     # Request rate limits always configured
}


# ── Vendor SDK Registry ───────────────────────────────────────────────────
# Maps vendor product names (snake_case from ArchiMate element names) to SDK metadata.
# When the AABL compiler encounters a vendor-origin module, it looks up the SDK
# config here to generate a typed integration client instead of CRUD entities.
_VENDOR_SDK_MAP = {
    # Email / Notifications
    "sendgrid": {
        "protocol": "rest", "auth_method": "bearer",
        "base_url": "https://api.sendgrid.com/v3",
        "sdk_package": "@sendgrid/mail",
        "capability": "notifications",
        "operations": [
            {"name": "send_email", "method": "POST", "path": "/mail/send", "description": "Send a transactional email"},
            {"name": "list_templates", "method": "GET", "path": "/templates", "description": "List email templates"},
        ],
    },
    "mailchimp": {
        "protocol": "rest", "auth_method": "bearer",
        "base_url": "https://server.api.mailchimp.com/3.0",
        "sdk_package": "@mailchimp/mailchimp_marketing",
        "capability": "notifications",
        "operations": [
            {"name": "send_campaign", "method": "POST", "path": "/campaigns/{id}/actions/send"},
            {"name": "add_subscriber", "method": "POST", "path": "/lists/{list_id}/members"},
        ],
    },
    "twilio": {
        "protocol": "rest", "auth_method": "basic",
        "base_url": "https://api.twilio.com/2010-04-01",
        "sdk_package": "twilio",
        "capability": "notifications",
        "operations": [
            {"name": "send_sms", "method": "POST", "path": "/Accounts/{sid}/Messages.json"},
            {"name": "send_whatsapp", "method": "POST", "path": "/Accounts/{sid}/Messages.json"},
        ],
    },
    # Storage
    "aws_s3": {
        "protocol": "rest", "auth_method": "aws_sigv4",
        "base_url": "https://s3.amazonaws.com",
        "sdk_package": "boto3",
        "capability": "file_storage",
        "operations": [
            {"name": "upload_file", "method": "PUT", "path": "/{bucket}/{key}"},
            {"name": "download_file", "method": "GET", "path": "/{bucket}/{key}"},
            {"name": "delete_file", "method": "DELETE", "path": "/{bucket}/{key}"},
            {"name": "generate_presigned_url", "method": "GET", "path": "/{bucket}/{key}?presigned"},
        ],
    },
    "azure_blob_storage": {
        "protocol": "rest", "auth_method": "bearer",
        "base_url": "https://{account}.blob.core.windows.net",
        "sdk_package": "@azure/storage-blob",
        "capability": "file_storage",
        "operations": [
            {"name": "upload_blob", "method": "PUT", "path": "/{container}/{blob}"},
            {"name": "download_blob", "method": "GET", "path": "/{container}/{blob}"},
        ],
    },
    # Payment
    "stripe": {
        "protocol": "rest", "auth_method": "bearer",
        "base_url": "https://api.stripe.com/v1",
        "sdk_package": "stripe",
        "capability": "payment",
        "operations": [
            {"name": "create_payment_intent", "method": "POST", "path": "/payment_intents"},
            {"name": "create_customer", "method": "POST", "path": "/customers"},
            {"name": "list_invoices", "method": "GET", "path": "/invoices"},
            {"name": "create_subscription", "method": "POST", "path": "/subscriptions"},
        ],
    },
    # Search
    "elasticsearch": {
        "protocol": "rest", "auth_method": "basic",
        "base_url": "https://localhost:9200",
        "sdk_package": "elasticsearch",
        "capability": "search",
        "operations": [
            {"name": "index_document", "method": "POST", "path": "/{index}/_doc"},
            {"name": "search", "method": "POST", "path": "/{index}/_search"},
            {"name": "delete_document", "method": "DELETE", "path": "/{index}/_doc/{id}"},
        ],
    },
    "algolia": {
        "protocol": "rest", "auth_method": "api_key",
        "base_url": "https://{app_id}.algolia.net",
        "sdk_package": "algoliasearch",
        "capability": "search",
        "operations": [
            {"name": "save_object", "method": "POST", "path": "/1/indexes/{index}"},
            {"name": "search", "method": "POST", "path": "/1/indexes/{index}/query"},
        ],
    },
    # Auth / Identity
    "auth0": {
        "protocol": "rest", "auth_method": "bearer",
        "base_url": "https://{domain}.auth0.com",
        "sdk_package": "auth0-python",
        "capability": "auth",
        "operations": [
            {"name": "get_user", "method": "GET", "path": "/api/v2/users/{id}"},
            {"name": "create_user", "method": "POST", "path": "/api/v2/users"},
            {"name": "assign_role", "method": "POST", "path": "/api/v2/users/{id}/roles"},
        ],
    },
    "okta": {
        "protocol": "rest", "auth_method": "bearer",
        "base_url": "https://{domain}.okta.com",
        "sdk_package": "okta",
        "capability": "auth",
        "operations": [
            {"name": "get_user", "method": "GET", "path": "/api/v1/users/{id}"},
            {"name": "create_user", "method": "POST", "path": "/api/v1/users"},
        ],
    },
    # Messaging / Event Bus
    "kafka": {
        "protocol": "async", "auth_method": "sasl",
        "base_url": "localhost:9092",
        "sdk_package": "confluent-kafka",
        "capability": "event_bus",
        "operations": [
            {"name": "produce", "method": "PUBLISH", "path": "topic"},
            {"name": "consume", "method": "SUBSCRIBE", "path": "topic"},
        ],
    },
    "rabbitmq": {
        "protocol": "async", "auth_method": "basic",
        "base_url": "amqp://localhost:5672",
        "sdk_package": "pika",
        "capability": "event_bus",
        "operations": [
            {"name": "publish", "method": "PUBLISH", "path": "exchange/routing_key"},
            {"name": "consume", "method": "SUBSCRIBE", "path": "queue"},
        ],
    },
    # CRM / ERP (enterprise vendors)
    "salesforce": {
        "protocol": "rest", "auth_method": "oauth2",
        "base_url": "https://login.salesforce.com/services/data/v59.0",
        "sdk_package": "simple-salesforce",
        "operations": [
            {"name": "query", "method": "GET", "path": "/query?q={soql}"},
            {"name": "create_record", "method": "POST", "path": "/sobjects/{object}"},
            {"name": "update_record", "method": "PATCH", "path": "/sobjects/{object}/{id}"},
        ],
    },
    "sap_s4hana": {
        "protocol": "rest", "auth_method": "oauth2",
        "base_url": "https://api.sap.com/s4hana",
        "sdk_package": "@sap-cloud-sdk/core",
        "operations": [
            {"name": "get_business_partner", "method": "GET", "path": "/API_BUSINESS_PARTNER/A_BusinessPartner"},
            {"name": "create_sales_order", "method": "POST", "path": "/API_SALES_ORDER/A_SalesOrder"},
            {"name": "get_material", "method": "GET", "path": "/API_PRODUCT_SRV/A_Product"},
        ],
    },
    "dynamics_365": {
        "protocol": "rest", "auth_method": "oauth2",
        "base_url": "https://{org}.api.crm.dynamics.com/api/data/v9.2",
        "sdk_package": "@microsoft/microsoft-graph-client",
        "operations": [
            {"name": "get_account", "method": "GET", "path": "/accounts({id})"},
            {"name": "create_contact", "method": "POST", "path": "/contacts"},
            {"name": "list_opportunities", "method": "GET", "path": "/opportunities"},
        ],
    },
    # Monitoring / Observability
    "datadog": {
        "protocol": "rest", "auth_method": "api_key",
        "base_url": "https://api.datadoghq.com/api/v2",
        "sdk_package": "datadog-api-client",
        "capability": "observability",
        "operations": [
            {"name": "submit_metrics", "method": "POST", "path": "/series"},
            {"name": "create_event", "method": "POST", "path": "/events"},
        ],
    },
    # CI/CD
    "jira": {
        "protocol": "rest", "auth_method": "bearer",
        "base_url": "https://{domain}.atlassian.net/rest/api/3",
        "sdk_package": "jira",
        "operations": [
            {"name": "create_issue", "method": "POST", "path": "/issue"},
            {"name": "get_issue", "method": "GET", "path": "/issue/{key}"},
            {"name": "transition_issue", "method": "POST", "path": "/issue/{key}/transitions"},
        ],
    },
    "slack": {
        "protocol": "rest", "auth_method": "bearer",
        "base_url": "https://slack.com/api",
        "sdk_package": "@slack/web-api",
        "capability": "notifications",
        "operations": [
            {"name": "post_message", "method": "POST", "path": "/chat.postMessage"},
            {"name": "upload_file", "method": "POST", "path": "/files.upload"},
        ],
    },
}

# SQLAlchemy reserved attribute names that cannot be used as column names
_RESERVED_FIELD_NAMES = frozenset({
    "metadata", "registry", "query", "query_class",
})


def _snake_case(name: str) -> str:
    """Convert a name to snake_case for module/field keys.
    Prefixes 'entity_' if result starts with a digit.
    """
    s = re.sub(r"[^\w\s]", "", name)
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    result = s.lower()
    if result and result[0].isdigit():
        result = "entity_" + result
    return result


def _infer_integrations_from_text(text: str, existing_keys: set = None) -> dict:
    """Deterministically infer vendor integrations from free-text (enriched_brief, description).

    Scans for product/vendor names using a keyword map and emits typed integration
    configs.  Works without LLM — no API keys required.  Called as a fallback when
    Step 1 integration_requirements is empty (e.g., PDF-upload wizard path).

    Args:
        text: Combined enriched_brief + description text.
        existing_keys: Integration keys already present — skip duplicates.

    Returns:
        Dict of {integration_key: integration_config} to merge into genome integrations.
    """
    if existing_keys is None:
        existing_keys = set()

    text_lower = text.lower()
    results = {}

    # Ordered by specificity so "dynamics 365" matches before generic "microsoft"
    _VENDOR_TEXT_MAP = [
        # ERP / CRM
        ("microsoft dynamics 365", "dynamics_365",
         {"name": "Microsoft Dynamics 365", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://{tenant}.api.crm.dynamics.com/api/data/v9.2",
          "sdk_package": "msal", "description": "Microsoft Dynamics 365 CRM/ERP"}),
        ("dynamics 365", "dynamics_365",
         {"name": "Microsoft Dynamics 365", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://{tenant}.api.crm.dynamics.com/api/data/v9.2",
          "sdk_package": "msal", "description": "Microsoft Dynamics 365 CRM/ERP"}),
        ("dynamics", "dynamics_365",
         {"name": "Microsoft Dynamics", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://{tenant}.api.crm.dynamics.com/api/data/v9.2",
          "sdk_package": "msal", "description": "Microsoft Dynamics CRM/ERP"}),
        ("salesforce", "salesforce",
         {"name": "Salesforce", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://{instance}.salesforce.com/services/data/v57.0",
          "sdk_package": "simple-salesforce", "description": "Salesforce CRM integration"}),
        ("sap", "sap",
         {"name": "SAP", "protocol": "odata", "auth_method": "basic",
          "base_url": "https://{host}/sap/opu/odata/sap",
          "sdk_package": "pyrfc", "description": "SAP ERP/S4HANA integration"}),
        ("oracle", "oracle_erp",
         {"name": "Oracle ERP", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://{host}/fscmRestApi/resources/11.13.18.05",
          "description": "Oracle Fusion ERP integration"}),
        ("workday", "workday",
         {"name": "Workday", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://{tenant}.workday.com/ccx/service",
          "description": "Workday HCM/Finance integration"}),

        # Cloud / Infra
        ("aws", "aws_sdk",
         {"name": "AWS", "protocol": "rest", "auth_method": "aws_sig4",
          "sdk_package": "boto3", "description": "Amazon Web Services SDK"}),
        ("azure", "azure_sdk",
         {"name": "Microsoft Azure", "protocol": "rest", "auth_method": "oauth2",
          "sdk_package": "azure-sdk-for-python", "description": "Azure cloud services"}),
        ("google cloud", "gcp",
         {"name": "Google Cloud", "protocol": "rest", "auth_method": "service_account",
          "sdk_package": "google-cloud", "description": "Google Cloud Platform"}),

        # AI / ML
        ("openai", "openai",
         {"name": "OpenAI", "protocol": "rest", "auth_method": "api_key",
          "base_url": "https://api.openai.com/v1",
          "sdk_package": "openai", "description": "OpenAI GPT/embedding API"}),
        ("anthropic", "anthropic",
         {"name": "Anthropic Claude", "protocol": "rest", "auth_method": "api_key",
          "base_url": "https://api.anthropic.com/v1",
          "sdk_package": "anthropic", "description": "Anthropic Claude API"}),
        ("azure openai", "azure_openai",
         {"name": "Azure OpenAI", "protocol": "rest", "auth_method": "api_key",
          "base_url": "https://{resource}.openai.azure.com/openai",
          "sdk_package": "openai", "description": "Azure-hosted OpenAI service"}),
        ("document intelligence", "azure_doc_intelligence",
         {"name": "Azure Document Intelligence", "protocol": "rest", "auth_method": "api_key",
          "base_url": "https://{endpoint}.cognitiveservices.azure.com/formrecognizer/documentModels",
          "sdk_package": "azure-ai-formrecognizer",
          "description": "Azure Form Recognizer / Document Intelligence"}),
        ("form recognizer", "azure_doc_intelligence",
         {"name": "Azure Form Recognizer", "protocol": "rest", "auth_method": "api_key",
          "base_url": "https://{endpoint}.cognitiveservices.azure.com/formrecognizer/documentModels",
          "sdk_package": "azure-ai-formrecognizer",
          "description": "Azure Form Recognizer for document extraction"}),

        # Low-code / automation
        ("power automate", "power_automate",
         {"name": "Power Automate", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://api.flow.microsoft.com",
          "description": "Microsoft Power Automate workflow automation"}),
        ("power apps", "power_apps",
         {"name": "Power Apps", "protocol": "rest", "auth_method": "oauth2",
          "description": "Microsoft Power Apps low-code platform"}),
        ("appsheet", "appsheet",
         {"name": "AppSheet", "protocol": "rest", "auth_method": "api_key",
          "base_url": "https://api.appsheet.com/api/v2",
          "description": "Google AppSheet no-code mobile app platform"}),
        ("servicenow", "servicenow",
         {"name": "ServiceNow", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://{instance}.service-now.com/api/now",
          "description": "ServiceNow ITSM integration"}),

        # Email / Messaging
        ("sendgrid", "sendgrid",
         {"name": "SendGrid", "protocol": "rest", "auth_method": "api_key",
          "base_url": "https://api.sendgrid.com/v3",
          "sdk_package": "sendgrid", "description": "SendGrid transactional email"}),
        ("smtp", "smtp_email",
         {"name": "SMTP Email", "protocol": "smtp", "auth_method": "basic",
          "description": "SMTP email relay for transactional notifications"}),
        ("twilio", "twilio",
         {"name": "Twilio", "protocol": "rest", "auth_method": "basic",
          "base_url": "https://api.twilio.com/2010-04-01",
          "sdk_package": "twilio", "description": "Twilio SMS/voice communications"}),
        ("teams", "microsoft_teams",
         {"name": "Microsoft Teams", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://graph.microsoft.com/v1.0",
          "sdk_package": "botbuilder-core",
          "description": "Microsoft Teams bot / webhook notifications"}),
        ("slack", "slack",
         {"name": "Slack", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://slack.com/api",
          "sdk_package": "slack-sdk", "description": "Slack notifications and commands"}),

        # Auth / Identity
        ("active directory", "active_directory",
         {"name": "Active Directory / LDAP", "protocol": "ldap", "auth_method": "kerberos",
          "description": "Microsoft Active Directory LDAP authentication"}),
        ("oauth", "oauth2_provider",
         {"name": "OAuth2 Provider", "protocol": "rest", "auth_method": "oauth2",
          "description": "OAuth2 identity provider integration"}),
        ("auth0", "auth0",
         {"name": "Auth0", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://{domain}.auth0.com",
          "sdk_package": "authlib", "description": "Auth0 identity platform"}),
        ("okta", "okta",
         {"name": "Okta", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://{domain}.okta.com/api/v1",
          "sdk_package": "okta-sdk-python", "description": "Okta identity and SSO"}),

        # Payment
        ("stripe", "stripe",
         {"name": "Stripe", "protocol": "rest", "auth_method": "api_key",
          "base_url": "https://api.stripe.com/v1",
          "sdk_package": "stripe", "description": "Stripe payment processing"}),
        ("paypal", "paypal",
         {"name": "PayPal", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://api.paypal.com/v2",
          "description": "PayPal payment integration"}),

        # Storage / Data
        ("sharepoint", "sharepoint",
         {"name": "SharePoint", "protocol": "rest", "auth_method": "oauth2",
          "base_url": "https://graph.microsoft.com/v1.0/sites",
          "sdk_package": "msal",
          "description": "SharePoint document storage and collaboration"}),
        ("s3", "aws_s3",
         {"name": "AWS S3", "protocol": "rest", "auth_method": "aws_sig4",
          "sdk_package": "boto3", "description": "AWS S3 object storage"}),
        ("docparser", "docparser",
         {"name": "Docparser", "protocol": "rest", "auth_method": "api_key",
          "base_url": "https://api.docparser.com/v1",
          "description": "Docparser document parsing service"}),
    ]

    for keyword, integ_key, template in _VENDOR_TEXT_MAP:
        if keyword in text_lower and integ_key not in existing_keys and integ_key not in results:
            results[integ_key] = dict(template)
            results[integ_key]["_inferred_from_text"] = True

            results[integ_key]["_inferred_from_text"] = True

    return results


def _infer_integrations_from_components(component_names: list, existing_keys: set = None) -> dict:
    """Infer infrastructure integrations from architecture component names.

    Maps well-known component types (API gateway, message broker, monitoring, etc.)
    to concrete integration configs.  Works purely from element names — no vendor
    keywords, no LLM required.  Covers the PDF-upload wizard path where enriched_brief
    contains no specific product names.

    Args:
        component_names: List of element/module names from genome_modules.
        existing_keys: Integration keys already present — skip duplicates.

    Returns:
        Dict of {integration_key: integration_config} to merge into genome integrations.
    """
    if existing_keys is None:
        existing_keys = set()

    combined = " ".join(n.lower() for n in component_names if n)
    results = {}

    def _add(key, config):
        if key not in existing_keys and key not in results:
            results[key] = dict(config)
            results[key]["_inferred_from_components"] = True

    # API Gateway / Management
    if any(kw in combined for kw in ("api gateway", "api management", "api manager")):
        _add("api_gateway", {
            "name": "API Gateway",
            "protocol": "rest",
            "auth_method": "api_key",
            "description": "API gateway for routing, rate-limiting, and authentication",
            "sdk_package": "httpx",
        })

    # Message broker / queue
    if any(kw in combined for kw in ("message broker", "message queue", "event bus", "kafka", "rabbitmq", "pub/sub", "pubsub")):
        _add("message_queue", {
            "name": "Message Queue (e.g. RabbitMQ / SQS)",
            "protocol": "amqp",
            "auth_method": "basic",
            "description": "Async message queue for decoupled pipeline stages",
            "sdk_package": "kombu",
            "operations": ["publish", "subscribe", "ack", "nack", "dead_letter"],
        })

    # Identity / auth / SSO
    if any(kw in combined for kw in ("identity", "access management", "authentication", "sso", "ldap", "oauth")):
        _add("identity_provider", {
            "name": "Identity Provider (OAuth2 / OIDC)",
            "protocol": "rest",
            "auth_method": "oauth2",
            "base_url": "https://{idp-domain}/oauth2",
            "description": "OAuth2/OIDC identity provider for authentication and SSO",
            "sdk_package": "authlib",
            "operations": ["authorize", "token", "refresh", "introspect", "userinfo"],
        })

    # Email / SMTP / notifications
    if any(kw in combined for kw in ("email", "notification", "smtp", "mail", "alert")):
        _add("smtp_email", {
            "name": "SMTP Email / Notification Service",
            "protocol": "smtp",
            "auth_method": "basic",
            "description": "Transactional email and notification delivery",
            "sdk_package": "smtplib",
            "operations": ["send_email", "send_bulk", "track_delivery"],
        })

    # Document storage / object storage
    if any(kw in combined for kw in ("document", "content platform", "storage", "file", "pdf", "blob", "upload")):
        _add("document_storage", {
            "name": "Document / Object Storage (S3-compatible)",
            "protocol": "rest",
            "auth_method": "aws_sig4",
            "base_url": "https://s3.{region}.amazonaws.com",
            "description": "Object storage for documents, PDFs, images, and generated files",
            "sdk_package": "boto3",
            "operations": ["upload", "download", "delete", "list", "presign"],
        })

    # Monitoring / observability
    if any(kw in combined for kw in ("monitoring", "observability", "metrics", "logging", "tracing", "analytics engine")):
        _add("monitoring", {
            "name": "Observability Platform (OpenTelemetry)",
            "protocol": "grpc",
            "auth_method": "bearer",
            "description": "Metrics, traces, and logs via OpenTelemetry collector",
            "sdk_package": "opentelemetry-sdk",
            "operations": ["record_metric", "start_span", "log_event", "flush"],
        })

    # CI/CD
    if any(kw in combined for kw in ("ci/cd", "cicd", "pipeline", "toolchain", "release management", "deployment")):
        _add("cicd_pipeline", {
            "name": "CI/CD Pipeline (GitHub Actions / GitLab CI)",
            "protocol": "rest",
            "auth_method": "bearer",
            "description": "CI/CD automation for build, test, and deploy workflows",
            "sdk_package": "requests",
            "operations": ["trigger_pipeline", "get_run_status", "get_artifacts"],
        })

    # Reporting / BI
    if any(kw in combined for kw in ("reporting", "kpi", "analytics", "dashboard", "metrics")):
        _add("reporting_service", {
            "name": "Reporting / BI Service",
            "protocol": "rest",
            "auth_method": "bearer",
            "description": "Business intelligence and report generation",
            "operations": ["generate_report", "get_dashboard", "export_data"],
        })

    # Caching
    if any(kw in combined for kw in ("cache", "redis", "memcache", "session store")):
        _add("cache_store", {
            "name": "Cache Store (Redis)",
            "protocol": "redis",
            "auth_method": "password",
            "description": "In-memory cache and session store",
            "sdk_package": "redis",
            "operations": ["get", "set", "delete", "expire", "publish", "subscribe"],
        })

    # Search
    if any(kw in combined for kw in ("search", "elasticsearch", "opensearch", "full text")):
        _add("search_engine", {
            "name": "Search Engine (Elasticsearch / OpenSearch)",
            "protocol": "rest",
            "auth_method": "basic",
            "base_url": "https://{host}:9200",
            "description": "Full-text and vector search engine",
            "sdk_package": "elasticsearch",
            "operations": ["index", "search", "delete", "bulk"],
        })

    # AI / ML inference
    if any(kw in combined for kw in ("ai", "ml", "machine learning", "inference", "model", "classification", "extraction")):
        _add("ai_inference", {
            "name": "AI/ML Inference Service",
            "protocol": "rest",
            "auth_method": "api_key",
            "description": "AI model inference endpoint for classification, extraction, and generation",
            "operations": ["predict", "classify", "extract", "embed", "generate"],
        })

    # ERP / business system integration (when component is named "core business function" etc.)
    if any(kw in combined for kw in ("core business", "erp", "business logic", "integration point")):
        _add("erp_integration", {
            "name": "ERP / Core Business System",
            "protocol": "rest",
            "auth_method": "oauth2",
            "description": "Core ERP or business system integration for data synchronisation",
            "operations": ["sync_records", "get_entity", "create_entity", "update_entity"],
        })

    return results


def _pascal_case(name: str) -> str:
    """Convert a name to PascalCase for entity class names.

    Handles space-delimited, snake_case, kebab-case, AND existing CamelCase input.
    "CommentData" must stay "CommentData", not degrade to "Commentdata" — Python's
    str.capitalize() lowercases everything after the first char, so we must split at
    CamelCase boundaries first.
    Strips non-alphanumeric chars and prefixes 'Entity' if result starts with a digit.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9\s_\-]", "", name.strip())
    # Insert word boundaries at CamelCase transitions BEFORE splitting so that
    # "CommentData" → "Comment_Data" → ["Comment", "Data"] → "CommentData".
    sanitized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", sanitized)
    sanitized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", sanitized)
    parts = re.split(r"[\s_\-]+", sanitized)
    result = "".join(word.capitalize() for word in parts if word)
    if result and result[0].isdigit():
        result = "Entity" + result
    return result or "Unknown"


def _parse_json_field(value: Any) -> Any:
    """Parse a JSON string field, returning the parsed value or empty dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _infer_field_type(field_name: str, field_type_hint: str = "") -> str:
    """Infer genome field type from name and optional type hint."""
    hint = field_type_hint.lower() if field_type_hint else ""
    name = field_name.lower()

    if hint in ("integer", "int", "bigint", "smallint"):
        return "integer"
    if hint in ("float", "double", "real", "numeric"):
        return "float"
    if hint in ("decimal", "money", "currency"):
        return "decimal"
    if hint in ("boolean", "bool"):
        return "boolean"
    if hint in ("datetime", "timestamp", "timestamptz"):
        return "datetime"
    if hint in ("date",):
        return "date"
    if hint in ("text", "longtext", "clob"):
        return "text"
    if hint in ("json", "jsonb"):
        return "json"
    if hint in ("uuid",):
        return "uuid"

    # Infer from field name patterns
    if name == "id":
        return "uuid"  # G15: primary keys use UUID strings, not sequential integers
    if name.endswith("_id"):
        return "uuid"  # G15: FK references must match UUID PK type to avoid migration failures
    if name.endswith("_at") or name.endswith("_date"):
        return "datetime"
    if name.startswith("is_") or name.startswith("has_"):
        return "boolean"
    if name in ("email",):
        return "string"
    if name in ("amount", "price", "cost", "total", "balance"):
        return "decimal"
    if name in ("count", "quantity", "qty"):
        return "integer"

    return "string"


def _infer_field_format(field_name: str, field_type: str) -> Optional[str]:
    """Infer semantic format from field name."""
    name = field_name.lower()
    if "email" in name:
        return "email"
    if "url" in name or "link" in name or "href" in name:
        return "url"
    if "phone" in name or "mobile" in name:
        return "phone"
    if field_type == "uuid":
        return "uuid"
    if field_type == "datetime":
        return "date-time"
    if field_type == "date":
        return "date"
    return None


def compile_genome(
    solution_id: int,
    language: str = "python-fastapi",
    config: Optional[dict] = None,
) -> dict:
    """
    Compile an Architectural Genome from a solution's ArchiMate elements.

    Reads accepted ArchiMate elements linked to the solution via
    SolutionArchiMateElement junctions, groups them into modules,
    extracts entities/fields/rules/state-machines, and produces
    a genome dict conforming to architectural_genome_schema.json.

    Args:
        solution_id: Solution.id to compile from.
        language: Target language for code generation.
        config: Optional overrides (security, deployment, mobile settings).

    Returns:
        Genome dict ready for validation and code generation.
    """
    from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship
    from app.models.solution_models import Solution, SolutionArchiMateElement

    config = config or {}

    # Load solution
    solution = Solution.query.get(solution_id)
    if not solution:
        raise ValueError(f"Solution {solution_id} not found")

    # Load all junction records + their ArchiMate elements
    junctions = SolutionArchiMateElement.query.filter_by(
        solution_id=solution_id
    ).all()

    element_ids = [j.element_id for j in junctions if j.element_id]

    # Auto-promote: if no junctions exist but proposals do, promote them automatically.
    # This bridges the UX gap where users skip Steps 4-6 (proposal review) and go
    # straight to code generation. Proposals with promoted_element_id already have
    # a corresponding ArchiMateElement in the global catalog — we just need the junction.
    if not element_ids:
        from app.models.solution_blueprint_proposal import SolutionBlueprintProposal
        proposals = SolutionBlueprintProposal.query.filter(
            SolutionBlueprintProposal.solution_id == solution_id,
            SolutionBlueprintProposal.promoted_element_id.isnot(None),
        ).all()
        if proposals:
            logger.info(
                "Auto-promoting %d proposals to junctions for solution %d (user skipped review)",
                len(proposals), solution_id,
            )
            existing_ids = set()
            for p in proposals:
                if p.promoted_element_id in existing_ids:
                    continue
                existing_ids.add(p.promoted_element_id)
                db.session.add(SolutionArchiMateElement(
                    solution_id=solution_id,
                    element_id=p.promoted_element_id,
                    layer_type=p.archimate_type or "ApplicationComponent",
                    element_table="archimate_elements",
                    element_name=p.name,
                    element_role="auto_promoted",
                    is_new_element=True,
                ))
                # Also mark proposal as accepted
                if p.status in ("proposed", "pending"):
                    p.status = "accepted"
            db.session.flush()
            # Reload junctions after promotion
            junctions = SolutionArchiMateElement.query.filter_by(
                solution_id=solution_id
            ).all()
            element_ids = [j.element_id for j in junctions if j.element_id]

    if not element_ids:
        raise ValueError(f"Solution {solution_id} has no linked ArchiMate elements")

    # Query elements using column-safe strategy.
    # The migration freeze means ORM model columns may not exist in the DB.
    # We probe available columns first, then query only those that exist.
    from sqlalchemy import text as _text, inspect as _sa_inspect

    def _load_elements(eids):
        """Load ArchiMate elements with automatic column discovery.

        Probes the actual DB schema to determine which columns exist,
        then queries only those columns. This survives any ORM/DB drift.
        """
        # Discover actual columns in the table
        try:
            inspector = _sa_inspect(db.engine)
            db_columns = {c["name"] for c in inspector.get_columns("archimate_elements")}
        except Exception:
            db_columns = {"id", "name", "type", "layer", "description", "properties"}

        # Columns the compiler uses, in order of importance
        wanted = ["id", "name", "type", "layer", "description", "properties", "acm_properties"]
        available = [c for c in wanted if c in db_columns]

        cols = ", ".join(available)
        rows = db.session.execute(
            _text(f"SELECT {cols} FROM archimate_elements WHERE id = ANY(:ids)"),
            {"ids": eids},
        ).fetchall()

        result = {}
        for row in rows:
            class _Elem:
                pass
            e = _Elem()
            for i, col in enumerate(available):
                setattr(e, col, row[i])
            # Set defaults for columns not in the DB
            for col in wanted:
                if col not in db_columns:
                    setattr(e, col, None)
            result[e.id] = e
        return result

    elements = _load_elements(element_ids)

    # Build junction lookup: element_id → junction (for spec_data access)
    junction_map = {j.element_id: j for j in junctions if j.element_id}

    # Load relationships using the same column-safe strategy as elements
    def _load_relationships(src_ids, tgt_ids):
        try:
            inspector = _sa_inspect(db.engine)
            db_columns = {c["name"] for c in inspector.get_columns("archimate_relationships")}
        except Exception:
            db_columns = {"id", "source_id", "target_id", "type", "description"}

        wanted = ["id", "source_id", "target_id", "type", "description"]
        available = [c for c in wanted if c in db_columns]
        cols = ", ".join(available)
        rows = db.session.execute(
            _text(
                f"SELECT {cols} FROM archimate_relationships "
                f"WHERE source_id = ANY(:src_ids) AND target_id = ANY(:tgt_ids)"
            ),
            {"src_ids": src_ids, "tgt_ids": tgt_ids},
        ).fetchall()
        result = []
        for row in rows:
            class _Rel:
                pass
            r = _Rel()
            for i, col in enumerate(available):
                setattr(r, col, row[i])
            for col in wanted:
                if col not in db_columns:
                    setattr(r, col, None)
            result.append(r)
        return result

    relationships = _load_relationships(element_ids, element_ids)

    # Classify elements by type
    modules_elements = []      # ApplicationComponent etc. → become modules
    entity_elements = []       # DataObject etc. → become entities within modules
    rule_elements = []         # Constraint, Requirement → become business rules
    process_elements = []      # BusinessProcess → inform state machines
    capability_elements = []   # Capability → genome.capabilities
    other_elements = []        # Everything else

    for eid, elem in elements.items():
        # Convert PascalCase ("ApplicationComponent") and spaced ("Application Component")
        # to snake_case ("application_component") for _LAYER_MAP lookup
        _raw = (elem.type or "").replace(" ", "")
        _raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", _raw)
        _raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", _raw)
        etype = _raw.lower()
        if etype in _MODULE_TYPES:
            modules_elements.append(elem)
        elif etype in _ENTITY_TYPES:
            entity_elements.append(elem)
        elif etype in _RULE_TYPES:
            rule_elements.append(elem)
        elif etype in _PROCESS_TYPES:
            process_elements.append(elem)
        elif etype == "capability":
            capability_elements.append(elem)
        else:
            other_elements.append(elem)

    # Build relationship graph for module-entity assignment
    # Relationships tell us which data objects belong to which application components
    component_to_entities = _map_component_entities(
        modules_elements, entity_elements, relationships, elements
    )

    # Build modules
    genome_modules = {}
    archimate_sources = {}

    for comp in modules_elements:
        module_key = _snake_case(_strip_archimate_suffix(comp.name))
        entity_elems = component_to_entities.get(comp.id, [])

        # Track whether this module has real domain entities (DataObject/BusinessObject)
        # or only falls back to using the component itself as an entity.
        # Modules with only self-entity are infrastructure/service components — not user-facing CRUD.
        _has_domain_entities = bool(entity_elems)

        # If no entities assigned via relationships, create a default entity from the component itself
        if not entity_elems:
            entity_elems = [comp]

        # Build entity field definitions from spec_data and element properties
        module_entities = []
        module_fields = {}
        aggregate_root = None

        for entity_elem in entity_elems:
            entity_name = _pascal_case(_strip_archimate_suffix(entity_elem.name))
            module_entities.append(entity_name)
            if aggregate_root is None:
                aggregate_root = entity_name

            # Extract fields from spec_data on the junction
            junction = junction_map.get(entity_elem.id)
            spec_data = _parse_json_field(junction.spec_data if junction else None)
            elem_props = _parse_json_field(entity_elem.properties)

            fields = _extract_fields(entity_elem, spec_data, elem_props)
            if fields:
                module_fields[entity_name] = fields

            archimate_sources[f"modules.{module_key}.{entity_name}"] = entity_elem.id

        # Infer FK fields from relationships between entities in this module.
        # If Entity A → Entity B via a composition/association, A gets a b_id FK.
        _entity_id_map = {e.id: _pascal_case(_strip_archimate_suffix(e.name)) for e in entity_elems}
        for rel in relationships:
            src_name = _entity_id_map.get(rel.source_id)
            tgt_name = _entity_id_map.get(rel.target_id)
            if src_name and tgt_name and src_name != tgt_name:
                fk_field_name = _snake_case(tgt_name) + "_id"
                src_fields = module_fields.get(src_name, [])
                if not any(f.get("name") == fk_field_name for f in src_fields):
                    src_fields.append({
                        "name": fk_field_name,
                        "type": "string",
                        "max_length": 36,
                        "foreign_key": f"{_snake_case(tgt_name)}s.id",
                        "index": True,
                    })
                    if src_name not in module_fields:
                        module_fields[src_name] = src_fields

        # Extract state machine from related business processes
        state_machine = _extract_state_machine(
            comp, process_elements, relationships, elements
        )

        # Extract operations from element properties and spec_data
        junction = junction_map.get(comp.id)
        spec_data = _parse_json_field(junction.spec_data if junction else None)
        operations = _extract_operations(comp, spec_data, module_entities)

        # Extract sensitive fields from ACM properties
        sensitive_fields = _extract_sensitive_fields(entity_elems, junction_map)

        # Build views from entity fields
        views = _build_default_views(module_fields, aggregate_root, state_machine)

        # Compute archimate_type (snake_case) for the component
        _comp_raw = (comp.type or "").replace(" ", "")
        _comp_raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", _comp_raw)
        _comp_raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", _comp_raw)
        _comp_etype = _comp_raw.lower() or "application_component"

        # Modules with real linked domain entities (DataObject/BusinessObject) are user-facing;
        # modules that fall back to self-entity are infrastructure/service components.
        # Pipeline modules are always user-facing — they ARE the product's AI features.
        _is_pipeline_module = bool(
            spec_data.get("pipeline_pattern") or spec_data.get("pipeline_steps")
        )
        _module_user_facing = _has_domain_entities or _is_pipeline_module

        module_def = {
            "aggregate_root": aggregate_root or _pascal_case(_strip_archimate_suffix(comp.name)),
            "display_name": " ".join(w if w.isupper() and len(w) > 1 else w.capitalize() for w in _strip_archimate_suffix(comp.name).split()),
            "entities": module_entities,
            "archimate_element_ids": [comp.id] + [e.id for e in entity_elems if e.id != comp.id],
            "archimate_type": _comp_etype,
            "user_facing": _module_user_facing,
        }

        if comp.description:
            module_def["_rationale"] = comp.description

        if module_fields:
            module_def["fields"] = module_fields
        if operations:
            module_def["operations"] = operations
        if state_machine:
            module_def["state_machine"] = state_machine
        if views:
            module_def["views"] = views
        if sensitive_fields:
            module_def["sensitive_fields"] = sensitive_fields

        # Detect vendor-origin: check if the component's spec_data came from vendor_template
        _comp_junction = junction_map.get(comp.id)
        _comp_spec = _parse_json_field(_comp_junction.spec_data if _comp_junction else None)
        if _comp_spec.get("source") == "vendor_template":
            module_def["_vendor_origin"] = True
            module_def["_vendor_version"] = _comp_spec.get("version", "")

        # G6: propagate build_or_buy decision from wizard spec_data into module_def so
        # genome_to_bundle can route buy-decision modules through the vendor SDK path.
        _build_or_buy = _comp_spec.get("build_or_buy")
        if _build_or_buy:
            module_def["build_or_buy"] = _build_or_buy

        # G5: when multi_tenancy=True, inject tenant_id on every entity so the
        # generated SQLAlchemy models and Alembic migration enforce row-level isolation.
        # Without this, multi_tenancy:true in the genome YAML is decorative only.
        # Note: module_fields values are lists-of-dicts (each dict has a "name" key),
        # not dicts keyed by field name — use list semantics throughout.
        if config.get("multi_tenancy"):
            for _entity_name in module_entities:
                _entity_fields = module_fields.get(_entity_name, [])
                if not any(isinstance(f, dict) and f.get("name") == "tenant_id"
                           for f in _entity_fields):
                    _entity_fields.append({
                        "name": "tenant_id",
                        "type": "uuid",
                        "required": True,
                        "index": True,
                    })
                    module_fields[_entity_name] = _entity_fields
            if module_fields:
                module_def["fields"] = module_fields

        genome_modules[module_key] = module_def
        archimate_sources[f"modules.{module_key}"] = comp.id

    # Handle orphan entities (data objects not linked to any component)
    assigned_entity_ids = set()
    for entity_list in component_to_entities.values():
        assigned_entity_ids.update(e.id for e in entity_list)

    for entity_elem in entity_elements:
        if entity_elem.id not in assigned_entity_ids:
            module_key = _snake_case(entity_elem.name)
            entity_name = _pascal_case(entity_elem.name)

            junction = junction_map.get(entity_elem.id)
            spec_data = _parse_json_field(junction.spec_data if junction else None)
            elem_props = _parse_json_field(entity_elem.properties)
            fields = _extract_fields(entity_elem, spec_data, elem_props)

            # Compute archimate_type for orphan entity element
            _oe_raw = (entity_elem.type or "").replace(" ", "")
            _oe_raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", _oe_raw)
            _oe_raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", _oe_raw)
            _oe_etype = _oe_raw.lower() or "data_object"
            module_def = {
                "aggregate_root": entity_name,
                "display_name": " ".join(w if w.isupper() and len(w) > 1 else w.capitalize() for w in entity_elem.name.split()),
                "entities": [entity_name],
                "archimate_element_ids": [entity_elem.id],
                "archimate_type": _oe_etype,
                "user_facing": True,  # Orphan data/business objects are always user-facing
            }
            if fields:
                module_def["fields"] = {entity_name: fields}
            module_def["views"] = _build_default_views(
                module_def.get("fields", {}), entity_name, None
            )

            genome_modules[module_key] = module_def
            archimate_sources[f"modules.{module_key}"] = entity_elem.id

    # D-PASS4-7 / G10: Auto-promoted genomes compile to skeleton modules — no fields, no
    # state machines. Quality score ~5–15/100 → quality gate blocks wizard users.
    # Post-processing pass: any module whose aggregate root has zero meaningful fields
    # gets domain-convention defaults inferred from its name, so the generated code has
    # a minimal but functional schema instead of empty models.
    _DEFAULT_FIELD_SETS = {
        "user": [
            {"name": "email", "type": "string", "required": True, "index": True},
            {"name": "name", "type": "string", "required": True},
            {"name": "role", "type": "string", "required": False},
            {"name": "is_active", "type": "boolean", "required": False},
            {"name": "last_login_at", "type": "datetime", "required": False},
        ],
        "order": [
            {"name": "order_number", "type": "string", "required": True},
            {"name": "status", "type": "string", "required": True},
            {"name": "total_amount", "type": "float", "required": False},
            {"name": "currency", "type": "string", "required": False},
        ],
        "product": [
            {"name": "sku", "type": "string", "required": True, "index": True},
            {"name": "name", "type": "string", "required": True},
            {"name": "description", "type": "text", "required": False},
            {"name": "price", "type": "float", "required": False},
            {"name": "is_active", "type": "boolean", "required": False},
        ],
        "customer": [
            {"name": "full_name", "type": "string", "required": True},
            {"name": "email", "type": "string", "required": True, "index": True},
            {"name": "phone", "type": "string", "required": False},
            {"name": "tier", "type": "string", "required": False},
        ],
        "project": [
            {"name": "name", "type": "string", "required": True},
            {"name": "status", "type": "string", "required": True},
            {"name": "start_date", "type": "date", "required": False},
            {"name": "end_date", "type": "date", "required": False},
            {"name": "owner_id", "type": "uuid", "required": False, "foreign_key": True},
        ],
        "task": [
            {"name": "title", "type": "string", "required": True},
            {"name": "description", "type": "text", "required": False},
            {"name": "status", "type": "string", "required": True},
            {"name": "priority", "type": "string", "required": False},
            {"name": "due_date", "type": "datetime", "required": False},
            {"name": "assignee_id", "type": "uuid", "required": False, "foreign_key": True},
        ],
        "invoice": [
            {"name": "invoice_number", "type": "string", "required": True},
            {"name": "status", "type": "string", "required": True},
            {"name": "amount", "type": "float", "required": True},
            {"name": "due_date", "type": "date", "required": False},
            {"name": "customer_id", "type": "uuid", "required": False, "foreign_key": True},
        ],
        "report": [
            {"name": "title", "type": "string", "required": True},
            {"name": "type", "type": "string", "required": False},
            {"name": "status", "type": "string", "required": True},
            {"name": "generated_at", "type": "datetime", "required": False},
        ],
        "notification": [
            {"name": "title", "type": "string", "required": True},
            {"name": "message", "type": "text", "required": False},
            {"name": "is_read", "type": "boolean", "required": False},
            {"name": "recipient_id", "type": "uuid", "required": False, "foreign_key": True},
        ],
    }
    _GENERIC_FIELDS = [
        {"name": "name", "type": "string", "required": True},
        {"name": "description", "type": "text", "required": False},
        {"name": "status", "type": "string", "required": False},
        {"name": "is_active", "type": "boolean", "required": False},
        {"name": "created_by_id", "type": "uuid", "required": False, "foreign_key": True},
    ]
    _AUDIT_FIELDS = [
        {"name": "created_at", "type": "datetime", "required": False, "_injected": "audit"},
        {"name": "updated_at", "type": "datetime", "required": False, "_injected": "audit"},
    ]
    for _mod_key, _mod_def in genome_modules.items():
        _root = _mod_def.get("aggregate_root", "")
        _existing_fields = _mod_def.get("fields", {})
        _root_fields = _existing_fields.get(_root, [])
        # A meaningful field set has at least 2 non-audit, non-id, non-injected fields
        _meaningful = [
            f for f in _root_fields
            if f.get("name") not in ("id", "created_at", "updated_at", "tenant_id")
            and not f.get("_injected")
        ]
        if len(_meaningful) >= 2:
            continue  # already has real fields — don't overwrite architect's intent
        if _mod_def.get("build_or_buy") in ("buy", "vendor"):
            continue  # vendor modules don't need a DB schema
        _root_lower = _root.lower()
        _inferred_fields = None
        for _pattern, _field_set in _DEFAULT_FIELD_SETS.items():
            if _pattern in _root_lower:
                _inferred_fields = list(_field_set)
                break
        if _inferred_fields is None:
            _inferred_fields = list(_GENERIC_FIELDS)
        # Append audit fields if not already present
        _existing_names = {f.get("name") for f in _root_fields}
        for _af in _AUDIT_FIELDS:
            if _af["name"] not in _existing_names:
                _inferred_fields.append(_af)
        # Merge — don't replace any existing field the architect explicitly added
        _merged = {f["name"]: f for f in _root_fields}
        for _f in _inferred_fields:
            if _f["name"] not in _merged:
                _merged[_f["name"]] = dict(_f, **{"_inferred": True})
        _mod_def.setdefault("fields", {})[_root] = list(_merged.values())
        _mod_def["_auto_enriched"] = "skeleton_defaults"
        logger.debug("Auto-enriched skeleton module %s with %d inferred fields", _mod_key, len(_merged))

    # Build capabilities list
    capabilities = []
    for cap_elem in capability_elements:
        cap_props = _parse_json_field(cap_elem.properties)
        acm_props = _parse_json_field(getattr(cap_elem, "acm_properties", None))
        cap = {
            "id": f"cap_{cap_elem.id}",
            "name": cap_elem.name,
            "archimate_element_id": cap_elem.id,
        }
        if cap_elem.description:
            cap["description"] = cap_elem.description
        if acm_props.get("acm_domain"):
            cap["acm_domain"] = acm_props["acm_domain"]
        maturity_current = cap_props.get("maturity_current") or cap_props.get("current_maturity")
        maturity_target = cap_props.get("maturity_target") or cap_props.get("target_maturity")
        if maturity_current is not None or maturity_target is not None:
            cap["maturity"] = {}
            if maturity_current is not None:
                cap["maturity"]["current"] = int(maturity_current)
            if maturity_target is not None:
                cap["maturity"]["target"] = int(maturity_target)
        capabilities.append(cap)

    # Build problem section from solution metadata
    problem = {"statement": solution.description or solution.name or "No problem statement defined"}
    if hasattr(solution, "problem_clarification") and solution.problem_clarification:
        clarification = _parse_json_field(solution.problem_clarification)
        if isinstance(clarification, dict):
            if clarification.get("enriched_brief"):
                problem["statement"] = clarification["enriched_brief"]
            if clarification.get("success_metrics"):
                problem["success_metrics"] = clarification["success_metrics"]
            if clarification.get("constraints"):
                problem["constraints"] = clarification["constraints"]
        elif isinstance(clarification, str):
            problem["statement"] = clarification
    if solution.business_domain:
        problem["business_domain"] = solution.business_domain

    journey_state = _parse_json_field(getattr(solution, "journey_state", None))
    step1 = journey_state.get("step1", {})
    if step1.get("enriched_brief"):
        problem["statement"] = step1["enriched_brief"]

    # Capture enriched_brief for deterministic vendor inference later.
    # PDF-upload wizard stores this in journey_state["enriched_brief"] (top-level),
    # not in step1 — check both locations.
    _enriched_brief = (
        journey_state.get("enriched_brief")
        or step1.get("enriched_brief")
        or problem.get("statement")
        or ""
    )


    # The architect provides compliance, integration, scaling, and tech stack
    # data in Step 1 that gets saved to SolutionProblemDefinition. The compiler
    # previously ignored all of it and used hardcoded defaults.
    _problem_def = None
    _compliance = []
    _integrations_from_step1 = []
    _tech_stack = []
    _scaling = {}
    try:
        from app.models.solution_architect_models import (
            SolutionAnalysisSession,
            SolutionProblemDefinition,
            SolutionRequirement,
            RequirementType,
        )
        _session = SolutionAnalysisSession.query.filter(
            SolutionAnalysisSession.name.like(f"%Solution {solution_id}%")
        ).first()
        # G18: LIKE lookup fails for custom-named solutions. Fall back to FK join via
        # SolutionRequirement → SolutionProblemDefinition → SolutionAnalysisSession.
        if not _session:
            try:
                _req = SolutionRequirement.query.filter_by(solution_id=solution_id).first()
                if _req and _req.problem_id:
                    from app.models.solution_architect_models import SolutionProblemDefinition as _SPD
                    _prob = _SPD.query.get(_req.problem_id)
                    if _prob:
                        _session = SolutionAnalysisSession.query.get(_prob.session_id)
            except Exception as _fk_err:
                logger.debug("FK-based session lookup failed: %s", _fk_err)
        if _session:
            _problem_def = _session.problem_definition
        if _problem_def:
            _compliance = _problem_def.compliance_requirements or []
            _integrations_from_step1 = _problem_def.integration_requirements or []
            _tech_stack = _problem_def.existing_technology_stack or []
            if _problem_def.user_count:
                _scaling["user_count"] = _problem_def.user_count
            if _problem_def.transaction_volume:
                _scaling["transaction_volume"] = _problem_def.transaction_volume
            if _problem_def.data_volume_gb:
                _scaling["data_volume_gb"] = _problem_def.data_volume_gb
            if _problem_def.organization_size:
                _scaling["organization_size"] = _problem_def.organization_size

        # Read NFR requirements linked to this solution
        _nfr_requirements = SolutionRequirement.query.filter_by(
            solution_id=solution_id,
        ).all()
        if not _nfr_requirements and _problem_def:
            _nfr_requirements = SolutionRequirement.query.filter_by(
                problem_id=_problem_def.id,
            ).all()
    except Exception as _step1_err:
        logger.debug("Could not read Step 1 data: %s", _step1_err)
        _nfr_requirements = []

    # ── Infer capabilities from Step 1 data ───────────────────────────────
    # Compliance frameworks → security flags
    _compliance_lower = [c.lower() if isinstance(c, str) else "" for c in _compliance]
    _needs_encryption = any(f in c for c in _compliance_lower for f in ("gdpr", "hipaa", "pci", "sox", "iso 27001"))
    _needs_audit = any(f in c for c in _compliance_lower for f in ("gdpr", "hipaa", "sox", "iso", "audit"))
    _needs_mfa = any(f in c for c in _compliance_lower for f in ("hipaa", "pci", "nist", "iso 27001"))

    # Integration systems → integration stubs
    _integration_keywords = {
        "sap": {"protocol": "rest", "auth": "oauth2", "base_url": "https://api.sap.com"},
        "salesforce": {"protocol": "rest", "auth": "oauth2", "base_url": "https://login.salesforce.com"},
        "servicenow": {"protocol": "rest", "auth": "basic", "base_url": "https://instance.service-now.com"},
        "jira": {"protocol": "rest", "auth": "bearer", "base_url": "https://jira.atlassian.net"},
        "slack": {"protocol": "rest", "auth": "bearer", "base_url": "https://slack.com/api"},
        "kafka": {"protocol": "async", "auth": "none"},
        "rabbitmq": {"protocol": "async", "auth": "basic"},
        "email": {"protocol": "smtp", "auth": "basic"},
    }

    # Tech stack → infrastructure overrides
    _stack_lower = [t.lower() if isinstance(t, str) else "" for t in _tech_stack]
    _inferred_db = "postgresql"  # default
    for t in _stack_lower:
        if "mysql" in t:
            _inferred_db = "mysql"
        elif "mongodb" in t or "mongo" in t:
            _inferred_db = "mongodb"
        elif "oracle" in t:
            _inferred_db = "oracle"
    _inferred_cache = "none"
    for t in _stack_lower:
        if "redis" in t:
            _inferred_cache = "redis"
        elif "memcache" in t:
            _inferred_cache = "memcached"
    _inferred_search = "none"
    for t in _stack_lower:
        if "elastic" in t:
            _inferred_search = "elasticsearch"
    _inferred_bus = "none"
    for t in _stack_lower:
        if "kafka" in t:
            _inferred_bus = "kafka"
        elif "rabbit" in t or "amqp" in t:
            _inferred_bus = "rabbitmq"

    # Scaling → rate limiting + multi-tenancy inference
    _high_scale = _scaling.get("user_count", 0) > 1000 or _scaling.get("transaction_volume", 0) > 10000
    _is_multi_org = _scaling.get("organization_size") in ("enterprise", "midmarket")

    # NFR requirements → genome flags
    _nfr_flags_from_reqs = set()
    for req in (_nfr_requirements or []):
        name_lower = (req.name or "").lower()
        desc_lower = (req.description or "").lower()
        combined = name_lower + " " + desc_lower
        if "audit" in combined:
            _nfr_flags_from_reqs.add("audit_trail")
        if "multi-tenant" in combined or "multi tenant" in combined or "tenancy" in combined:
            _nfr_flags_from_reqs.add("multi_tenancy")
        if "rate limit" in combined or "throttl" in combined:
            _nfr_flags_from_reqs.add("rate_limiting")
        if "encrypt" in combined:
            _nfr_flags_from_reqs.add("encryption_at_rest")
        if "api key" in combined:
            _nfr_flags_from_reqs.add("api_keys")
        if "mfa" in combined or "multi-factor" in combined or "two-factor" in combined or "2fa" in combined:
            _nfr_flags_from_reqs.add("mfa")
        if "webhook" in combined or "event" in combined:
            _nfr_flags_from_reqs.add("webhooks")
        if "search" in combined or "full-text" in combined:
            _nfr_flags_from_reqs.add("search")
        if "file" in combined and ("upload" in combined or "storage" in combined or "attachment" in combined):
            _nfr_flags_from_reqs.add("file_storage")
        if "email" in combined or "notification" in combined:
            _nfr_flags_from_reqs.add("notifications")
        if "export" in combined or "csv" in combined or "pdf" in combined:
            _nfr_flags_from_reqs.add("export")

    # ── Apply universal mandatory baseline (before domain augmentation) ─────────
    _nfr_flags_from_reqs.update(_UNIVERSAL_BASELINE)

    # ── Infer capabilities from domain + entity names ────────────────────────
    _domain = (solution.business_domain or "").lower()
    for domain_key, domain_caps in _DOMAIN_CAPABILITY_MAP.items():
        if domain_key in _domain:
            _nfr_flags_from_reqs.update(domain_caps)

    for module_key, module_def in genome_modules.items():
        for entity_name in module_def.get("entities", []):
            entity_lower = entity_name.lower()
            for pattern, entity_caps in _ENTITY_CAPABILITY_MAP.items():
                if pattern in entity_lower:
                    _nfr_flags_from_reqs.update(entity_caps)

    # ── Read journey_state capabilities if architect explicitly selected them ─
    _journey_caps = journey_state.get("codegenCaps", {}) or journey_state.get("capabilities", {})
    _vendor_selections = {}  # capability → vendor_key (e.g. "notifications" → "sendgrid")
    if isinstance(_journey_caps, dict):
        for cap_key, cap_val in _journey_caps.items():
            if cap_key.startswith("vendor_") and cap_val:
                # vendor_notifications = "sendgrid" → route to vendor SDK
                real_cap = cap_key[len("vendor_"):]
                _vendor_selections[real_cap] = cap_val
            elif cap_key == "auth_type":
                continue  # handled separately
            elif cap_val:  # truthy = architect enabled this capability
                _nfr_flags_from_reqs.add(cap_key)

    # Build infrastructure section (Step 1 data overrides defaults)
    infrastructure = {
        "database": config.get("database", _inferred_db),
        "auth": config.get("auth", "jwt_local"),
        "observability": config.get("observability", "opentelemetry"),
        "cache": config.get("cache", _inferred_cache),
        "search": config.get("search", _inferred_search),
        "event_bus": config.get("event_bus", _inferred_bus),
    }
    if _scaling:
        infrastructure["scaling"] = _scaling

    # Build security section (Step 1 compliance + NFRs override defaults)
    security = {
        "mfa": config.get("mfa", "required_for_admin" if (_needs_mfa or "mfa" in _nfr_flags_from_reqs) else "none"),
        "api_keys": config.get("api_keys", "api_keys" in _nfr_flags_from_reqs),
        "encryption_at_rest": config.get("encryption_at_rest", _needs_encryption or "encryption_at_rest" in _nfr_flags_from_reqs),
        "multi_tenancy": config.get("multi_tenancy", _is_multi_org or "multi_tenancy" in _nfr_flags_from_reqs),
    }
    if _high_scale or "rate_limiting" in _nfr_flags_from_reqs or config.get("rate_limiting"):
        security["rate_limiting"] = config.get("rate_limiting") or {"default": "100/min", "authenticated": "1000/min"}
    if _compliance:
        security["compliance"] = _compliance

    # Build deployment section
    deployment = {
        "target": config.get("deployment_target", "docker_compose"),
        "environments": config.get("environments", ["staging", "production"]),
    }
    ci_cd_provider = config.get("ci_cd_provider", "github_actions")
    if ci_cd_provider != "none":
        deployment["ci_cd"] = {
            "provider": ci_cd_provider,
            "registry": config.get("ci_cd_registry", "ghcr"),
        }

    # Build identity provider section
    idp = {}
    idp_config = config.get("identity_provider", {})
    if idp_config:
        idp = idp_config
    elif infrastructure["auth"] == "keycloak":
        idp = {
            "type": "oidc",
            "preset": "keycloak",
            "roles": config.get("roles", ["admin", "user", "viewer"]),
        }
    else:
        idp = {
            "type": "jwt-local",
            "roles": config.get("roles", ["admin", "user", "viewer"]),
        }

    # ── Build integrations from Step 1 data ─────────────────────────────────
    integrations = {}
    for sys_entry in _integrations_from_step1:
        # Step 1 picker stores {id, name} dicts; also accept plain strings
        if isinstance(sys_entry, dict):
            sys_name = sys_entry.get("name", "")
        elif isinstance(sys_entry, str):
            sys_name = sys_entry
        else:
            continue
        if not sys_name:
            continue
        sys_lower = sys_name.lower().strip()
        matched = None
        for keyword, template in _integration_keywords.items():
            if keyword in sys_lower:
                matched = template
                break
        integ_key = re.sub(r"[^a-z0-9]", "_", sys_lower).strip("_")
        integrations[integ_key] = {
            "name": sys_name,
            "protocol": (matched or {}).get("protocol", "rest"),
            "auth_method": (matched or {}).get("auth", "bearer"),
            "base_url": (matched or {}).get("base_url", f"https://api.{integ_key}.example.com"),
            "description": f"Integration with {sys_name} (from Step 1 requirements)",
        }

    # ── Extract vendor-origin modules → integrations ─────────────────────
    # Modules marked _vendor_origin should become typed integration clients,
    # not CRUD entities. Move them from genome_modules to integrations.
    _vendor_modules_to_remove = []
    for mod_key, mod_def in genome_modules.items():
        if mod_def.get("_vendor_origin"):
            vendor_name = mod_def.get("aggregate_root", mod_key)
            # Check if we have SDK metadata for this vendor
            _sdk = _VENDOR_SDK_MAP.get(mod_key) or _VENDOR_SDK_MAP.get(vendor_name.lower())
            if _sdk:
                integrations[mod_key] = {
                    "name": vendor_name,
                    "protocol": _sdk.get("protocol", "rest"),
                    "auth_method": _sdk.get("auth_method", "bearer"),
                    "base_url": _sdk.get("base_url", ""),
                    "sdk_package": _sdk.get("sdk_package", ""),
                    "operations": _sdk.get("operations", []),
                    "description": f"Integration with {vendor_name} (from vendor template)",
                    "_vendor_origin": True,
                }
            else:
                integrations[mod_key] = {
                    "name": vendor_name,
                    "protocol": "rest",
                    "auth_method": "bearer",
                    "base_url": f"https://api.{mod_key.replace('_', '-')}.example.com",
                    "description": f"Integration with {vendor_name} (vendor-linked)",
                    "_vendor_origin": True,
                }
            _vendor_modules_to_remove.append(mod_key)
    for mod_key in _vendor_modules_to_remove:
        del genome_modules[mod_key]

    # ── Add architect-selected vendor integrations from Step 3 panel ──────
    for cap_name, vendor_key in _vendor_selections.items():
        if vendor_key in _VENDOR_SDK_MAP and vendor_key not in integrations:
            sdk = _VENDOR_SDK_MAP[vendor_key]
            integrations[vendor_key] = {
                "name": vendor_key.replace("_", " ").title(),
                "protocol": sdk.get("protocol", "rest"),
                "auth_method": sdk.get("auth_method", "bearer"),
                "base_url": sdk.get("base_url", ""),
                "sdk_package": sdk.get("sdk_package", ""),
                "operations": sdk.get("operations", []),
                "description": f"{vendor_key.replace('_', ' ').title()} — selected for {cap_name} capability",
                "_vendor_origin": True,
                "_capability": cap_name,
            }

    # ── Deterministic vendor inference from enriched_brief / description ──
    # PDF-upload solutions skip the Step 1 form entirely, so _integrations_from_step1
    # is always empty and _vendor_selections is empty.  Instead, scan the enriched_brief
    # and solution description text for vendor product names and infer integrations.
    if _enriched_brief or solution.description:
        _inferred = _infer_integrations_from_text(
            (_enriched_brief or "") + " " + (solution.description or ""),
            existing_keys=set(integrations.keys()),
        )
        integrations.update(_inferred)
        if _inferred:
            logger.info(
                "Inferred %d vendor integrations from text for solution %d: %s",
                len(_inferred), solution_id, list(_inferred.keys()),
            )

    # ── Component-name-based integration inference ────────────────────────
    # Element names like "Message broker", "API gateway", "Identity and access
    # management" map directly to infrastructure integrations regardless of which
    # specific vendor product is chosen.  This covers the PDF-upload path where no
    # vendor names appear in the free text at all.
    _all_element_names = list(genome_modules.keys()) + [
        m.get("display_name", "") for m in genome_modules.values()
    ]
    _comp_inferred = _infer_integrations_from_components(
        _all_element_names, existing_keys=set(integrations.keys())
    )
    integrations.update(_comp_inferred)
    if _comp_inferred:
        logger.info(
            "Inferred %d infra integrations from component names for solution %d: %s",
            len(_comp_inferred), solution_id, list(_comp_inferred.keys()),
        )

    # ── Build webhooks config from NFR flags ──────────────────────────────
    webhooks = {}
    if "webhooks" in _nfr_flags_from_reqs or config.get("webhooks_enabled"):
        webhooks = {
            "enabled": True,
            "delivery": {
                "retry_attempts": 3,
                "retry_backoff": "exponential",
            },
            "subscriptions": [],
        }

    # ── BFG/SFG Behavioral Enrichment ──────────────────────────────────────
    # If the solution has uploaded documents or a detailed problem statement,
    # extract behavioral pipelines (BFG) and screen flows (SFG) and use them
    # to upgrade matching modules from CRUD to pipeline services.
    _behavioral_ctx = None
    if config.get("use_behavioral", True):
        try:
            from app.modules.codegen.services.behavioral_extractor import BehavioralExtractorService
            from app.modules.codegen.services.pattern_library import match_module_to_pipeline, match_pipeline_to_pattern
            _behavioral_ctx = BehavioralExtractorService().extract(solution_id)

            if _behavioral_ctx and _behavioral_ctx.pipelines:
                logger.info(
                    "BFG extracted %d pipelines for solution %d",
                    len(_behavioral_ctx.pipelines), solution_id,
                )

                # Enrich modules: if a module matches a BFG pipeline step,
                # mark it as a pipeline module with behavioral metadata
                for mod_key, mod_def in genome_modules.items():
                    matched = match_module_to_pipeline(
                        mod_def.get("display_name", mod_key),
                        mod_def.get("_rationale", ""),
                        [_pipeline_to_dict(p) for p in _behavioral_ctx.pipelines],
                    )
                    if matched:
                        mod_def["module_type"] = "pipeline"
                        # Find which pattern this pipeline matches
                        pattern_id, score = match_pipeline_to_pattern(matched)
                        if pattern_id:
                            mod_def["pipeline_pattern"] = pattern_id
                            mod_def["pipeline_pattern_score"] = round(score, 3)
                        mod_def["pipeline"] = matched
                        logger.info(
                            "Module '%s' matched to pipeline '%s' (pattern: %s, score: %.2f)",
                            mod_key, matched.get("name"), pattern_id, score,
                        )

                # Fallback: create pipeline modules from BFG pipelines that
                # no ArchiMate module claimed.  This handles the common case
                # where the ArchiMate elements describe abstract components
                # (e.g. "Web Application") but the BFG describes concrete
                # domain pipelines (e.g. "quote_ingestion").
                _matched_pipelines = set()
                for _md in genome_modules.values():
                    _mp = _md.get("pipeline", {})
                    if _mp:
                        _matched_pipelines.add(_mp.get("name", ""))

                for pipeline in _behavioral_ctx.pipelines:
                    p_dict = _pipeline_to_dict(pipeline)
                    p_name = p_dict.get("name", "unnamed_pipeline")
                    if p_name in _matched_pipelines:
                        continue  # already claimed by an existing module

                    mod_key = _snake_case(p_name)
                    entity_name = _pascal_case(p_name)
                    pattern_id, score = match_pipeline_to_pattern(p_dict)

                    # Pipeline job-tracking fields (not step names as columns)
                    job_fields = [
                        {"name": "status", "type": "string", "max_length": 20,
                         "default_value": "pending"},
                        {"name": "input_data", "type": "json"},
                        {"name": "output_data", "type": "json", "required": False},
                        {"name": "error_message", "type": "text", "required": False},
                        {"name": "started_at", "type": "datetime", "required": False},
                        {"name": "completed_at", "type": "datetime", "required": False},
                        {"name": "steps_completed", "type": "json", "required": False},
                    ]

                    new_mod = {
                        "aggregate_root": entity_name,
                        "display_name": p_name.replace("_", " ").title(),
                        "entities": [entity_name],
                        "module_type": "pipeline",
                        "pipeline": p_dict,
                        "user_facing": True,
                        "_rationale": "Auto-created from BFG pipeline extraction",
                    }
                    if pattern_id:
                        new_mod["pipeline_pattern"] = pattern_id
                        new_mod["pipeline_pattern_score"] = round(score, 3)
                    new_mod["fields"] = {entity_name: job_fields}
                    new_mod["views"] = _build_default_views(
                        new_mod.get("fields", {}), entity_name, None
                    )

                    genome_modules[mod_key] = new_mod
                    logger.info(
                        "Created pipeline module '%s' from BFG (pattern: %s, score: %.2f)",
                        mod_key, pattern_id, score,
                    )

                # Add pipeline-specific integrations
                for integ in _behavioral_ctx.integrations:
                    int_key = integ.name.lower().replace(" ", "_").replace("-", "_")
                    if int_key not in integrations:
                        integrations[int_key] = {
                            "name": integ.name,
                            "service": integ.service,
                            "protocol": integ.protocol,
                            "auth_method": integ.auth_method,
                            "data_format": integ.data_format,
                            "base_url": integ.base_url,
                            "operations": integ.operations,
                            "description": f"Extracted from requirements via BFG",
                        }

            if _behavioral_ctx and _behavioral_ctx.screens:
                logger.info(
                    "SFG extracted %d screens for solution %d",
                    len(_behavioral_ctx.screens), solution_id,
                )
        except Exception as e:
            logger.warning("Behavioral extraction failed (non-fatal): %s", e)
            _behavioral_ctx = None

    # Assemble genome
    genome = {
        "genome_version": GENOME_VERSION,
        "solution_id": solution_id,
        "solution_name": solution.name or f"Solution {solution_id}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "language": language,
        "problem": problem,
        "modules": genome_modules,
        "infrastructure": infrastructure,
        "security": security,
        "deployment": deployment,
        "identity_provider": idp,
        "_archimate_sources": archimate_sources,
    }

    # Add behavioral context to genome for downstream consumption
    if _behavioral_ctx:
        genome["_behavioral"] = {
            "pipelines": [_pipeline_to_dict(p) for p in _behavioral_ctx.pipelines],
            "screens": [_screen_to_dict(s) for s in _behavioral_ctx.screens],
            "data_contracts": [
                {"name": dc.name, "fields": dc.fields}
                for dc in _behavioral_ctx.data_contracts
            ],
            "quality_constraints": _behavioral_ctx.quality_constraints,
        }

    if capabilities:
        genome["capabilities"] = capabilities
    if integrations:
        genome["integrations"] = integrations
    if webhooks:
        genome["webhooks"] = webhooks

    # Inferred capability flags — these drive conditional template rendering
    genome["_inferred_capabilities"] = sorted(_nfr_flags_from_reqs)

    # Optional sections from config
    if config.get("mobile"):
        genome["mobile"] = config["mobile"]
    if config.get("compliance"):
        genome["compliance"] = config["compliance"]

    # ── FK cleanup: strip foreign_key references to entities that don't exist ──
    # The field inference engine sometimes generates FKs to 'users', 'organizations',
    # etc. that aren't defined as genome modules. Remove these to pass validation.
    # Build allowlist in all naming conventions (PascalCase, snake_case, plural).
    _all_entities = set()
    for _md in genome_modules.values():
        for _ent in _md.get("entities", []):
            _all_entities.add(_ent)                        # PascalCase: Customer
            _sc = _snake_case(_ent)
            _all_entities.add(_sc)                         # snake_case: customer
            _all_entities.add(_sc + "s")                   # plural:     customers
            _all_entities.add(_sc + "es")                  # plural:     addresses
    for _md in genome_modules.values():
        for _ename, _fields in _md.get("fields", {}).items():
            for _f in _fields:
                _fk = _f.get("foreign_key")
                if _fk:
                    _ref = _fk.split(".")[0]
                    if _ref not in _all_entities:
                        _f.pop("foreign_key", None)

    # ── Strip internal-only metadata keys from field dicts ───────────────────
    # _injected and _inferred are compilation markers used during this function
    # to distinguish auto-added fields from architect-specified ones.  They are
    # NOT part of the FieldDef schema (additionalProperties: false) and will cause
    # jsonschema validation to reject the genome.  Strip them before returning.
    _INTERNAL_FIELD_KEYS = ("_injected", "_inferred")
    for _md_val in genome_modules.values():
        for _entity_fields in _md_val.get("fields", {}).values():
            if isinstance(_entity_fields, list):
                for _fld in _entity_fields:
                    if isinstance(_fld, dict):
                        for _ik in _INTERNAL_FIELD_KEYS:
                            _fld.pop(_ik, None)

    # ── Post-Step-3 deterministic inference pass ──────────────────────────────
    # Fills production concerns that can be inferred from what the wizard already
    # knows.  No new questions, no user burden.  Run unconditionally on every genome.
    genome = _apply_production_defaults(genome, solution, config)

    return genome


def _apply_production_defaults(genome: dict, solution, config: dict) -> dict:
    """Deterministic inference pass: fills production concerns from wizard context.

    Rules (all unconditional unless stated):
    - security.headers: always set — HTTP security headers cost nothing to enable
    - security.rate_limiting: always set — prevents abuse with zero config overhead
    - gdpr: true when solution name/description mentions EU, GDPR, or data privacy
    - deployment.ci_cd: always github_actions unless already set to something else
    - error_tracking: always sentry — standard observable production baseline
    """
    sec = genome.setdefault("security", {})

    # Security headers — always on
    if not sec.get("headers"):
        sec["headers"] = {
            "x_content_type_options": "nosniff",
            "x_frame_options": "DENY",
            "x_xss_protection": "1; mode=block",
            "strict_transport_security": "max-age=31536000; includeSubDomains",
            "referrer_policy": "strict-origin-when-cross-origin",
            "content_security_policy": "default-src 'self'",
        }

    # Rate limiting — always on
    if not sec.get("rate_limiting"):
        sec["rate_limiting"] = {
            "enabled": True,
            "strategy": "sliding_window",
            "default_limit": "100/minute",
            "auth_limit": "10/minute",
        }

    # GDPR — infer from solution context
    _gdpr_keywords = ("gdpr", "eu ", "european", "data privacy", "data protection",
                      "personal data", "pii", "right to erasure", "consent")
    _solution_text = " ".join([
        (solution.name or "").lower(),
        (solution.description or "").lower(),
        genome.get("problem", {}).get("statement", "").lower(),
    ])
    if not genome.get("gdpr") and any(kw in _solution_text for kw in _gdpr_keywords):
        genome["gdpr"] = {
            "enabled": True,
            "data_residency": "EU",
            "consent_management": True,
            "right_to_erasure": True,
        }
    # Always include GDPR baseline (set flag even if not EU-specific)
    if "gdpr" not in genome:
        genome["gdpr"] = {"enabled": False}

    # CI/CD — github_actions unless already configured to something else
    deployment = genome.setdefault("deployment", {})
    if not deployment.get("ci_cd"):
        deployment["ci_cd"] = {
            "provider": "github_actions",
            "registry": "ghcr",
        }

    # Error tracking — sentry as baseline observable production standard
    if not genome.get("error_tracking"):
        genome["error_tracking"] = {
            "provider": "sentry",
            "enabled": True,
            "capture_exceptions": True,
            "performance_monitoring": True,
        }

    return genome


def _map_component_entities(
    components: list,
    entities: list,
    relationships: list,
    elements_by_id: dict,
) -> dict:
    """Map application components to their data object entities via relationships.

    Uses ArchiMate relationships (access, association, composition, aggregation)
    to determine which data objects belong to which application components.

    Returns: {component_id: [entity_elements]}
    """
    result = {comp.id: [] for comp in components}
    entity_id_set = {e.id for e in entities}
    component_id_set = {c.id for c in components}

    for rel in relationships:
        src_id = rel.source_id
        tgt_id = rel.target_id

        # Component → Entity relationship
        if src_id in component_id_set and tgt_id in entity_id_set:
            entity_elem = elements_by_id.get(tgt_id)
            if entity_elem and entity_elem not in result[src_id]:
                result[src_id].append(entity_elem)

        # Entity → Component relationship (reverse direction)
        if tgt_id in component_id_set and src_id in entity_id_set:
            entity_elem = elements_by_id.get(src_id)
            if entity_elem and entity_elem not in result[tgt_id]:
                result[tgt_id].append(entity_elem)

    return result


def _extract_fields(element, spec_data: dict, elem_props: dict) -> list:
    """Extract field definitions from an element's spec_data and properties.

    Looks in multiple locations (spec_data.fields, properties.attributes,
    acm_properties) and normalizes to genome FieldDef format.
    """
    fields = []
    seen_names = set()

    # Source 1: spec_data.fields (highest priority — confirmed by architect)
    for field_def in spec_data.get("fields", []):
        name = field_def.get("name")
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        ftype = _infer_field_type(name, field_def.get("type", ""))
        safe_name = _snake_case(name)
        if safe_name in _RESERVED_FIELD_NAMES:
            safe_name = f"{safe_name}_value"
        field = {
            "name": safe_name,
            "type": ftype,
        }
        fmt = _infer_field_format(name, ftype)
        if fmt:
            field["format"] = fmt
        if field_def.get("required") is not None:
            field["required"] = bool(field_def["required"])
        if field_def.get("unique"):
            field["unique"] = True
        if field_def.get("max_length"):
            field["max_length"] = int(field_def["max_length"])
        if field_def.get("description"):
            field["description"] = field_def["description"]
        if field_def.get("enum_values"):
            field["enum_values"] = field_def["enum_values"]
            field["type"] = "enum"
        if field_def.get("foreign_key"):
            field["foreign_key"] = field_def["foreign_key"]
        if field_def.get("default_value") is not None:
            field["default_value"] = field_def["default_value"]
        fields.append(field)

    # Source 2: properties.attributes (from ArchiMate element properties)
    for attr in elem_props.get("attributes", []):
        name = attr.get("name") or attr.get("key")
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        ftype = _infer_field_type(name, attr.get("type", ""))
        safe_name = _snake_case(name)
        if safe_name in _RESERVED_FIELD_NAMES:
            safe_name = f"{safe_name}_value"
        field = {
            "name": safe_name,
            "type": ftype,
        }
        fmt = _infer_field_format(name, ftype)
        if fmt:
            field["format"] = fmt
        if attr.get("description"):
            field["description"] = attr["description"]
        fields.append(field)

    # Source 3: Infer default fields when no spec_data or properties exist.
    # Produces a minimal but functional CRUD scaffold from the entity name alone.
    if not fields:
        fields = _infer_default_fields(element)

    return fields


def _infer_default_fields(element) -> list:
    """Generate domain-specific fields for an entity with no spec_data.

    Uses three strategies in priority order:
    1. **Description mining** — extract field hints from the element description
    2. **Domain pattern matching** — match entity name against known domain archetypes
    3. **Base scaffold** — every entity gets name, description, status, timestamps

    Returns a field list rich enough to generate a functional CRUD app, not just
    empty shells with id/created_at/updated_at.
    """
    entity_name = _snake_case(_strip_archimate_suffix(element.name)) if element.name else "entity"
    desc = ((element.description or "") + " " + (element.name or "")).lower()
    name_lower = entity_name.lower()

    # ── Strategy 1: mine description for field hints ─────────────────────
    # Descriptions often contain phrases like "stores email, phone, and address"
    # or "tracks amount, currency, and payment status".
    desc_fields = _mine_fields_from_description(desc, name_lower)

    # ── Strategy 2: domain pattern matching ──────────────────────────────
    # Comprehensive patterns covering common SaaS, enterprise, and platform entities.
    pattern_fields = _match_domain_pattern(name_lower, desc)

    # ── Merge: description-mined fields take priority, then pattern fields ──
    seen = set()
    domain_fields = []
    for f in desc_fields + pattern_fields:
        if f["name"] not in seen:
            seen.add(f["name"])
            domain_fields.append(f)

    # ── Base scaffold — always present ───────────────────────────────────
    base = []
    # Only add "name" if no better label field was inferred
    label_fields = {"name", "title", "label", "display_name", "subject", "email"}
    if not (seen & label_fields):
        base.append({"name": "name", "type": "string", "required": True, "max_length": 255})
    if "description" not in seen:
        base.append({"name": "description", "type": "text", "required": False})
    if "status" not in seen:
        base.append({"name": "status", "type": "enum",
                      "enum_values": ["active", "inactive", "archived"],
                      "required": True, "default_value": "active"})

    timestamps = []
    if "created_at" not in seen:
        timestamps.append({"name": "created_at", "type": "datetime", "required": False})
    if "updated_at" not in seen:
        timestamps.append({"name": "updated_at", "type": "datetime", "required": False})

    return base + domain_fields + timestamps


def _mine_fields_from_description(desc: str, entity_name: str) -> list:
    """Extract field candidates from element description text.

    Looks for common phrases like "stores X, Y, and Z" or "contains X and Y"
    and maps recognized nouns to typed fields.
    """
    fields = []
    # Known field-name → type mappings for description mining
    _KNOWN_FIELDS = {
        "email": {"type": "string", "format": "email", "max_length": 255},
        "phone": {"type": "string", "format": "phone", "max_length": 20},
        "address": {"type": "text"},
        "url": {"type": "string", "format": "url", "max_length": 500},
        "amount": {"type": "decimal"},
        "price": {"type": "decimal"},
        "cost": {"type": "decimal"},
        "currency": {"type": "string", "max_length": 3, "default_value": "USD"},
        "quantity": {"type": "integer"},
        "count": {"type": "integer"},
        "percentage": {"type": "decimal"},
        "rate": {"type": "decimal"},
        "date": {"type": "datetime"},
        "deadline": {"type": "datetime"},
        "title": {"type": "string", "max_length": 500},
        "label": {"type": "string", "max_length": 255},
        "code": {"type": "string", "max_length": 50, "unique": True},
        "reference": {"type": "string", "max_length": 100},
        "priority": {"type": "enum", "enum_values": ["low", "medium", "high", "critical"]},
        "type": {"type": "string", "max_length": 50},
        "category": {"type": "string", "max_length": 100},
        "tags": {"type": "json"},
        "metadata": {"type": "json"},
        "config": {"type": "json"},
        "settings": {"type": "json"},
        "payload": {"type": "json"},
        "notes": {"type": "text"},
        "color": {"type": "string", "max_length": 7},
        "icon": {"type": "string", "max_length": 100},
        "slug": {"type": "string", "max_length": 255, "unique": True},
        "sort_order": {"type": "integer", "default_value": 0},
        "is_active": {"type": "boolean", "default_value": True},
        "is_default": {"type": "boolean", "default_value": False},
        "version": {"type": "integer", "default_value": 1},
    }
    seen = set()
    for keyword, field_def in _KNOWN_FIELDS.items():
        if keyword in desc and keyword not in seen:
            seen.add(keyword)
            field_name = _snake_case(keyword)
            # Avoid generic collisions: "type" → "<entity>_type"
            if field_name in ("type", "status", "code", "date"):
                field_name = f"{entity_name}_{field_name}"
            f = {"name": field_name, **field_def}
            if "required" not in f:
                f["required"] = False
            fields.append(f)
    return fields


# ── Domain archetype registry ────────────────────────────────────────────
# Each entry: (keyword_set, field_list).
# Checked in order; first match wins (but description-mined fields add on top).
_DOMAIN_ARCHETYPES = [
    # ── SaaS / Multi-tenant ──
    ({"workspace", "tenant", "organisation", "organization"},
     [{"name": "display_name", "type": "string", "required": True, "max_length": 255},
      {"name": "slug", "type": "string", "max_length": 255, "unique": True},
      {"name": "owner_id", "type": "string", "max_length": 36, "foreign_key": "users.id"},
      {"name": "plan", "type": "enum", "enum_values": ["free", "starter", "pro", "enterprise"], "default_value": "free"},
      {"name": "settings", "type": "json"},
      {"name": "logo_url", "type": "string", "format": "url", "max_length": 500},
      {"name": "is_active", "type": "boolean", "default_value": True}]),
    # ── Users / Accounts ──
    ({"user", "account", "member", "person", "contact", "stakeholder", "vendor", "customer", "profile"},
     [{"name": "email", "type": "string", "format": "email", "max_length": 255, "unique": True, "required": True},
      {"name": "display_name", "type": "string", "max_length": 255},
      {"name": "phone", "type": "string", "format": "phone", "max_length": 20},
      {"name": "avatar_url", "type": "string", "format": "url", "max_length": 500},
      {"name": "role", "type": "enum", "enum_values": ["admin", "member", "viewer"], "default_value": "member"},
      {"name": "last_login_at", "type": "datetime"},
      {"name": "is_active", "type": "boolean", "default_value": True}]),
    # ── Team / Group ──
    ({"team", "group", "department"},
     [{"name": "display_name", "type": "string", "required": True, "max_length": 255},
      {"name": "slug", "type": "string", "max_length": 255, "unique": True},
      {"name": "owner_id", "type": "string", "max_length": 36, "foreign_key": "users.id"},
      {"name": "max_members", "type": "integer"},
      {"name": "settings", "type": "json"}]),
    # ── Invite ──
    ({"invite", "invitation"},
     [{"name": "email", "type": "string", "format": "email", "max_length": 255, "required": True},
      {"name": "role", "type": "enum", "enum_values": ["admin", "member", "viewer"], "default_value": "member"},
      {"name": "token", "type": "string", "max_length": 255, "unique": True},
      {"name": "invited_by_id", "type": "string", "max_length": 36, "foreign_key": "users.id"},
      {"name": "accepted_at", "type": "datetime"},
      {"name": "expires_at", "type": "datetime", "required": True}]),
    # ── API Key / LLM Key / Secret ──
    ({"api_key", "llm_key", "secret", "credential", "token"},
     [{"name": "label", "type": "string", "required": True, "max_length": 255},
      {"name": "key_hash", "type": "string", "max_length": 255, "required": True,
       "description": "Sensitive: store hashed, never expose raw key"},
      {"name": "key_prefix", "type": "string", "max_length": 8, "description": "First 8 chars for identification"},
      {"name": "provider", "type": "enum", "enum_values": ["openai", "anthropic", "google", "azure", "custom"]},
      {"name": "scopes", "type": "json"},
      {"name": "last_used_at", "type": "datetime"},
      {"name": "expires_at", "type": "datetime"},
      {"name": "is_active", "type": "boolean", "default_value": True}]),
    # ── Subscription / Plan / Billing ──
    ({"subscription", "billing", "plan"},
     [{"name": "plan_id", "type": "string", "max_length": 100, "required": True},
      {"name": "stripe_subscription_id", "type": "string", "max_length": 255},
      {"name": "stripe_customer_id", "type": "string", "max_length": 255},
      {"name": "current_period_start", "type": "datetime"},
      {"name": "current_period_end", "type": "datetime"},
      {"name": "cancel_at", "type": "datetime"},
      {"name": "trial_end", "type": "datetime"}]),
    # ── Financial (Order/Invoice/Payment) ──
    ({"order", "transaction", "invoice", "payment", "ledger", "charge"},
     [{"name": "amount", "type": "decimal", "required": True},
      {"name": "currency", "type": "string", "max_length": 3, "default_value": "USD"},
      {"name": "reference_number", "type": "string", "max_length": 100, "unique": True},
      {"name": "paid_at", "type": "datetime"},
      {"name": "payment_method", "type": "string", "max_length": 50},
      {"name": "external_id", "type": "string", "max_length": 255, "description": "Stripe/PayPal ID"}]),
    # ── Usage / Metering ──
    ({"usage", "metering", "consumption", "quota"},
     [{"name": "metric", "type": "string", "max_length": 100, "required": True},
      {"name": "quantity", "type": "decimal", "required": True},
      {"name": "unit", "type": "string", "max_length": 20},
      {"name": "period_start", "type": "datetime", "required": True},
      {"name": "period_end", "type": "datetime", "required": True},
      {"name": "limit_value", "type": "decimal"}]),
    # ── Feature Flag ──
    ({"feature_flag", "feature", "toggle", "flag"},
     [{"name": "key", "type": "string", "max_length": 255, "unique": True, "required": True},
      {"name": "is_enabled", "type": "boolean", "default_value": False},
      {"name": "rollout_percentage", "type": "integer", "default_value": 0},
      {"name": "targeting_rules", "type": "json"},
      {"name": "variants", "type": "json"}]),
    # ── Blueprint / Template / Version ──
    ({"blueprint", "template", "scaffold", "boilerplate"},
     [{"name": "title", "type": "string", "required": True, "max_length": 500},
      {"name": "version", "type": "integer", "default_value": 1},
      {"name": "content", "type": "json", "required": True},
      {"name": "is_published", "type": "boolean", "default_value": False},
      {"name": "published_at", "type": "datetime"},
      {"name": "tags", "type": "json"}]),
    # ── Version / Revision ──
    ({"version", "revision", "snapshot", "changelog"},
     [{"name": "version_number", "type": "integer", "required": True},
      {"name": "change_summary", "type": "text"},
      {"name": "content_hash", "type": "string", "max_length": 64},
      {"name": "content", "type": "json"},
      {"name": "published_by_id", "type": "string", "max_length": 36, "foreign_key": "users.id"},
      {"name": "is_current", "type": "boolean", "default_value": False}]),
    # ── Section / Block / Component ──
    ({"section", "block", "component", "widget", "panel"},
     [{"name": "title", "type": "string", "max_length": 255},
      {"name": "content", "type": "json"},
      {"name": "sort_order", "type": "integer", "default_value": 0},
      {"name": "is_visible", "type": "boolean", "default_value": True},
      {"name": "config", "type": "json"}]),
    # ── Document / Contract / Tender ──
    ({"document", "contract", "tender", "report", "attachment", "file"},
     [{"name": "title", "type": "string", "required": True, "max_length": 500},
      {"name": "document_type", "type": "string", "max_length": 50},
      {"name": "file_url", "type": "string", "format": "url", "max_length": 500},
      {"name": "file_size", "type": "integer"},
      {"name": "mime_type", "type": "string", "max_length": 100},
      {"name": "effective_date", "type": "datetime"},
      {"name": "expiry_date", "type": "datetime"}]),
    # ── Notification / Alert / Message ──
    ({"notification", "alert", "message", "announcement"},
     [{"name": "title", "type": "string", "max_length": 255},
      {"name": "body", "type": "text", "required": True},
      {"name": "channel", "type": "enum", "enum_values": ["email", "sms", "push", "in_app"], "default_value": "in_app"},
      {"name": "recipient_id", "type": "string", "max_length": 36, "foreign_key": "users.id"},
      {"name": "read_at", "type": "datetime"},
      {"name": "sent_at", "type": "datetime"}]),
    # ── Audit / Event / Log ──
    ({"audit", "audit_event", "audit_log", "event_log", "log", "activity"},
     [{"name": "action", "type": "string", "max_length": 100, "required": True},
      {"name": "actor_id", "type": "string", "max_length": 36, "foreign_key": "users.id"},
      {"name": "resource_type", "type": "string", "max_length": 100},
      {"name": "resource_id", "type": "string", "max_length": 36},
      {"name": "changes", "type": "json"},
      {"name": "ip_address", "type": "string", "max_length": 45},
      {"name": "user_agent", "type": "string", "max_length": 500}]),
    # ── KPI / Metric / Score ──
    ({"kpi", "metric", "score", "analytics", "measure"},
     [{"name": "metric_name", "type": "string", "max_length": 100, "required": True},
      {"name": "value", "type": "decimal", "required": True},
      {"name": "target", "type": "decimal"},
      {"name": "unit", "type": "string", "max_length": 20},
      {"name": "measured_at", "type": "datetime", "required": True},
      {"name": "dimension", "type": "string", "max_length": 100}]),
    # ── Workflow / Process / Approval / Task ──
    ({"workflow", "process", "approval", "task", "ticket", "issue"},
     [{"name": "title", "type": "string", "required": True, "max_length": 500},
      {"name": "assignee_id", "type": "string", "max_length": 36, "foreign_key": "users.id"},
      {"name": "reporter_id", "type": "string", "max_length": 36, "foreign_key": "users.id"},
      {"name": "priority", "type": "enum", "enum_values": ["low", "medium", "high", "critical"], "default_value": "medium"},
      {"name": "due_date", "type": "datetime"},
      {"name": "labels", "type": "json"}]),
    # ── Integration / Service / API / Connector ──
    ({"service", "api", "integration", "gateway", "connector", "webhook"},
     [{"name": "endpoint_url", "type": "string", "format": "url", "max_length": 500},
      {"name": "service_type", "type": "string", "max_length": 50},
      {"name": "auth_method", "type": "enum", "enum_values": ["none", "api_key", "oauth2", "bearer"], "default_value": "api_key"},
      {"name": "config", "type": "json"},
      {"name": "health_status", "type": "enum", "enum_values": ["healthy", "degraded", "down"], "default_value": "healthy"},
      {"name": "last_checked_at", "type": "datetime"}]),
    # ── Settings / Preference / Config ──
    ({"setting", "preference", "config", "option"},
     [{"name": "key", "type": "string", "max_length": 255, "unique": True, "required": True},
      {"name": "value", "type": "json", "required": True},
      {"name": "value_type", "type": "enum", "enum_values": ["string", "number", "boolean", "json"], "default_value": "string"},
      {"name": "is_secret", "type": "boolean", "default_value": False},
      {"name": "category", "type": "string", "max_length": 100}]),
    # ── Comment / Review / Feedback ──
    ({"comment", "review", "feedback", "rating"},
     [{"name": "body", "type": "text", "required": True},
      {"name": "author_id", "type": "string", "max_length": 36, "foreign_key": "users.id"},
      {"name": "parent_id", "type": "string", "max_length": 36, "description": "Self-referential for threading"},
      {"name": "rating", "type": "integer"},
      {"name": "resource_type", "type": "string", "max_length": 100},
      {"name": "resource_id", "type": "string", "max_length": 36}]),
    # ── Tag / Category / Label ──
    ({"tag", "category", "label"},
     [{"name": "display_name", "type": "string", "required": True, "max_length": 255},
      {"name": "slug", "type": "string", "max_length": 255, "unique": True},
      {"name": "color", "type": "string", "max_length": 7},
      {"name": "icon", "type": "string", "max_length": 100},
      {"name": "sort_order", "type": "integer", "default_value": 0}]),
    # ── Media / Image / Asset ──
    ({"media", "image", "asset", "upload"},
     [{"name": "file_url", "type": "string", "format": "url", "max_length": 500, "required": True},
      {"name": "file_name", "type": "string", "max_length": 255},
      {"name": "file_size", "type": "integer"},
      {"name": "mime_type", "type": "string", "max_length": 100},
      {"name": "alt_text", "type": "string", "max_length": 500},
      {"name": "uploaded_by_id", "type": "string", "max_length": 36, "foreign_key": "users.id"}]),
    # ── Store / Database / Repository / Cache ──
    ({"store", "database", "repository", "cache"},
     [{"name": "storage_type", "type": "string", "max_length": 50},
      {"name": "capacity", "type": "string", "max_length": 50},
      {"name": "connection_string", "type": "string", "max_length": 500,
       "description": "Sensitive: encrypted at rest"}]),
    # ── Address / Location ──
    ({"address", "location"},
     [{"name": "line1", "type": "string", "max_length": 255, "required": True},
      {"name": "line2", "type": "string", "max_length": 255},
      {"name": "city", "type": "string", "max_length": 100, "required": True},
      {"name": "state", "type": "string", "max_length": 100},
      {"name": "postal_code", "type": "string", "max_length": 20},
      {"name": "country", "type": "string", "max_length": 2, "default_value": "US"},
      {"name": "latitude", "type": "decimal"},
      {"name": "longitude", "type": "decimal"}]),
]


def _match_domain_pattern(name_lower: str, desc: str) -> list:
    """Match entity name (and optionally description) against domain archetypes.

    For compound names like "workspace_llm_key", builds all sub-segments
    (both suffixes and prefixes) and picks the longest matching keyword.
    "workspace_llm_key" → tries "workspace_llm_key", "llm_key", "workspace_llm",
    "key", "llm", "workspace" — "llm_key" matches first (api_key archetype).
    """
    parts = name_lower.split("_")

    # Build all contiguous sub-segments, ordered to prefer specificity:
    # 1. Longest first (multi-word compounds like "llm_key" before "key")
    # 2. Deprioritize namespace/context-only words (workspace, app, system, etc.)
    # 3. At equal length, rightmost first (suffix often carries domain meaning)
    _CONTEXT_ONLY = {"workspace", "app", "system", "platform", "project", "org",
                     "global", "internal", "external", "default", "base", "core", "main"}
    segments = []
    for i in range(len(parts)):
        for j in range(i + 1, len(parts) + 1):
            seg = "_".join(parts[i:j])
            is_context = seg in _CONTEXT_ONLY
            segments.append((seg, j - i, i, is_context))
    # Sort: longest first, non-context before context, then rightmost first
    segments.sort(key=lambda x: (-x[1], x[3], -x[2]))
    ordered = [s[0] for s in segments]

    for seg in ordered:
        for keywords, field_defs in _DOMAIN_ARCHETYPES:
            if seg in keywords:
                return [dict(f) for f in field_defs]

    # No exact segment match — fall back to substring matching on full name
    for keywords, field_defs in _DOMAIN_ARCHETYPES:
        if any(kw in name_lower for kw in keywords):
            return [dict(f) for f in field_defs]

    # Last resort: check description for archetype hints
    for keywords, field_defs in _DOMAIN_ARCHETYPES:
        if any(kw in desc for kw in keywords):
            return [dict(f) for f in field_defs]
    return []


def _extract_state_machine(
    component,
    process_elements: list,
    relationships: list,
    elements_by_id: dict,
) -> Optional[dict]:
    """Extract a state machine definition from related business processes.

    Looks for BusinessProcess elements linked to the component that
    describe state transitions (status-based workflows).
    """
    # Find processes related to this component
    component_id = component.id
    related_process_ids = set()
    for rel in relationships:
        if rel.source_id == component_id and rel.target_id in {p.id for p in process_elements}:
            related_process_ids.add(rel.target_id)
        if rel.target_id == component_id and rel.source_id in {p.id for p in process_elements}:
            related_process_ids.add(rel.source_id)

    if not related_process_ids:
        # No linked BusinessProcess elements — use component name to infer a
        # domain-appropriate state machine deterministically (no LLM required).
        # This is the common case for PDF-upload wizard solutions where the
        # wizard creates ApplicationComponent elements but not cross-type relationships.
        return _infer_state_machine_from_component_name(component)

    # Analyze process elements for state machine patterns
    states = []
    transitions = []

    for pid in related_process_ids:
        proc = elements_by_id.get(pid)
        if not proc:
            continue

        props = _parse_json_field(proc.properties)

        # Check for explicit state machine in properties
        sm = props.get("state_machine") or props.get("states")
        if isinstance(sm, dict) and "states" in sm:
            return sm  # Already well-formed

        if isinstance(sm, list):
            states.extend(sm)

        # Check for transitions in properties
        trans = props.get("transitions")
        if isinstance(trans, list):
            transitions.extend(trans)

    if not states and not transitions:
        # No explicit state machine — infer from process context.
        # If related processes exist, the entity likely has a lifecycle.
        # Generate a domain-appropriate default state machine.
        if related_process_ids:
            states, transitions = _infer_lifecycle_states(
                component, [elements_by_id.get(pid) for pid in related_process_ids if elements_by_id.get(pid)]
            )

    if not states and not transitions:
        return None

    # Deduplicate states
    seen = set()
    unique_states = []
    for s in states:
        s_str = s if isinstance(s, str) else str(s)
        if s_str not in seen:
            seen.add(s_str)
            unique_states.append(s_str)

    if len(unique_states) < 2:
        return None

    # Infer the actual status field name from the component's data entities.
    # Many domain models use verification_status, account_status, kyc_status, etc.
    # rather than a plain "status" column.
    status_field = "status"
    comp_name_lower = (component.name or "").lower().replace(" ", "_")
    for entity_elem in (elements_by_id.get(eid) for eid in elements_by_id):
        if entity_elem is None:
            continue
        props = _parse_json_field(getattr(entity_elem, "properties", None))
        if not isinstance(props, dict):
            continue
        for field_def in (props.get("fields") or props.get("attributes") or []):
            fname = (field_def.get("name", "") if isinstance(field_def, dict) else str(field_def)).lower()
            if fname.endswith("_status") or fname.endswith("_state"):
                # Prefer a status field that matches the component's domain
                status_field = fname
                break
        if status_field != "status":
            break

    result = {
        "field": status_field,
        "states": unique_states,
        "initial_state": unique_states[0],
    }
    if transitions:
        result["transitions"] = transitions

    return result


def _infer_lifecycle_states(component, processes: list) -> tuple:
    """Infer lifecycle state machine from related business processes.

    When no explicit state machine is defined, generates a reasonable default
    based on the domain context (process names and descriptions). The architect
    can override this in the genome YAML.

    Returns (states, transitions) tuple.
    """
    # Analyze process names and descriptions for domain signals
    all_text = " ".join(
        f"{(p.name or '')} {(p.description or '')}" for p in processes
    ).lower()

    # Domain-specific lifecycle patterns
    if any(kw in all_text for kw in ["kyc", "verification", "identity", "compliance", "screening"]):
        states = ["submitted", "documents_uploaded", "under_review", "verified", "rejected", "expired"]
        transitions = [
            {"from": "submitted", "to": "documents_uploaded", "trigger": "upload_documents"},
            {"from": "documents_uploaded", "to": "under_review", "trigger": "start_review"},
            {"from": "under_review", "to": "verified", "trigger": "approve"},
            {"from": "under_review", "to": "rejected", "trigger": "reject"},
            {"from": ["submitted", "documents_uploaded"], "to": "expired", "trigger": "expire"},
        ]
    elif any(kw in all_text for kw in ["account creation", "onboarding", "registration"]):
        states = ["initiated", "identity_verified", "compliance_cleared", "account_created", "active", "suspended"]
        transitions = [
            {"from": "initiated", "to": "identity_verified", "trigger": "verify_identity"},
            {"from": "identity_verified", "to": "compliance_cleared", "trigger": "clear_compliance"},
            {"from": "compliance_cleared", "to": "account_created", "trigger": "create_account"},
            {"from": "account_created", "to": "active", "trigger": "activate"},
            {"from": "active", "to": "suspended", "trigger": "suspend"},
        ]
    elif any(kw in all_text for kw in ["fraud", "risk", "scoring", "assessment"]):
        states = ["pending", "analyzing", "low_risk", "medium_risk", "high_risk", "escalated"]
        transitions = [
            {"from": "pending", "to": "analyzing", "trigger": "start_analysis"},
            {"from": "analyzing", "to": "low_risk", "trigger": "classify_low"},
            {"from": "analyzing", "to": "medium_risk", "trigger": "classify_medium"},
            {"from": "analyzing", "to": "high_risk", "trigger": "classify_high"},
            {"from": "high_risk", "to": "escalated", "trigger": "escalate"},
        ]
    elif any(kw in all_text for kw in ["migration", "import", "transfer", "sync"]):
        states = ["queued", "in_progress", "validating", "completed", "failed"]
        transitions = [
            {"from": "queued", "to": "in_progress", "trigger": "start"},
            {"from": "in_progress", "to": "validating", "trigger": "validate"},
            {"from": "validating", "to": "completed", "trigger": "complete"},
            {"from": ["in_progress", "validating"], "to": "failed", "trigger": "fail"},
            {"from": "failed", "to": "queued", "trigger": "retry"},
        ]
    else:
        # Generic CRUD entity lifecycle
        states = ["draft", "active", "archived"]
        transitions = [
            {"from": "draft", "to": "active", "trigger": "activate"},
            {"from": "active", "to": "archived", "trigger": "archive"},
            {"from": "archived", "to": "active", "trigger": "restore"},
        ]

    return states, transitions


def _infer_state_machine_from_component_name(component) -> Optional[dict]:
    """Deterministic state machine inference from component name alone.

    Used when there are no linked BusinessProcess elements (typical for PDF-upload
    wizard solutions).  Covers AI/pipeline, document, order, and generic patterns.
    Returns a fully-formed state_machine dict or None for trivial CRUD components.
    """
    name = (getattr(component, "name", "") or "").lower()
    desc = (getattr(component, "description", "") or "").lower()
    combined = name + " " + desc

    # AI extraction / OCR / document ingestion pipeline
    if any(kw in combined for kw in ("extract", "ocr", "ingest", "parse", "scan")):
        return {
            "field": "job_status",
            "states": ["pending", "submitted", "extracting", "extracted", "review_required", "completed", "failed"],
            "initial_state": "pending",
            "transitions": [
                {"from": "pending", "to": "submitted", "trigger": "submit"},
                {"from": "submitted", "to": "extracting", "trigger": "start_extraction"},
                {"from": "extracting", "to": "extracted", "trigger": "extraction_complete"},
                {"from": "extracting", "to": "review_required", "trigger": "low_confidence_detected"},
                {"from": "review_required", "to": "extracted", "trigger": "human_review_approved"},
                {"from": "review_required", "to": "failed", "trigger": "human_review_rejected"},
                {"from": "extracted", "to": "completed", "trigger": "finalize"},
                {"from": ["extracting", "extracted"], "to": "failed", "trigger": "error"},
                {"from": "failed", "to": "pending", "trigger": "retry"},
            ],
        }

    # Classification / categorization
    if any(kw in combined for kw in ("classif", "categoriz", "tag", "label")):
        return {
            "field": "classification_status",
            "states": ["unclassified", "classifying", "classified", "review_required", "approved", "rejected"],
            "initial_state": "unclassified",
            "transitions": [
                {"from": "unclassified", "to": "classifying", "trigger": "start_classification"},
                {"from": "classifying", "to": "classified", "trigger": "classification_complete"},
                {"from": "classifying", "to": "review_required", "trigger": "low_confidence"},
                {"from": "classified", "to": "review_required", "trigger": "flag_for_review"},
                {"from": "review_required", "to": "approved", "trigger": "approve"},
                {"from": "review_required", "to": "rejected", "trigger": "reject"},
                {"from": "rejected", "to": "unclassified", "trigger": "reset"},
            ],
        }

    # Order / purchase order processing
    if any(kw in combined for kw in ("order", "purchase", "procurement", "requisition")):
        return {
            "field": "order_status",
            "states": ["draft", "submitted", "validated", "approved", "fulfilling", "fulfilled", "cancelled"],
            "initial_state": "draft",
            "transitions": [
                {"from": "draft", "to": "submitted", "trigger": "submit"},
                {"from": "submitted", "to": "validated", "trigger": "validate"},
                {"from": "validated", "to": "approved", "trigger": "approve"},
                {"from": "validated", "to": "draft", "trigger": "request_changes"},
                {"from": "approved", "to": "fulfilling", "trigger": "start_fulfillment"},
                {"from": "fulfilling", "to": "fulfilled", "trigger": "complete"},
                {"from": ["draft", "submitted", "approved"], "to": "cancelled", "trigger": "cancel"},
            ],
        }

    # Route planning / logistics / delivery
    if any(kw in combined for kw in ("route", "delivery", "dispatch", "logistics", "vrp")):
        return {
            "field": "delivery_status",
            "states": ["planned", "assigned", "in_transit", "delivered", "failed", "returned"],
            "initial_state": "planned",
            "transitions": [
                {"from": "planned", "to": "assigned", "trigger": "assign_driver"},
                {"from": "assigned", "to": "in_transit", "trigger": "start_delivery"},
                {"from": "in_transit", "to": "delivered", "trigger": "confirm_delivery"},
                {"from": "in_transit", "to": "failed", "trigger": "report_failure"},
                {"from": "failed", "to": "returned", "trigger": "return_to_depot"},
                {"from": "failed", "to": "planned", "trigger": "reschedule"},
            ],
        }

    # Approval / review / human-in-the-loop
    if any(kw in combined for kw in ("approv", "review", "verif", "audit", "check")):
        return {
            "field": "review_status",
            "states": ["pending_review", "under_review", "approved", "rejected", "escalated"],
            "initial_state": "pending_review",
            "transitions": [
                {"from": "pending_review", "to": "under_review", "trigger": "start_review"},
                {"from": "under_review", "to": "approved", "trigger": "approve"},
                {"from": "under_review", "to": "rejected", "trigger": "reject"},
                {"from": "under_review", "to": "escalated", "trigger": "escalate"},
                {"from": "escalated", "to": "approved", "trigger": "approve_after_escalation"},
                {"from": "rejected", "to": "pending_review", "trigger": "resubmit"},
            ],
        }

    # Generic async job / processing
    if any(kw in combined for kw in ("process", "generat", "run", "execut", "job", "task", "batch")):
        return {
            "field": "job_status",
            "states": ["queued", "running", "completed", "failed"],
            "initial_state": "queued",
            "transitions": [
                {"from": "queued", "to": "running", "trigger": "start"},
                {"from": "running", "to": "completed", "trigger": "complete"},
                {"from": "running", "to": "failed", "trigger": "error"},
                {"from": "failed", "to": "queued", "trigger": "retry"},
            ],
        }

    # No meaningful state machine for simple lookup/config components
    return None


def _extract_operations(component, spec_data: dict, entity_names: list) -> dict:
    """Extract operations (commands/queries) from spec_data and element metadata."""
    operations = {}

    # From spec_data.api_contract
    api_contract = spec_data.get("api_contract", {})
    for endpoint in api_contract.get("endpoints", []):
        op_id = endpoint.get("operation_id") or endpoint.get("name")
        if not op_id:
            continue
        method = (endpoint.get("method") or "GET").upper()
        op_type = "command" if method in ("POST", "PUT", "PATCH", "DELETE") else "query"
        op = {"type": op_type}
        if endpoint.get("description"):
            op["description"] = endpoint["description"]
        if endpoint.get("authorization"):
            op["authorization"] = endpoint["authorization"]
        operations[_snake_case(op_id)] = op

    # Pipeline/AI operation inference — deterministic, no LLM needed.
    # Components named "Bid Document AI Extraction" or "Order Processing" imply
    # job-tracking semantics, not CRUD.  Infer appropriate operations.
    if not operations:
        comp_name = (getattr(component, "name", "") or "").lower()
        comp_desc = (getattr(component, "description", "") or "").lower()
        comp_combined = comp_name + " " + comp_desc
        root = _snake_case(_strip_archimate_suffix(getattr(component, "name", "") or "entity"))
        pc = _pascal_case(root)

        if any(kw in comp_combined for kw in ("extract", "extraction", "parse", "parsing", "ocr", "ingest")):
            operations = {
                f"submit_{root}_job": {"type": "command", "input": f"{pc}Request", "output": f"{pc}JobId",
                                       "description": "Submit document for async extraction"},
                f"get_{root}_status": {"type": "query", "input": f"{pc}JobId", "output": f"{pc}Status",
                                       "description": "Poll extraction job status"},
                f"get_{root}_result": {"type": "query", "input": f"{pc}JobId", "output": f"{pc}Result",
                                       "description": "Retrieve extracted data when job completes"},
                f"list_{root}_jobs": {"type": "query", "output": f"Page<{pc}Summary>",
                                      "description": "List extraction jobs"},
                f"retry_{root}": {"type": "command", "input": f"{pc}JobId",
                                   "description": "Retry a failed extraction job"},
            }
        elif any(kw in comp_combined for kw in ("classif", "categoriz", "mapping", "map")):
            operations = {
                f"classify_{root}": {"type": "command", "input": f"{pc}Input", "output": f"{pc}Classification",
                                     "description": "Run classification on input"},
                f"get_{root}_result": {"type": "query", "input": f"{pc}Id", "output": f"{pc}Detail"},
                f"reclassify_{root}": {"type": "command", "input": f"{pc}Id",
                                       "description": "Trigger reclassification with updated model"},
                f"list_{root}_results": {"type": "query", "output": f"Page<{pc}Summary>"},
            }
        elif any(kw in comp_combined for kw in ("normaliz", "standardiz", "transform")):
            operations = {
                f"normalize_{root}": {"type": "command", "input": f"Raw{pc}", "output": f"{pc}Normalized",
                                      "description": "Normalize raw input to canonical form"},
                f"validate_{root}": {"type": "query", "input": f"{pc}Normalized", "output": "ValidationResult"},
                f"get_{root}": {"type": "query", "input": f"{pc}Id", "output": f"{pc}Detail"},
                f"list_{root}s": {"type": "query", "output": f"Page<{pc}Summary>"},
            }
        elif any(kw in comp_combined for kw in ("review", "confidence", "approv", "verif")):
            operations = {
                f"submit_{root}_for_review": {"type": "command", "input": f"{pc}Draft",
                                               "description": "Submit item for human review"},
                f"approve_{root}": {"type": "command", "input": f"{pc}Id",
                                    "description": "Approve reviewed item"},
                f"reject_{root}": {"type": "command", "input": f"{pc}Id",
                                   "description": "Reject with reason"},
                f"list_pending_{root}s": {"type": "query", "output": f"Page<{pc}Summary>"},
            }
        elif any(kw in comp_combined for kw in ("generat", "build", "produc", "creat")):
            operations = {
                f"generate_{root}": {"type": "command", "input": f"{pc}Spec", "output": f"{pc}Id",
                                     "description": "Trigger generation job"},
                f"get_{root}_status": {"type": "query", "input": f"{pc}Id", "output": f"{pc}Status"},
                f"get_{root}_result": {"type": "query", "input": f"{pc}Id", "output": f"{pc}Result"},
                f"list_{root}s": {"type": "query", "output": f"Page<{pc}Summary>"},
            }
        elif any(kw in comp_combined for kw in ("process", "execut", "run", "handl")):
            operations = {
                f"submit_{root}": {"type": "command", "input": f"{pc}Request", "output": f"{pc}JobId",
                                   "description": "Submit for async processing"},
                f"get_{root}_status": {"type": "query", "input": f"{pc}JobId", "output": f"{pc}Status"},
                f"cancel_{root}": {"type": "command", "input": f"{pc}JobId",
                                   "description": "Cancel in-progress job"},
                f"list_{root}_jobs": {"type": "query", "output": f"Page<{pc}Summary>"},
            }

    # Fallback: generic CRUD when no domain pattern matched
    if not operations and entity_names:
        root = _snake_case(entity_names[0])
        pc = _pascal_case(entity_names[0])
        operations = {
            f"create_{root}": {"type": "command", "input": f"{pc}Draft", "output": f"{pc}Id"},
            f"get_{root}": {"type": "query", "input": f"{pc}Id", "output": f"{pc}Detail"},
            f"list_{root}s": {"type": "query", "output": f"Page<{pc}Summary>"},
            f"update_{root}": {"type": "command", "input": f"{pc}Update", "output": f"{pc}Detail"},
            f"delete_{root}": {"type": "command", "input": f"{pc}Id"},
        }

    return operations


def _extract_sensitive_fields(entity_elements: list, junction_map: dict) -> list:
    """Extract sensitivity annotations from element ACM properties."""
    sensitive = []
    for elem in entity_elements:
        acm_props = _parse_json_field(getattr(elem, "acm_properties", None))
        for field_annotation in acm_props.get("sensitive_fields", []):
            field_name = field_annotation.get("field")
            level = field_annotation.get("level", "pii")
            if field_name:
                sensitive.append({
                    "field": f"{_pascal_case(elem.name)}.{_snake_case(field_name)}",
                    "level": level,
                })
    return sensitive


def _build_default_views(fields_by_entity: dict, aggregate_root: str, state_machine: Optional[dict]) -> dict:
    """Build default list/detail/create view definitions from entity fields."""
    views = {}

    if not aggregate_root or not fields_by_entity:
        return views

    root_fields = fields_by_entity.get(aggregate_root, [])
    field_names = [f["name"] for f in root_fields]

    if field_names:
        # List view: show first 5 fields + status if state machine
        list_columns = field_names[:5]
        if state_machine and state_machine.get("field") not in list_columns:
            list_columns.append(state_machine["field"])
        views["list"] = {
            "columns": list_columns,
            "default_sort": {"field": field_names[0], "dir": "desc"},
        }

        # Filters: status (if state machine) + any enum/boolean fields
        filters = []
        if state_machine:
            filters.append(state_machine["field"])
        for f in root_fields:
            if f.get("type") in ("enum", "boolean") and f["name"] not in filters:
                filters.append(f["name"])
        if filters:
            views["list"]["filters"] = filters[:5]

        # Actions: default CRUD + state machine triggers
        actions = ["view", "edit", "delete"]
        if state_machine:
            triggers = [t.get("trigger") for t in state_machine.get("transitions", []) if t.get("trigger")]
            actions.extend(triggers[:3])
        views["list"]["actions"] = actions

        # Detail view
        views["detail"] = {"sections": ["summary", "details", "history"]}

        # Create view: required fields only
        create_fields = [f["name"] for f in root_fields if f.get("required", True)]
        if create_fields:
            views["create"] = {"fields": create_fields}

    return views


# ---------------------------------------------------------------------------
# BFG/SFG serialization helpers
# ---------------------------------------------------------------------------

def _pipeline_to_dict(pipeline) -> dict:
    """Convert a Pipeline dataclass to a plain dict for genome storage."""
    from dataclasses import asdict
    try:
        return asdict(pipeline)
    except TypeError:
        # Already a dict
        if isinstance(pipeline, dict):
            return pipeline
        return {"name": str(pipeline)}


def _screen_to_dict(screen) -> dict:
    """Convert a Screen dataclass to a plain dict for genome storage."""
    from dataclasses import asdict
    try:
        return asdict(screen)
    except TypeError:
        if isinstance(screen, dict):
            return screen
        return {"name": str(screen)}
