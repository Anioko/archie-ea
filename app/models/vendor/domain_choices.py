"""
Vendor Domain Taxonomy - Standardized Domain Classifications

This module provides a simple, standardized lookup for vendor product domains.
Use these constants when categorizing vendor products to ensure consistency.

Usage:
    from app.models.vendor.domain_choices import VENDOR_DOMAINS, get_domain_label, get_domain_choices

    # Get display label
    label = get_domain_label('erp')  # Returns 'ERP'

    # Get choices for form select
    choices = get_domain_choices()  # Returns [('erp', 'ERP - Enterprise Resource Planning'), ...]
"""

# Standardized vendor product domains
# Key: lowercase slug (stored in database)
# Value: dict with display info
VENDOR_DOMAINS = {
    "erp": {
        "label": "ERP",
        "full_name": "Enterprise Resource Planning",
        "description": "Core business operations including finance, procurement, manufacturing",
        "color": "blue",  # Tailwind color name for UI
    },
    "crm": {
        "label": "CRM",
        "full_name": "Customer Relationship Management",
        "description": "Sales, marketing, and customer service automation",
        "color": "green",
    },
    "hcm": {
        "label": "HCM",
        "full_name": "Human Capital Management",
        "description": "HR, payroll, talent management, workforce planning",
        "color": "purple",
    },
    "scm": {
        "label": "SCM",
        "full_name": "Supply Chain Management",
        "description": "Logistics, inventory, supplier management, procurement",
        "color": "orange",
    },
    "analytics": {
        "label": "Analytics",
        "full_name": "Business Intelligence & Analytics",
        "description": "Reporting, dashboards, data visualization, BI tools",
        "color": "cyan",
    },
    "itsm": {
        "label": "ITSM",
        "full_name": "IT Service Management",
        "description": "IT helpdesk, service desk, IT operations management",
        "color": "indigo",
    },
    "mdm": {
        "label": "MDM",
        "full_name": "Master Data Management",
        "description": "Data governance, data quality, master data hubs",
        "color": "slate",
    },
    "security": {
        "label": "Security",
        "full_name": "Cybersecurity & Compliance",
        "description": "Identity management, access control, security monitoring",
        "color": "red",
    },
    "integration": {
        "label": "Integration",
        "full_name": "Integration & iPaaS",
        "description": "API management, ETL, data integration platforms",
        "color": "yellow",
    },
    "collaboration": {
        "label": "Collaboration",
        "full_name": "Collaboration & Productivity",
        "description": "Communication, document management, workflow tools",
        "color": "pink",
    },
    "plm": {
        "label": "PLM",
        "full_name": "Product Lifecycle Management",
        "description": "Product design, engineering, manufacturing processes",
        "color": "teal",
    },
    "eam": {
        "label": "EAM",
        "full_name": "Enterprise Asset Management",
        "description": "Asset tracking, maintenance, facility management",
        "color": "amber",
    },
    "grc": {
        "label": "GRC",
        "full_name": "Governance, Risk & Compliance",
        "description": "Risk management, audit, regulatory compliance",
        "color": "rose",
    },
    "cloud": {
        "label": "Cloud",
        "full_name": "Cloud Infrastructure",
        "description": "IaaS, PaaS, cloud platforms and services",
        "color": "sky",
    },
    "database": {
        "label": "Database",
        "full_name": "Database & Data Platform",
        "description": "RDBMS, NoSQL, data warehouses, data lakes",
        "color": "emerald",
    },
    "devops": {
        "label": "DevOps",
        "full_name": "DevOps & Development Tools",
        "description": "CI/CD, version control, development platforms",
        "color": "violet",
    },
    "other": {
        "label": "Other",
        "full_name": "Other / Unclassified",
        "description": "Products not fitting standard categories",
        "color": "gray",
    },
}

# Mapping patterns for auto-categorization
# Used by cleanup scripts to map existing free-text values to standardized domains
DOMAIN_MAPPING_PATTERNS = {
    "erp": [
        "erp",
        "enterprise resource",
        "finance",
        "financials",
        "accounting",
        "procurement",
        "manufacturing",
        "netsuite",
        "s/4hana",
        "dynamics 365 finance",
        "oracle cloud erp",
        "workday financial",
        "sage",
        "infor",
    ],
    "crm": [
        "crm",
        "customer relationship",
        "sales",
        "salesforce",
        "hubspot",
        "dynamics 365 sales",
        "marketing automation",
        "customer service",
        "service cloud",
        "sales cloud",
        "zoho crm",
        "pipedrive",
    ],
    "hcm": [
        "hcm",
        "human capital",
        "hr",
        "human resources",
        "payroll",
        "talent",
        "workforce",
        "workday hcm",
        "successfactors",
        "adp",
        "bamboohr",
        "recruiting",
        "onboarding",
        "performance management",
    ],
    "scm": [
        "scm",
        "supply chain",
        "logistics",
        "inventory",
        "warehouse",
        "transportation",
        "supplier",
        "fulfillment",
        "order management",
        "blue yonder",
        "manhattan",
        "kinaxis",
    ],
    "analytics": [
        "analytics",
        "business intelligence",
        "bi",
        "reporting",
        "dashboard",
        "visualization",
        "tableau",
        "power bi",
        "looker",
        "qlik",
        "sisense",
        "data analytics",
        "thoughtspot",
        "domo",
    ],
    "itsm": [
        "itsm",
        "it service",
        "service management",
        "servicenow",
        "jira service",
        "helpdesk",
        "service desk",
        "incident management",
        "bmc",
        "freshservice",
    ],
    "mdm": [
        "mdm",
        "master data",
        "data management",
        "data governance",
        "data quality",
        "informatica mdm",
        "reltio",
        "stibo",
        "pim",
        "product information",
    ],
    "security": [
        "security",
        "cybersecurity",
        "identity",
        "access management",
        "iam",
        "sso",
        "okta",
        "auth0",
        "crowdstrike",
        "palo alto",
        "splunk security",
        "siem",
        "endpoint",
        "firewall",
        "encryption",
    ],
    "integration": [
        "integration",
        "ipaas",
        "api",
        "etl",
        "data integration",
        "mulesoft",
        "boomi",
        "informatica",
        "talend",
        "snaplogic",
        "workato",
        "celigo",
        "middleware",
        "esb",
        "kafka",
        "dataflow",
    ],
    "collaboration": [
        "collaboration",
        "productivity",
        "microsoft 365",
        "google workspace",
        "slack",
        "teams",
        "zoom",
        "document management",
        "sharepoint",
        "confluence",
        "notion",
        "asana",
        "monday.com",
    ],
    "plm": [
        "plm",
        "product lifecycle",
        "cad",
        "engineering",
        "ptc",
        "siemens plm",
        "autodesk",
        "solidworks",
        "product design",
        "arena",
    ],
    "eam": [
        "eam",
        "asset management",
        "maintenance",
        "cmms",
        "facility",
        "maximo",
        "infor eam",
        "fiix",
        "uptake",
    ],
    "grc": [
        "grc",
        "governance",
        "risk",
        "compliance",
        "audit",
        "regulatory",
        "archer",
        "servicenow grc",
        "metricstream",
        "diligent",
    ],
    "cloud": [
        "cloud",
        "iaas",
        "paas",
        "aws",
        "azure",
        "google cloud",
        "gcp",
        "infrastructure",
        "compute",
        "storage",
        "kubernetes",
        "container",
    ],
    "database": [
        "database",
        "sql",
        "nosql",
        "data warehouse",
        "data lake",
        "snowflake",
        "databricks",
        "oracle database",
        "sql server",
        "postgresql",
        "mongodb",
        "redis",
        "elasticsearch",
        "bigquery",
        "redshift",
    ],
    "devops": [
        "devops",
        "ci/cd",
        "jenkins",
        "gitlab",
        "github",
        "bitbucket",
        "terraform",
        "ansible",
        "docker",
        "development",
        "ide",
        "code",
    ],
}

# Tailwind color classes for each domain
DOMAIN_COLORS = {
    "blue": {"bg": "bg-blue - 100", "text": "text-blue - 800", "border": "border-blue - 200"},
    "green": {"bg": "bg-green - 100", "text": "text-green - 800", "border": "border-green - 200"},
    "purple": {
        "bg": "bg-purple - 100",
        "text": "text-purple - 800",
        "border": "border-purple - 200",
    },
    "orange": {
        "bg": "bg-orange - 100",
        "text": "text-orange - 800",
        "border": "border-orange - 200",
    },
    "cyan": {"bg": "bg-cyan - 100", "text": "text-cyan - 800", "border": "border-cyan - 200"},
    "indigo": {
        "bg": "bg-indigo - 100",
        "text": "text-indigo - 800",
        "border": "border-indigo - 200",
    },
    "slate": {"bg": "bg-slate - 100", "text": "text-slate - 800", "border": "border-slate - 200"},
    "red": {"bg": "bg-red - 100", "text": "text-red - 800", "border": "border-red - 200"},
    "yellow": {
        "bg": "bg-yellow - 100",
        "text": "text-yellow - 800",
        "border": "border-yellow - 200",
    },
    "pink": {"bg": "bg-pink - 100", "text": "text-pink - 800", "border": "border-pink - 200"},
    "teal": {"bg": "bg-teal - 100", "text": "text-teal - 800", "border": "border-teal - 200"},
    "amber": {"bg": "bg-amber - 100", "text": "text-amber - 800", "border": "border-amber - 200"},
    "rose": {"bg": "bg-rose - 100", "text": "text-rose - 800", "border": "border-rose - 200"},
    "sky": {"bg": "bg-sky - 100", "text": "text-sky - 800", "border": "border-sky - 200"},
    "emerald": {
        "bg": "bg-emerald - 100",
        "text": "text-emerald - 800",
        "border": "border-emerald - 200",
    },
    "violet": {
        "bg": "bg-violet - 100",
        "text": "text-violet - 800",
        "border": "border-violet - 200",
    },
    "gray": {"bg": "bg-gray - 100", "text": "text-gray - 800", "border": "border-gray - 200"},
}


def get_domain_label(domain_key: str) -> str:
    """Get the short display label for a domain key."""
    if not domain_key:
        return "Unknown"
    domain = VENDOR_DOMAINS.get(domain_key.lower())
    return domain["label"] if domain else domain_key.title()


def get_domain_full_name(domain_key: str) -> str:
    """Get the full name for a domain key."""
    if not domain_key:
        return "Unknown"
    domain = VENDOR_DOMAINS.get(domain_key.lower())
    return domain["full_name"] if domain else domain_key.title()


def get_domain_color_classes(domain_key: str) -> dict:
    """Get Tailwind color classes for a domain."""
    if not domain_key:
        return DOMAIN_COLORS["gray"]
    domain = VENDOR_DOMAINS.get(domain_key.lower())
    if domain:
        color = domain.get("color", "gray")
        return DOMAIN_COLORS.get(color, DOMAIN_COLORS["gray"])
    return DOMAIN_COLORS["gray"]


def get_domain_choices() -> list:
    """Get domain choices for form select fields.

    Returns:
        List of tuples: [(key, "LABEL - Full Name"), ...]
    """
    choices = [("", "-- Select Domain --")]
    for key, domain in VENDOR_DOMAINS.items():
        if key != "other":  # Put 'other' at the end
            choices.append((key, f"{domain['label']} - {domain['full_name']}"))
    choices.append(
        ("other", f"{VENDOR_DOMAINS['other']['label']} - {VENDOR_DOMAINS['other']['full_name']}")
    )
    return choices


def get_domain_filter_choices() -> list:
    """Get domain choices for filter dropdowns (includes 'All' option).

    Returns:
        List of tuples: [('all', 'All Domains'), (key, "LABEL"), ...]
    """
    choices = [("all", "All Domains")]
    for key, domain in VENDOR_DOMAINS.items():
        choices.append((key, domain["label"]))
    return choices


def auto_categorize_domain(text: str) -> str:
    """Attempt to auto-categorize a domain based on text patterns.

    Args:
        text: Product name, description, or existing domain text

    Returns:
        Standardized domain key, or 'other' if no match found
    """
    if not text:
        return "other"

    text_lower = text.lower()

    for domain_key, patterns in DOMAIN_MAPPING_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                return domain_key

    return "other"


def normalize_domain(domain_value: str) -> str:
    """Normalize a domain value to a standard key.

    Args:
        domain_value: Raw domain value from database

    Returns:
        Standardized domain key
    """
    if not domain_value:
        return "other"

    # Check if already a valid key
    if domain_value.lower() in VENDOR_DOMAINS:
        return domain_value.lower()

    # Try auto-categorization
    return auto_categorize_domain(domain_value)
