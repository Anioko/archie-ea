"""
Mendix Low-Code Platform Comprehensive Vendor Template Seed Data

Complete ArchiMate 3.2 coverage across ALL layers:
- Strategy Layer
- Business Layer
- Application Layer
- Technology Layer
- Motivation Layer
- Implementation & Migration Layer
- Physical Layer

Run with: python manage.py seed-vendor-mendix
"""
import json

from app import create_app, db
from app.models import User, VendorStackTemplate
from config import DevelopmentConfig


def create_mendix_template():
    """Mendix FULLY COMPREHENSIVE template - ALL ArchiMate 3.2 layers"""
    return VendorStackTemplate(
        vendor_name="Mendix",
        name="Mendix Low-Code Application Platform",
        description="Enterprise low-code platform for rapid application development, enabling visual development of web and mobile applications with built-in collaboration, DevOps, and cloud deployment capabilities",
        # ==================== TECHNOLOGY LAYER ====================
        platform="cloud",
        primary_language="java",
        framework="Mendix Runtime",
        framework_version="10.6",
        primary_database="postgresql",
        database_version="15.0",
        container_runtime="docker",
        orchestration="kubernetes",
        service_mesh="istio",
        api_standard="REST",
        api_gateway="mendix-api-gateway",
        message_broker="kafka",
        auth_provider="mendix-sso",
        secrets_manager="hashicorp-vault",
        logging_framework="mendix-logging",
        metrics_platform="prometheus",
        apm_tool="new-relic",
        tracing_tool="jaeger",
        build_tool="mendix-studio-pro",
        ci_cd_platform="mendix-cloud-portal",
        sast_tool="veracode",
        dast_tool="burp-suite",
        dependency_scanner="snyk",
        nodes=json.dumps(
            [
                {
                    "name": "Mendix Runtime Server Primary",
                    "type": "container",
                    "os": "Linux",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "Mendix Runtime Server Secondary",
                    "type": "container",
                    "os": "Linux",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "PostgreSQL Primary Database",
                    "type": "container",
                    "os": "Linux",
                    "cpu_cores": 4,
                    "ram_gb": 16,
                },
                {
                    "name": "PostgreSQL Replica Database",
                    "type": "container",
                    "os": "Linux",
                    "cpu_cores": 4,
                    "ram_gb": 16,
                },
                {
                    "name": "Mendix Studio Pro Workstation",
                    "type": "virtual-machine",
                    "os": "Windows 11",
                    "cpu_cores": 8,
                    "ram_gb": 16,
                },
                {
                    "name": "Mendix Cloud Portal",
                    "type": "cloud-platform",
                    "os": "Cloud",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
                {
                    "name": "Build Server",
                    "type": "container",
                    "os": "Linux",
                    "cpu_cores": 4,
                    "ram_gb": 8,
                },
            ]
        ),
        devices=json.dumps(
            [
                {
                    "name": "Mendix Load Balancer",
                    "type": "load-balancer",
                    "description": "Distributes traffic across runtime instances",
                },
                {
                    "name": "CDN Edge Nodes",
                    "type": "cdn",
                    "description": "Content delivery network for static assets",
                },
                {
                    "name": "API Gateway Appliance",
                    "type": "api-gateway",
                    "description": "Manages external API access",
                },
                {
                    "name": "Web Application Firewall",
                    "type": "firewall",
                    "description": "Protects applications from web attacks",
                },
                {
                    "name": "Mobile Device Manager",
                    "type": "mdm",
                    "description": "Manages mobile app deployments",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {"name": "Mendix Runtime", "type": "application-server", "version": "10.6"},
                {"name": "Mendix Studio Pro", "type": "ide", "version": "10.6"},
                {"name": "Java Runtime Environment", "type": "runtime", "version": "11"},
                {"name": "PostgreSQL", "type": "database-engine", "version": "15.0"},
                {"name": "Nginx", "type": "web-server", "version": "1.24"},
                {"name": "Docker Engine", "type": "container-runtime", "version": "24.0"},
                {"name": "Kubernetes", "type": "orchestration", "version": "1.28"},
                {
                    "name": "Mendix Native Mobile Builder",
                    "type": "mobile-build-tool",
                    "version": "10.6",
                },
                {"name": "Node.js", "type": "runtime", "version": "18.0"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "Mendix Runtime Service",
                    "type": "application-runtime",
                    "description": "Executes Mendix applications",
                },
                {
                    "name": "Mendix Data Hub",
                    "type": "data-catalog",
                    "description": "Central data discovery and integration",
                },
                {
                    "name": "Mendix Model API",
                    "type": "api-service",
                    "description": "Programmatic model manipulation",
                },
                {
                    "name": "Mendix SSO Service",
                    "type": "authentication",
                    "description": "Single sign-on for all apps",
                },
                {
                    "name": "Mendix Cloud Portal API",
                    "type": "platform-api",
                    "description": "Platform management API",
                },
                {
                    "name": "Mendix App Store",
                    "type": "marketplace",
                    "description": "Component and module marketplace",
                },
                {
                    "name": "Mendix Build Service",
                    "type": "build-automation",
                    "description": "Automated application builds",
                },
                {
                    "name": "Mendix Deploy API",
                    "type": "deployment-service",
                    "description": "Application deployment automation",
                },
                {
                    "name": "Mendix Feedback Widget Service",
                    "type": "collaboration",
                    "description": "In-app feedback collection",
                },
                {
                    "name": "Mendix Mobile Services",
                    "type": "mobile-platform",
                    "description": "Native mobile app services",
                },
                {
                    "name": "Mendix Analytics",
                    "type": "analytics",
                    "description": "Application performance insights",
                },
                {
                    "name": "Mendix Workflow Engine",
                    "type": "workflow",
                    "description": "Business process automation",
                },
                {
                    "name": "Mendix AI Bot Service",
                    "type": "ai-service",
                    "description": "Conversational AI integration",
                },
                {
                    "name": "Mendix Email Service",
                    "type": "messaging",
                    "description": "Email delivery service",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "Mendix App Package (.mda)",
                    "type": "deployment-package",
                    "size_mb": 50,
                    "registry": "Mendix Cloud Portal",
                },
                {
                    "name": "Mendix Project File (.mpr)",
                    "type": "source-code",
                    "size_mb": 10,
                    "registry": "Git Repository",
                },
                {
                    "name": "Custom Java Module (.jar)",
                    "type": "library",
                    "size_mb": 5,
                    "registry": "Mendix App Store",
                },
                {
                    "name": "Mendix Widget Package",
                    "type": "ui-component",
                    "size_mb": 1,
                    "registry": "Mendix App Store",
                },
                {
                    "name": "Mendix Module Package",
                    "type": "module",
                    "size_mb": 3,
                    "registry": "Mendix App Store",
                },
                {
                    "name": "Container Image",
                    "type": "container-image",
                    "size_mb": 500,
                    "registry": "Mendix Container Registry",
                },
                {
                    "name": "Database Backup",
                    "type": "backup-archive",
                    "size_mb": 1000,
                    "registry": "Mendix Cloud Storage",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "Mendix Production Network",
                    "type": "vpc",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 2,
                },
                {
                    "name": "Database Replication Network",
                    "type": "private",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 1,
                },
                {
                    "name": "Internet Gateway",
                    "type": "wan",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 20,
                },
                {"name": "VPN Connection", "type": "vpn", "bandwidth_mbps": 500, "latency_ms": 30},
                {"name": "CDN Network", "type": "cdn", "bandwidth_mbps": 100000, "latency_ms": 10},
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="Mendix (Siemens)",
        market_position="leader",
        company_size="enterprise",
        founded_year=2005,
        headquarters="Boston, MA / Rotterdam, Netherlands",
        revenue_usd=300000000,
        customer_count=4000,
        market_share_percentage=15.0,
        acquisition_risk="low",
        financial_health="strong",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                {
                    "name": "Visual Application Development",
                    "description": "Drag-and-drop application modeling with visual IDE",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Multi-Experience Development",
                    "description": "Single model for web, mobile, and progressive web apps",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Collaborative Development",
                    "description": "Team collaboration with version control and branching",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "API-First Integration",
                    "description": "Built-in REST, SOAP, OData API consumption and publishing",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Data Modeling & Management",
                    "description": "Visual data modeling with automated database schema generation",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Workflow Automation",
                    "description": "Visual workflow designer with BPMN support",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "UI/UX Design System",
                    "description": "Responsive design with Atlas UI framework",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Microservices Architecture",
                    "description": "Container-based deployment with microservices patterns",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "DevOps & CI/CD",
                    "description": "Automated build, test, and deployment pipelines",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Cloud-Native Deployment",
                    "description": "Multi-cloud and on-premise deployment options",
                    "coverage_percentage": 93,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Application Lifecycle Management",
                    "description": "Complete ALM from dev to production",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Security & Compliance",
                    "description": "Built-in security controls and compliance frameworks",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "Analytics & Monitoring",
                    "description": "Real-time application performance monitoring",
                    "coverage_percentage": 85,
                    "maturity_level": "managed",
                },
                {
                    "name": "Extensibility & Custom Code",
                    "description": "Java and JavaScript extension points",
                    "coverage_percentage": 92,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Data Integration Hub",
                    "description": "Centralized data catalog and OData services",
                    "coverage_percentage": 87,
                    "maturity_level": "managed",
                },
                {
                    "name": "AI & Machine Learning Integration",
                    "description": "Pre-built AI services and ML model integration",
                    "coverage_percentage": 82,
                    "maturity_level": "defined",
                },
                {
                    "name": "Mobile App Development",
                    "description": "Native iOS and Android app generation",
                    "coverage_percentage": 93,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Citizen Developer Enablement",
                    "description": "Low-code tools for business users",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "Enterprise Marketplace",
                    "description": "App Store for reusable components and modules",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Multi-Tenancy Support",
                    "description": "SaaS application development capabilities",
                    "coverage_percentage": 86,
                    "maturity_level": "managed",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Idea-to-Application",
                    "stages": [
                        "Business Requirement",
                        "Visual Modeling",
                        "Rapid Prototyping",
                        "User Testing",
                        "Iterative Development",
                        "Deployment",
                        "Feedback Loop",
                    ],
                    "description": "Rapid application development lifecycle",
                },
                {
                    "name": "Develop-to-Deploy",
                    "stages": ["Code", "Build", "Test", "Package", "Deploy", "Monitor", "Iterate"],
                    "description": "DevOps pipeline for app delivery",
                },
                {
                    "name": "Integrate-to-Operate",
                    "stages": [
                        "API Discovery",
                        "Integration Design",
                        "Data Mapping",
                        "Testing",
                        "Deployment",
                        "Monitoring",
                        "Optimization",
                    ],
                    "description": "Enterprise integration workflow",
                },
                {
                    "name": "Design-to-Experience",
                    "stages": [
                        "UX Research",
                        "Design System",
                        "Prototype",
                        "User Testing",
                        "Implementation",
                        "Deployment",
                        "Analytics",
                    ],
                    "description": "User experience development",
                },
                {
                    "name": "Request-to-Resolution",
                    "stages": [
                        "Intake",
                        "Triage",
                        "Assignment",
                        "Development",
                        "Testing",
                        "Deployment",
                        "Support",
                    ],
                    "description": "Application request management",
                },
                {
                    "name": "Plan-to-Operate",
                    "stages": [
                        "Platform Planning",
                        "Environment Setup",
                        "App Development",
                        "Quality Assurance",
                        "Go-Live",
                        "Operations",
                        "Optimization",
                    ],
                    "description": "Platform operations lifecycle",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "Greenfield Low-Code Transformation",
                    "description": "Start new projects with Mendix from scratch",
                    "timeline_months": 6,
                    "risk_level": "low",
                },
                {
                    "name": "Legacy Modernization",
                    "description": "Replace legacy apps with Mendix applications",
                    "timeline_months": 12,
                    "risk_level": "medium",
                },
                {
                    "name": "Citizen Developer Program",
                    "description": "Enable business users to build apps",
                    "timeline_months": 9,
                    "risk_level": "low",
                },
                {
                    "name": "Center of Excellence",
                    "description": "Establish Mendix CoE with best practices",
                    "timeline_months": 6,
                    "risk_level": "low",
                },
                {
                    "name": "Cloud Migration",
                    "description": "Move on-premise apps to Mendix Cloud",
                    "timeline_months": 4,
                    "risk_level": "low",
                },
                {
                    "name": "Hybrid Integration",
                    "description": "Integrate Mendix with existing enterprise systems",
                    "timeline_months": 8,
                    "risk_level": "medium",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Application Development Service",
                    "description": "Build custom enterprise applications",
                    "service_type": "internal",
                    "sla_commitment": "24/7 platform availability",
                },
                {
                    "name": "API Management Service",
                    "description": "Publish and consume REST/SOAP APIs",
                    "service_type": "internal",
                    "sla_commitment": "99.95% API uptime",
                },
                {
                    "name": "Data Integration Service",
                    "description": "Connect and integrate data sources",
                    "service_type": "internal",
                    "sla_commitment": "Real-time data sync",
                },
                {
                    "name": "Mobile App Delivery",
                    "description": "Deploy native mobile applications",
                    "service_type": "customer-facing",
                    "sla_commitment": "Same-day app updates",
                },
                {
                    "name": "Workflow Automation Service",
                    "description": "Automate business processes",
                    "service_type": "internal",
                    "sla_commitment": "< 1 second process execution",
                },
                {
                    "name": "User Experience Design",
                    "description": "Create responsive user interfaces",
                    "service_type": "supporting",
                    "sla_commitment": "Design system compliance",
                },
                {
                    "name": "Platform Administration",
                    "description": "Manage Mendix environments",
                    "service_type": "supporting",
                    "sla_commitment": "24/7 support",
                },
                {
                    "name": "Application Monitoring",
                    "description": "Monitor app performance and health",
                    "service_type": "supporting",
                    "sla_commitment": "Real-time alerts",
                },
                {
                    "name": "Security Management",
                    "description": "Manage authentication and authorization",
                    "service_type": "supporting",
                    "sla_commitment": "Zero security breaches",
                },
                {
                    "name": "Development Training",
                    "description": "Train developers on Mendix platform",
                    "service_type": "supporting",
                    "sla_commitment": "Monthly training sessions",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Application Development Process",
                    "description": "End-to-end app creation workflow",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Requirements Gathering",
                        "Visual Modeling",
                        "Data Model Design",
                        "UI Design",
                        "Logic Implementation",
                        "Testing",
                        "Deployment",
                        "Monitoring",
                    ],
                    "cycle_time": "2 - 8 weeks",
                    "kpis": ["Time to Market", "Developer Productivity", "Code Quality"],
                },
                {
                    "name": "API Integration Process",
                    "description": "Connect external systems via APIs",
                    "automation_level": "partially-automated",
                    "steps": [
                        "API Discovery",
                        "Service Definition",
                        "Mapping Configuration",
                        "Testing",
                        "Deployment",
                        "Monitoring",
                    ],
                    "cycle_time": "1 - 2 weeks",
                    "kpis": ["Integration Success Rate", "API Response Time", "Data Accuracy"],
                },
                {
                    "name": "Mobile App Deployment",
                    "description": "Build and deploy mobile apps",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Native Build",
                        "Code Signing",
                        "App Store Submission",
                        "Review",
                        "Publication",
                        "Distribution",
                    ],
                    "cycle_time": "1 - 3 days",
                    "kpis": ["Build Success Rate", "App Store Approval Time", "User Adoption"],
                },
                {
                    "name": "DevOps Pipeline",
                    "description": "Continuous integration and deployment",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Code Commit",
                        "Build",
                        "Unit Tests",
                        "Integration Tests",
                        "Package",
                        "Deploy",
                        "Smoke Tests",
                    ],
                    "cycle_time": "< 1 hour",
                    "kpis": ["Deployment Frequency", "Lead Time", "Change Failure Rate"],
                },
                {
                    "name": "Platform Governance",
                    "description": "Manage platform standards and compliance",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Policy Definition",
                        "App Review",
                        "Compliance Check",
                        "Approval",
                        "Deployment",
                        "Audit",
                    ],
                    "cycle_time": "1 - 3 days",
                    "kpis": ["Compliance Rate", "Policy Violations", "Review Time"],
                },
                {
                    "name": "User Feedback Loop",
                    "description": "Collect and act on user feedback",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Feedback Collection",
                        "Triage",
                        "Prioritization",
                        "Development",
                        "Testing",
                        "Release",
                    ],
                    "cycle_time": "1 - 2 weeks",
                    "kpis": ["User Satisfaction", "Feedback Resolution Time", "Feature Adoption"],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Mendix Application",
                    "description": "Deployable application package",
                    "lifecycle": "created -> developed -> tested -> deployed -> maintained -> retired",
                },
                {
                    "name": "Data Model",
                    "description": "Entity and relationship definitions",
                    "lifecycle": "designed -> validated -> generated -> versioned -> archived",
                },
                {
                    "name": "Microflow",
                    "description": "Business logic workflow",
                    "lifecycle": "created -> tested -> deployed -> executed -> optimized",
                },
                {
                    "name": "Page",
                    "description": "User interface definition",
                    "lifecycle": "designed -> prototyped -> implemented -> published -> maintained",
                },
                {
                    "name": "API Service",
                    "description": "Published or consumed API",
                    "lifecycle": "defined -> tested -> published -> monitored -> versioned",
                },
                {
                    "name": "Module",
                    "description": "Reusable application component",
                    "lifecycle": "created -> tested -> published -> consumed -> maintained",
                },
                {
                    "name": "User Role",
                    "description": "Security role definition",
                    "lifecycle": "defined -> assigned -> monitored -> audited",
                },
                {
                    "name": "Environment",
                    "description": "Deployment environment (dev/test/prod)",
                    "lifecycle": "provisioned -> configured -> active -> archived",
                },
                {
                    "name": "Build Package",
                    "description": "Deployable artifact",
                    "lifecycle": "built -> tested -> deployed -> archived",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Citizen Developer",
                    "description": "Business user building apps",
                    "responsibilities": [
                        "App Development",
                        "Requirements Translation",
                        "User Testing",
                        "Documentation",
                    ],
                },
                {
                    "name": "Professional Developer",
                    "description": "Technical developer",
                    "responsibilities": [
                        "Complex Logic",
                        "Integrations",
                        "Custom Code",
                        "Performance Optimization",
                    ],
                },
                {
                    "name": "UX Designer",
                    "description": "User experience designer",
                    "responsibilities": [
                        "UI Design",
                        "Wireframing",
                        "Prototyping",
                        "Usability Testing",
                    ],
                },
                {
                    "name": "Business Analyst",
                    "description": "Requirements analyst",
                    "responsibilities": [
                        "Requirements Gathering",
                        "Process Mapping",
                        "User Stories",
                        "Acceptance Criteria",
                    ],
                },
                {
                    "name": "Scrum Master",
                    "description": "Agile team facilitator",
                    "responsibilities": [
                        "Sprint Planning",
                        "Daily Standups",
                        "Retrospectives",
                        "Impediment Removal",
                    ],
                },
                {
                    "name": "Product Owner",
                    "description": "Application product owner",
                    "responsibilities": [
                        "Backlog Management",
                        "Prioritization",
                        "Stakeholder Communication",
                        "Acceptance",
                    ],
                },
                {
                    "name": "Platform Administrator",
                    "description": "Mendix platform admin",
                    "responsibilities": [
                        "Environment Management",
                        "User Provisioning",
                        "Security Configuration",
                        "Monitoring",
                    ],
                },
                {
                    "name": "DevOps Engineer",
                    "description": "CI/CD pipeline manager",
                    "responsibilities": [
                        "Pipeline Configuration",
                        "Deployment Automation",
                        "Infrastructure Management",
                        "Monitoring",
                    ],
                },
                {
                    "name": "Integration Specialist",
                    "description": "API integration expert",
                    "responsibilities": [
                        "API Design",
                        "Integration Development",
                        "Data Mapping",
                        "Testing",
                    ],
                },
                {
                    "name": "QA Tester",
                    "description": "Quality assurance tester",
                    "responsibilities": [
                        "Test Planning",
                        "Test Execution",
                        "Defect Reporting",
                        "Regression Testing",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "Mendix Studio Pro",
                    "description": "Professional IDE for developers",
                    "target_market": "Development Teams",
                },
                {
                    "name": "Mendix Studio",
                    "description": "Web-based IDE for citizen developers",
                    "target_market": "Business Users",
                },
                {
                    "name": "Mendix Cloud",
                    "description": "Managed cloud hosting platform",
                    "target_market": "All Customers",
                },
                {
                    "name": "Mendix for Private Cloud",
                    "description": "On-premise deployment option",
                    "target_market": "Enterprise Customers",
                },
                {
                    "name": "Mendix Data Hub",
                    "description": "Data catalog and OData service platform",
                    "target_market": "Data-Driven Organizations",
                },
                {
                    "name": "Mendix Mobile",
                    "description": "Native mobile app development",
                    "target_market": "Mobile-First Companies",
                },
                {
                    "name": "Mendix App Store",
                    "description": "Marketplace for components",
                    "target_market": "All Developers",
                },
                {
                    "name": "Mendix Workflow",
                    "description": "Business process automation",
                    "target_market": "Process-Oriented Teams",
                },
                {
                    "name": "Mendix AI Assist",
                    "description": "AI-powered development assistance",
                    "target_market": "All Developers",
                },
                {
                    "name": "Mendix Solutions",
                    "description": "Pre-built industry solutions",
                    "target_market": "Industry-Specific Customers",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "Mendix Runtime",
                    "type": "application-server",
                    "description": "Application execution engine",
                    "technology": "Java",
                },
                {
                    "name": "Mendix Studio Pro",
                    "type": "desktop-app",
                    "description": "Professional development IDE",
                    "technology": "C#/.NET",
                },
                {
                    "name": "Mendix Studio",
                    "type": "web-app",
                    "description": "Web-based development IDE",
                    "technology": "React",
                },
                {
                    "name": "Mendix Model Server",
                    "type": "backend-service",
                    "description": "Model version control and collaboration",
                    "technology": "Java",
                },
                {
                    "name": "Mendix Build Server",
                    "type": "build-system",
                    "description": "Application packaging and deployment",
                    "technology": "Java",
                },
                {
                    "name": "Mendix Client",
                    "type": "web-framework",
                    "description": "Frontend application framework",
                    "technology": "React/Dojo",
                },
                {
                    "name": "Mendix Mobile Client",
                    "type": "mobile-framework",
                    "description": "Native mobile runtime",
                    "technology": "React Native",
                },
                {
                    "name": "Mendix Data Hub",
                    "type": "data-platform",
                    "description": "Data catalog and OData services",
                    "technology": "Java",
                },
                {
                    "name": "Mendix SSO Service",
                    "type": "authentication-service",
                    "description": "Single sign-on platform",
                    "technology": "Java",
                },
                {
                    "name": "Mendix Feedback Widget",
                    "type": "collaboration-tool",
                    "description": "In-app feedback collection",
                    "technology": "JavaScript",
                },
                {
                    "name": "Mendix App Store Service",
                    "type": "marketplace-platform",
                    "description": "Component distribution",
                    "technology": "Node.js",
                },
                {
                    "name": "Mendix Deploy API",
                    "type": "deployment-service",
                    "description": "Application deployment automation",
                    "technology": "REST API",
                },
                {
                    "name": "Mendix Cloud Portal",
                    "type": "management-console",
                    "description": "Platform administration",
                    "technology": "React",
                },
                {
                    "name": "Mendix Database",
                    "type": "database",
                    "description": "Application data storage",
                    "technology": "PostgreSQL",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "Runtime API",
                    "type": "REST",
                    "description": "Application runtime services",
                    "endpoints": ["/runtime/v1/objects", "/runtime/v1/login", "/runtime/v1/logout"],
                },
                {
                    "name": "Model API",
                    "type": "REST",
                    "description": "Model manipulation API",
                    "endpoints": ["/model/v1/app", "/model/v1/modules", "/model/v1/entities"],
                },
                {
                    "name": "Deploy API",
                    "type": "REST",
                    "description": "Deployment management",
                    "endpoints": [
                        "/deploy/v1/apps",
                        "/deploy/v1/environments",
                        "/deploy/v1/packages",
                    ],
                },
                {
                    "name": "Build API",
                    "type": "REST",
                    "description": "Application build service",
                    "endpoints": ["/build/v1/builds", "/build/v1/status"],
                },
                {
                    "name": "Data Hub Catalog API",
                    "type": "OData",
                    "description": "Data discovery and consumption",
                    "endpoints": ["/odata/v4/catalog", "/odata/v4/services"],
                },
                {
                    "name": "SSO Authentication API",
                    "type": "OAuth2",
                    "description": "Single sign-on service",
                    "endpoints": ["/oauth/authorize", "/oauth/token", "/oauth/userinfo"],
                },
                {
                    "name": "Feedback API",
                    "type": "REST",
                    "description": "User feedback collection",
                    "endpoints": ["/feedback/v1/items", "/feedback/v1/comments"],
                },
                {
                    "name": "App Store API",
                    "type": "REST",
                    "description": "Component marketplace",
                    "endpoints": ["/appstore/v1/content", "/appstore/v1/download"],
                },
                {
                    "name": "Metrics API",
                    "type": "REST",
                    "description": "Application performance metrics",
                    "endpoints": ["/metrics/v1/apps", "/metrics/v1/transactions"],
                },
                {
                    "name": "Mobile Build API",
                    "type": "REST",
                    "description": "Native mobile builds",
                    "endpoints": ["/mobile/v1/builds", "/mobile/v1/packages"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "REST API Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "OAuth2/API Key",
                },
                {
                    "name": "OData Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON/XML",
                    "authentication": "OAuth2",
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
                    "authentication": "Username/Password",
                },
                {
                    "name": "File Interface",
                    "protocol": "S3/FTP",
                    "data_format": "Various",
                    "authentication": "API Key/Credentials",
                },
                {
                    "name": "Email Interface",
                    "protocol": "SMTP/IMAP",
                    "data_format": "MIME",
                    "authentication": "Username/Password",
                },
                {
                    "name": "Push Notification Interface",
                    "protocol": "HTTPS",
                    "data_format": "JSON",
                    "authentication": "API Key",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {
                    "name": "Entity Instance",
                    "type": "transactional",
                    "retention_policy": "Application-defined",
                },
                {
                    "name": "User Account",
                    "type": "master",
                    "retention_policy": "Account lifecycle + 7 years",
                },
                {"name": "Session Data", "type": "transactional", "retention_policy": "24 hours"},
                {
                    "name": "File Document",
                    "type": "transactional",
                    "retention_policy": "Application-defined",
                },
                {"name": "Audit Log", "type": "audit", "retention_policy": "7 years"},
                {
                    "name": "Application Model",
                    "type": "configuration",
                    "retention_policy": "Permanent",
                },
                {"name": "Build Package", "type": "artifact", "retention_policy": "180 days"},
                {"name": "Metrics Data", "type": "analytical", "retention_policy": "90 days"},
                {"name": "Feedback Item", "type": "transactional", "retention_policy": "2 years"},
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "Entity CRUD Operations",
                    "type": "CRUD",
                    "description": "Create, read, update, delete entity instances",
                },
                {
                    "name": "Microflow Execution",
                    "type": "business-logic",
                    "description": "Execute business logic workflows",
                },
                {
                    "name": "Page Rendering",
                    "type": "UI",
                    "description": "Generate and render user interfaces",
                },
                {
                    "name": "API Call",
                    "type": "integration",
                    "description": "Invoke external REST/SOAP services",
                },
                {
                    "name": "Data Validation",
                    "type": "validation",
                    "description": "Validate entity attributes and relationships",
                },
                {
                    "name": "Authentication",
                    "type": "security",
                    "description": "Authenticate users via SSO or local credentials",
                },
                {
                    "name": "Authorization Check",
                    "type": "security",
                    "description": "Check user permissions for entities and microflows",
                },
                {
                    "name": "File Upload/Download",
                    "type": "file-management",
                    "description": "Handle file uploads and downloads",
                },
                {
                    "name": "Scheduled Event",
                    "type": "batch-processing",
                    "description": "Execute scheduled background tasks",
                },
                {
                    "name": "Push Notification",
                    "type": "messaging",
                    "description": "Send push notifications to mobile devices",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "Chief Digital Officer (CDO)",
                    "role": "executive",
                    "concerns": ["Digital Transformation", "Innovation Speed", "Time to Market"],
                    "influence": "high",
                },
                {
                    "name": "Chief Technology Officer (CTO)",
                    "role": "executive",
                    "concerns": ["Platform Strategy", "Technical Debt", "Architecture Governance"],
                    "influence": "high",
                },
                {
                    "name": "Head of Application Development",
                    "role": "senior-management",
                    "concerns": ["Developer Productivity", "Application Portfolio", "Quality"],
                    "influence": "high",
                },
                {
                    "name": "Business Unit Leader",
                    "role": "management",
                    "concerns": ["Business Solutions", "Cost Efficiency", "User Satisfaction"],
                    "influence": "high",
                },
                {
                    "name": "IT Director",
                    "role": "management",
                    "concerns": ["Platform Operations", "Security", "Compliance"],
                    "influence": "medium",
                },
                {
                    "name": "Development Manager",
                    "role": "management",
                    "concerns": ["Team Productivity", "Delivery Speed", "Code Quality"],
                    "influence": "medium",
                },
                {
                    "name": "Enterprise Architect",
                    "role": "technical",
                    "concerns": ["Architecture Standards", "Integration", "Scalability"],
                    "influence": "medium",
                },
                {
                    "name": "Security Officer",
                    "role": "technical",
                    "concerns": ["Application Security", "Data Privacy", "Compliance"],
                    "influence": "high",
                },
                {
                    "name": "Business Analysts",
                    "role": "operational",
                    "concerns": ["Requirements Clarity", "User Experience", "Business Value"],
                    "influence": "medium",
                },
                {
                    "name": "End Users",
                    "role": "operational",
                    "concerns": ["Usability", "Performance", "Reliability"],
                    "influence": "low",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Digital Transformation",
                    "description": "Accelerate digital business initiatives",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Application Backlog",
                    "description": "Reduce massive IT backlog of application requests",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Developer Shortage",
                    "description": "Address scarcity of professional developers",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Time to Market Pressure",
                    "description": "Deliver applications faster to meet business needs",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Legacy Modernization",
                    "description": "Replace aging legacy applications",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Cost Optimization",
                    "description": "Reduce application development and maintenance costs",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Business Agility",
                    "description": "Enable rapid response to market changes",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Citizen Development",
                    "description": "Empower business users to build solutions",
                    "urgency": "medium",
                    "impact": "medium",
                },
                {
                    "name": "Cloud Adoption",
                    "description": "Move to cloud-native application development",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Mobile Enablement",
                    "description": "Provide mobile apps for workforce and customers",
                    "urgency": "high",
                    "impact": "medium",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "Reduce Application Delivery Time by 70%",
                    "description": "Cut average app delivery from months to weeks",
                    "timeframe": "12 months",
                    "measurable": "Average delivery time < 4 weeks",
                },
                {
                    "name": "Enable 100 Citizen Developers",
                    "description": "Train business users to build applications",
                    "timeframe": "18 months",
                    "measurable": "100+ certified citizen developers",
                },
                {
                    "name": "Deliver 50 New Applications",
                    "description": "Build 50 new business applications",
                    "timeframe": "24 months",
                    "measurable": "50 apps in production",
                },
                {
                    "name": "Achieve 95% User Satisfaction",
                    "description": "High user satisfaction with applications",
                    "timeframe": "Ongoing",
                    "measurable": "NPS > 50",
                },
                {
                    "name": "Reduce Development Costs by 40%",
                    "description": "Lower per-application development cost",
                    "timeframe": "18 months",
                    "measurable": "40% cost reduction vs traditional",
                },
                {
                    "name": "Establish Low-Code Center of Excellence",
                    "description": "Create governance and best practices",
                    "timeframe": "6 months",
                    "measurable": "CoE operational with standards",
                },
                {
                    "name": "Migrate 20 Legacy Applications",
                    "description": "Modernize legacy apps with Mendix",
                    "timeframe": "24 months",
                    "measurable": "20 legacy apps replaced",
                },
                {
                    "name": "Achieve Platform 99.9% Uptime",
                    "description": "Ensure platform reliability",
                    "timeframe": "Ongoing",
                    "measurable": "< 8.76 hours downtime per year",
                },
                {
                    "name": "Deploy 30 Mobile Applications",
                    "description": "Build native mobile app portfolio",
                    "timeframe": "18 months",
                    "measurable": "30 mobile apps published",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "Faster Time to Market",
                    "description": "Applications delivered 10x faster than traditional development",
                    "benefit_type": "operational",
                    "quantified_benefit": "70% reduction in delivery time",
                },
                {
                    "name": "Increased Developer Productivity",
                    "description": "Developers build more with less code",
                    "benefit_type": "operational",
                    "quantified_benefit": "5x productivity improvement",
                },
                {
                    "name": "Reduced Development Costs",
                    "description": "Lower application development and maintenance costs",
                    "benefit_type": "financial",
                    "quantified_benefit": "$2M annual savings",
                },
                {
                    "name": "Business User Empowerment",
                    "description": "Business users build their own solutions",
                    "benefit_type": "strategic",
                    "quantified_benefit": "50% of apps built by business",
                },
                {
                    "name": "Improved Application Quality",
                    "description": "Fewer defects and better user experience",
                    "benefit_type": "quality",
                    "quantified_benefit": "60% reduction in production defects",
                },
                {
                    "name": "Enhanced Agility",
                    "description": "Faster response to changing business needs",
                    "benefit_type": "strategic",
                    "quantified_benefit": "Monthly release cadence",
                },
                {
                    "name": "Better User Experience",
                    "description": "Modern, responsive applications",
                    "benefit_type": "customer-experience",
                    "quantified_benefit": "NPS improvement of 25 points",
                },
                {
                    "name": "Reduced Technical Debt",
                    "description": "Modern architecture with less maintenance",
                    "benefit_type": "technical",
                    "quantified_benefit": "40% less maintenance effort",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Low-Code First",
                    "description": "Prefer low-code solutions over custom development",
                    "rationale": "Maximize speed and minimize maintenance",
                },
                {
                    "name": "Reuse Before Build",
                    "description": "Leverage App Store components before building custom",
                    "rationale": "Avoid reinventing the wheel",
                },
                {
                    "name": "API-First Integration",
                    "description": "Use standard APIs for all integrations",
                    "rationale": "Ensure maintainability and loose coupling",
                },
                {
                    "name": "Cloud-Native Architecture",
                    "description": "Build for cloud deployment from the start",
                    "rationale": "Enable scalability and resilience",
                },
                {
                    "name": "Mobile-First Design",
                    "description": "Design for mobile experience first",
                    "rationale": "Meet modern user expectations",
                },
                {
                    "name": "Continuous Delivery",
                    "description": "Deploy frequently with automated pipelines",
                    "rationale": "Accelerate feedback and value delivery",
                },
                {
                    "name": "Collaborative Development",
                    "description": "Foster collaboration between business and IT",
                    "rationale": "Ensure solutions meet business needs",
                },
                {
                    "name": "Security by Design",
                    "description": "Build security into every application",
                    "rationale": "Protect sensitive data and comply with regulations",
                },
                {
                    "name": "Data-Driven Decisions",
                    "description": "Use metrics to guide platform improvements",
                    "rationale": "Continuously optimize platform usage",
                },
                {
                    "name": "Governance with Flexibility",
                    "description": "Balance standards with developer autonomy",
                    "rationale": "Enable innovation while ensuring quality",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "Platform Availability",
                    "type": "performance",
                    "description": "Platform must be available 99.9% of time",
                    "priority": "critical",
                },
                {
                    "name": "Application Response Time",
                    "type": "performance",
                    "description": "Page load time < 2 seconds",
                    "priority": "high",
                },
                {
                    "name": "Concurrent Users",
                    "type": "capacity",
                    "description": "Support 10,000 concurrent users",
                    "priority": "high",
                },
                {
                    "name": "Data Security",
                    "type": "security",
                    "description": "Encrypt data at rest and in transit",
                    "priority": "critical",
                },
                {
                    "name": "Authentication",
                    "type": "security",
                    "description": "Support SSO and MFA",
                    "priority": "critical",
                },
                {
                    "name": "Compliance",
                    "type": "compliance",
                    "description": "Meet GDPR, HIPAA, SOC 2 requirements",
                    "priority": "critical",
                },
                {
                    "name": "Backup & Recovery",
                    "type": "continuity",
                    "description": "Daily backups with 4 - hour RTO",
                    "priority": "critical",
                },
                {
                    "name": "API Performance",
                    "type": "performance",
                    "description": "API response time < 500ms",
                    "priority": "high",
                },
                {
                    "name": "Mobile Support",
                    "type": "functional",
                    "description": "Support iOS and Android native apps",
                    "priority": "high",
                },
                {
                    "name": "Browser Support",
                    "type": "functional",
                    "description": "Support modern browsers (Chrome, Firefox, Safari, Edge)",
                    "priority": "high",
                },
                {
                    "name": "Scalability",
                    "type": "performance",
                    "description": "Auto-scale based on load",
                    "priority": "high",
                },
                {
                    "name": "Developer Training",
                    "type": "operational",
                    "description": "Provide comprehensive training program",
                    "priority": "medium",
                },
                {
                    "name": "Documentation",
                    "type": "operational",
                    "description": "Maintain up-to-date platform documentation",
                    "priority": "medium",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget Limit",
                    "type": "financial",
                    "description": "Platform budget capped at $500K annually",
                },
                {
                    "name": "Timeline",
                    "type": "schedule",
                    "description": "Must deliver first apps within 3 months",
                },
                {
                    "name": "Resource Availability",
                    "type": "resource",
                    "description": "Limited number of trained Mendix developers",
                },
                {
                    "name": "Legacy Integration",
                    "type": "technical",
                    "description": "Must integrate with 15+ legacy systems",
                },
                {
                    "name": "Regulatory Compliance",
                    "type": "compliance",
                    "description": "Must maintain regulatory certifications",
                },
                {
                    "name": "Network Bandwidth",
                    "type": "technical",
                    "description": "Limited bandwidth in some locations",
                },
                {
                    "name": "Data Residency",
                    "type": "compliance",
                    "description": "EU data must remain in EU region",
                },
                {
                    "name": "Browser Compatibility",
                    "type": "technical",
                    "description": "Must support legacy IE11 for some users",
                },
                {
                    "name": "Change Management",
                    "type": "organizational",
                    "description": "Cultural resistance to low-code approach",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "Platform Readiness Assessment",
                    "type": "maturity",
                    "description": "Assess organization readiness for low-code",
                    "result": "Score: 72/100 - Ready to proceed",
                },
                {
                    "name": "Use Case Prioritization",
                    "type": "business",
                    "description": "Identify highest-value use cases",
                    "result": "15 priority use cases identified",
                },
                {
                    "name": "Technical Landscape Analysis",
                    "type": "technical",
                    "description": "Document existing systems and integrations",
                    "result": "50 systems cataloged",
                },
                {
                    "name": "Developer Skill Assessment",
                    "type": "capability",
                    "description": "Evaluate team capabilities",
                    "result": "20 developers, 5 need training",
                },
                {
                    "name": "Security & Compliance Review",
                    "type": "risk",
                    "description": "Assess security and compliance requirements",
                    "result": "No blocking issues identified",
                },
            ]
        ),
        # ==================== IMPLEMENTATION & MIGRATION LAYER ====================
        implementation_events=json.dumps(
            [
                {
                    "name": "Platform Procurement",
                    "date": "2024 - 01 - 15",
                    "milestone": True,
                    "description": "Mendix licenses purchased",
                },
                {
                    "name": "Team Training Complete",
                    "date": "2024 - 02 - 28",
                    "milestone": True,
                    "description": "Initial team certified on Mendix",
                },
                {
                    "name": "Development Standards Published",
                    "date": "2024 - 03 - 15",
                    "milestone": False,
                    "description": "CoE standards documented",
                },
                {
                    "name": "First Pilot App Deployed",
                    "date": "2024 - 04 - 30",
                    "milestone": True,
                    "description": "First application in production",
                },
                {
                    "name": "Integration Framework Complete",
                    "date": "2024 - 06 - 15",
                    "milestone": True,
                    "description": "Reusable integration modules ready",
                },
                {
                    "name": "Citizen Developer Program Launch",
                    "date": "2024 - 07 - 01",
                    "milestone": True,
                    "description": "Business user training begins",
                },
                {
                    "name": "10 Applications Deployed",
                    "date": "2024 - 09 - 30",
                    "milestone": True,
                    "description": "10 apps in production",
                },
                {
                    "name": "Platform Optimization Complete",
                    "date": "2024 - 11 - 30",
                    "milestone": False,
                    "description": "Performance tuning finished",
                },
                {
                    "name": "Year 1 Review",
                    "date": "2025 - 01 - 15",
                    "milestone": True,
                    "description": "Platform success review",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Platform Setup",
                    "description": "Configure Mendix environments",
                    "duration_weeks": 4,
                    "team_size": 3,
                },
                {
                    "name": "Team Training",
                    "description": "Train developers and citizen developers",
                    "duration_weeks": 6,
                    "team_size": 2,
                },
                {
                    "name": "CoE Establishment",
                    "description": "Set up Center of Excellence",
                    "duration_weeks": 8,
                    "team_size": 4,
                },
                {
                    "name": "Integration Framework",
                    "description": "Build reusable integration modules",
                    "duration_weeks": 12,
                    "team_size": 5,
                },
                {
                    "name": "Pilot Applications",
                    "description": "Develop first 3 pilot apps",
                    "duration_weeks": 12,
                    "team_size": 8,
                },
                {
                    "name": "Security Implementation",
                    "description": "Configure SSO and security policies",
                    "duration_weeks": 4,
                    "team_size": 2,
                },
                {
                    "name": "Citizen Developer Program",
                    "description": "Launch business user development program",
                    "duration_weeks": 16,
                    "team_size": 3,
                },
                {
                    "name": "Legacy Migration",
                    "description": "Migrate first legacy application",
                    "duration_weeks": 20,
                    "team_size": 6,
                },
                {
                    "name": "Mobile Enablement",
                    "description": "Build mobile app capabilities",
                    "duration_weeks": 8,
                    "team_size": 4,
                },
                {
                    "name": "Governance & Monitoring",
                    "description": "Implement platform governance",
                    "duration_weeks": 6,
                    "team_size": 3,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Platform Architecture Document",
                    "type": "document",
                    "due_phase": "initiation",
                    "owner": "Enterprise Architect",
                },
                {
                    "name": "Development Standards",
                    "type": "document",
                    "due_phase": "initiation",
                    "owner": "CoE Lead",
                },
                {
                    "name": "Training Curriculum",
                    "type": "training",
                    "due_phase": "planning",
                    "owner": "Training Lead",
                },
                {
                    "name": "Integration Framework",
                    "type": "code",
                    "due_phase": "build",
                    "owner": "Integration Lead",
                },
                {
                    "name": "Pilot Applications",
                    "type": "application",
                    "due_phase": "build",
                    "owner": "Development Team",
                },
                {
                    "name": "Security Configuration",
                    "type": "configuration",
                    "due_phase": "build",
                    "owner": "Security Engineer",
                },
                {
                    "name": "Governance Playbook",
                    "type": "document",
                    "due_phase": "deploy",
                    "owner": "CoE Lead",
                },
                {
                    "name": "Operations Runbook",
                    "type": "document",
                    "due_phase": "deploy",
                    "owner": "Platform Admin",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "Platform Ready",
                    "date": "2024 - 02 - 28",
                    "description": "Platform configured, team trained, ready to build",
                },
                {
                    "name": "Pilot Success",
                    "date": "2024 - 06 - 30",
                    "description": "First 3 apps deployed successfully",
                },
                {
                    "name": "Production Ready",
                    "date": "2024 - 09 - 30",
                    "description": "10 apps in production, patterns established",
                },
                {
                    "name": "Scaled Adoption",
                    "date": "2025 - 01 - 15",
                    "description": "Citizen developers active, 25+ apps deployed",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "AWS us-east - 1",
                    "location": "Virginia, USA",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "Primary cloud region",
                },
                {
                    "name": "AWS eu-west - 1",
                    "location": "Ireland",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "European cloud region",
                },
                {
                    "name": "Corporate Data Center",
                    "location": "Boston, MA",
                    "tier": "Tier III",
                    "size_sqm": 200,
                    "description": "On-premise development environment",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "Runtime Containers",
                    "type": "container",
                    "quantity": 20,
                    "location": "AWS",
                    "specs": "4 CPU, 8GB RAM",
                },
                {
                    "name": "Database Instances",
                    "type": "database",
                    "quantity": 4,
                    "location": "AWS",
                    "specs": "8 CPU, 32GB RAM",
                },
                {
                    "name": "Load Balancers",
                    "type": "load-balancer",
                    "quantity": 2,
                    "location": "AWS",
                    "specs": "Auto-scaling",
                },
                {
                    "name": "Developer Workstations",
                    "type": "desktop",
                    "quantity": 50,
                    "location": "Corporate",
                    "specs": "i7, 16GB RAM, Windows 11",
                },
                {
                    "name": "Build Servers",
                    "type": "server",
                    "quantity": 3,
                    "location": "AWS",
                    "specs": "8 CPU, 16GB RAM",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "Corporate WAN",
                    "type": "wan",
                    "coverage": "Global",
                    "bandwidth_mbps": 1000,
                    "provider": "AT&T",
                },
                {
                    "name": "AWS Direct Connect",
                    "type": "private-link",
                    "coverage": "AWS us-east - 1",
                    "bandwidth_mbps": 1000,
                    "provider": "AWS",
                },
                {
                    "name": "Internet Gateway",
                    "type": "internet",
                    "coverage": "Global",
                    "bandwidth_mbps": 1000,
                    "provider": "Multiple ISPs",
                },
                {
                    "name": "CDN",
                    "type": "cdn",
                    "coverage": "Global",
                    "bandwidth_mbps": 100000,
                    "provider": "CloudFront",
                },
            ]
        ),
    )


def seed_mendix(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(vendor_name="Mendix").first()
            if existing:
                print("⚠️  Mendix template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_mendix_template()
            db.session.add(template)
            db.session.commit()

            print("✅ Mendix template seeded successfully!")
            print(f"   - Vendor: {template.vendor_name}")
            print(f"   - Technology Layer: ✅ Complete")
            print(f"   - Strategy Layer: ✅ Complete (20 capabilities, 6 value streams)")
            print(
                f"   - Business Layer: ✅ Complete (10 services, 6 processes, 9 objects, 10 actors, 10 products)"
            )
            print(
                f"   - Application Layer: ✅ Complete (14 components, 10 services, 8 interfaces, 9 data objects, 10 functions)"
            )
            print(
                f"   - Motivation Layer: ✅ Complete (10 stakeholders, 10 drivers, 9 goals, 8 outcomes, 10 principles, 13 requirements, 9 constraints, 5 assessments)"
            )
            print(
                f"   - Implementation Layer: ✅ Complete (9 events, 10 work packages, 8 deliverables, 4 plateaus)"
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
            print(f"❌ Error seeding Mendix template: {str(e)}")
            import traceback

            traceback.print_exc()

            raise


if __name__ == "__main__":
    seed_mendix()
