"""
Platform-specific models for Salesforce, SAP, and Microsoft Dynamics 365.
Supports AI-powered code generation with platform-native LLM SDKs.
"""
from datetime import datetime

from .. import db


class PlatformType(db.Model):
    """Supported enterprise platforms."""

    __tablename__ = "platform_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # Salesforce, SAP, Dynamics365
    display_name = db.Column(db.String(100))
    description = db.Column(db.Text)
    primary_language = db.Column(db.String(50))  # Apex, ABAP, C#
    api_style = db.Column(db.String(50))  # REST, OData, RFC
    deployment_tool = db.Column(db.String(100))  # SFDX, SAP Transport, Solution Packager
    ai_sdk_name = db.Column(db.String(100))  # Einstein API, SAP AI Core, Azure OpenAI
    ai_sdk_docs_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    configurations = db.relationship(
        "PlatformConfiguration", backref="platform_type", lazy="dynamic"
    )
    pipelines = db.relationship(
        "GenerationPipeline",
        backref="target_platform",
        lazy="dynamic",
        foreign_keys="GenerationPipeline.platform_type_id",
        overlaps="platform_type",
    )

    def __repr__(self):
        return f"<PlatformType {self.name}>"


class PlatformConfiguration(db.Model):
    """Platform-specific configuration and credentials."""

    __tablename__ = "platform_configurations"

    id = db.Column(db.Integer, primary_key=True)
    platform_type_id = db.Column(db.Integer, db.ForeignKey("platform_types.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    # Connection settings (encrypted in production)
    instance_url = db.Column(db.String(500))  # Salesforce: https://myorg.salesforce.com
    username = db.Column(db.String(255))
    encrypted_password = db.Column(db.Text)  # Encrypted
    encrypted_token = db.Column(db.Text)  # API token, encrypted

    # Platform-specific settings (JSON)
    org_id = db.Column(db.String(100))  # Salesforce Org ID
    api_version = db.Column(db.String(20))  # Salesforce: v59.0, SAP: 2.0
    namespace_prefix = db.Column(db.String(50))  # Salesforce namespace
    sap_client = db.Column(db.String(10))  # SAP client number
    sap_system_id = db.Column(db.String(10))  # SAP SID
    dynamics_environment = db.Column(db.String(100))  # Dynamics environment URL

    # AI/LLM Configuration
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_model_name = db.Column(db.String(100))  # einstein-gpt, gpt - 4, etc.
    encrypted_ai_api_key = db.Column(db.Text)  # Encrypted
    ai_endpoint_url = db.Column(db.String(500))
    ai_settings = db.Column(db.Text)  # JSON: temperature, max_tokens, etc.

    # Status
    is_active = db.Column(db.Boolean, default=True)
    last_connection_test = db.Column(db.DateTime)
    connection_status = db.Column(db.String(20))  # success, failed, pending
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    created_by = db.relationship("User", backref="platform_configurations")

    def __repr__(self):
        return f"<PlatformConfiguration {self.name} ({self.platform_type.name if self.platform_type else 'N/A'})>"


class SalesforceConfigMetadata(db.Model):
    """Salesforce-specific configuration metadata (SObjects, Fields, Apex Classes)."""

    __tablename__ = "salesforce_config_metadata"

    id = db.Column(db.Integer, primary_key=True)
    configuration_id = db.Column(db.Integer, db.ForeignKey("platform_configurations.id"))

    # Metadata type
    metadata_type = db.Column(
        db.String(50)
    )  # CustomObject, CustomField, ApexClass, ApexTrigger, LWC
    api_name = db.Column(db.String(255))  # Account, MyCustomObject__c
    label = db.Column(db.String(255))

    # Object-specific
    object_type = db.Column(db.String(50))  # Standard, Custom
    fields_json = db.Column(db.Text)  # JSON array of fields
    relationships_json = db.Column(db.Text)  # JSON of relationships

    # Code-specific
    apex_code = db.Column(db.Text)  # Apex class/trigger code
    lwc_html = db.Column(db.Text)  # Lightning Web Component HTML
    lwc_js = db.Column(db.Text)  # Lightning Web Component JS
    lwc_css = db.Column(db.Text)  # Lightning Web Component CSS

    # Metadata
    last_synced = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    configuration = db.relationship("PlatformConfiguration", backref="salesforce_config_metadata")

    def __repr__(self):
        return f"<SalesforceConfigMetadata {self.api_name} ({self.metadata_type})>"


class SAPMetadata(db.Model):
    """SAP-specific metadata (Tables, Function Modules, Programs)."""

    __tablename__ = "sap_metadata"

    id = db.Column(db.Integer, primary_key=True)
    configuration_id = db.Column(db.Integer, db.ForeignKey("platform_configurations.id"))

    # Metadata type
    metadata_type = db.Column(db.String(50))  # Table, FunctionModule, Program, BAPI, UI5App
    technical_name = db.Column(db.String(255))  # MARA, BAPI_CUSTOMER_CREATE, Z_MY_REPORT
    description = db.Column(db.Text)

    # Table-specific
    table_category = db.Column(db.String(10))  # TRANSP, POOL, CLUSTER
    fields_json = db.Column(db.Text)  # JSON array of fields

    # Function Module / BAPI specific
    import_parameters = db.Column(db.Text)  # JSON
    export_parameters = db.Column(db.Text)  # JSON
    tables_parameters = db.Column(db.Text)  # JSON

    # ABAP Code
    abap_code = db.Column(db.Text)

    # UI5 - specific
    ui5_manifest = db.Column(db.Text)  # manifest.json
    ui5_controller = db.Column(db.Text)  # Controller.js
    ui5_view = db.Column(db.Text)  # View.xml

    # Metadata
    transport_request = db.Column(db.String(20))  # e.g., EH6K900123
    package_name = db.Column(db.String(30))
    last_synced = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    configuration = db.relationship("PlatformConfiguration", backref="sap_metadata")

    def __repr__(self):
        return f"<SAPMetadata {self.technical_name} ({self.metadata_type})>"


class DynamicsMetadata(db.Model):
    """Microsoft Dynamics 365 / Power Platform metadata."""

    __tablename__ = "dynamics_metadata"

    id = db.Column(db.Integer, primary_key=True)
    configuration_id = db.Column(db.Integer, db.ForeignKey("platform_configurations.id"))

    # Metadata type
    metadata_type = db.Column(db.String(50))  # Table, Plugin, Workflow, PowerApp, PowerAutomate
    logical_name = db.Column(db.String(255))  # account, cr5a3_customentity
    display_name = db.Column(db.String(255))
    schema_name = db.Column(db.String(255))  # Account, cr5a3_CustomEntity

    # Table/Entity specific
    entity_type = db.Column(db.String(50))  # Standard, Custom, Virtual
    columns_json = db.Column(db.Text)  # JSON array of columns/attributes
    relationships_json = db.Column(db.Text)  # JSON of relationships

    # Plugin specific
    plugin_assembly_name = db.Column(db.String(255))
    plugin_type_name = db.Column(db.String(255))
    plugin_code = db.Column(db.Text)  # C# code
    plugin_steps_json = db.Column(db.Text)  # JSON of plugin steps

    # Power Platform
    canvas_app_json = db.Column(db.Text)  # Power Apps canvas definition
    model_app_json = db.Column(db.Text)  # Model-driven app definition
    flow_definition = db.Column(db.Text)  # Power Automate flow JSON

    # Solution info
    solution_name = db.Column(db.String(255))
    solution_version = db.Column(db.String(50))
    publisher_prefix = db.Column(db.String(10))

    # Metadata
    last_synced = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    configuration = db.relationship("PlatformConfiguration", backref="dynamics_metadata")

    def __repr__(self):
        return f"<DynamicsMetadata {self.logical_name} ({self.metadata_type})>"


class PlatformAIInteraction(db.Model):
    """Track AI interactions for platform-specific code generation."""

    __tablename__ = "platform_ai_interactions"

    id = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey("generation_pipelines.id"))
    platform_type_id = db.Column(db.Integer, db.ForeignKey("platform_types.id"))
    configuration_id = db.Column(db.Integer, db.ForeignKey("platform_configurations.id"))

    # AI Request
    ai_provider = db.Column(db.String(50))  # Einstein, SAP_AI_Core, Azure_OpenAI
    model_name = db.Column(db.String(100))
    prompt_text = db.Column(db.Text)
    prompt_tokens = db.Column(db.Integer)

    # AI Response
    generated_code = db.Column(db.Text)
    code_language = db.Column(db.String(50))  # Apex, ABAP, C#
    completion_tokens = db.Column(db.Integer)
    total_tokens = db.Column(db.Integer)

    # Quality metrics
    code_quality_score = db.Column(db.Float)  # 0 - 100
    governor_limit_compliant = db.Column(db.Boolean)  # Salesforce-specific
    best_practices_score = db.Column(db.Float)  # 0 - 100
    security_scan_passed = db.Column(db.Boolean)

    # Metadata
    response_time_ms = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    pipeline = db.relationship("GenerationPipeline", backref="platform_ai_interactions")
    platform_type = db.relationship("PlatformType", backref="ai_interactions")
    configuration = db.relationship("PlatformConfiguration", backref="ai_interactions")

    def __repr__(self):
        return f"<PlatformAIInteraction {self.ai_provider} - {self.model_name}>"


# Extension to existing GenerationPipeline model
def extend_generation_pipeline():
    """
    This function documents the schema changes needed to GenerationPipeline.
    Add these columns via migration:
    """
    return """
    ALTER TABLE generation_pipelines ADD COLUMN platform_type_id INTEGER REFERENCES platform_types(id);
    ALTER TABLE generation_pipelines ADD COLUMN platform_configuration_id INTEGER REFERENCES platform_configurations(id);
    ALTER TABLE generation_pipelines ADD COLUMN deployment_package_path VARCHAR(500);  # Path to SFDX project, SAP transport, or Dynamics solution
    ALTER TABLE generation_pipelines ADD COLUMN platform_metadata_json TEXT;  # Platform-specific metadata
    """
