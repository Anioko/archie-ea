"""
Appian Low-Code Platform Comprehensive Vendor Template Seed Data

Complete ArchiMate 3.2 coverage across ALL layers:
- Strategy Layer
- Business Layer
- Application Layer
- Technology Layer
- Motivation Layer
- Implementation & Migration Layer
- Physical Layer

Run with: python manage.py seed-vendor-appian
"""
import json

from app import create_app, db
from app.models import User, VendorStackTemplate
from config import DevelopmentConfig


def create_appian_template():
    """Appian Low-Code Platform FULLY COMPREHENSIVE template - ALL ArchiMate 3.2 layers"""
    return VendorStackTemplate(
        vendor_name="Appian Corporation",
        name="Appian Low-Code Automation Platform",
        description="Enterprise low-code platform combining intelligent automation, process mining, RPA, AI, and case management for end-to-end process orchestration and digital transformation at scale",
        # ==================== TECHNOLOGY LAYER ====================
        platform="cloud",
        primary_language="java",
        framework="Appian Platform",
        framework_version="23.4",
        primary_database="mariadb",
        database_version="10.11",
        container_runtime="docker",
        orchestration="kubernetes",
        service_mesh="istio",
        api_standard="REST",
        api_gateway="kong",
        message_broker="kafka",
        auth_provider="okta",
        secrets_manager="hashicorp-vault",
        logging_framework="elk-stack",
        metrics_platform="prometheus",
        apm_tool="new-relic",
        tracing_tool="jaeger",
        build_tool="maven",
        ci_cd_platform="jenkins",
        sast_tool="veracode",
        dast_tool="qualys",
        dependency_scanner="snyk",
        nodes=json.dumps(
            [
                {
                    "name": "Appian Cloud Node 1",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
                {
                    "name": "Appian Cloud Node 2",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
                {
                    "name": "Appian Cloud Node 3",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
                {
                    "name": "Process Mining Server",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 64,
                    "ram_gb": 256,
                },
                {
                    "name": "RPA Orchestrator",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "Data Fabric Node",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 48,
                    "ram_gb": 192,
                },
                {
                    "name": "MariaDB Primary",
                    "type": "cloud-database",
                    "os": "RHEL 8",
                    "cpu_cores": 48,
                    "ram_gb": 256,
                },
                {
                    "name": "MariaDB Replica",
                    "type": "cloud-database",
                    "os": "RHEL 8",
                    "cpu_cores": 48,
                    "ram_gb": 256,
                },
                {
                    "name": "API Gateway",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "Search Server (Elasticsearch)",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
            ]
        ),
        devices=json.dumps(
            [
                {
                    "name": "Cloud Load Balancer",
                    "type": "load-balancer",
                    "description": "Multi-region load distribution",
                },
                {"name": "CDN", "type": "cdn", "description": "Content delivery network"},
                {"name": "WAF", "type": "firewall", "description": "Web application firewall"},
                {"name": "Mobile Devices", "type": "mobile", "description": "iOS/Android devices"},
                {
                    "name": "RPA Bots",
                    "type": "software-robot",
                    "description": "Attended and unattended bots",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {"name": "Appian Platform", "type": "low-code-platform", "version": "23.4"},
                {"name": "Appian Process Mining", "type": "process-mining", "version": "2023.4"},
                {"name": "Appian RPA", "type": "rpa", "version": "23.4"},
                {"name": "Appian AI", "type": "ai-ml", "version": "23.4"},
                {"name": "Data Fabric", "type": "data-virtualization", "version": "23.4"},
                {"name": "MariaDB", "type": "database", "version": "10.11"},
                {"name": "Elasticsearch", "type": "search-engine", "version": "8.10"},
                {"name": "Apache Kafka", "type": "message-broker", "version": "3.5"},
                {"name": "Redis", "type": "cache", "version": "7.2"},
                {"name": "Kubernetes", "type": "orchestration", "version": "1.27"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "Appian Process Engine",
                    "type": "bpm-engine",
                    "description": "BPMN 2.0 process orchestration",
                },
                {
                    "name": "Case Management Service",
                    "type": "case-management",
                    "description": "Dynamic case management",
                },
                {
                    "name": "UI Rendering Service",
                    "type": "ui-engine",
                    "description": "SAIL form and interface rendering",
                },
                {
                    "name": "Process Mining Engine",
                    "type": "process-mining",
                    "description": "Process discovery and conformance",
                },
                {
                    "name": "RPA Orchestrator Service",
                    "type": "rpa-orchestrator",
                    "description": "Robot scheduling and management",
                },
                {
                    "name": "AI/ML Service",
                    "type": "ai-ml",
                    "description": "Document extraction, predictions",
                },
                {
                    "name": "Data Fabric Service",
                    "type": "data-virtualization",
                    "description": "Unified data access layer",
                },
                {
                    "name": "Rules Engine",
                    "type": "business-rules",
                    "description": "Decision management",
                },
                {
                    "name": "Workflow Service",
                    "type": "workflow-engine",
                    "description": "Task routing and escalation",
                },
                {
                    "name": "Document Management",
                    "type": "content-management",
                    "description": "Document storage and versioning",
                },
                {
                    "name": "Integration Service",
                    "type": "integration",
                    "description": "API and connector management",
                },
                {
                    "name": "Mobile Service",
                    "type": "mobile-backend",
                    "description": "Native mobile app backend",
                },
                {
                    "name": "Analytics Service",
                    "type": "analytics",
                    "description": "Process and operational analytics",
                },
                {
                    "name": "Security Service",
                    "type": "authentication",
                    "description": "SSO and authorization",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "Application Package",
                    "type": "deployment-package",
                    "size_mb": 100,
                    "registry": "Appian Cloud",
                },
                {
                    "name": "Process Models",
                    "type": "bpmn-models",
                    "size_mb": 50,
                    "registry": "Appian Designer",
                },
                {
                    "name": "UI Interfaces",
                    "type": "sail-interfaces",
                    "size_mb": 30,
                    "registry": "Appian Designer",
                },
                {
                    "name": "Process Mining Models",
                    "type": "mining-models",
                    "size_mb": 500,
                    "registry": "Process Mining",
                },
                {
                    "name": "RPA Bot Scripts",
                    "type": "rpa-scripts",
                    "size_mb": 20,
                    "registry": "RPA Designer",
                },
                {"name": "AI Models", "type": "ml-models", "size_mb": 200, "registry": "Appian AI"},
                {
                    "name": "Database Backup",
                    "type": "backup",
                    "size_mb": 50000,
                    "registry": "MariaDB",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "Appian Cloud VPC",
                    "type": "cloud-vpc",
                    "bandwidth_mbps": 100000,
                    "latency_ms": 5,
                },
                {
                    "name": "Inter-Service Mesh",
                    "type": "service-mesh",
                    "bandwidth_mbps": 100000,
                    "latency_ms": 1,
                },
                {
                    "name": "VPN/ExpressRoute",
                    "type": "vpn",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 20,
                },
                {"name": "CDN Network", "type": "cdn", "bandwidth_mbps": 1000000, "latency_ms": 15},
                {
                    "name": "Public Internet",
                    "type": "internet",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 50,
                },
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="Appian Corporation",
        market_position="leader",
        company_size="large",
        founded_year=1999,
        headquarters="McLean, VA, USA",
        revenue_usd=500000000,
        customer_count=700,
        market_share_percentage=8.0,
        acquisition_risk="very-low",
        financial_health="excellent",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                {
                    "name": "Low-Code Development",
                    "description": "Visual application development with minimal code",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Process Orchestration",
                    "description": "BPMN-based process automation",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Case Management",
                    "description": "Dynamic case and knowledge worker processes",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Process Mining",
                    "description": "Discover and analyze actual business processes",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Robotic Process Automation",
                    "description": "Attended and unattended software robots",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Intelligent Document Processing",
                    "description": "AI-powered document extraction",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Data Fabric",
                    "description": "Unified data access across systems",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Mobile App Development",
                    "description": "Native iOS/Android apps",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Business Rules Management",
                    "description": "Centralized decision management",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "API Management",
                    "description": "API creation and governance",
                    "coverage_percentage": 95,
                    "maturity_level": "managed",
                },
                {
                    "name": "Workflow Automation",
                    "description": "Task routing and escalation",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Process Analytics",
                    "description": "Real-time process performance metrics",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Document Management",
                    "description": "Content storage and versioning",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Integration",
                    "description": "Pre-built connectors and custom integrations",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Collaboration",
                    "description": "Team collaboration and social features",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "AI/ML Integration",
                    "description": "Embedded AI and ML capabilities",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Governance",
                    "description": "Application lifecycle governance",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Deployment Automation",
                    "description": "CI/CD for applications",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Multi-Tenancy",
                    "description": "Secure tenant isolation",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Localization",
                    "description": "Multi-language and regional support",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Discover-to-Automate",
                    "stages": [
                        "Process Discovery",
                        "Process Analysis",
                        "Process Design",
                        "Automation Build",
                        "Deployment",
                        "Monitoring",
                    ],
                    "description": "Process mining to automation",
                },
                {
                    "name": "Idea-to-Application",
                    "stages": ["Requirements", "Design", "Build", "Test", "Deploy", "Monitor"],
                    "description": "Low-code development lifecycle",
                },
                {
                    "name": "Request-to-Resolution",
                    "stages": [
                        "Request Intake",
                        "Case Creation",
                        "Investigation",
                        "Decision",
                        "Action",
                        "Closure",
                    ],
                    "description": "Case management",
                },
                {
                    "name": "Document-to-Data",
                    "stages": [
                        "Document Receipt",
                        "Classification",
                        "Extraction",
                        "Validation",
                        "Integration",
                        "Archive",
                    ],
                    "description": "Intelligent document processing",
                },
                {
                    "name": "Manual-to-Automated",
                    "stages": [
                        "Task Identification",
                        "Bot Design",
                        "Bot Build",
                        "Testing",
                        "Deployment",
                        "Orchestration",
                    ],
                    "description": "RPA implementation",
                },
                {
                    "name": "Data-to-Decision",
                    "stages": [
                        "Data Access",
                        "Data Preparation",
                        "Rule Definition",
                        "Decision Execution",
                        "Monitoring",
                    ],
                    "description": "Business rules automation",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "Cloud-Native Deployment",
                    "description": "Full Appian Cloud implementation",
                    "timeline_months": 6,
                    "risk_level": "low",
                },
                {
                    "name": "Hybrid Cloud",
                    "description": "Cloud platform with on-premise data",
                    "timeline_months": 9,
                    "risk_level": "medium",
                },
                {
                    "name": "Process Mining First",
                    "description": "Start with process discovery",
                    "timeline_months": 3,
                    "risk_level": "low",
                },
                {
                    "name": "Citizen Developer Program",
                    "description": "Empower business users to build apps",
                    "timeline_months": 12,
                    "risk_level": "medium",
                },
                {
                    "name": "RPA Integration",
                    "description": "Combine Appian with existing RPA",
                    "timeline_months": 6,
                    "risk_level": "low",
                },
                {
                    "name": "AI-First Approach",
                    "description": "Lead with intelligent document processing",
                    "timeline_months": 6,
                    "risk_level": "medium",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Process Automation Service",
                    "description": "Automated business process execution",
                    "service_type": "internal",
                    "sla_commitment": "99.9% uptime, < 1 sec response",
                },
                {
                    "name": "Case Management Service",
                    "description": "Dynamic case handling",
                    "service_type": "internal",
                    "sla_commitment": "99.9% availability",
                },
                {
                    "name": "Process Mining Service",
                    "description": "Process discovery and analysis",
                    "service_type": "internal",
                    "sla_commitment": "Daily process model refresh",
                },
                {
                    "name": "RPA Service",
                    "description": "Software robot execution",
                    "service_type": "internal",
                    "sla_commitment": "99% bot availability",
                },
                {
                    "name": "Document Processing Service",
                    "description": "Intelligent document extraction",
                    "service_type": "internal",
                    "sla_commitment": "> 95% extraction accuracy",
                },
                {
                    "name": "Mobile Application Service",
                    "description": "Native mobile apps",
                    "service_type": "external",
                    "sla_commitment": "99.9% uptime",
                },
                {
                    "name": "API Service",
                    "description": "REST API access",
                    "service_type": "integration",
                    "sla_commitment": "< 500ms response time",
                },
                {
                    "name": "Analytics Service",
                    "description": "Process and operational analytics",
                    "service_type": "internal",
                    "sla_commitment": "Real-time dashboards",
                },
                {
                    "name": "Integration Service",
                    "description": "System integration",
                    "service_type": "integration",
                    "sla_commitment": "< 2 sec integration latency",
                },
                {
                    "name": "Collaboration Service",
                    "description": "Team collaboration",
                    "service_type": "internal",
                    "sla_commitment": "99.9% availability",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Process Discovery & Mining",
                    "description": "Discover actual processes from system logs",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Log Extraction",
                        "Process Discovery",
                        "Conformance Checking",
                        "Bottleneck Analysis",
                        "Variant Analysis",
                        "Optimization Recommendations",
                    ],
                    "cycle_time": "Hours to days",
                    "kpis": [
                        "Process Variants Discovered",
                        "Conformance Rate",
                        "Cycle Time Reduction Opportunities",
                    ],
                },
                {
                    "name": "Automated Workflow Execution",
                    "description": "Execute BPMN process instances",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Process Instance Creation",
                        "Task Assignment",
                        "Automated Activities",
                        "Human Task Execution",
                        "Decision Points",
                        "Process Completion",
                    ],
                    "cycle_time": "Minutes to days",
                    "kpis": ["Process Cycle Time", "SLA Compliance", "Automation Rate"],
                },
                {
                    "name": "Dynamic Case Management",
                    "description": "Handle complex knowledge worker cases",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Case Initiation",
                        "Data Gathering",
                        "Investigation",
                        "Collaboration",
                        "Decision Making",
                        "Action Execution",
                        "Case Closure",
                    ],
                    "cycle_time": "Days to weeks",
                    "kpis": ["Average Handle Time", "First Contact Resolution", "Case Backlog"],
                },
                {
                    "name": "RPA Bot Execution",
                    "description": "Execute attended and unattended bots",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Bot Trigger",
                        "System Login",
                        "Data Extraction",
                        "Data Processing",
                        "System Updates",
                        "Exception Handling",
                        "Completion",
                    ],
                    "cycle_time": "Seconds to minutes",
                    "kpis": ["Bot Success Rate", "Processing Time", "Error Rate"],
                },
                {
                    "name": "Intelligent Document Processing",
                    "description": "Extract data from documents using AI",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Document Receipt",
                        "Classification",
                        "Data Extraction",
                        "Validation",
                        "Human Review (if needed)",
                        "Data Integration",
                    ],
                    "cycle_time": "Seconds to minutes",
                    "kpis": [
                        "Extraction Accuracy > 95%",
                        "Straight-Through Processing Rate",
                        "Manual Review Rate",
                    ],
                },
                {
                    "name": "Application Development",
                    "description": "Build applications with low-code",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Requirements Gathering",
                        "Process Modeling",
                        "UI Design",
                        "Integration Configuration",
                        "Testing",
                        "Deployment",
                    ],
                    "cycle_time": "Weeks",
                    "kpis": [
                        "Time to Deploy",
                        "Code Lines (should be minimal)",
                        "Developer Productivity",
                    ],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Process Instance",
                    "description": "Running process instance",
                    "lifecycle": "initiated -> in-progress -> completed -> archived",
                },
                {
                    "name": "Case",
                    "description": "Dynamic case record",
                    "lifecycle": "opened -> in-progress -> resolved -> closed",
                },
                {
                    "name": "Task",
                    "description": "Work item assigned to user",
                    "lifecycle": "created -> assigned -> in-progress -> completed",
                },
                {
                    "name": "Document",
                    "description": "Managed content item",
                    "lifecycle": "uploaded -> processed -> validated -> archived",
                },
                {
                    "name": "Process Model",
                    "description": "BPMN process definition",
                    "lifecycle": "discovered -> designed -> published -> active -> deprecated",
                },
                {
                    "name": "RPA Bot",
                    "description": "Software robot definition",
                    "lifecycle": "designed -> tested -> deployed -> active -> retired",
                },
                {
                    "name": "Business Rule",
                    "description": "Decision rule or policy",
                    "lifecycle": "drafted -> tested -> published -> active -> superseded",
                },
                {
                    "name": "Data Record",
                    "description": "Business data entity",
                    "lifecycle": "created -> validated -> active -> archived",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Citizen Developer",
                    "description": "Business user building apps",
                    "responsibilities": [
                        "Application Design",
                        "Process Modeling",
                        "UI Configuration",
                        "Testing",
                    ],
                },
                {
                    "name": "Process Owner",
                    "description": "Business process owner",
                    "responsibilities": [
                        "Process Definition",
                        "Performance Monitoring",
                        "Continuous Improvement",
                        "Stakeholder Management",
                    ],
                },
                {
                    "name": "Case Worker",
                    "description": "Knowledge worker handling cases",
                    "responsibilities": [
                        "Case Investigation",
                        "Decision Making",
                        "Collaboration",
                        "Documentation",
                    ],
                },
                {
                    "name": "Process Analyst",
                    "description": "Process mining specialist",
                    "responsibilities": [
                        "Process Discovery",
                        "Analysis",
                        "Optimization Recommendations",
                        "Conformance Checking",
                    ],
                },
                {
                    "name": "RPA Developer",
                    "description": "Bot developer",
                    "responsibilities": ["Bot Design", "Bot Development", "Testing", "Deployment"],
                },
                {
                    "name": "Professional Developer",
                    "description": "IT developer",
                    "responsibilities": [
                        "Complex Integrations",
                        "Custom Functionality",
                        "Performance Tuning",
                        "Architecture",
                    ],
                },
                {
                    "name": "Business Analyst",
                    "description": "Requirements specialist",
                    "responsibilities": [
                        "Requirements Gathering",
                        "Process Documentation",
                        "UAT",
                        "Training",
                    ],
                },
                {
                    "name": "Application Administrator",
                    "description": "Platform administrator",
                    "responsibilities": [
                        "User Management",
                        "Environment Management",
                        "Monitoring",
                        "Governance",
                    ],
                },
                {
                    "name": "End User",
                    "description": "Application user",
                    "responsibilities": ["Task Execution", "Data Entry", "Reporting", "Feedback"],
                },
                {
                    "name": "Executive Sponsor",
                    "description": "Business executive",
                    "responsibilities": [
                        "Strategy",
                        "Budget Approval",
                        "Governance",
                        "Performance Review",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "Appian Platform",
                    "description": "Core low-code platform",
                    "target_market": "Enterprise",
                },
                {
                    "name": "Appian Process Mining",
                    "description": "Process discovery and analysis",
                    "target_market": "Process Improvement Teams",
                },
                {
                    "name": "Appian RPA",
                    "description": "Robotic process automation",
                    "target_market": "Operations Teams",
                },
                {
                    "name": "Appian AI",
                    "description": "AI and ML capabilities",
                    "target_market": "Intelligent Automation",
                },
                {
                    "name": "Appian Data Fabric",
                    "description": "Data virtualization layer",
                    "target_market": "Data Integration",
                },
                {
                    "name": "Appian Mobile",
                    "description": "Native mobile apps",
                    "target_market": "Mobile Workforce",
                },
                {
                    "name": "Appian Portals",
                    "description": "External-facing portals",
                    "target_market": "Customer/Partner Engagement",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "Appian Designer",
                    "type": "ide",
                    "description": "Low-code development environment",
                    "technology": "Java/JavaScript",
                },
                {
                    "name": "Process Engine",
                    "type": "bpm-engine",
                    "description": "BPMN 2.0 execution engine",
                    "technology": "Java",
                },
                {
                    "name": "SAIL UI Framework",
                    "type": "ui-framework",
                    "description": "Component-based UI framework",
                    "technology": "JavaScript/Java",
                },
                {
                    "name": "Process Mining Engine",
                    "type": "process-mining",
                    "description": "Process discovery engine",
                    "technology": "Java/Python",
                },
                {
                    "name": "RPA Orchestrator",
                    "type": "rpa-platform",
                    "description": "Bot management platform",
                    "technology": "Java",
                },
                {
                    "name": "AI Engine",
                    "type": "ai-ml",
                    "description": "Document AI and predictions",
                    "technology": "Python/Java",
                },
                {
                    "name": "Data Fabric",
                    "type": "data-virtualization",
                    "description": "Unified data access layer",
                    "technology": "Java",
                },
                {
                    "name": "Rules Engine",
                    "type": "brms",
                    "description": "Business rules management",
                    "technology": "Java",
                },
                {
                    "name": "Mobile App Framework",
                    "type": "mobile-framework",
                    "description": "Native mobile app generator",
                    "technology": "Swift/Kotlin",
                },
                {
                    "name": "Integration Framework",
                    "type": "integration",
                    "description": "Connector and API framework",
                    "technology": "Java",
                },
                {
                    "name": "MariaDB",
                    "type": "database",
                    "description": "Application database",
                    "technology": "SQL",
                },
                {
                    "name": "Elasticsearch",
                    "type": "search",
                    "description": "Full-text search",
                    "technology": "Java",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "Appian REST API",
                    "type": "REST",
                    "description": "Platform API",
                    "endpoints": ["/suite/rest/a/*//*", "/suite/webapi/*"],
                },
                {
                    "name": "Process API",
                    "type": "REST",
                    "description": "Process management API",
                    "endpoints": ["/suite/rest/a/process/*"],
                },
                {
                    "name": "Content API",
                    "type": "REST",
                    "description": "Document management API",
                    "endpoints": ["/suite/rest/a/content/*"],
                },
                {
                    "name": "Query API",
                    "type": "REST",
                    "description": "Data query API",
                    "endpoints": ["/suite/rest/a/query/*"],
                },
                {
                    "name": "Process Mining API",
                    "type": "REST",
                    "description": "Process mining services",
                    "endpoints": ["/processmining/api/v1/*"],
                },
                {
                    "name": "RPA API",
                    "type": "REST",
                    "description": "RPA orchestration API",
                    "endpoints": ["/rpa/api/v1/*"],
                },
                {
                    "name": "AI API",
                    "type": "REST",
                    "description": "AI services API",
                    "endpoints": ["/ai/api/v1/*"],
                },
                {
                    "name": "Data Fabric API",
                    "type": "REST",
                    "description": "Data access API",
                    "endpoints": ["/datafabric/api/v1/*"],
                },
                {
                    "name": "Integration API",
                    "type": "REST",
                    "description": "Connected systems API",
                    "endpoints": ["/suite/rest/a/integration/*"],
                },
                {
                    "name": "WebSocket API",
                    "type": "WebSocket",
                    "description": "Real-time updates",
                    "endpoints": ["wss://*/suite/tempo/*"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "REST API",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "OAuth2/API Key",
                },
                {
                    "name": "SOAP Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "XML",
                    "authentication": "WS-Security",
                },
                {
                    "name": "WebSocket Interface",
                    "protocol": "WebSocket",
                    "data_format": "JSON",
                    "authentication": "Token",
                },
                {
                    "name": "Database Interface",
                    "protocol": "JDBC",
                    "data_format": "SQL",
                    "authentication": "Database Credentials",
                },
                {
                    "name": "File Interface",
                    "protocol": "SFTP/S3",
                    "data_format": "Various",
                    "authentication": "SSH/API Key",
                },
                {
                    "name": "Message Queue",
                    "protocol": "Kafka/JMS",
                    "data_format": "JSON/Avro",
                    "authentication": "SASL",
                },
                {
                    "name": "Mobile SDK",
                    "protocol": "HTTPS",
                    "data_format": "JSON",
                    "authentication": "OAuth2",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {
                    "name": "Process Definition",
                    "type": "master",
                    "retention_policy": "Lifetime of process",
                },
                {
                    "name": "Process Instance Data",
                    "type": "transactional",
                    "retention_policy": "7 years",
                },
                {
                    "name": "Case Data",
                    "type": "transactional",
                    "retention_policy": "Case retention policy",
                },
                {
                    "name": "Document Content",
                    "type": "content",
                    "retention_policy": "Per compliance requirements",
                },
                {
                    "name": "Process Mining Event Log",
                    "type": "analytical",
                    "retention_policy": "2 years",
                },
                {"name": "RPA Execution Log", "type": "operational", "retention_policy": "1 year"},
                {
                    "name": "Business Rules",
                    "type": "master",
                    "retention_policy": "Superseded + 3 years",
                },
                {"name": "User Data", "type": "master", "retention_policy": "User lifecycle"},
                {"name": "Analytics Data", "type": "analytical", "retention_policy": "3 years"},
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "Process Modeling",
                    "type": "design",
                    "description": "Visual BPMN process design",
                },
                {"name": "UI Design", "type": "design", "description": "SAIL interface design"},
                {
                    "name": "Process Execution",
                    "type": "runtime",
                    "description": "Execute process instances",
                },
                {
                    "name": "Task Management",
                    "type": "workflow",
                    "description": "Assign and route tasks",
                },
                {
                    "name": "Process Discovery",
                    "type": "analytics",
                    "description": "Mine processes from logs",
                },
                {"name": "Bot Execution", "type": "automation", "description": "Execute RPA bots"},
                {
                    "name": "Document Extraction",
                    "type": "ai",
                    "description": "Extract data from documents",
                },
                {
                    "name": "Data Virtualization",
                    "type": "data",
                    "description": "Unified data access",
                },
                {
                    "name": "Business Rules Execution",
                    "type": "decision",
                    "description": "Execute business rules",
                },
                {
                    "name": "API Integration",
                    "type": "integration",
                    "description": "Connect to external systems",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "Chief Digital Officer",
                    "role": "executive",
                    "concerns": ["Digital Transformation", "Innovation", "ROI"],
                    "influence": "high",
                },
                {
                    "name": "VP Process Excellence",
                    "role": "executive",
                    "concerns": ["Process Optimization", "Automation", "Efficiency"],
                    "influence": "high",
                },
                {
                    "name": "CIO",
                    "role": "executive",
                    "concerns": ["Technology Strategy", "Integration", "Governance"],
                    "influence": "high",
                },
                {
                    "name": "Business Process Owners",
                    "role": "management",
                    "concerns": ["Process Performance", "User Adoption", "Continuous Improvement"],
                    "influence": "high",
                },
                {
                    "name": "IT Director",
                    "role": "technical",
                    "concerns": ["Platform Management", "Security", "Scalability"],
                    "influence": "high",
                },
                {
                    "name": "Citizen Developers",
                    "role": "technical",
                    "concerns": ["Tool Usability", "Training", "Support"],
                    "influence": "medium",
                },
                {
                    "name": "Professional Developers",
                    "role": "technical",
                    "concerns": ["Technical Capabilities", "Integration", "Performance"],
                    "influence": "medium",
                },
                {
                    "name": "Operations Manager",
                    "role": "management",
                    "concerns": ["Automation ROI", "Process Efficiency", "Cost Reduction"],
                    "influence": "high",
                },
                {
                    "name": "Compliance Officer",
                    "role": "governance",
                    "concerns": ["Regulatory Compliance", "Audit Trail", "Data Privacy"],
                    "influence": "high",
                },
                {
                    "name": "End Users",
                    "role": "operational",
                    "concerns": ["User Experience", "Performance", "Training"],
                    "influence": "medium",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Digital Transformation Imperative",
                    "description": "Company-wide digital transformation mandate",
                    "urgency": "critical",
                    "impact": "transformational",
                },
                {
                    "name": "Legacy Application Portfolio",
                    "description": "Aging custom applications expensive to maintain",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Slow Time-to-Market",
                    "description": "Traditional development too slow",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Process Inefficiency",
                    "description": "Manual processes and disconnected systems",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "IT Backlog",
                    "description": "2 - year backlog for new applications",
                    "urgency": "critical",
                    "impact": "high",
                },
                {
                    "name": "Competitive Pressure",
                    "description": "Competitors more agile with technology",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Customer Experience Gap",
                    "description": "Customer-facing processes outdated",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Compliance Requirements",
                    "description": "Need audit trails and process documentation",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Shadow IT Growth",
                    "description": "Business units building unauthorized solutions",
                    "urgency": "medium",
                    "impact": "medium",
                },
                {
                    "name": "Developer Shortage",
                    "description": "Cannot hire enough developers",
                    "urgency": "high",
                    "impact": "high",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "10x Faster Application Delivery",
                    "description": "Reduce time from idea to production",
                    "timeframe": "12 months",
                    "measurable": "From 12 months to 6 weeks average",
                },
                {
                    "name": "Empower Citizen Developers",
                    "description": "Enable business users to build apps",
                    "timeframe": "18 months",
                    "measurable": "50% of apps built by citizen developers",
                },
                {
                    "name": "Automate 100 Processes",
                    "description": "Automate top manual processes",
                    "timeframe": "24 months",
                    "measurable": "100 processes automated, 80% automation rate",
                },
                {
                    "name": "Achieve Process Excellence",
                    "description": "Optimize all critical processes",
                    "timeframe": "18 months",
                    "measurable": "30% cycle time reduction across all processes",
                },
                {
                    "name": "Reduce IT Backlog 75%",
                    "description": "Clear application backlog",
                    "timeframe": "12 months",
                    "measurable": "Backlog from 24 months to 6 months",
                },
                {
                    "name": "Deploy 20 Mobile Apps",
                    "description": "Mobile-enable field workforce",
                    "timeframe": "18 months",
                    "measurable": "20 mobile apps deployed",
                },
                {
                    "name": "Achieve 95% User Satisfaction",
                    "description": "High user adoption and satisfaction",
                    "timeframe": "24 months",
                    "measurable": "NPS > 50, satisfaction > 95%",
                },
                {
                    "name": "Save $10M Annually",
                    "description": "Process automation cost savings",
                    "timeframe": "24 months",
                    "measurable": "$10M annual run-rate savings",
                },
                {
                    "name": "100% Compliance",
                    "description": "Full audit trail and compliance",
                    "timeframe": "12 months",
                    "measurable": "Zero compliance findings",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "Acceleration",
                    "description": "Dramatically faster application delivery",
                    "benefit_type": "strategic",
                    "quantified_benefit": "10x faster, 6 weeks average vs 12 months",
                },
                {
                    "name": "Democratization",
                    "description": "Business users building applications",
                    "benefit_type": "strategic",
                    "quantified_benefit": "50% of apps by citizen developers, 500 trained",
                },
                {
                    "name": "Process Excellence",
                    "description": "Optimized and automated processes",
                    "benefit_type": "operational",
                    "quantified_benefit": "100 processes automated, 30% cycle time reduction, $10M savings",
                },
                {
                    "name": "Agility",
                    "description": "Rapid response to business needs",
                    "benefit_type": "strategic",
                    "quantified_benefit": "75% IT backlog reduction, 2 - week average response time",
                },
                {
                    "name": "Innovation",
                    "description": "New digital capabilities",
                    "benefit_type": "strategic",
                    "quantified_benefit": "20 mobile apps, 50 integrated applications",
                },
                {
                    "name": "User Experience",
                    "description": "Modern, intuitive applications",
                    "benefit_type": "operational",
                    "quantified_benefit": "95% user satisfaction, NPS > 50",
                },
                {
                    "name": "Compliance Confidence",
                    "description": "Complete audit trail and governance",
                    "benefit_type": "compliance",
                    "quantified_benefit": "100% compliance, zero findings",
                },
                {
                    "name": "Cost Optimization",
                    "description": "Reduced development and operations costs",
                    "benefit_type": "financial",
                    "quantified_benefit": "$10M annual savings, 60% lower TCO",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Business-Led Development",
                    "description": "Empower business users to build solutions",
                    "rationale": "Faster delivery, better alignment",
                },
                {
                    "name": "Process-Centric",
                    "description": "Design around end-to-end processes",
                    "rationale": "Optimize entire value streams",
                },
                {
                    "name": "Cloud-First",
                    "description": "Default to cloud deployment",
                    "rationale": "Scalability and reduced infrastructure burden",
                },
                {
                    "name": "API-First",
                    "description": "Everything accessible via API",
                    "rationale": "Enable integration and reusability",
                },
                {
                    "name": "Mobile-First",
                    "description": "Design for mobile devices",
                    "rationale": "Support mobile workforce",
                },
                {
                    "name": "Data-Driven",
                    "description": "Use process mining and analytics",
                    "rationale": "Optimize based on actual data",
                },
                {
                    "name": "Governance by Design",
                    "description": "Build governance into platform",
                    "rationale": "Balance agility with control",
                },
                {
                    "name": "Reusability",
                    "description": "Build reusable components",
                    "rationale": "Accelerate future development",
                },
                {
                    "name": "Security First",
                    "description": "Security built into platform",
                    "rationale": "Protect enterprise data",
                },
                {
                    "name": "Continuous Improvement",
                    "description": "Monitor and optimize continuously",
                    "rationale": "Sustain performance improvements",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "Platform Availability",
                    "type": "performance",
                    "description": "99.9% platform uptime",
                    "priority": "critical",
                },
                {
                    "name": "Response Time",
                    "type": "performance",
                    "description": "< 2 sec page load time",
                    "priority": "high",
                },
                {
                    "name": "Concurrent Users",
                    "type": "capacity",
                    "description": "Support 10,000 concurrent users",
                    "priority": "high",
                },
                {
                    "name": "Application Deployment",
                    "type": "performance",
                    "description": "Deploy application in < 10 minutes",
                    "priority": "medium",
                },
                {
                    "name": "Process Execution",
                    "type": "performance",
                    "description": "Process instance creation < 1 sec",
                    "priority": "high",
                },
                {
                    "name": "Mobile Support",
                    "type": "functional",
                    "description": "Native iOS and Android apps",
                    "priority": "critical",
                },
                {
                    "name": "API Performance",
                    "type": "performance",
                    "description": "API response < 500ms",
                    "priority": "high",
                },
                {
                    "name": "Audit Trail",
                    "type": "compliance",
                    "description": "Complete audit trail for all actions",
                    "priority": "critical",
                },
                {
                    "name": "Data Retention",
                    "type": "compliance",
                    "description": "7 - year data retention",
                    "priority": "critical",
                },
                {
                    "name": "SSO Integration",
                    "type": "security",
                    "description": "Enterprise SSO support",
                    "priority": "critical",
                },
                {
                    "name": "Localization",
                    "type": "functional",
                    "description": "Support 20+ languages",
                    "priority": "high",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget Limitation",
                    "type": "financial",
                    "description": "Total program budget $5M",
                },
                {
                    "name": "Timeline Pressure",
                    "type": "schedule",
                    "description": "Must show quick wins in 3 months",
                },
                {
                    "name": "Skills Gap",
                    "type": "resource",
                    "description": "Limited low-code development expertise",
                },
                {
                    "name": "Change Management",
                    "type": "organizational",
                    "description": "Significant cultural change required",
                },
                {
                    "name": "Integration Complexity",
                    "type": "technical",
                    "description": "Complex legacy system landscape",
                },
                {
                    "name": "Data Privacy",
                    "type": "compliance",
                    "description": "GDPR, CCPA compliance required",
                },
                {
                    "name": "Network Bandwidth",
                    "type": "technical",
                    "description": "Limited bandwidth in some locations",
                },
                {
                    "name": "Governance Framework",
                    "type": "organizational",
                    "description": "Must establish citizen developer governance",
                },
                {
                    "name": "Vendor Lock-In Concern",
                    "type": "strategic",
                    "description": "Executive concern about platform dependency",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "Digital Maturity Assessment",
                    "type": "maturity",
                    "description": "Organization digital capability",
                    "result": "Level 2 maturity, significant opportunity",
                },
                {
                    "name": "Process Maturity Assessment",
                    "type": "maturity",
                    "description": "Process management capability",
                    "result": "Ad-hoc processes, significant improvement needed",
                },
                {
                    "name": "Technical Readiness",
                    "type": "technical",
                    "description": "Infrastructure and integration readiness",
                    "result": "Cloud-ready, complex integration landscape",
                },
                {
                    "name": "ROI Analysis",
                    "type": "financial",
                    "description": "Business case validation",
                    "result": "Projected 420% ROI over 5 years, payback 18 months",
                },
                {
                    "name": "Change Readiness",
                    "type": "organizational",
                    "description": "Organizational change capability",
                    "result": "Moderate readiness, strong executive support, training needed",
                },
            ]
        ),
        # ==================== IMPLEMENTATION & MIGRATION LAYER ====================
        implementation_events=json.dumps(
            [
                {
                    "name": "Program Kickoff",
                    "date": "2024 - 01 - 15",
                    "milestone": True,
                    "description": "Project charter and CoE formation",
                },
                {
                    "name": "Appian Cloud Operational",
                    "date": "2024 - 03 - 01",
                    "milestone": True,
                    "description": "Platform deployed and configured",
                },
                {
                    "name": "First Quick Win App",
                    "date": "2024 - 04 - 15",
                    "milestone": True,
                    "description": "First application in production",
                },
                {
                    "name": "Citizen Developer Training Complete",
                    "date": "2024 - 06 - 30",
                    "milestone": False,
                    "description": "100 citizen developers trained",
                },
                {
                    "name": "Process Mining Deployed",
                    "date": "2024 - 08 - 31",
                    "milestone": True,
                    "description": "Process mining operational",
                },
                {
                    "name": "RPA Integration Complete",
                    "date": "2024 - 10 - 31",
                    "milestone": False,
                    "description": "RPA bots integrated",
                },
                {
                    "name": "50 Processes Automated",
                    "date": "2025 - 06 - 30",
                    "milestone": True,
                    "description": "Halfway to automation goal",
                },
                {
                    "name": "Mobile Apps Deployed",
                    "date": "2025 - 09 - 30",
                    "milestone": False,
                    "description": "20 mobile apps live",
                },
                {
                    "name": "100 Processes Automated",
                    "date": "2026 - 01 - 15",
                    "milestone": True,
                    "description": "Automation goal achieved",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Program Management",
                    "description": "Overall program governance and CoE",
                    "duration_weeks": 104,
                    "team_size": 6,
                },
                {
                    "name": "Platform Deployment",
                    "description": "Appian Cloud setup and configuration",
                    "duration_weeks": 8,
                    "team_size": 8,
                },
                {
                    "name": "Quick Win Applications",
                    "description": "Initial high-value applications",
                    "duration_weeks": 20,
                    "team_size": 12,
                },
                {
                    "name": "Citizen Developer Program",
                    "description": "Training and enablement",
                    "duration_weeks": 78,
                    "team_size": 4,
                },
                {
                    "name": "Process Mining Implementation",
                    "description": "Process discovery and optimization",
                    "duration_weeks": 32,
                    "team_size": 6,
                },
                {
                    "name": "RPA Integration",
                    "description": "Integrate RPA capabilities",
                    "duration_weeks": 24,
                    "team_size": 8,
                },
                {
                    "name": "Core Process Automation",
                    "description": "Automate top 50 processes",
                    "duration_weeks": 78,
                    "team_size": 20,
                },
                {
                    "name": "Mobile App Development",
                    "description": "Build mobile applications",
                    "duration_weeks": 52,
                    "team_size": 10,
                },
                {
                    "name": "Integration Development",
                    "description": "Connect to enterprise systems",
                    "duration_weeks": 60,
                    "team_size": 12,
                },
                {
                    "name": "Change Management",
                    "description": "User adoption and training",
                    "duration_weeks": 104,
                    "team_size": 6,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Digital Transformation Strategy",
                    "type": "document",
                    "due_phase": "initiation",
                    "owner": "CDO",
                },
                {
                    "name": "Appian Cloud Platform",
                    "type": "cloud-platform",
                    "due_phase": "build",
                    "owner": "Platform Lead",
                },
                {
                    "name": "Center of Excellence",
                    "type": "organization",
                    "due_phase": "initiation",
                    "owner": "CoE Lead",
                },
                {
                    "name": "Quick Win Applications",
                    "type": "applications",
                    "due_phase": "build",
                    "owner": "Development Team",
                },
                {
                    "name": "Citizen Developer Program",
                    "type": "training-program",
                    "due_phase": "prepare",
                    "owner": "Training Lead",
                },
                {
                    "name": "Process Mining Platform",
                    "type": "analytics-platform",
                    "due_phase": "build",
                    "owner": "Process Excellence",
                },
                {
                    "name": "Automated Processes",
                    "type": "process-automation",
                    "due_phase": "build",
                    "owner": "Process Owners",
                },
                {
                    "name": "Mobile Applications",
                    "type": "mobile-apps",
                    "due_phase": "build",
                    "owner": "Mobile Lead",
                },
                {
                    "name": "Integration Framework",
                    "type": "integration",
                    "due_phase": "build",
                    "owner": "Integration Architect",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "Platform Ready",
                    "date": "2024 - 03 - 01",
                    "description": "Appian Cloud operational",
                },
                {
                    "name": "First Success",
                    "date": "2024 - 04 - 15",
                    "description": "First application in production",
                },
                {
                    "name": "Citizen Developers Active",
                    "date": "2024 - 06 - 30",
                    "description": "100 citizen developers trained",
                },
                {
                    "name": "Process Intelligence",
                    "date": "2024 - 08 - 31",
                    "description": "Process mining discovering opportunities",
                },
                {
                    "name": "Automation at Scale",
                    "date": "2025 - 06 - 30",
                    "description": "50 processes automated",
                },
                {
                    "name": "Mobile Enabled",
                    "date": "2025 - 09 - 30",
                    "description": "Mobile workforce enabled",
                },
                {
                    "name": "Transformation Complete",
                    "date": "2026 - 01 - 15",
                    "description": "100 processes automated, goals achieved",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "Appian Cloud US-East",
                    "location": "AWS US-East - 1",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "Primary cloud region",
                },
                {
                    "name": "Appian Cloud US-West",
                    "location": "AWS US-West - 2",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "Secondary cloud region",
                },
                {
                    "name": "Appian Cloud EU",
                    "location": "AWS EU-West - 1",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "European cloud region",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "Cloud Application Instances",
                    "type": "cloud-vm",
                    "quantity": 20,
                    "location": "AWS",
                    "specs": "r5.4xlarge, 16 vCPU, 128GB RAM",
                },
                {
                    "name": "Cloud Database Instances",
                    "type": "cloud-database",
                    "quantity": 4,
                    "location": "AWS",
                    "specs": "r5.8xlarge, 32 vCPU, 256GB RAM",
                },
                {
                    "name": "Process Mining Instances",
                    "type": "cloud-vm",
                    "quantity": 5,
                    "location": "AWS",
                    "specs": "c5.9xlarge, 36 vCPU, 72GB RAM",
                },
                {
                    "name": "Developer Workstations",
                    "type": "laptop",
                    "quantity": 150,
                    "location": "Offices",
                    "specs": "Modern laptops with browsers",
                },
                {
                    "name": "Mobile Devices",
                    "type": "mobile",
                    "quantity": 500,
                    "location": "Field",
                    "specs": "iOS/Android devices",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "AWS Cloud Network",
                    "type": "cloud-vpc",
                    "coverage": "Global",
                    "bandwidth_mbps": 100000,
                    "provider": "AWS",
                },
                {
                    "name": "AWS DirectConnect",
                    "type": "dedicated-link",
                    "coverage": "Corporate to Cloud",
                    "bandwidth_mbps": 10000,
                    "provider": "AWS",
                },
                {
                    "name": "CloudFront CDN",
                    "type": "cdn",
                    "coverage": "Global",
                    "bandwidth_mbps": 1000000,
                    "provider": "AWS",
                },
                {
                    "name": "Corporate Network",
                    "type": "wan",
                    "coverage": "All Sites",
                    "bandwidth_mbps": 1000,
                    "provider": "AT&T",
                },
            ]
        ),
    )


def seed_appian(link_capabilities: bool = True):
    """Seed the Appian vendor template and optionally link capabilities."""
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(vendor_name="Appian Corporation").first()
            if existing:
                print("⚠️  Appian template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_appian_template()
            db.session.add(template)
            db.session.commit()

            print("✅ Appian template seeded successfully!")
            print(f"   - Vendor: {template.vendor_name}")
            print(f"   - Technology Layer: ✅ Complete")
            print(f"   - Strategy Layer: ✅ Complete (20 capabilities, 6 value streams)")
            print(
                f"   - Business Layer: ✅ Complete (10 services, 6 processes, 8 objects, 10 actors, 7 products)"
            )
            print(
                f"   - Application Layer: ✅ Complete (12 components, 10 services, 7 interfaces, 9 data objects, 10 functions)"
            )
            print(
                f"   - Motivation Layer: ✅ Complete (10 stakeholders, 10 drivers, 9 goals, 8 outcomes, 10 principles, 11 requirements, 9 constraints, 5 assessments)"
            )
            print(
                f"   - Implementation Layer: ✅ Complete (9 events, 10 work packages, 9 deliverables, 7 plateaus)"
            )
            print(f"   - Physical Layer: ✅ Complete (3 facilities, 5 equipment types, 4 networks)")
            print(f"   - Total ArchiMate Coverage: 100%")
            # Link capabilities to BusinessCapability records
            if link_capabilities:
                print("\n🔗 Linking capabilities to BusinessCapability records...")
                from app.commands.vendor_capability_linker import VendorCapabilityLinker

                linker = VendorCapabilityLinker()
                results = linker.link_vendor_template_to_capabilities(
                    template,
                    create_missing=True,  # Create BusinessCapability if not exists
                    auto_link_fuzzy=False,  # Don't auto-link fuzzy matches (require exact)
                )

                linker.print_report(results)

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding Appian template: {str(e)}")
            import traceback

            traceback.print_exc()

            raise


if __name__ == "__main__":
    seed_appian()
