"""Searchable registry of available connectors with metadata.

Provides a catalog of supported external system connectors and
keyword-based suggestion matching against architecture tech stacks.
"""

CONNECTOR_CATALOG = [
    {
        "type": "salesforce",
        "name": "Salesforce",
        "category": "crm",
        "auth_type": "oauth2",
        "objects": ["Account", "Contact", "Opportunity", "Case", "Lead"],
        "setup_fields": ["instance_url", "client_id", "client_secret"],
        "logo_url": "/static/img/connectors/salesforce.svg",
        "setup_guide": "Create a Connected App in Salesforce Setup > App Manager. Enable OAuth with 'api' and 'refresh_token' scopes. Copy the Consumer Key (client_id) and Consumer Secret (client_secret). Your instance URL is https://yourorg.my.salesforce.com.",
    },
    {
        "type": "sap",
        "name": "SAP S/4HANA",
        "category": "erp",
        "auth_type": "basic",
        "objects": ["BusinessPartner", "SalesOrder", "Material", "CostCenter"],
        "setup_fields": ["server_url", "client", "username", "password"],
        "logo_url": "/static/img/connectors/sap.svg",
        "setup_guide": "Use the SAP S/4HANA OData API base URL (e.g. https://host:port/sap/opu/odata/sap/). Provide the SAP client number (typically 100 or 800), and a service account with RFC authorization.",
    },
    {
        "type": "servicenow",
        "name": "ServiceNow",
        "category": "itsm",
        "auth_type": "oauth2",
        "objects": ["incident", "cmdb_ci_service", "cmdb_ci_application"],
        "setup_fields": ["instance_url", "client_id", "client_secret"],
        "logo_url": "/static/img/connectors/servicenow.svg",
        "setup_guide": "In ServiceNow, navigate to System OAuth > Application Registry. Create an OAuth API endpoint for external clients. Your instance URL is https://yourinstance.service-now.com.",
    },
    {
        "type": "jira",
        "name": "Jira",
        "category": "project",
        "auth_type": "api_key",
        "objects": ["Issue", "Project", "Sprint", "Board"],
        "setup_fields": ["base_url", "email", "api_token"],
        "logo_url": "/static/img/connectors/jira.svg",
        "setup_guide": "Go to https://id.atlassian.com/manage-profile/security/api-tokens and create an API token. Use your Atlassian email and this token for authentication. Base URL is https://yourorg.atlassian.net.",
    },
    {
        "type": "sharepoint",
        "name": "SharePoint",
        "category": "collaboration",
        "auth_type": "oauth2",
        "objects": ["List", "Document", "Site"],
        "setup_fields": ["tenant_id", "client_id", "client_secret"],
        "logo_url": "/static/img/connectors/sharepoint.svg",
        "setup_guide": "Register an app in Azure AD > App Registrations. Grant Sites.Read.All (or Sites.ReadWrite.All) permissions. Copy the Tenant ID, Application (client) ID, and create a client secret.",
    },
    {
        "type": "google_sheets",
        "name": "Google Sheets",
        "category": "data",
        "auth_type": "oauth2",
        "objects": ["Sheet"],
        "setup_fields": ["spreadsheet_id", "credentials_json"],
        "logo_url": "/static/img/connectors/google_sheets.svg",
        "setup_guide": "Create a service account in Google Cloud Console > IAM & Admin. Download the JSON key file. Share your spreadsheet with the service account email. The spreadsheet_id is in the URL: docs.google.com/spreadsheets/d/{spreadsheet_id}/edit.",
    },
    {
        "type": "postgresql",
        "name": "PostgreSQL",
        "category": "data",
        "auth_type": "basic",
        "objects": ["table"],
        "setup_fields": ["host", "port", "database", "username", "password"],
        "logo_url": "/static/img/connectors/postgresql.svg",
        "setup_guide": "Provide the PostgreSQL connection details. Ensure the user has SELECT permission on the tables you want to sync. Default port is 5432. Use SSL if connecting over the internet.",
    },
    {
        "type": "rest_api",
        "name": "REST API",
        "category": "generic",
        "auth_type": "api_key",
        "objects": ["endpoint"],
        "setup_fields": ["base_url", "auth_header", "auth_value"],
        "logo_url": "/static/img/connectors/rest_api.svg",
        "setup_guide": "Provide the base URL of the API. Set the auth_header to the name of the authentication header (e.g. 'Authorization') and auth_value to the full header value (e.g. 'Bearer your-token-here').",
    },
    {
        "type": "slack",
        "name": "Slack",
        "category": "messaging",
        "auth_type": "oauth2",
        "objects": ["Channel", "Message"],
        "setup_fields": ["bot_token", "channel_id"],
        "logo_url": "/static/img/connectors/slack.svg",
        "setup_guide": "Create a Slack App at https://api.slack.com/apps. Add Bot Token Scopes: chat:write, channels:read. Install to your workspace and copy the Bot User OAuth Token (xoxb-...).",
    },
    {
        "type": "microsoft_teams",
        "name": "Microsoft Teams",
        "category": "messaging",
        "auth_type": "oauth2",
        "objects": ["Channel", "Message"],
        "setup_fields": ["tenant_id", "client_id", "client_secret"],
        "logo_url": "/static/img/connectors/microsoft_teams.svg",
        "setup_guide": "Register an app in Azure AD > App Registrations. Grant ChannelMessage.Send and Channel.ReadBasic.All permissions. Copy the Tenant ID, Application (client) ID, and create a client secret.",
    },
]

_TECH_KEYWORDS = {
    "sap": ["sap", "s/4hana", "s4hana", "abap"],
    "salesforce": ["salesforce", "sfdc", "crm"],
    "servicenow": ["servicenow", "snow", "itsm"],
    "jira": ["jira", "atlassian"],
    "sharepoint": ["sharepoint", "microsoft 365"],
    "postgresql": ["postgres", "postgresql", "database"],
}


class ConnectorCatalogService:
    """Searchable connector catalog with architecture-aware suggestion."""

    def list_connectors(self) -> list[dict]:
        """Return all available connectors."""
        return CONNECTOR_CATALOG

    def suggest(self, tech_stacks: list[str]) -> list[dict]:
        """Match architecture tech stacks to connectors via keyword matching."""
        suggestions = []
        for connector in CONNECTOR_CATALOG:
            keywords = _TECH_KEYWORDS.get(connector["type"], [])
            for stack in tech_stacks:
                if any(kw in stack.lower() for kw in keywords):
                    suggestions.append(connector)
                    break
        return suggestions

    def get_connector(self, connector_type: str) -> dict | None:
        """Look up a single connector by type. Returns None if not found."""
        return next(
            (c for c in CONNECTOR_CATALOG if c["type"] == connector_type), None
        )
