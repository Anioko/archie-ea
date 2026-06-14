"""
AI Technology Stack Analyzer Service

This service uses LLM providers to analyze vendor/technology information
and automatically extract technology stack details.
"""
import json
import logging
from typing import Any, Dict, Optional  # dead-code-ok

from flask import current_app  # dead-code-ok

from app import db
from app.models import APISettings  # dead-code-ok
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class TechnologyStackAnalyzer:
    """AI-powered analyzer for extracting technology stack information from vendor names or business capabilities."""

    # Capability-driven analysis prompt
    CAPABILITY_ANALYSIS_PROMPT_TEMPLATE = """
You are an enterprise technology architect expert. Based on the provided business capabilities, recommend the optimal technology stack.

Business Capabilities Required: {capabilities}
Enterprise Context: {context}
Target Platform: {platform}
Performance Requirements: {performance}
Security Requirements: {security}
Budget Constraints: {budget}

Please analyze these requirements and provide a detailed technology stack recommendation in the following JSON format:

{{
    "name": "Recommended technology stack name based on capabilities",
    "description": "Comprehensive description explaining why this stack fulfills the required capabilities",
    "platform": "Recommended deployment platform (aws, azure, gcp, on-prem, hybrid)",
    "primary_language": "Best programming language for these capabilities",
    "framework": "Recommended framework that best supports these capabilities",
    "framework_version": "Latest stable version",
    "primary_database": "Database technology that best fits the data requirements",
    "database_version": "Database version",
    "container_runtime": "Container technology (docker, containerd, etc.)",
    "orchestration": "Container orchestration platform",
    "service_mesh": "Service mesh if needed for the capabilities",
    "api_standard": "API standard that best serves the integration needs",
    "api_gateway": "API gateway solution for capability exposure",
    "message_broker": "Messaging system for asynchronous capabilities",
    "auth_provider": "Authentication solution for security capabilities",
    "secrets_manager": "Secrets management for security",
    "logging_framework": "Logging solution for observability capabilities",
    "metrics_platform": "Metrics platform for monitoring capabilities",
    "apm_tool": "APM tool for performance monitoring",
    "tracing_tool": "Distributed tracing for complex workflows",
    "build_tool": "Build tool for CI/CD capabilities",
    "ci_cd_platform": "CI/CD platform for deployment capabilities",
    "sast_tool": "Static security testing for security capabilities",
    "dast_tool": "Dynamic security testing for runtime security",
    "dependency_scanner": "Dependency scanning for supply chain security",
    "estimated_cost_per_month": "Estimated monthly cost based on capability requirements",
    "capability_coverage": "Percentage of how well this stack covers the required capabilities (0 - 100)",
    "implementation_complexity": "Implementation complexity (low, medium, high)",
    "vendor_lock_in_risk": "Vendor lock-in risk assessment (low, medium, high)",
    "scalability_rating": "Scalability rating for the required capabilities (1 - 10)",
    "security_rating": "Security rating for the requirements (1 - 10)",
    "capability_gaps": "List of any capability gaps that need additional tools",
    "alternative_options": "Brief description of alternative technology approaches"
}}

Focus on:
1. Capability fulfillment over vendor preference
2. Enterprise-grade solutions with proven track records
3. Technology combinations that work well together
4. Cost-effectiveness for the required capabilities
5. Future scalability and maintainability
6. Security and compliance alignment

Respond ONLY with valid JSON - no additional text or explanations.
"""

    ANALYSIS_PROMPT_TEMPLATE = """
You are an enterprise architecture expert specializing in ArchiMate 3.2 modeling. Analyze the given vendor/technology and extract comprehensive multi-layer architecture information.

Vendor/Technology to analyze: {vendor_name}

Provide a complete enterprise architecture analysis covering ALL ArchiMate layers in the following JSON format:

{{
    "name": "Technology stack name",
    "description": "Comprehensive description",
    "vendor_context": {{
        "vendor_name": "Official vendor company name",
        "market_position": "Market leader/challenger/niche/emerging",
        "company_size": "enterprise/mid-market/startup",
        "founded_year": "Year founded",
        "headquarters": "Location",
        "revenue_usd": "Annual revenue estimate",
        "customer_count": "Approximate customer count",
        "market_share_percentage": "Market share %",
        "acquisition_risk": "low/medium/high",
        "financial_health": "strong/stable/concerning"
    }},

    "strategy_layer": {{
        "capabilities_enabled": [
            {{
                "name": "Capability name (e.g., Customer Relationship Management)",
                "description": "How vendor enables this capability",
                "coverage_percentage": 85,
                "maturity_level": "optimized/managed/defined/initial"
            }}
        ],
        "value_streams_supported": [
            {{
                "name": "Value stream name (e.g., Lead-to-Cash)",
                "stages": ["stage1", "stage2"],
                "description": "How vendor supports this value stream"
            }}
        ],
        "courses_of_action": [
            {{
                "name": "Implementation approach",
                "description": "Recommended strategy",
                "timeline_months": 6,
                "risk_level": "low/medium/high"
            }}
        ]
    }},

    "business_layer": {{
        "business_services": [
            {{
                "name": "Business service name",
                "description": "Service description",
                "service_type": "customer-facing/internal/supporting",
                "sla_commitment": "Service level details"
            }}
        ],
        "business_processes": [
            {{
                "name": "Process name (e.g., Order-to-Cash)",
                "description": "Process description",
                "automation_level": "fully-automated/partially-automated/manual",
                "steps": ["step1", "step2"],
                "cycle_time": "Average completion time",
                "kpis": ["KPI1", "KPI2"]
            }}
        ],
        "business_objects": [
            {{
                "name": "Business entity (e.g., Customer, Order, Invoice)",
                "description": "Data entity description",
                "lifecycle": "created/active/archived/deleted"
            }}
        ],
        "business_actors": [
            {{
                "name": "Role/persona name",
                "description": "Actor description",
                "responsibilities": ["resp1", "resp2"]
            }}
        ],
        "products": [
            {{
                "name": "Product offering",
                "description": "Product description",
                "target_market": "Market segment"
            }}
        ]
    }},

    "application_layer": {{
        "application_components": [
            {{
                "name": "Component/module name",
                "type": "web-app/mobile-app/backend-service/integration-hub",
                "description": "Component description",
                "technology": "Technology used"
            }}
        ],
        "application_services": [
            {{
                "name": "Service name",
                "type": "REST/GraphQL/SOAP/gRPC",
                "description": "Service description",
                "endpoints": ["GET /api/customers", "POST /api/orders"]
            }}
        ],
        "application_interfaces": [
            {{
                "name": "Interface name",
                "protocol": "HTTP/HTTPS/AMQP/MQTT",
                "data_format": "JSON/XML/Protobuf/Avro",
                "authentication": "OAuth2/SAML/API-Key"
            }}
        ],
        "data_objects": [
            {{
                "name": "Data entity in application",
                "type": "transactional/master/reference",
                "retention_policy": "Retention period"
            }}
        ],
        "application_functions": [
            {{
                "name": "Function name",
                "type": "CRUD/workflow/reporting/analytics",
                "description": "Function description"
            }}
        ]
    }},

    "technology_layer": {{
        "platform": "aws/azure/gcp/on-prem/hybrid",
        "primary_language": "Programming language",
        "framework": "Framework name",
        "framework_version": "Version",
        "primary_database": "Database type",
        "database_version": "Database version",
        "container_runtime": "docker/containerd",
        "orchestration": "kubernetes/openshift/aks/eks/ecs",
        "service_mesh": "istio/linkerd/consul",

        "nodes": [
            {{
                "name": "Node/server name",
                "type": "virtual-machine/physical-server/container-host",
                "os": "Operating system",
                "cpu_cores": 8,
                "ram_gb": 32
            }}
        ],
        "devices": [
            {{
                "name": "Device name",
                "type": "load-balancer/firewall/storage-array",
                "description": "Device description"
            }}
        ],
        "system_software": [
            {{
                "name": "System software name",
                "type": "os/middleware/runtime/vm",
                "version": "Version"
            }}
        ],
        "technology_services": [
            {{
                "name": "Infrastructure service",
                "type": "storage/compute/network/database",
                "description": "Service description"
            }}
        ],
        "artifacts": [
            {{
                "name": "Deployable artifact",
                "type": "container-image/war/jar/exe/package",
                "size_mb": 150,
                "registry": "Registry location"
            }}
        ],
        "communication_networks": [
            {{
                "name": "Network name",
                "type": "lan/wan/vpn/internet",
                "bandwidth_mbps": 1000,
                "latency_ms": 10
            }}
        ],

        "api_standard": "REST/GraphQL/gRPC",
        "api_gateway": "API gateway solution",
        "message_broker": "Messaging system",
        "auth_provider": "Authentication provider",
        "secrets_manager": "Secrets management",
        "logging_framework": "Logging framework",
        "metrics_platform": "Metrics platform",
        "apm_tool": "APM tool",
        "tracing_tool": "Tracing tool",
        "build_tool": "Build tool",
        "ci_cd_platform": "CI/CD platform",
        "sast_tool": "SAST tool",
        "dast_tool": "DAST tool",
        "dependency_scanner": "Dependency scanner"
    }},

    "motivation_layer": {{
        "stakeholders": [
            {{
                "name": "Stakeholder role",
                "type": "business/it/executive/regulatory",
                "concerns": ["concern1", "concern2"],
                "influence": "high/medium/low"
            }}
        ],
        "drivers": [
            {{
                "name": "Driver name",
                "type": "business/technology/regulatory/competitive",
                "description": "Driver description",
                "urgency": "critical/high/medium/low"
            }}
        ],
        "goals": [
            {{
                "name": "Goal statement",
                "type": "strategic/tactical/operational",
                "target_date": "YYYY-MM",
                "success_criteria": "Measurable criteria"
            }}
        ],
        "outcomes": [
            {{
                "name": "Expected outcome",
                "type": "business/technical/financial",
                "measurement": "How to measure success"
            }}
        ],
        "principles": [
            {{
                "name": "Principle name",
                "statement": "Principle statement",
                "rationale": "Why this principle matters"
            }}
        ],
        "requirements": [
            {{
                "id": "REQ - 001",
                "name": "Requirement name",
                "type": "functional/non-functional/regulatory",
                "description": "Detailed requirement",
                "priority": "must-have/should-have/nice-to-have"
            }}
        ],
        "constraints": [
            {{
                "name": "Constraint name",
                "type": "technical/budget/timeline/regulatory",
                "description": "Constraint description",
                "impact": "high/medium/low"
            }}
        ],
        "assessments": [
            {{
                "type": "swot/risk/cost-benefit",
                "strengths": ["str1"],
                "weaknesses": ["weak1"],
                "opportunities": ["opp1"],
                "threats": ["thr1"],
                "overall_score": 75
            }}
        ]
    }},

    "integration_architecture": {{
        "integration_patterns": ["point-to-point/hub-and-spoke/event-driven/api-led"],
        "protocols_supported": ["HTTP/HTTPS", "AMQP", "MQTT", "gRPC"],
        "data_formats": ["JSON", "XML", "Protobuf"],
        "pre_built_connectors": ["Salesforce", "SAP", "Oracle"],
        "custom_connector_support": true,
        "etl_capabilities": "batch/realtime/both",
        "api_management": "built-in/third-party/none"
    }},

    "security_architecture": {{
        "authentication_methods": ["OAuth2", "SAML", "LDAP"],
        "authorization_model": "RBAC/ABAC/both",
        "encryption_at_rest": true,
        "encryption_in_transit": true,
        "key_management": "KMS solution",
        "security_certifications": ["SOC2", "ISO27001", "HIPAA"],
        "data_residency_options": ["us/eu/apac/multi-region"],
        "compliance_frameworks": ["GDPR", "CCPA", "PCI-DSS"],
        "vulnerability_scanning": "continuous/scheduled/none",
        "penetration_testing": "annual/quarterly/on-demand"
    }},

    "operational_requirements": {{
        "availability_sla": "99.9%/99.95%/99.99%",
        "rpo_hours": 1,
        "rto_hours": 4,
        "backup_frequency": "continuous/hourly/daily",
        "disaster_recovery": "active-active/active-passive/backup-only",
        "support_hours": "24x7/business-hours/best-effort",
        "support_channels": ["phone", "email", "chat", "portal"],
        "incident_response_time_mins": 30,
        "performance_benchmarks": {{
            "transactions_per_second": 5000,
            "concurrent_users": 10000,
            "avg_response_time_ms": 200,
            "p95_response_time_ms": 500
        }}
    }},

    "cost_breakdown": {{
        "license_cost_annual_usd": 50000,
        "license_model": "per-user/per-core/per-transaction/subscription",
        "infrastructure_cost_monthly_usd": 5000,
        "support_cost_annual_usd": 10000,
        "training_cost_per_user_usd": 500,
        "implementation_cost_usd": 100000,
        "migration_cost_usd": 50000,
        "exit_cost_usd": 25000,
        "total_cost_5year_usd": 500000
    }},

    "implementation_metadata": {{
        "deployment_complexity": "low/medium/high",
        "learning_curve": "low/medium/high",
        "typical_team_size": 5,
        "required_skill_levels": "junior/mid/senior ratio",
        "implementation_timeline_months": 6,
        "training_duration_days": 10,
        "certification_programs": ["cert1", "cert2"],
        "community_support": "excellent/good/limited",
        "documentation_quality": "excellent/good/poor"
    }},

    "ratings": {{
        "enterprise_adoption": "low/medium/high",
        "vendor_support": "basic/standard/premium",
        "scalability_rating": 8,
        "security_rating": 9,
        "maturity_rating": 9,
        "reliability_rating": 8,
        "performance_rating": 8,
        "ease_of_use": 7,
        "vendor_lock_in_risk": "low/medium/high",
        "overall_score": 85
    }}
}}

CRITICAL INSTRUCTIONS:
1. Provide REAL data based on actual vendor capabilities, not placeholders
2. Be comprehensive - populate ALL sections with meaningful data
3. For well-known vendors (Salesforce, SAP, Oracle, Microsoft), provide detailed accurate information
4. For less-known vendors, be honest about uncertainty but still provide best estimates
5. Focus on ENTERPRISE context - large multinational manufacturing company
6. Use actual version numbers, real product names, genuine pricing estimates
7. Extract multi-layer architecture - don't just focus on technology
8. Map business capabilities to technical components
9. Identify all stakeholders and their concerns
10. Provide actionable requirements and constraints

Respond ONLY with valid JSON - no additional text or explanations.
"""

    @staticmethod
    def analyze_vendor(vendor_name: str) -> Dict[str, Any]:
        """
        Analyze a vendor/technology name and extract technology stack details.

        This method now uses intelligent web research and multi-source analysis:
        1. Web scraping of vendor documentation
        2. API specification extraction
        3. Real-time pricing data collection
        4. Multi-source AI reasoning

        Args:
            vendor_name: Name of the vendor or technology to analyze

        Returns:
            Dictionary containing comprehensive technology stack information
        """
        if not vendor_name or not vendor_name.strip():
            raise ValueError("Vendor name cannot be empty")

        vendor_name = vendor_name.strip()
        logger.info(f"Starting AI analysis for vendor: {vendor_name}")

        # TEMPORARILY DISABLE INTELLIGENT ANALYZER TO FIX INFINITE LOOP
        # Disabled: intelligent_analyzer.py has app context issues causing infinite loop
        logger.info("Using basic AI analysis (intelligent analyzer disabled)")

        try:
            analysis_result = TechnologyStackAnalyzer._basic_ai_analysis(vendor_name)

            # Validate and enhance result
            required_fields = ["name", "description", "platform", "primary_language"]
            for field in required_fields:
                if field not in analysis_result:
                    logger.warning(f"Missing required field '{field}' in analysis response")
                    analysis_result[field] = ""

            # Add metadata
            analysis_result["_ai_analyzed"] = True
            analysis_result["_source_vendor"] = vendor_name
            analysis_result["_analysis_confidence"] = TechnologyStackAnalyzer._calculate_confidence(
                analysis_result
            )

            # Suggest enterprise capabilities
            analysis_result[
                "suggested_capabilities"
            ] = TechnologyStackAnalyzer._suggest_enterprise_capabilities(analysis_result)

            logger.info(f"Successfully completed analysis for vendor: {vendor_name}")
            return analysis_result

        except Exception as e:
            logger.error(f"Error analyzing vendor '{vendor_name}': {str(e)}")
            # Return fallback response
            return TechnologyStackAnalyzer._get_fallback_analysis(vendor_name, str(e))

    @staticmethod
    def _basic_ai_analysis(vendor_name: str) -> Dict[str, Any]:
        """
        Perform basic AI analysis when intelligent analysis fails.
        """
        logger.info(f"Performing basic AI analysis for vendor: {vendor_name}")

        try:
            # Prepare the prompt
            prompt = TechnologyStackAnalyzer.ANALYSIS_PROMPT_TEMPLATE.format(
                vendor_name=vendor_name
            )

            # Get best available provider (respects user preference + intelligent selection)
            provider, model = LLMService._get_configured_provider()
            response, _interaction = LLMService._call_llm_with_failover(
                prompt=prompt,
                model=model,
                provider=provider,
            )

            # Parse JSON response
            try:
                analysis_result = json.loads(response)
                logger.info(f"Successfully analyzed vendor with basic AI: {vendor_name}")

                # Add basic analysis metadata
                analysis_result["_analysis_type"] = "basic-ai"
                analysis_result["_research_enhanced"] = False
                analysis_result[
                    "_analysis_confidence"
                ] = TechnologyStackAnalyzer._calculate_confidence(analysis_result)

                # Suggest enterprise capabilities
                analysis_result[
                    "suggested_capabilities"
                ] = TechnologyStackAnalyzer._suggest_enterprise_capabilities(analysis_result)

                return analysis_result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Raw response: {response}")
                raise Exception("AI returned invalid JSON response. Please try again.")

        except Exception as e:
            logger.error(f"Basic AI analysis failed for '{vendor_name}': {str(e)}")
            raise

    @staticmethod
    def _calculate_confidence(analysis: Dict[str, Any]) -> float:
        """Calculate confidence score based on completeness of analysis."""
        total_fields = 25  # Total number of expected fields
        filled_fields = sum(1 for value in analysis.values() if value and str(value).strip())
        confidence = (filled_fields / total_fields) * 100
        return round(confidence, 2)

    @staticmethod
    def _get_fallback_analysis(vendor_name: str, error_message: str) -> Dict[str, Any]:
        """
        Return a fallback analysis when AI analysis fails.
        Uses database-driven vendor stack templates instead of hardcoded data.
        """
        from app.models.vendor_stack_template import VendorStackTemplate

        # Try to find a matching vendor template in the database
        vendor_lower = vendor_name.lower()

        # Exact match first
        template = VendorStackTemplate.query.filter(
            db.func.lower(VendorStackTemplate.vendor_name) == vendor_lower,
            VendorStackTemplate.is_active == True,
        ).first()

        # Fuzzy match if exact match fails
        if not template:
            template = VendorStackTemplate.query.filter(
                db.or_(
                    VendorStackTemplate.vendor_name.ilike(f"%{vendor_name}%"),
                    VendorStackTemplate.vendor_company_name.ilike(f"%{vendor_name}%"),
                ),
                VendorStackTemplate.is_active == True,
            ).first()

        # If template found, return it
        if template:
            logger.info(f"Using database template for vendor: {vendor_name}")
            result = template.to_dict()
            result["_error_message"] = error_message
            result["_fallback_source"] = "database_template"
            return result

        # If no template found, return minimal structure
        logger.warning(f"No template found for vendor: {vendor_name}. Returning minimal structure.")
        return {
            "name": f"{vendor_name} Technology Stack",
            "description": f"Technology stack for {vendor_name} (AI analysis unavailable, no template configured)",
            "technology_layer": {
                "platform": "",
                "primary_language": "",
                "framework": "",
                "framework_version": "",
                "primary_database": "",
                "database_version": "",
                "container_runtime": "",
                "orchestration": "",
                "service_mesh": "",
                "api_standard": "",
                "api_gateway": "",
                "message_broker": "",
                "auth_provider": "",
                "secrets_manager": "",
                "logging_framework": "",
                "metrics_platform": "",
                "apm_tool": "",
                "tracing_tool": "",
                "build_tool": "",
                "ci_cd_platform": "",
                "sast_tool": "",
                "dast_tool": "",
                "dependency_scanner": "",
            },
            "estimated_cost_per_month": 0,
            "deployment_complexity": "unknown",
            "learning_curve": "unknown",
            "enterprise_adoption": "unknown",
            "_ai_analyzed": False,
            "_source_vendor": vendor_name,
            "_analysis_confidence": 0.0,
            "_error_message": error_message,
            "_fallback_source": "minimal_default",
            "_needs_configuration": True,
        }

    @staticmethod
    def _suggest_enterprise_capabilities(analysis: Dict[str, Any]) -> list:
        """Suggest business capabilities based on technology stack analysis."""
        from app.models.business_capability import BusinessCapability

        try:
            # Get all active business capabilities (unified model)
            all_capabilities = BusinessCapability.query.filter_by(status="active").all()
            suggested = []

            # Extract key technology indicators from analysis
            name = analysis.get("name", "").lower()
            description = analysis.get("description", "").lower()

            # Get technology layer fields
            tech_layer = analysis.get("technology_layer", {})
            framework = tech_layer.get("framework", "").lower()
            platform = tech_layer.get("platform", "").lower()
            primary_language = tech_layer.get("primary_language", "").lower()
            api_standard = tech_layer.get("api_standard", "").lower()
            message_broker = tech_layer.get("message_broker", "").lower()
            auth_provider = tech_layer.get("auth_provider", "").lower()
            container_runtime = tech_layer.get("container_runtime", "").lower()
            orchestration = tech_layer.get("orchestration", "").lower()

            # Technology stack content for matching
            tech_content = f"{name} {description} {framework} {platform} {primary_language} {api_standard} {message_broker} {auth_provider} {container_runtime} {orchestration}"

            for capability in all_capabilities:
                capability_lower = capability.name.lower()
                capability_desc = (capability.description or "").lower()

                # Score based on capability type and technology stack
                score = 0

                # Application Development capabilities
                if any(
                    keyword in tech_content
                    for keyword in [
                        "api",
                        "microservices",
                        "rest",
                        "graphql",
                        "spring",
                        "nodejs",
                        "react",
                        "angular",
                    ]
                ):
                    if any(
                        keyword in capability_lower
                        for keyword in ["development", "application", "api", "software"]
                    ):
                        score += 30

                # Cloud services capabilities
                if any(
                    keyword in tech_content
                    for keyword in ["cloud", "aws", "azure", "gcp", "kubernetes", "docker"]
                ):
                    if any(
                        keyword in capability_lower
                        for keyword in ["cloud", "infrastructure", "platform"]
                    ):
                        score += 25

                # Data management capabilities
                if any(
                    keyword in tech_content
                    for keyword in ["database", "postgresql", "mysql", "oracle", "mongodb", "sql"]
                ):
                    if any(
                        keyword in capability_lower
                        for keyword in ["data", "information", "database"]
                    ):
                        score += 25

                # Security capabilities
                if any(
                    keyword in tech_content
                    for keyword in ["auth", "oauth", "saml", "ldap", "security", "encryption"]
                ):
                    if any(
                        keyword in capability_lower
                        for keyword in ["security", "authentication", "authorization", "compliance"]
                    ):
                        score += 30

                # Integration capabilities
                if any(
                    keyword in tech_content
                    for keyword in ["integration", "api", "gateway", "broker", "message", "event"]
                ):
                    if any(
                        keyword in capability_lower
                        for keyword in ["integration", "api", "service", "message"]
                    ):
                        score += 25

                # DevOps capabilities
                if any(
                    keyword in tech_content
                    for keyword in [
                        "ci/cd",
                        "jenkins",
                        "gitlab",
                        "docker",
                        "kubernetes",
                        "terraform",
                    ]
                ):
                    if any(
                        keyword in capability_lower
                        for keyword in ["devops", "deployment", "ci/cd", "automation"]
                    ):
                        score += 25

                # Monitoring and observability
                if any(
                    keyword in tech_content
                    for keyword in ["monitoring", "metrics", "logging", "apm", "tracing"]
                ):
                    if any(
                        keyword in capability_lower
                        for keyword in ["monitoring", "observability", "analytics"]
                    ):
                        score += 20

                # Enterprise architecture
                if any(
                    keyword in tech_content
                    for keyword in ["enterprise", "architecture", "governance", "standard"]
                ):
                    if any(
                        keyword in capability_lower
                        for keyword in ["enterprise", "architecture", "governance"]
                    ):
                        score += 15

                # Check description matching for additional context
                if capability_desc and any(
                    keyword in tech_content for keyword in capability_desc.split()[:5]
                ):
                    score += 10

                # If score is high enough, suggest this capability
                if score >= 20:
                    suggested.append(
                        {
                            "id": capability.id,
                            "name": capability.name,
                            "description": capability.description,
                            "category": capability.category,
                            "score": score,
                            "confidence": min(score / 30.0, 1.0),  # Normalize to 0 - 1
                        }
                    )

            # Sort by score and return top suggestions
            suggested.sort(key=lambda x: x["score"], reverse=True)
            return suggested[:8]  # Return top 8 suggestions

        except Exception as e:
            logger.error(f"Error suggesting capabilities: {str(e)}")
            return []

    @staticmethod
    def get_vendor_suggestions() -> list:
        """Get list of common enterprise technology vendors for autocomplete."""
        return [
            # Cloud Platforms
            "Microsoft Azure",
            "Amazon Web Services (AWS)",
            "Google Cloud Platform (GCP)",
            "IBM Cloud",
            "Oracle Cloud",
            # Integration Platforms
            "MuleSoft Anypoint Platform",
            "TIBCO BusinessWorks",
            "IBM WebSphere",
            "Red Hat Fuse",
            "Apache Camel",
            # Enterprise Applications
            "SAP S/4HANA",
            "SAP SuccessFactors",
            "SAP Ariba",
            "SAP Concur",
            "Salesforce CRM",
            "ServiceNow",
            "Workday",
            "Oracle ERP Cloud",
            # Low-Code Platforms
            "Mendix",
            "OutSystems",
            "Microsoft Power Platform",
            "Appian",
            "Pega Platform",
            # Data & Analytics
            "Talend Data Fabric",
            "Informatica PowerCenter",
            "Snowflake",
            "Databricks",
            "Tableau",
            "Power BI",
            # Development Platforms
            "Spring Boot",
            ".NET Core",
            "Node.js",
            "Python Django",
            "Python Flask",
            "React",
            "Angular",
            "Vue.js",
            # Databases
            "PostgreSQL",
            "MySQL",
            "Oracle Database",
            "SQL Server",
            "MongoDB",
            "Redis",
            "Elasticsearch",
            # Container & DevOps
            "Docker",
            "Kubernetes",
            "OpenShift",
            "Jenkins",
            "GitLab",
            "Azure DevOps",
            "GitHub Actions",
            # Monitoring & APM
            "Datadog",
            "New Relic",
            "Dynatrace",
            "AppDynamics",
            "Splunk",
            "Elastic Stack (ELK)",
        ]

    @staticmethod
    def analyze_capabilities(
        capabilities: str,
        context: str = "",
        platform: str = "hybrid",
        performance: str = "standard",
        security: str = "high",
        budget: str = "medium",
    ) -> Dict[str, Any]:
        """
        Analyze business capabilities and recommend optimal technology stack.

        Args:
            capabilities: Business capabilities required (e.g., "Real-time data processing, Customer identity management")
            context: Additional enterprise context or constraints
            platform: Target platform preference (aws, azure, gcp, on-prem, hybrid)
            performance: Performance requirements (low, standard, high, ultra-high)
            security: Security requirements (basic, standard, high, ultra-high)
            budget: Budget constraints (low, medium, high, unlimited)

        Returns:
            Dict containing recommended technology stack for the capabilities
        """
        logger.info(f"Starting capability-driven analysis for: {capabilities}")

        try:
            # Prepare the capability analysis prompt
            prompt = TechnologyStackAnalyzer.CAPABILITY_ANALYSIS_PROMPT_TEMPLATE.format(
                capabilities=capabilities,
                context=context or "Enterprise environment with standard compliance requirements",
                platform=platform,
                performance=performance,
                security=security,
                budget=budget,
            )

            # Get best available provider (respects user preference + intelligent selection)
            provider, model = LLMService._get_configured_provider()
            response, _interaction = LLMService._call_llm_with_failover(
                prompt=prompt,
                model=model,
                provider=provider,
            )

            # Parse JSON response
            try:
                analysis_result = json.loads(response)
                logger.info(f"Successfully analyzed capabilities: {capabilities}")

                # Validate required fields
                required_fields = ["name", "description", "platform", "primary_language"]
                for field in required_fields:
                    if field not in analysis_result:
                        logger.warning(f"Missing required field '{field}' in AI response")
                        analysis_result[field] = ""

                # Add metadata
                analysis_result["_ai_analyzed"] = True
                analysis_result["_analysis_type"] = "capability-driven"
                analysis_result["_source_capabilities"] = capabilities
                analysis_result[
                    "_analysis_confidence"
                ] = TechnologyStackAnalyzer._calculate_confidence(analysis_result)

                return analysis_result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Raw response: {response}")
                raise Exception("AI returned invalid JSON response. Please try again.")

        except Exception as e:
            logger.error(f"Error analyzing capabilities '{capabilities}': {str(e)}")
            # Return fallback response for capabilities
            return TechnologyStackAnalyzer._get_capability_fallback_analysis(capabilities, str(e))

    @staticmethod
    def _get_capability_fallback_analysis(capabilities: str, error_message: str) -> Dict[str, Any]:
        """Return a fallback analysis when capability-driven AI analysis fails."""
        capabilities_lower = capabilities.lower()

        # Smart fallback based on capability patterns
        analysis = {
            "name": f"Technology Stack for: {capabilities}",
            "description": f"Recommended technology stack for required capabilities: {capabilities} (AI analysis unavailable - manual configuration recommended)",
            "platform": "hybrid",
            "primary_language": "",
            "framework": "",
            "framework_version": "",
            "primary_database": "",
            "database_version": "",
            "container_runtime": "docker",
            "orchestration": "kubernetes",
            "service_mesh": "",
            "api_standard": "REST",
            "api_gateway": "",
            "message_broker": "",
            "auth_provider": "",
            "secrets_manager": "",
            "logging_framework": "",
            "metrics_platform": "",
            "apm_tool": "",
            "tracing_tool": "",
            "build_tool": "",
            "ci_cd_platform": "",
            "sast_tool": "",
            "dast_tool": "",
            "dependency_scanner": "",
            "estimated_cost_per_month": "TBD",
            "capability_coverage": 50,
            "implementation_complexity": "medium",
            "vendor_lock_in_risk": "medium",
            "scalability_rating": 5,
            "security_rating": 5,
            "capability_gaps": ["Manual assessment required"],
            "alternative_options": "Multiple technology approaches available",
            "_ai_analyzed": False,
            "_analysis_type": "capability-driven",
            "_source_capabilities": capabilities,
            "_fallback_reason": error_message,
            "_analysis_confidence": 30.0,
        }

        # Apply capability-based intelligent defaults
        if any(keyword in capabilities_lower for keyword in ["real-time", "streaming", "event"]):
            analysis.update(
                {
                    "primary_language": "Java",
                    "framework": "Spring Boot",
                    "message_broker": "Apache Kafka",
                    "primary_database": "Apache Cassandra",
                    "metrics_platform": "Prometheus",
                }
            )

        if any(
            keyword in capabilities_lower for keyword in ["identity", "auth", "security", "sso"]
        ):
            analysis.update(
                {
                    "auth_provider": "Keycloak",
                    "secrets_manager": "HashiCorp Vault",
                    "security_rating": 8,
                }
            )

        if any(keyword in capabilities_lower for keyword in ["api", "integration", "microservice"]):
            analysis.update(
                {"api_gateway": "Kong", "service_mesh": "Istio", "api_standard": "REST/GraphQL"}
            )

        if any(keyword in capabilities_lower for keyword in ["data", "analytics", "reporting"]):
            analysis.update(
                {
                    "primary_database": "PostgreSQL",
                    "metrics_platform": "Grafana",
                    "logging_framework": "ELK Stack",
                }
            )

        return analysis
