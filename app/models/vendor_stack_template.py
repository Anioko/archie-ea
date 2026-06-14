"""
Vendor Technology Stack Template Model

Stores pre-configured vendor technology stack templates that can be used
when LLM analysis is unavailable. These templates cover all ArchiMate 3.2
layers and all required form fields.

CRITICAL: This replaces hardcoded fallback data with database-driven templates.

EXTENDED: Includes hierarchical decomposition for EA/SA intelligence:
- Capability hierarchy (L0 - L4)
- Service catalog with hierarchy and contracts
- Integration architecture catalog
- Comprehensive cost models
- Security & compliance framework
- Solution architecture patterns
"""
from datetime import datetime

from app import db
from app.models.mixins import TenantMixin


class VendorStackTemplate(TenantMixin, db.Model):
    """
    Pre-configured vendor technology stack templates for when LLM is unavailable.
    Covers ALL ArchiMate 3.2 layers and form fields.
    """

    __tablename__ = "vendor_stack_templates"

    id = db.Column(db.Integer, primary_key=True)
    vendor_name = db.Column(db.String(100), nullable=False, unique=True, index=True)

    # Basic Information
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # ==================== TECHNOLOGY LAYER (Primary Form Fields) ====================
    platform = db.Column(db.String(50))
    primary_language = db.Column(db.String(50))
    framework = db.Column(db.String(100))
    framework_version = db.Column(db.String(20))
    primary_database = db.Column(db.String(50))
    database_version = db.Column(db.String(20))
    container_runtime = db.Column(db.String(50))
    orchestration = db.Column(db.String(50))
    service_mesh = db.Column(db.String(50))
    api_standard = db.Column(db.String(50))
    api_gateway = db.Column(db.String(50))
    message_broker = db.Column(db.String(50))
    auth_provider = db.Column(db.String(50))
    secrets_manager = db.Column(db.String(50))
    logging_framework = db.Column(db.String(50))
    metrics_platform = db.Column(db.String(50))
    apm_tool = db.Column(db.String(50))
    tracing_tool = db.Column(db.String(50))
    build_tool = db.Column(db.String(50))
    ci_cd_platform = db.Column(db.String(50))
    sast_tool = db.Column(db.String(50))
    dast_tool = db.Column(db.String(50))
    dependency_scanner = db.Column(db.String(50))

    # Additional Technology Layer Fields (JSON for ArchiMate elements)
    nodes = db.Column(db.Text)  # JSON: [{name, type, os, cpu_cores, ram_gb}]
    devices = db.Column(db.Text)  # JSON: [{name, type, description}]
    system_software = db.Column(db.Text)  # JSON: [{name, type, version}]
    technology_services = db.Column(db.Text)  # JSON: [{name, type, description}]
    artifacts = db.Column(db.Text)  # JSON: [{name, type, size_mb, registry}]
    communication_networks = db.Column(db.Text)  # JSON: [{name, type, bandwidth_mbps, latency_ms}]

    # ==================== VENDOR CONTEXT ====================
    vendor_company_name = db.Column(db.String(200))
    market_position = db.Column(db.String(50))  # leader/challenger/niche/emerging
    company_size = db.Column(db.String(50))  # enterprise/mid-market/startup
    founded_year = db.Column(db.Integer)
    headquarters = db.Column(db.String(100))
    revenue_usd = db.Column(db.BigInteger)
    customer_count = db.Column(db.Integer)
    market_share_percentage = db.Column(db.Float)
    acquisition_risk = db.Column(db.String(20))  # low/medium/high
    financial_health = db.Column(db.String(20))  # strong/stable/concerning

    # ==================== STRATEGY LAYER ====================
    capabilities_enabled = db.Column(
        db.Text
    )  # JSON: [{name, description, coverage_percentage, maturity_level}]
    value_streams_supported = db.Column(db.Text)  # JSON: [{name, stages, description}]
    courses_of_action = db.Column(
        db.Text
    )  # JSON: [{name, description, timeline_months, risk_level}]

    # ==================== BUSINESS LAYER ====================
    business_services = db.Column(
        db.Text
    )  # JSON: [{name, description, service_type, sla_commitment}]
    business_processes = db.Column(
        db.Text
    )  # JSON: [{name, description, automation_level, steps, cycle_time, kpis}]
    business_objects = db.Column(db.Text)  # JSON: [{name, description, lifecycle}]
    business_actors = db.Column(db.Text)  # JSON: [{name, description, responsibilities}]
    products = db.Column(db.Text)  # JSON: [{name, description, target_market}]

    # ==================== APPLICATION LAYER ====================
    application_components = db.Column(db.Text)  # JSON: [{name, type, description, technology}]
    application_services = db.Column(db.Text)  # JSON: [{name, type, description, endpoints}]
    application_interfaces = db.Column(
        db.Text
    )  # JSON: [{name, protocol, data_format, authentication}]
    data_objects = db.Column(db.Text)  # JSON: [{name, type, retention_policy}]
    application_functions = db.Column(db.Text)  # JSON: [{name, type, description}]

    # ==================== MOTIVATION LAYER ====================

    def instantiate_as_technology_stack(self, name=None, description=None, **overrides):
        """
        Create a TechnologyStack instance from this template.

        This enables:
        1. Semantic separation: Template = reference architecture, Instance = actual vendor
        2. EA intelligence: Instance links back to template for ArchiMate layers
        3. Customization: Override specific fields while inheriting template structure

        Args:
            name: Custom name for the instance (defaults to template name)
            description: Custom description (defaults to template description)
            **overrides: Any TechnologyStack fields to override from template

        Returns:
            TechnologyStack instance (not yet saved to DB)
        """
        from app.models.models import TechnologyStack

        # Create instance with template data
        instance = TechnologyStack(
            name=name or self.name,
            description=description or self.description,
            vendor_template_id=self.id,
            # Technology Layer fields
            platform=overrides.get("platform", self.platform),
            primary_language=overrides.get("primary_language", self.primary_language),
            framework=overrides.get("framework", self.framework),
            framework_version=overrides.get("framework_version", self.framework_version),
            primary_database=overrides.get("primary_database", self.primary_database),
            database_version=overrides.get("database_version", self.database_version),
            container_runtime=overrides.get("container_runtime", self.container_runtime),
            orchestration=overrides.get("orchestration", self.orchestration),
            service_mesh=overrides.get("service_mesh", self.service_mesh),
            api_standard=overrides.get("api_standard", self.api_standard),
            api_gateway=overrides.get("api_gateway", self.api_gateway),
            message_broker=overrides.get("message_broker", self.message_broker),
            auth_provider=overrides.get("auth_provider", self.auth_provider),
            secrets_manager=overrides.get("secrets_manager", self.secrets_manager),
            logging_framework=overrides.get("logging_framework", self.logging_framework),
            metrics_platform=overrides.get("metrics_platform", self.metrics_platform),
            apm_tool=overrides.get("apm_tool", self.apm_tool),
            tracing_tool=overrides.get("tracing_tool", self.tracing_tool),
            build_tool=overrides.get("build_tool", self.build_tool),
            ci_cd_platform=overrides.get("ci_cd_platform", self.ci_cd_platform),
            sast_tool=overrides.get("sast_tool", self.sast_tool),
            dast_tool=overrides.get("dast_tool", self.dast_tool),
            dependency_scanner=overrides.get("dependency_scanner", self.dependency_scanner),
            # Approval status
            approval_status=overrides.get("approval_status", "draft"),
        )

        return instance

    def get_archimate_intelligence(self):
        """
        Extract enterprise architecture intelligence from this template.

        Returns dict with parsed ArchiMate layers for EA analysis:
        - Strategy Layer: capabilities, value streams, courses of action
        - Business Layer: services, processes, objects, actors, products
        - Application Layer: components, services, interfaces, data objects
        - Technology Layer: nodes, devices, software, services, artifacts
        - Integration: patterns, protocols, data formats
        - Costs: pricing models, TCO breakdown
        """
        import json

        return {
            "strategy": {
                "capabilities": json.loads(self.capabilities_enabled)
                if self.capabilities_enabled
                else [],
                "value_streams": json.loads(self.value_streams_supported)
                if self.value_streams_supported
                else [],
                "courses_of_action": json.loads(self.courses_of_action)
                if self.courses_of_action
                else [],
            },
            "business": {
                "services": json.loads(self.business_services) if self.business_services else [],
                "processes": json.loads(self.business_processes) if self.business_processes else [],
                "objects": json.loads(self.business_objects) if self.business_objects else [],
                "actors": json.loads(self.business_actors) if self.business_actors else [],
                "products": json.loads(self.products) if self.products else [],
            },
            "application": {
                "components": json.loads(self.application_components)
                if self.application_components
                else [],
                "services": json.loads(self.application_services)
                if self.application_services
                else [],
                "interfaces": json.loads(self.application_interfaces)
                if self.application_interfaces
                else [],
                "data_objects": json.loads(self.data_objects) if self.data_objects else [],
                "functions": json.loads(self.application_functions)
                if self.application_functions
                else [],
            },
            "technology": {
                "nodes": json.loads(self.nodes) if self.nodes else [],
                "devices": json.loads(self.devices) if self.devices else [],
                "system_software": json.loads(self.system_software) if self.system_software else [],
                "services": json.loads(self.technology_services)
                if self.technology_services
                else [],
                "artifacts": json.loads(self.artifacts) if self.artifacts else [],
                "networks": json.loads(self.communication_networks)
                if self.communication_networks
                else [],
            },
            "integration": {
                "patterns": json.loads(self.integration_patterns)
                if self.integration_patterns
                else []
            },
            "costs": {
                "pricing_models": json.loads(self.pricing_models) if self.pricing_models else []
            },
            "vendor_context": {
                "company_name": self.vendor_company_name,
                "market_position": self.market_position,
                "company_size": self.company_size,
                "founded_year": self.founded_year,
                "headquarters": self.headquarters,
            },
        }

    stakeholders = db.Column(db.Text)  # JSON: [{name, type, concerns, influence}]
    drivers = db.Column(db.Text)  # JSON: [{name, type, description, urgency}]
    goals = db.Column(db.Text)  # JSON: [{name, type, target_date, success_criteria}]
    outcomes = db.Column(db.Text)  # JSON: [{name, type, measurement}]
    principles = db.Column(db.Text)  # JSON: [{name, statement, rationale}]
    requirements = db.Column(db.Text)  # JSON: [{id, name, type, description, priority}]
    constraints = db.Column(db.Text)  # JSON: [{name, type, description, impact}]
    assessments = db.Column(
        db.Text
    )  # JSON: [{type, strengths, weaknesses, opportunities, threats, overall_score}]

    # ==================== IMPLEMENTATION & MIGRATION LAYER ====================
    implementation_events = db.Column(db.Text)  # JSON: [{name, date, description, deliverables}]
    work_packages = db.Column(
        db.Text
    )  # JSON: [{name, description, duration_weeks, dependencies, resources}]
    deliverables = db.Column(db.Text)  # JSON: [{name, type, description, due_date}]
    plateaus = db.Column(db.Text)  # JSON: [{name, description, target_date, outcomes}]
    gaps = db.Column(db.Text)  # JSON: [{name, description, impact, remediation_plan}]

    # ==================== PHYSICAL LAYER ====================
    physical_elements = db.Column(db.Text)  # JSON: [{name, type, location, description}]
    facilities = db.Column(db.Text)  # JSON: [{name, type, location, capacity}]
    equipment = db.Column(db.Text)  # JSON: [{name, type, specifications, location}]
    materials = db.Column(db.Text)  # JSON: [{name, type, description, quantity}]
    distribution_networks = db.Column(db.Text)  # JSON: [{name, type, locations, capacity}]

    # ==================== RELATIONSHIPS ====================
    relationships = db.Column(
        db.Text
    )  # JSON: [{source_type, source_name, target_type, target_name, relationship_type}]

    # ==================== SOLUTION ARCHITECTURE PATTERNS ====================
    reference_architectures = db.Column(
        db.Text
    )  # JSON: [{name, industry, description, diagram_url, use_cases}]
    deployment_topologies = db.Column(
        db.Text
    )  # JSON: [{type, description, infrastructure_requirements, pros, cons}]
    scaling_patterns = db.Column(
        db.Text
    )  # JSON: [{pattern_type, description, triggers, limits, cost_implications}]
    disaster_recovery = db.Column(
        db.Text
    )  # JSON: {rpo_hours, rto_hours, backup_frequency, failover_mechanism, geo_redundancy}
    performance_characteristics = db.Column(
        db.Text
    )  # JSON: {response_time_ms, throughput_tps, concurrency_limit, latency_p95_ms, latency_p99_ms}
    extensibility_models = db.Column(
        db.Text
    )  # JSON: [{extension_type, description, custom_code_support, marketplace_apps, api_extensibility}]
    migration_patterns = db.Column(
        db.Text
    )  # JSON: [{pattern_name, approach, duration_weeks, risk_level, rollback_strategy, data_migration_tools}]

    # ==================== DATA ARCHITECTURE ====================
    data_domains = db.Column(
        db.Text
    )  # JSON: [{domain_name, description, entity_count, volume_gb, growth_rate_annual}]
    data_models = db.Column(
        db.Text
    )  # JSON: [{model_type, entities, relationships, normalization_level}]
    data_lineage = db.Column(
        db.Text
    )  # JSON: [{source_system, transformations, target_system, frequency, data_quality_rules}]
    data_quality_rules = db.Column(
        db.Text
    )  # JSON: [{rule_type, description, threshold, validation_frequency}]
    data_governance = db.Column(
        db.Text
    )  # JSON: [{data_classification, data_owner, data_steward, retention_policy, privacy_requirements}]
    master_data_management = db.Column(
        db.Text
    )  # JSON: [{mdm_domain, golden_record_strategy, matching_rules, survivorship_rules}]
    reference_data = db.Column(
        db.Text
    )  # JSON: [{ref_data_type, code_tables, taxonomies, hierarchies}]
    data_volumes = db.Column(
        db.Text
    )  # JSON: [{entity_name, record_count, growth_rate_monthly, storage_gb, archive_policy}]
    data_access_patterns = db.Column(
        db.Text
    )  # JSON: [{pattern_type, read_write_ratio, query_patterns, indexing_strategy, caching_strategy}]

    # ==================== INTEGRATION ARCHITECTURE ====================
    integration_patterns = db.Column(
        db.Text
    )  # JSON: [{pattern_name, description, use_cases, pros, cons}]
    integration_styles = db.Column(
        db.Text
    )  # JSON: [{style, protocols, latency, throughput, reliability}]
    integration_protocols = db.Column(
        db.Text
    )  # JSON: [{protocol, version, use_case, security, performance}]
    pre_built_connectors = db.Column(
        db.Text
    )  # JSON: [{target_system, connector_type, bi_directional, certification_level, cost}]
    data_transformation = db.Column(
        db.Text
    )  # JSON: [{transformation_type, mapping_rules, format_conversions, enrichment_logic}]
    integration_security = db.Column(
        db.Text
    )  # JSON: [{auth_method, encryption, token_management, certificate_requirements}]
    integration_governance = db.Column(
        db.Text
    )  # JSON: {api_catalog_url, versioning_policy, deprecation_policy, lifecycle_stages}
    integration_monitoring = db.Column(
        db.Text
    )  # JSON: [{metric, threshold, alert_severity, sla_target}]
    integration_resilience = db.Column(
        db.Text
    )  # JSON: [{mechanism, retry_policy, dlq_strategy, circuit_breaker_config}]
    integration_costs = db.Column(
        db.Text
    )  # JSON: [{cost_type, pricing_model, rate, overage_charges}]

    # ==================== SECURITY & COMPLIANCE FRAMEWORK ====================
    compliance_certifications = db.Column(
        db.Text
    )  # JSON: [{certification, issuing_body, valid_until, scope, audit_frequency}]
    data_residency = db.Column(
        db.Text
    )  # JSON: [{region, data_centers, cross_border_restrictions, sovereignty_compliance}]
    encryption_standards = db.Column(
        db.Text
    )  # JSON: [{encryption_type, algorithm, key_length, key_management, rotation_policy}]
    access_control_models = db.Column(
        db.Text
    )  # JSON: [{model_type, granularity, delegation_support, audit_capability}]
    authentication_methods = db.Column(
        db.Text
    )  # JSON: [{method, protocols, mfa_support, passwordless_options, session_management}]
    audit_capabilities = db.Column(
        db.Text
    )  # JSON: {retention_period_days, tamper_proof, export_formats, real_time_monitoring, forensic_support}
    vulnerability_management = db.Column(
        db.Text
    )  # JSON: {pentest_frequency, bug_bounty, cve_disclosure_sla, patch_cycle_days}
    incident_response = db.Column(
        db.Text
    )  # JSON: {mttr_hours, breach_notification_sla_hours, incident_history, playbooks}
    data_privacy = db.Column(
        db.Text
    )  # JSON: [{privacy_feature, gdpr_compliant, ccpa_compliant, right_to_erasure, data_portability, consent_management}]
    third_party_risk = db.Column(
        db.Text
    )  # JSON: [{subprocessor_name, location, services_provided, security_assessment_date, risk_level}]

    # ==================== COMPREHENSIVE COST MODEL ====================
    pricing_models = db.Column(
        db.Text
    )  # JSON: [{model_name, unit, base_price, minimum_commitment, contract_term_months}]
    cost_components = db.Column(
        db.Text
    )  # JSON: [{component, description, cost_category, monthly_cost, annual_cost, variable_costs}]
    hidden_costs = db.Column(
        db.Text
    )  # JSON: [{cost_type, description, estimated_amount, frequency, avoidability}]
    tco_analysis = db.Column(
        db.Text
    )  # JSON: {year_1, year_2, year_3, year_4, year_5, total_tco, maintenance_costs, upgrade_costs}
    roi_metrics = db.Column(
        db.Text
    )  # JSON: {payback_period_months, npv, irr_percentage, cost_benefit_ratio, productivity_gains}
    cost_optimization = db.Column(
        db.Text
    )  # JSON: [{optimization_type, potential_savings_percentage, implementation_effort, recommendation}]
    exit_costs = db.Column(
        db.Text
    )  # JSON: {data_export_fee, termination_penalty, switching_cost, knowledge_transfer_cost}

    # ==================== VENDOR RISK ASSESSMENT ====================
    market_risks = db.Column(
        db.Text
    )  # JSON: {gartner_position, forrester_ranking, market_share_trend, consolidation_risk, competitive_threats}
    technology_risks = db.Column(
        db.Text
    )  # JSON: {technical_debt_level, eol_products, modernization_roadmap, innovation_rate}
    operational_risks = db.Column(
        db.Text
    )  # JSON: {uptime_sla_percentage, mtbf_hours, mttr_hours, outage_history, dr_capability}
    strategic_risks = db.Column(
        db.Text
    )  # JSON: {product_strategy_alignment, ma_likelihood, strategic_fit_score}
    competitive_risks = db.Column(
        db.Text
    )  # JSON: [{alternative_vendor, switching_barrier_level, vendor_lockin_factors}]
    regulatory_risks = db.Column(
        db.Text
    )  # JSON: [{regulation, compliance_status, cross_border_risk, emerging_regulation_impact}]
    dependency_risks = db.Column(
        db.Text
    )  # JSON: [{dependency_type, spof_risk, mitigation_strategy, redundancy_options}]
    support_risks = db.Column(
        db.Text
    )  # JSON: {support_quality_score, response_time_sla_hours, escalation_levels, community_support}

    # ==================== ADDITIONAL METADATA ====================
    estimated_cost_per_month = db.Column(db.Integer)
    license_requirements = db.Column(db.Text)
    deployment_complexity = db.Column(db.String(20))  # low/medium/high
    learning_curve = db.Column(db.String(20))  # low/medium/high
    enterprise_adoption = db.Column(db.String(20))  # low/medium/high
    vendor_support = db.Column(db.String(50))  # basic/standard/premium/enterprise
    integration_capabilities = db.Column(db.Text)
    scalability_rating = db.Column(db.Integer)  # 1 - 10
    security_rating = db.Column(db.Integer)  # 1 - 10
    maturity_rating = db.Column(db.Integer)  # 1 - 10

    # System Fields
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    created_by = db.relationship(
        "User", foreign_keys=[created_by_id], backref="vendor_templates_created"
    )
    updated_by = db.relationship(
        "User", foreign_keys=[updated_by_id], backref="vendor_templates_updated"
    )

    def __repr__(self):
        return f"<VendorStackTemplate {self.vendor_name}>"

    def to_dict(self):
        """Convert template to dictionary format matching LLM response structure."""
        import json

        return {
            "name": self.name,
            "description": self.description,
            "vendor_context": {
                "vendor_name": self.vendor_company_name,
                "market_position": self.market_position,
                "company_size": self.company_size,
                "founded_year": self.founded_year,
                "headquarters": self.headquarters,
                "revenue_usd": self.revenue_usd,
                "customer_count": self.customer_count,
                "market_share_percentage": self.market_share_percentage,
                "acquisition_risk": self.acquisition_risk,
                "financial_health": self.financial_health,
            }
            if self.vendor_company_name
            else {},
            "strategy_layer": {
                "capabilities_enabled": json.loads(self.capabilities_enabled)
                if self.capabilities_enabled
                else [],
                "value_streams_supported": json.loads(self.value_streams_supported)
                if self.value_streams_supported
                else [],
                "courses_of_action": json.loads(self.courses_of_action)
                if self.courses_of_action
                else [],
            },
            "business_layer": {
                "business_services": json.loads(self.business_services)
                if self.business_services
                else [],
                "business_processes": json.loads(self.business_processes)
                if self.business_processes
                else [],
                "business_objects": json.loads(self.business_objects)
                if self.business_objects
                else [],
                "business_actors": json.loads(self.business_actors) if self.business_actors else [],
                "products": json.loads(self.products) if self.products else [],
            },
            "application_layer": {
                "application_components": json.loads(self.application_components)
                if self.application_components
                else [],
                "application_services": json.loads(self.application_services)
                if self.application_services
                else [],
                "application_interfaces": json.loads(self.application_interfaces)
                if self.application_interfaces
                else [],
                "data_objects": json.loads(self.data_objects) if self.data_objects else [],
                "application_functions": json.loads(self.application_functions)
                if self.application_functions
                else [],
            },
            "technology_layer": {
                "platform": self.platform,
                "primary_language": self.primary_language,
                "framework": self.framework,
                "framework_version": self.framework_version,
                "primary_database": self.primary_database,
                "database_version": self.database_version,
                "container_runtime": self.container_runtime,
                "orchestration": self.orchestration,
                "service_mesh": self.service_mesh,
                "nodes": json.loads(self.nodes) if self.nodes else [],
                "devices": json.loads(self.devices) if self.devices else [],
                "system_software": json.loads(self.system_software) if self.system_software else [],
                "technology_services": json.loads(self.technology_services)
                if self.technology_services
                else [],
                "artifacts": json.loads(self.artifacts) if self.artifacts else [],
                "communication_networks": json.loads(self.communication_networks)
                if self.communication_networks
                else [],
                "api_standard": self.api_standard,
                "api_gateway": self.api_gateway,
                "message_broker": self.message_broker,
                "auth_provider": self.auth_provider,
                "secrets_manager": self.secrets_manager,
                "logging_framework": self.logging_framework,
                "metrics_platform": self.metrics_platform,
                "apm_tool": self.apm_tool,
                "tracing_tool": self.tracing_tool,
                "build_tool": self.build_tool,
                "ci_cd_platform": self.ci_cd_platform,
                "sast_tool": self.sast_tool,
                "dast_tool": self.dast_tool,
                "dependency_scanner": self.dependency_scanner,
            },
            "motivation_layer": {
                "stakeholders": json.loads(self.stakeholders) if self.stakeholders else [],
                "drivers": json.loads(self.drivers) if self.drivers else [],
                "goals": json.loads(self.goals) if self.goals else [],
                "outcomes": json.loads(self.outcomes) if self.outcomes else [],
                "principles": json.loads(self.principles) if self.principles else [],
                "requirements": json.loads(self.requirements) if self.requirements else [],
                "constraints": json.loads(self.constraints) if self.constraints else [],
                "assessments": json.loads(self.assessments) if self.assessments else [],
            },
            "implementation_migration_layer": {
                "implementation_events": json.loads(self.implementation_events)
                if self.implementation_events
                else [],
                "work_packages": json.loads(self.work_packages) if self.work_packages else [],
                "deliverables": json.loads(self.deliverables) if self.deliverables else [],
                "plateaus": json.loads(self.plateaus) if self.plateaus else [],
                "gaps": json.loads(self.gaps) if self.gaps else [],
            },
            "physical_layer": {
                "physical_elements": json.loads(self.physical_elements)
                if self.physical_elements
                else [],
                "facilities": json.loads(self.facilities) if self.facilities else [],
                "equipment": json.loads(self.equipment) if self.equipment else [],
                "materials": json.loads(self.materials) if self.materials else [],
                "distribution_networks": json.loads(self.distribution_networks)
                if self.distribution_networks
                else [],
            },
            "relationships": json.loads(self.relationships) if self.relationships else [],
            "solution_architecture": {
                "reference_architectures": json.loads(self.reference_architectures)
                if self.reference_architectures
                else [],
                "deployment_topologies": json.loads(self.deployment_topologies)
                if self.deployment_topologies
                else [],
                "scaling_patterns": json.loads(self.scaling_patterns)
                if self.scaling_patterns
                else [],
                "disaster_recovery": json.loads(self.disaster_recovery)
                if self.disaster_recovery
                else {},
                "performance_characteristics": json.loads(self.performance_characteristics)
                if self.performance_characteristics
                else {},
                "extensibility_models": json.loads(self.extensibility_models)
                if self.extensibility_models
                else [],
                "migration_patterns": json.loads(self.migration_patterns)
                if self.migration_patterns
                else [],
            },
            "data_architecture": {
                "data_domains": json.loads(self.data_domains) if self.data_domains else [],
                "data_models": json.loads(self.data_models) if self.data_models else [],
                "data_lineage": json.loads(self.data_lineage) if self.data_lineage else [],
                "data_quality_rules": json.loads(self.data_quality_rules)
                if self.data_quality_rules
                else [],
                "data_governance": json.loads(self.data_governance) if self.data_governance else [],
                "master_data_management": json.loads(self.master_data_management)
                if self.master_data_management
                else [],
                "reference_data": json.loads(self.reference_data) if self.reference_data else [],
                "data_volumes": json.loads(self.data_volumes) if self.data_volumes else [],
                "data_access_patterns": json.loads(self.data_access_patterns)
                if self.data_access_patterns
                else [],
            },
            "integration_architecture": {
                "integration_patterns": json.loads(self.integration_patterns)
                if self.integration_patterns
                else [],
                "integration_styles": json.loads(self.integration_styles)
                if self.integration_styles
                else [],
                "integration_protocols": json.loads(self.integration_protocols)
                if self.integration_protocols
                else [],
                "pre_built_connectors": json.loads(self.pre_built_connectors)
                if self.pre_built_connectors
                else [],
                "data_transformation": json.loads(self.data_transformation)
                if self.data_transformation
                else [],
                "integration_security": json.loads(self.integration_security)
                if self.integration_security
                else [],
                "integration_governance": json.loads(self.integration_governance)
                if self.integration_governance
                else {},
                "integration_monitoring": json.loads(self.integration_monitoring)
                if self.integration_monitoring
                else [],
                "integration_resilience": json.loads(self.integration_resilience)
                if self.integration_resilience
                else [],
                "integration_costs": json.loads(self.integration_costs)
                if self.integration_costs
                else [],
            },
            "security_compliance": {
                "compliance_certifications": json.loads(self.compliance_certifications)
                if self.compliance_certifications
                else [],
                "data_residency": json.loads(self.data_residency) if self.data_residency else [],
                "encryption_standards": json.loads(self.encryption_standards)
                if self.encryption_standards
                else [],
                "access_control_models": json.loads(self.access_control_models)
                if self.access_control_models
                else [],
                "authentication_methods": json.loads(self.authentication_methods)
                if self.authentication_methods
                else [],
                "audit_capabilities": json.loads(self.audit_capabilities)
                if self.audit_capabilities
                else {},
                "vulnerability_management": json.loads(self.vulnerability_management)
                if self.vulnerability_management
                else {},
                "incident_response": json.loads(self.incident_response)
                if self.incident_response
                else {},
                "data_privacy": json.loads(self.data_privacy) if self.data_privacy else [],
                "third_party_risk": json.loads(self.third_party_risk)
                if self.third_party_risk
                else [],
            },
            "cost_model": {
                "pricing_models": json.loads(self.pricing_models) if self.pricing_models else [],
                "cost_components": json.loads(self.cost_components) if self.cost_components else [],
                "hidden_costs": json.loads(self.hidden_costs) if self.hidden_costs else [],
                "tco_analysis": json.loads(self.tco_analysis) if self.tco_analysis else {},
                "roi_metrics": json.loads(self.roi_metrics) if self.roi_metrics else {},
                "cost_optimization": json.loads(self.cost_optimization)
                if self.cost_optimization
                else [],
                "exit_costs": json.loads(self.exit_costs) if self.exit_costs else {},
            },
            "vendor_risk_assessment": {
                "market_risks": json.loads(self.market_risks) if self.market_risks else {},
                "technology_risks": json.loads(self.technology_risks)
                if self.technology_risks
                else {},
                "operational_risks": json.loads(self.operational_risks)
                if self.operational_risks
                else {},
                "strategic_risks": json.loads(self.strategic_risks) if self.strategic_risks else {},
                "competitive_risks": json.loads(self.competitive_risks)
                if self.competitive_risks
                else [],
                "regulatory_risks": json.loads(self.regulatory_risks)
                if self.regulatory_risks
                else [],
                "dependency_risks": json.loads(self.dependency_risks)
                if self.dependency_risks
                else [],
                "support_risks": json.loads(self.support_risks) if self.support_risks else {},
            },
            "estimated_cost_per_month": self.estimated_cost_per_month,
            "license_requirements": self.license_requirements,
            "deployment_complexity": self.deployment_complexity,
            "learning_curve": self.learning_curve,
            "enterprise_adoption": self.enterprise_adoption,
            "vendor_support": self.vendor_support,
            "integration_capabilities": self.integration_capabilities,
            "scalability_rating": self.scalability_rating,
            "security_rating": self.security_rating,
            "maturity_rating": self.maturity_rating,
            "_ai_analyzed": False,
            "_source_vendor": self.vendor_name,
            "_analysis_confidence": 100.0,
            "_template_based": True,
        }
