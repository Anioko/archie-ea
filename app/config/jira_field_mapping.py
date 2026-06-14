"""
Jira Push Field Mapping Configuration

Defines field mappings from A.R.C.I.E ApplicationComponent → Jira issue fields.
Implements 3-system authority model:
  - Abacus wins: asset identity fields (name, lifecycle, owners)
  - A.R.C.I.E wins: enrichment fields (TCO, rationalization, risk scores)
  - Jira wins: workflow fields (status, assignee, sprint)

Field transforms handle Jira-specific formats:
  - ADF (Atlassian Document Format) for description
  - Priority mapping (Critical → Highest)
  - Component mapping for business domains

Mirrors pattern from app/config/abacus_field_mapping.py.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class JiraFieldRule:
    """Defines a single field mapping rule for A.R.C.I.E → Jira push."""

    app_field: str
    jira_field: str
    jira_custom_field_id: Optional[str] = None
    transform: Optional[Callable] = None
    authority: str = "arcie"  # abacus | arcie | jira
    required: bool = False
    description: str = ""


# =============================================================================
# TRANSFORM FUNCTIONS
# =============================================================================


def to_adf_description(value: Any) -> Optional[Dict]:
    """Convert plain text description to Atlassian Document Format (ADF).

    ADF is required by Jira Cloud REST API v3 for the description field.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    return {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def map_priority(value: Any) -> Optional[Dict]:
    """Map A.R.C.I.E criticality to Jira priority.

    Returns Jira priority object with name field.
    """
    if not value:
        return None
    mapping = {
        "Critical": "Highest",
        "High": "High",
        "Medium": "Medium",
        "Low": "Low",
    }
    priority_name = mapping.get(str(value).strip(), "Medium")
    return {"name": priority_name}


def map_lifecycle_to_labels(value: Any) -> Optional[List[str]]:
    """Map lifecycle status to Jira labels for filtering."""
    if not value:
        return None
    status = str(value).strip().lower()
    labels = [f"lifecycle:{status}"]
    if status in ("deprecated", "retired"):
        labels.append("sunset-candidate")
    return labels


def to_plain_string(value: Any) -> Optional[str]:
    """Ensure value is a clean string or None."""
    if not value:
        return None
    result = str(value).strip()
    return result if result else None


def to_json_string(value: Any) -> Optional[str]:
    """Convert dict/list to JSON string for text custom fields."""
    if not value:
        return None
    if isinstance(value, (dict, list)):
        import json
        return json.dumps(value)
    return str(value).strip() or None


# =============================================================================
# FIELD MAPPINGS — A.R.C.I.E → Jira
# =============================================================================

JIRA_FIELD_MAPPINGS: List[JiraFieldRule] = [
    # --- Core identity (Abacus authoritative) ---
    JiraFieldRule(
        app_field="name",
        jira_field="summary",
        required=True,
        authority="abacus",
        transform=to_plain_string,
        description="Application name → Jira issue summary",
    ),
    JiraFieldRule(
        app_field="description",
        jira_field="description",
        authority="abacus",
        transform=to_adf_description,
        description="Application description → ADF format description",
    ),
    # --- Priority mapping ---
    JiraFieldRule(
        app_field="business_criticality",
        jira_field="priority",
        authority="arcie",
        transform=map_priority,
        description="Business criticality → Jira priority (Critical→Highest, High→High, etc.)",
    ),
    # --- Labels (lifecycle) ---
    JiraFieldRule(
        app_field="lifecycle_status",
        jira_field="labels",
        authority="abacus",
        transform=map_lifecycle_to_labels,
        description="Lifecycle status → Jira labels for filtering",
    ),
    # --- Ownership (custom fields — IDs discovered at runtime) ---
    JiraFieldRule(
        app_field="business_owner",
        jira_field="customfield_business_owner",
        authority="abacus",
        transform=to_plain_string,
        description="Business owner → Jira custom field",
    ),
    JiraFieldRule(
        app_field="technical_owner",
        jira_field="customfield_technical_owner",
        authority="abacus",
        transform=to_plain_string,
        description="Technical owner → Jira custom field",
    ),
    # --- Technology context ---
    JiraFieldRule(
        app_field="vendor_name",
        jira_field="customfield_vendor",
        authority="arcie",
        transform=to_plain_string,
        description="Vendor name → Jira custom field",
    ),
    JiraFieldRule(
        app_field="technology_stack",
        jira_field="customfield_technology_stack",
        authority="arcie",
        transform=to_json_string,
        description="Technology stack → Jira custom field (JSON string)",
    ),
    # --- Business context ---
    JiraFieldRule(
        app_field="business_domain",
        jira_field="_component",
        authority="abacus",
        transform=to_plain_string,
        description="Business domain → Jira component (mapped separately)",
    ),
    JiraFieldRule(
        app_field="country",
        jira_field="customfield_country",
        authority="abacus",
        transform=to_plain_string,
        description="Country → Jira custom field",
    ),
    JiraFieldRule(
        app_field="business_unit",
        jira_field="customfield_business_unit",
        authority="abacus",
        transform=to_plain_string,
        description="Business unit → Jira custom field",
    ),
    # --- A.R.C.I.E enrichment fields ---
    JiraFieldRule(
        app_field="total_cost_of_ownership",
        jira_field="customfield_tco",
        authority="arcie",
        transform=to_plain_string,
        description="TCO → Jira custom field",
    ),
    JiraFieldRule(
        app_field="rationalization_score",
        jira_field="customfield_rationalization_score",
        authority="arcie",
        transform=to_plain_string,
        description="Rationalization score → Jira custom field",
    ),
    JiraFieldRule(
        app_field="deployment_status",
        jira_field="customfield_deployment_status",
        authority="abacus",
        transform=to_plain_string,
        description="Deployment status → Jira custom field",
    ),
    JiraFieldRule(
        app_field="external_id",
        jira_field="customfield_abacus_eeid",
        authority="abacus",
        transform=to_plain_string,
        description="Abacus EEID for cross-reference",
    ),
]


# =============================================================================
# CONFLICT RESOLUTION — 3-system authority
# =============================================================================

CONFLICT_RESOLUTION = {
    "abacus_wins": [
        "name", "description", "lifecycle_status", "deployment_status",
        "business_owner", "technical_owner", "country", "business_unit",
        "business_domain", "external_id",
    ],
    "arcie_wins": [
        "business_criticality", "total_cost_of_ownership",
        "rationalization_score", "vendor_name", "technology_stack",
    ],
    "jira_wins": [
        "status", "assignee", "sprint", "resolution",
    ],
}


# =============================================================================
# CUSTOM FIELD DISCOVERY MAPPING
# =============================================================================
# Maps logical field names to actual Jira custom field IDs.
# Updated at runtime via discover_fields() API call.

DEFAULT_CUSTOM_FIELD_MAP: Dict[str, str] = {
    "customfield_business_owner": "",
    "customfield_technical_owner": "",
    "customfield_vendor": "",
    "customfield_technology_stack": "",
    "customfield_country": "",
    "customfield_business_unit": "",
    "customfield_tco": "",
    "customfield_rationalization_score": "",
    "customfield_deployment_status": "",
    "customfield_abacus_eeid": "",
}


def get_jira_field_mappings() -> List[JiraFieldRule]:
    """Get all Jira field mappings."""
    return JIRA_FIELD_MAPPINGS


def resolve_authority(field_name: str) -> str:
    """Determine which system is authoritative for a given field.

    Returns:
        'abacus', 'arcie', or 'jira'
    """
    for authority, fields in CONFLICT_RESOLUTION.items():
        if field_name in fields:
            return authority.replace("_wins", "")
    return "arcie"
