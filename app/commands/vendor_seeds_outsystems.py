"""
OutSystems Low-Code Platform Comprehensive Vendor Template Seed Data

Complete ArchiMate 3.2 coverage across ALL layers:
- Strategy Layer
- Business Layer
- Application Layer
- Technology Layer
- Motivation Layer
- Implementation & Migration Layer
- Physical Layer

Run with: python manage.py seed-vendor-outsystems
"""
import json

from app import create_app, db
from app.models import User, VendorStackTemplate
from config import DevelopmentConfig


def create_outsystems_template():
    """OutSystems FULLY COMPREHENSIVE template - ALL ArchiMate 3.2 layers"""
    return VendorStackTemplate(
        vendor_name="OutSystems",
        name="OutSystems Low-Code Application Platform",
        description="Enterprise-grade low-code platform for building, deploying, and managing mission-critical applications with full-stack development capabilities, AI-assisted development, and automated DevOps",
        # ==================== TECHNOLOGY LAYER ====================
        platform="hybrid",
        primary_language="c-sharp",
        framework="OutSystems Platform",
        framework_version="11.27",
        primary_database="sql-server",
        database_version="2022",
        container_runtime="docker",
        orchestration="kubernetes",
        service_mesh="istio",
        api_standard="REST",
        api_gateway="outsystems-api-gateway",
        message_broker="redis",
        auth_provider="outsystems-users",
        secrets_manager="azure-key-vault",
        logging_framework="outsystems-logging",
        metrics_platform="outsystems-ai-mentor",
        apm_tool="dynatrace",
        tracing_tool="application-insights",
        build_tool="outsystems-service-studio",
        ci_cd_platform="outsystems-lifetim",
        sast_tool="veracode",
        dast_tool="acunetix",
        dependency_scanner="checkmarx",
        nodes=json.dumps(
            [
                {
                    "name": "OutSystems Controller",
                    "type": "virtual-machine",
                    "os": "Windows Server 2022",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "OutSystems Front-End Server 1",
                    "type": "virtual-machine",
                    "os": "Windows Server 2022",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "OutSystems Front-End Server 2",
                    "type": "virtual-machine",
                    "os": "Windows Server 2022",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "OutSystems Deployment Controller",
                    "type": "virtual-machine",
                    "os": "Windows Server 2022",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "SQL Server Primary",
                    "type": "virtual-machine",
                    "os": "Windows Server 2022",
                    "cpu_cores": 16,
                    "ram_gb": 128,
                },
                {
                    "name": "SQL Server Secondary",
                    "type": "virtual-machine",
                    "os": "Windows Server 2022",
                    "cpu_cores": 16,
                    "ram_gb": 128,
                },
                {
                    "name": "LifeTime Management Console",
                    "type": "virtual-machine",
                    "os": "Windows Server 2022",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "AI Mentor Studio",
                    "type": "cloud-service",
                    "os": "Cloud",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
            ]
        ),
        devices=json.dumps(
            [
                {
                    "name": "Azure Load Balancer",
                    "type": "load-balancer",
                    "description": "Load balancing across front-end servers",
                },
                {
                    "name": "Azure Application Gateway",
                    "type": "api-gateway",
                    "description": "Web application firewall and API gateway",
                },
                {
                    "name": "Azure CDN",
                    "type": "cdn",
                    "description": "Content delivery network for static assets",
                },
                {
                    "name": "Azure Traffic Manager",
                    "type": "dns-load-balancer",
                    "description": "Global traffic routing",
                },
                {
                    "name": "Mobile Device Manager",
                    "type": "mdm",
                    "description": "Enterprise mobility management",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {
                    "name": "OutSystems Platform Server",
                    "type": "application-server",
                    "version": "11.27",
                },
                {"name": "OutSystems Service Studio", "type": "ide", "version": "11.53"},
                {"name": "OutSystems LifeTime", "type": "alm-platform", "version": "11.20"},
                {"name": "IIS Web Server", "type": "web-server", "version": "10.0"},
                {"name": ".NET Framework", "type": "runtime", "version": "4.8"},
                {"name": "SQL Server", "type": "database-engine", "version": "2022"},
                {"name": "Redis Cache", "type": "cache", "version": "7.0"},
                {
                    "name": "OutSystems Mobile Apps Build Service",
                    "type": "mobile-build",
                    "version": "11.0",
                },
                {"name": "OutSystems AI Mentor Studio", "type": "ai-assistant", "version": "1.5"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "OutSystems Platform Server",
                    "type": "application-runtime",
                    "description": "Application execution engine",
                },
                {
                    "name": "OutSystems Deployment Service",
                    "type": "deployment",
                    "description": "Application deployment automation",
                },
                {
                    "name": "OutSystems Compiler Service",
                    "type": "build-service",
                    "description": "Visual model compilation to C#/.NET",
                },
                {
                    "name": "OutSystems Database Service",
                    "type": "data-platform",
                    "description": "Multi-database abstraction layer",
                },
                {
                    "name": "OutSystems Authentication Service",
                    "type": "authentication",
                    "description": "Built-in and external authentication",
                },
                {
                    "name": "OutSystems BPT Engine",
                    "type": "workflow",
                    "description": "Business process technology workflow engine",
                },
                {
                    "name": "OutSystems Mobile Apps Builder",
                    "type": "mobile-build",
                    "description": "Native mobile app compilation",
                },
                {
                    "name": "OutSystems AI Mentor Studio",
                    "type": "ai-service",
                    "description": "AI-powered code analysis and guidance",
                },
                {
                    "name": "OutSystems Architecture Dashboard",
                    "type": "analytics",
                    "description": "Architecture quality monitoring",
                },
                {
                    "name": "OutSystems API Gateway",
                    "type": "api-management",
                    "description": "API lifecycle management",
                },
                {
                    "name": "OutSystems Integration Builder",
                    "type": "integration",
                    "description": "Pre-built integrations and connectors",
                },
                {
                    "name": "OutSystems Forge",
                    "type": "marketplace",
                    "description": "Community component marketplace",
                },
                {
                    "name": "OutSystems Experience Builder",
                    "type": "design-system",
                    "description": "UI/UX design system and templates",
                },
                {
                    "name": "OutSystems Workflow Builder",
                    "type": "workflow-designer",
                    "description": "Visual workflow design tool",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "OutSystems Application Package (.oap)",
                    "type": "deployment-package",
                    "size_mb": 100,
                    "registry": "LifeTime",
                },
                {
                    "name": "OutSystems Solution Pack (.osp)",
                    "type": "source-code",
                    "size_mb": 50,
                    "registry": "LifeTime",
                },
                {
                    "name": "OutSystems Module (.oml)",
                    "type": "module",
                    "size_mb": 20,
                    "registry": "Service Center",
                },
                {
                    "name": "OutSystems Extension (.xif)",
                    "type": "native-extension",
                    "size_mb": 10,
                    "registry": "Integration Studio",
                },
                {
                    "name": "Forge Component",
                    "type": "component",
                    "size_mb": 5,
                    "registry": "OutSystems Forge",
                },
                {
                    "name": "Mobile App Package (.apk/.ipa)",
                    "type": "mobile-app",
                    "size_mb": 50,
                    "registry": "MABS",
                },
                {
                    "name": "Database Backup",
                    "type": "backup-archive",
                    "size_mb": 5000,
                    "registry": "Azure Backup",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "Azure Production VNet",
                    "type": "vpc",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 1,
                },
                {
                    "name": "SQL Always On Replication",
                    "type": "private",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 1,
                },
                {
                    "name": "Internet Gateway",
                    "type": "wan",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 15,
                },
                {
                    "name": "ExpressRoute",
                    "type": "private-link",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 5,
                },
                {"name": "Azure CDN", "type": "cdn", "bandwidth_mbps": 100000, "latency_ms": 10},
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="OutSystems",
        market_position="leader",
        company_size="enterprise",
        founded_year=2001,
        headquarters="Boston, MA / Atlanta, GA",
        revenue_usd=500000000,
        customer_count=1800,
        market_share_percentage=20.0,
        acquisition_risk="low",
        financial_health="strong",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                {
                    "name": "Full-Stack Low-Code Development",
                    "description": "Complete front-end to back-end application development",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "AI-Assisted Development",
                    "description": "AI Mentor Studio for architecture guidance and code analysis",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Multi-Experience Applications",
                    "description": "Web, mobile, and progressive web apps from single codebase",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Enterprise Integration",
                    "description": "Built-in connectors for SAP, Salesforce, Oracle, and more",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Business Process Management",
                    "description": "Visual workflow designer with case management",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Application Lifecycle Management",
                    "description": "LifeTime platform for complete DevOps automation",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Architecture Governance",
                    "description": "Automated architecture validation and technical debt monitoring",
                    "coverage_percentage": 93,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Cloud-Native & Hybrid Deployment",
                    "description": "Deploy to cloud, on-premise, or hybrid environments",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Database Independence",
                    "description": "Support for SQL Server, Oracle, MySQL, PostgreSQL",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Microservices Architecture",
                    "description": "Build and deploy microservices with service architecture canvas",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Mobile-Native Development",
                    "description": "True native iOS and Android app generation",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "API Economy Enablement",
                    "description": "Full API lifecycle management with versioning and documentation",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Security & Compliance",
                    "description": "Built-in security controls and compliance frameworks",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Performance Optimization",
                    "description": "Automated performance monitoring and optimization suggestions",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "Extensibility",
                    "description": "Custom C# and JavaScript extension capabilities",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Legacy Modernization",
                    "description": "Tools and patterns for legacy application migration",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "Scalability & High Availability",
                    "description": "Auto-scaling and load balancing capabilities",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Real-Time Applications",
                    "description": "WebSocket support for real-time communication",
                    "coverage_percentage": 87,
                    "maturity_level": "managed",
                },
                {
                    "name": "Offline-First Mobile",
                    "description": "Offline data sync for mobile applications",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Low-Code for Pro Developers",
                    "description": "Full code control with visual abstraction",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Concept-to-Production",
                    "stages": [
                        "Idea Validation",
                        "Visual Prototyping",
                        "Development",
                        "Testing",
                        "1 - Click Deployment",
                        "Monitoring",
                        "Iteration",
                    ],
                    "description": "Rapid application delivery from concept to live production",
                },
                {
                    "name": "Build-Deploy-Manage",
                    "stages": [
                        "Development",
                        "Code Review",
                        "Build",
                        "Test Automation",
                        "Staging",
                        "Production Deployment",
                        "Monitoring",
                        "Optimization",
                    ],
                    "description": "Complete DevOps lifecycle automation",
                },
                {
                    "name": "Integrate-Extend-Innovate",
                    "stages": [
                        "Integration Discovery",
                        "Connector Development",
                        "API Exposure",
                        "External Consumption",
                        "Monitoring",
                        "Enhancement",
                    ],
                    "description": "Enterprise integration and API management",
                },
                {
                    "name": "Design-Develop-Deliver",
                    "stages": [
                        "UX Design",
                        "Screen Development",
                        "Business Logic",
                        "Integration",
                        "Testing",
                        "Deployment",
                        "User Feedback",
                    ],
                    "description": "User-centric application delivery",
                },
                {
                    "name": "Modernize-Transform-Scale",
                    "stages": [
                        "Legacy Analysis",
                        "Architecture Design",
                        "Incremental Migration",
                        "Testing",
                        "Cutover",
                        "Optimization",
                        "Scaling",
                    ],
                    "description": "Legacy modernization journey",
                },
                {
                    "name": "Govern-Secure-Comply",
                    "stages": [
                        "Policy Definition",
                        "Architecture Review",
                        "Security Scan",
                        "Compliance Check",
                        "Approval",
                        "Deployment",
                        "Audit",
                    ],
                    "description": "Governance and compliance workflow",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "Enterprise Transformation",
                    "description": "Large-scale digital transformation with OutSystems",
                    "timeline_months": 24,
                    "risk_level": "medium",
                },
                {
                    "name": "Legacy Modernization Initiative",
                    "description": "Migrate legacy applications to OutSystems",
                    "timeline_months": 18,
                    "risk_level": "medium",
                },
                {
                    "name": "Rapid Innovation Lab",
                    "description": "Establish innovation team for rapid prototyping",
                    "timeline_months": 6,
                    "risk_level": "low",
                },
                {
                    "name": "Cloud Migration",
                    "description": "Move on-premise apps to OutSystems Cloud",
                    "timeline_months": 12,
                    "risk_level": "low",
                },
                {
                    "name": "Factory Model Implementation",
                    "description": "Set up application factory with reusable assets",
                    "timeline_months": 9,
                    "risk_level": "low",
                },
                {
                    "name": "Mobile-First Strategy",
                    "description": "Build mobile app portfolio with OutSystems",
                    "timeline_months": 12,
                    "risk_level": "low",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Application Development Service",
                    "description": "Build enterprise applications with low-code",
                    "service_type": "internal",
                    "sla_commitment": "99.99% platform availability",
                },
                {
                    "name": "Mobile App Development",
                    "description": "Create native mobile applications",
                    "service_type": "customer-facing",
                    "sla_commitment": "Same-day build and deployment",
                },
                {
                    "name": "Enterprise Integration",
                    "description": "Connect to enterprise systems",
                    "service_type": "internal",
                    "sla_commitment": "99.95% integration uptime",
                },
                {
                    "name": "API Management",
                    "description": "Publish and manage APIs",
                    "service_type": "internal",
                    "sla_commitment": "< 200ms API response time",
                },
                {
                    "name": "Workflow Automation",
                    "description": "Automate business processes",
                    "service_type": "internal",
                    "sla_commitment": "Real-time workflow execution",
                },
                {
                    "name": "Application Monitoring",
                    "description": "Monitor application health and performance",
                    "service_type": "supporting",
                    "sla_commitment": "Real-time performance insights",
                },
                {
                    "name": "Architecture Governance",
                    "description": "Validate and govern application architecture",
                    "service_type": "supporting",
                    "sla_commitment": "Daily architecture scans",
                },
                {
                    "name": "DevOps Automation",
                    "description": "Automated deployment pipelines",
                    "service_type": "supporting",
                    "sla_commitment": "< 5 minute deployment time",
                },
                {
                    "name": "Security Management",
                    "description": "Application security and compliance",
                    "service_type": "supporting",
                    "sla_commitment": "Zero security vulnerabilities",
                },
                {
                    "name": "Platform Administration",
                    "description": "Manage OutSystems environments",
                    "service_type": "supporting",
                    "sla_commitment": "24/7 support",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Application Development Lifecycle",
                    "description": "End-to-end app development process",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Requirements",
                        "Visual Design",
                        "Data Modeling",
                        "Logic Implementation",
                        "Integration",
                        "Testing",
                        "Deployment",
                        "Monitoring",
                    ],
                    "cycle_time": "1 - 6 weeks",
                    "kpis": ["Time to Market", "Code Quality Score", "User Adoption"],
                },
                {
                    "name": "1 - Click Deployment Process",
                    "description": "Automated deployment to any environment",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Select Version",
                        "Choose Environment",
                        "Validate Dependencies",
                        "Compile",
                        "Deploy",
                        "Smoke Test",
                        "Notify",
                    ],
                    "cycle_time": "< 5 minutes",
                    "kpis": ["Deployment Success Rate", "Deployment Time", "Rollback Frequency"],
                },
                {
                    "name": "Mobile App Build & Release",
                    "description": "Native mobile app compilation and distribution",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Code Freeze",
                        "Native Build",
                        "Code Signing",
                        "Testing",
                        "Store Submission",
                        "Approval",
                        "Release",
                    ],
                    "cycle_time": "2 - 4 days",
                    "kpis": ["Build Success Rate", "Time to Store", "Crash Rate"],
                },
                {
                    "name": "AI-Powered Code Review",
                    "description": "Automated architecture and code analysis",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Code Commit",
                        "AI Analysis",
                        "Architecture Validation",
                        "Performance Check",
                        "Security Scan",
                        "Technical Debt Assessment",
                        "Report Generation",
                    ],
                    "cycle_time": "< 1 hour",
                    "kpis": [
                        "Code Quality Trend",
                        "Technical Debt Ratio",
                        "Architecture Compliance",
                    ],
                },
                {
                    "name": "Enterprise Integration Development",
                    "description": "Build integrations with external systems",
                    "automation_level": "partially-automated",
                    "steps": [
                        "System Discovery",
                        "Connector Selection",
                        "Mapping Configuration",
                        "Testing",
                        "Deployment",
                        "Monitoring",
                    ],
                    "cycle_time": "1 - 2 weeks",
                    "kpis": ["Integration Success Rate", "Data Accuracy", "Performance"],
                },
                {
                    "name": "Factory Delivery Process",
                    "description": "Standardized application factory workflow",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Intake",
                        "Architecture Review",
                        "Component Reuse",
                        "Development",
                        "Quality Gate",
                        "Deployment",
                        "Support Handoff",
                    ],
                    "cycle_time": "2 - 8 weeks",
                    "kpis": ["Reuse Rate", "Quality Score", "Delivery Predictability"],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "OutSystems Application",
                    "description": "Deployed application in environment",
                    "lifecycle": "created -> developed -> tested -> deployed -> running -> archived",
                },
                {
                    "name": "Module",
                    "description": "Reusable application module",
                    "lifecycle": "created -> developed -> published -> consumed -> versioned",
                },
                {
                    "name": "Entity",
                    "description": "Data model entity",
                    "lifecycle": "designed -> validated -> generated -> populated -> maintained",
                },
                {
                    "name": "Screen",
                    "description": "User interface page",
                    "lifecycle": "designed -> developed -> tested -> published -> maintained",
                },
                {
                    "name": "Server Action",
                    "description": "Server-side business logic",
                    "lifecycle": "created -> tested -> deployed -> executed -> optimized",
                },
                {
                    "name": "REST API",
                    "description": "Published REST API",
                    "lifecycle": "designed -> implemented -> documented -> published -> monitored -> versioned",
                },
                {
                    "name": "Extension",
                    "description": "Custom C# integration",
                    "lifecycle": "developed -> tested -> packaged -> deployed -> maintained",
                },
                {
                    "name": "Business Process",
                    "description": "BPT workflow definition",
                    "lifecycle": "designed -> validated -> deployed -> executed -> optimized",
                },
                {
                    "name": "Mobile App",
                    "description": "Native mobile application",
                    "lifecycle": "developed -> built -> tested -> published -> maintained -> retired",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Full-Stack Developer",
                    "description": "Professional OutSystems developer",
                    "responsibilities": [
                        "Application Development",
                        "Architecture Design",
                        "Integration Development",
                        "Performance Optimization",
                    ],
                },
                {
                    "name": "Tech Lead",
                    "description": "Technical team leader",
                    "responsibilities": [
                        "Architecture Review",
                        "Code Review",
                        "Technical Guidance",
                        "Team Mentoring",
                    ],
                },
                {
                    "name": "UI/UX Designer",
                    "description": "User experience designer",
                    "responsibilities": [
                        "Screen Design",
                        "User Flow Design",
                        "Prototyping",
                        "Usability Testing",
                    ],
                },
                {
                    "name": "Business Analyst",
                    "description": "Requirements specialist",
                    "responsibilities": [
                        "Requirements Gathering",
                        "User Stories",
                        "Process Mapping",
                        "Acceptance Testing",
                    ],
                },
                {
                    "name": "Solutions Architect",
                    "description": "Enterprise architect",
                    "responsibilities": [
                        "Solution Design",
                        "Architecture Governance",
                        "Integration Strategy",
                        "Technical Standards",
                    ],
                },
                {
                    "name": "DevOps Engineer",
                    "description": "Platform operations specialist",
                    "responsibilities": [
                        "Environment Management",
                        "CI/CD Pipeline",
                        "Infrastructure Management",
                        "Monitoring",
                    ],
                },
                {
                    "name": "Integration Developer",
                    "description": "API and integration specialist",
                    "responsibilities": [
                        "API Development",
                        "Integration Design",
                        "Connector Development",
                        "Testing",
                    ],
                },
                {
                    "name": "Mobile Developer",
                    "description": "Mobile app specialist",
                    "responsibilities": [
                        "Mobile App Development",
                        "Native Features",
                        "Offline Sync",
                        "Performance Tuning",
                    ],
                },
                {
                    "name": "Platform Administrator",
                    "description": "OutSystems admin",
                    "responsibilities": [
                        "User Management",
                        "Environment Configuration",
                        "Security Setup",
                        "Monitoring",
                    ],
                },
                {
                    "name": "QA Engineer",
                    "description": "Quality assurance tester",
                    "responsibilities": [
                        "Test Planning",
                        "Automated Testing",
                        "Regression Testing",
                        "Defect Management",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "OutSystems 11",
                    "description": "Core low-code platform",
                    "target_market": "All Customers",
                },
                {
                    "name": "OutSystems Cloud",
                    "description": "Managed cloud hosting",
                    "target_market": "Cloud Customers",
                },
                {
                    "name": "OutSystems for Azure",
                    "description": "Azure-native deployment",
                    "target_market": "Azure Customers",
                },
                {
                    "name": "OutSystems for AWS",
                    "description": "AWS-native deployment",
                    "target_market": "AWS Customers",
                },
                {
                    "name": "LifeTime",
                    "description": "DevOps and ALM platform",
                    "target_market": "All Customers",
                },
                {
                    "name": "AI Mentor Studio",
                    "description": "AI-powered architecture assistant",
                    "target_market": "Enterprise Customers",
                },
                {
                    "name": "Architecture Dashboard",
                    "description": "Architecture governance tool",
                    "target_market": "Enterprise Customers",
                },
                {
                    "name": "Experience Builder",
                    "description": "UI/UX design system",
                    "target_market": "All Customers",
                },
                {
                    "name": "Workflow Builder",
                    "description": "Business process automation",
                    "target_market": "Process-Oriented Customers",
                },
                {
                    "name": "Integration Builder",
                    "description": "Pre-built integration connectors",
                    "target_market": "All Customers",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "OutSystems Platform Server",
                    "type": "application-server",
                    "description": "Application runtime and execution",
                    "technology": ".NET/C#",
                },
                {
                    "name": "OutSystems Deployment Controller",
                    "type": "deployment-service",
                    "description": "Automated deployment orchestration",
                    "technology": ".NET/C#",
                },
                {
                    "name": "OutSystems Compiler",
                    "type": "code-generator",
                    "description": "Visual model to C# code compilation",
                    "technology": ".NET/C#",
                },
                {
                    "name": "Service Studio",
                    "type": "desktop-app",
                    "description": "Professional IDE for developers",
                    "technology": ".NET/WPF",
                },
                {
                    "name": "Integration Studio",
                    "type": "desktop-app",
                    "description": "Custom extension development IDE",
                    "technology": ".NET/WPF",
                },
                {
                    "name": "LifeTime Console",
                    "type": "web-app",
                    "description": "DevOps and ALM management",
                    "technology": "OutSystems",
                },
                {
                    "name": "Service Center",
                    "type": "web-app",
                    "description": "Environment administration console",
                    "technology": "OutSystems",
                },
                {
                    "name": "Mobile Runtime",
                    "type": "mobile-framework",
                    "description": "Native mobile app runtime",
                    "technology": "Cordova/Capacitor",
                },
                {
                    "name": "OutSystems UI Framework",
                    "type": "ui-framework",
                    "description": "Responsive web UI components",
                    "technology": "CSS/JavaScript",
                },
                {
                    "name": "BPT Engine",
                    "type": "workflow-engine",
                    "description": "Business process automation engine",
                    "technology": ".NET/C#",
                },
                {
                    "name": "OutSystems AI Mentor",
                    "type": "ai-service",
                    "description": "AI-powered code analysis",
                    "technology": "Machine Learning",
                },
                {
                    "name": "Architecture Dashboard",
                    "type": "analytics-platform",
                    "description": "Architecture monitoring and metrics",
                    "technology": "OutSystems",
                },
                {
                    "name": "OutSystems Database",
                    "type": "database",
                    "description": "Multi-database abstraction",
                    "technology": "SQL Server/Oracle/PostgreSQL",
                },
                {
                    "name": "Redis Session Store",
                    "type": "cache",
                    "description": "Session state management",
                    "technology": "Redis",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "Platform API",
                    "type": "REST",
                    "description": "Platform management API",
                    "endpoints": [
                        "/lifetimeapi/rest/v2/applications",
                        "/lifetimeapi/rest/v2/environments",
                        "/lifetimeapi/rest/v2/deployments",
                    ],
                },
                {
                    "name": "ServiceCenter API",
                    "type": "REST",
                    "description": "Environment management API",
                    "endpoints": ["/ServiceCenter/api/applications", "/ServiceCenter/api/modules"],
                },
                {
                    "name": "Architecture Dashboard API",
                    "type": "REST",
                    "description": "Architecture metrics API",
                    "endpoints": [
                        "/ArchitectureDashboard/rest/v1/modules",
                        "/ArchitectureDashboard/rest/v1/findings",
                    ],
                },
                {
                    "name": "AI Mentor API",
                    "type": "REST",
                    "description": "AI analysis API",
                    "endpoints": ["/AImentorapi/rest/v1/probes", "/AImentorapi/rest/v1/findings"],
                },
                {
                    "name": "Application REST API",
                    "type": "REST",
                    "description": "Custom application APIs",
                    "endpoints": ["Custom endpoints per application"],
                },
                {
                    "name": "SOAP Web Service",
                    "type": "SOAP",
                    "description": "Legacy SOAP services",
                    "endpoints": ["Custom WSDL per application"],
                },
                {
                    "name": "BPT API",
                    "type": "REST",
                    "description": "Process automation API",
                    "endpoints": ["/BPTapi/rest/v1/processes", "/BPTapi/rest/v1/activities"],
                },
                {
                    "name": "Mobile Apps Build Service",
                    "type": "REST",
                    "description": "Native mobile build API",
                    "endpoints": ["/MABS/rest/v1/builds", "/MABS/rest/v1/status"],
                },
                {
                    "name": "Integration Connectors",
                    "type": "Various",
                    "description": "Pre-built system connectors",
                    "endpoints": ["SAP, Salesforce, Oracle, etc."],
                },
                {
                    "name": "User Authentication API",
                    "type": "REST",
                    "description": "Authentication services",
                    "endpoints": ["/Users/rest/v1/login", "/Users/rest/v1/logout"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "REST API Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "Token/OAuth2",
                },
                {
                    "name": "SOAP Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "XML",
                    "authentication": "WS-Security",
                },
                {
                    "name": "Database Interface",
                    "protocol": "ADO.NET",
                    "data_format": "SQL",
                    "authentication": "Integrated/SQL Auth",
                },
                {
                    "name": "SAP RFC Interface",
                    "protocol": "RFC",
                    "data_format": "ABAP Structures",
                    "authentication": "SAP Credentials",
                },
                {
                    "name": "File System Interface",
                    "protocol": "File I/O",
                    "data_format": "Various",
                    "authentication": "Windows Auth",
                },
                {
                    "name": "Email Interface",
                    "protocol": "SMTP",
                    "data_format": "MIME",
                    "authentication": "Credentials",
                },
                {
                    "name": "WebSocket Interface",
                    "protocol": "WebSocket",
                    "data_format": "JSON",
                    "authentication": "Token",
                },
                {
                    "name": "Mobile Push Interface",
                    "protocol": "HTTPS",
                    "data_format": "JSON",
                    "authentication": "API Key",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {
                    "name": "Entity Record",
                    "type": "transactional",
                    "retention_policy": "Application-defined",
                },
                {
                    "name": "User Account",
                    "type": "master",
                    "retention_policy": "User lifecycle + 7 years",
                },
                {
                    "name": "Session State",
                    "type": "transactional",
                    "retention_policy": "Session duration",
                },
                {
                    "name": "Binary Data",
                    "type": "transactional",
                    "retention_policy": "Application-defined",
                },
                {
                    "name": "Process Instance",
                    "type": "transactional",
                    "retention_policy": "Process completion + 5 years",
                },
                {"name": "Audit Log", "type": "audit", "retention_policy": "7 years"},
                {"name": "Application Package", "type": "artifact", "retention_policy": "90 days"},
                {"name": "Mobile App Build", "type": "artifact", "retention_policy": "180 days"},
                {
                    "name": "Performance Metrics",
                    "type": "analytical",
                    "retention_policy": "90 days",
                },
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "CRUD Operations",
                    "type": "CRUD",
                    "description": "Entity create, read, update, delete",
                },
                {
                    "name": "Server Action Execution",
                    "type": "business-logic",
                    "description": "Execute server-side logic",
                },
                {
                    "name": "Screen Rendering",
                    "type": "UI",
                    "description": "Generate and render responsive screens",
                },
                {
                    "name": "REST API Consume",
                    "type": "integration",
                    "description": "Call external REST APIs",
                },
                {
                    "name": "Data Validation",
                    "type": "validation",
                    "description": "Validate entity attributes",
                },
                {
                    "name": "User Authentication",
                    "type": "security",
                    "description": "Authenticate users",
                },
                {
                    "name": "Role-Based Authorization",
                    "type": "security",
                    "description": "Check user permissions",
                },
                {
                    "name": "Process Execution",
                    "type": "workflow",
                    "description": "Execute BPT workflows",
                },
                {
                    "name": "Timer Execution",
                    "type": "batch-processing",
                    "description": "Run scheduled jobs",
                },
                {
                    "name": "Email Sending",
                    "type": "messaging",
                    "description": "Send transactional emails",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "Chief Digital Officer (CDO)",
                    "role": "executive",
                    "concerns": ["Digital Innovation", "Speed to Market", "Competitive Advantage"],
                    "influence": "high",
                },
                {
                    "name": "Chief Technology Officer (CTO)",
                    "role": "executive",
                    "concerns": ["Platform ROI", "Technical Excellence", "Architecture Quality"],
                    "influence": "high",
                },
                {
                    "name": "VP of Engineering",
                    "role": "senior-management",
                    "concerns": ["Delivery Velocity", "Team Productivity", "Quality"],
                    "influence": "high",
                },
                {
                    "name": "Enterprise Architect",
                    "role": "technical",
                    "concerns": [
                        "Architecture Governance",
                        "Standards Compliance",
                        "Technical Debt",
                    ],
                    "influence": "high",
                },
                {
                    "name": "Development Manager",
                    "role": "management",
                    "concerns": [
                        "Team Performance",
                        "Resource Utilization",
                        "Delivery Predictability",
                    ],
                    "influence": "medium",
                },
                {
                    "name": "Security Officer",
                    "role": "technical",
                    "concerns": ["Application Security", "Data Protection", "Compliance"],
                    "influence": "high",
                },
                {
                    "name": "DevOps Manager",
                    "role": "management",
                    "concerns": ["Deployment Automation", "Environment Stability", "Monitoring"],
                    "influence": "medium",
                },
                {
                    "name": "Business Sponsor",
                    "role": "executive",
                    "concerns": ["Business Value", "Cost Control", "User Satisfaction"],
                    "influence": "high",
                },
                {
                    "name": "Professional Developers",
                    "role": "operational",
                    "concerns": ["Development Productivity", "Code Quality", "Career Growth"],
                    "influence": "medium",
                },
                {
                    "name": "End Users",
                    "role": "operational",
                    "concerns": ["Application Usability", "Performance", "Reliability"],
                    "influence": "low",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Application Delivery Crisis",
                    "description": "Massive backlog of application requests",
                    "urgency": "critical",
                    "impact": "transformational",
                },
                {
                    "name": "Developer Scarcity",
                    "description": "Shortage of skilled developers",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Legacy System Burden",
                    "description": "Aging applications require modernization",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Competitive Pressure",
                    "description": "Need for faster time to market",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Cloud Transformation",
                    "description": "Move to cloud-native architecture",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Mobile Imperative",
                    "description": "Mobile apps required for workforce and customers",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Technical Debt Accumulation",
                    "description": "Mounting maintenance burden",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Cost Optimization",
                    "description": "Reduce application development costs",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Innovation Requirement",
                    "description": "Need to innovate faster",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Customer Experience Expectations",
                    "description": "Modern UX required",
                    "urgency": "high",
                    "impact": "medium",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "10x Faster Application Delivery",
                    "description": "Reduce time from idea to production by 90%",
                    "timeframe": "12 months",
                    "measurable": "Average delivery < 2 weeks",
                },
                {
                    "name": "Build 100 Applications",
                    "description": "Deliver 100 new applications in 24 months",
                    "timeframe": "24 months",
                    "measurable": "100 apps in production",
                },
                {
                    "name": "Achieve 4.5+ AI Mentor Score",
                    "description": "Maintain high code quality across portfolio",
                    "timeframe": "Ongoing",
                    "measurable": "AI Mentor average > 4.5/5",
                },
                {
                    "name": "Zero Critical Security Vulnerabilities",
                    "description": "Eliminate critical security issues",
                    "timeframe": "Ongoing",
                    "measurable": "0 critical vulnerabilities",
                },
                {
                    "name": "Reduce Development Costs 50%",
                    "description": "Cut per-app development cost by half",
                    "timeframe": "18 months",
                    "measurable": "50% cost reduction",
                },
                {
                    "name": "95% First-Time-Right Deployments",
                    "description": "Minimize deployment failures",
                    "timeframe": "12 months",
                    "measurable": "< 5% failed deployments",
                },
                {
                    "name": "Migrate 30 Legacy Applications",
                    "description": "Modernize legacy portfolio",
                    "timeframe": "24 months",
                    "measurable": "30 legacy apps replaced",
                },
                {
                    "name": "Platform 99.99% Uptime",
                    "description": "Enterprise-grade reliability",
                    "timeframe": "Ongoing",
                    "measurable": "< 52.56 minutes downtime per year",
                },
                {
                    "name": "50 Mobile Apps Deployed",
                    "description": "Build comprehensive mobile portfolio",
                    "timeframe": "18 months",
                    "measurable": "50 native mobile apps",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "Unprecedented Speed",
                    "description": "Applications delivered 10x faster than traditional methods",
                    "benefit_type": "operational",
                    "quantified_benefit": "90% faster delivery",
                },
                {
                    "name": "Massive Cost Savings",
                    "description": "Development costs slashed by half",
                    "benefit_type": "financial",
                    "quantified_benefit": "$5M annual savings",
                },
                {
                    "name": "Superior Code Quality",
                    "description": "AI-driven quality governance",
                    "benefit_type": "quality",
                    "quantified_benefit": "80% reduction in production defects",
                },
                {
                    "name": "Developer Productivity Explosion",
                    "description": "Each developer delivers 10x more",
                    "benefit_type": "operational",
                    "quantified_benefit": "10x productivity increase",
                },
                {
                    "name": "Zero Technical Debt",
                    "description": "Continuous architecture monitoring prevents debt",
                    "benefit_type": "technical",
                    "quantified_benefit": "Maintainability index > 4.5",
                },
                {
                    "name": "Business Agility",
                    "description": "Respond to market changes in days, not months",
                    "benefit_type": "strategic",
                    "quantified_benefit": "Weekly release cadence",
                },
                {
                    "name": "Customer Satisfaction",
                    "description": "Modern applications delight users",
                    "benefit_type": "customer-experience",
                    "quantified_benefit": "NPS improvement of 30 points",
                },
                {
                    "name": "Competitive Advantage",
                    "description": "Outpace competitors with innovation speed",
                    "benefit_type": "strategic",
                    "quantified_benefit": "First to market on 5 initiatives",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "1 - Click Everything",
                    "description": "Automate all manual processes",
                    "rationale": "Eliminate human error and delay",
                },
                {
                    "name": "Architecture First",
                    "description": "Design proper architecture before coding",
                    "rationale": "Prevent technical debt accumulation",
                },
                {
                    "name": "AI-Driven Quality",
                    "description": "Use AI Mentor for continuous quality monitoring",
                    "rationale": "Maintain high standards automatically",
                },
                {
                    "name": "True Full-Stack",
                    "description": "Build complete solutions, not just front-ends",
                    "rationale": "Deliver production-ready applications",
                },
                {
                    "name": "Cloud-Native by Default",
                    "description": "Design for cloud from the start",
                    "rationale": "Enable scalability and resilience",
                },
                {
                    "name": "Mobile-Native, Not Hybrid",
                    "description": "Generate True native mobile apps",
                    "rationale": "Deliver superior mobile experience",
                },
                {
                    "name": "Security by Default",
                    "description": "Build security into platform, not bolt-on",
                    "rationale": "Protect applications automatically",
                },
                {
                    "name": "Continuous Deployment",
                    "description": "Deploy continuously with confidence",
                    "rationale": "Accelerate value delivery",
                },
                {
                    "name": "Factory Approach",
                    "description": "Standardize with reusable assets",
                    "rationale": "Maximize efficiency and consistency",
                },
                {
                    "name": "Governance Without Friction",
                    "description": "Automated governance, not manual gates",
                    "rationale": "Ensure quality without slowing delivery",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "Platform Availability",
                    "type": "performance",
                    "description": "Platform must be available 99.99% of time",
                    "priority": "critical",
                },
                {
                    "name": "Deployment Speed",
                    "type": "performance",
                    "description": "1 - click deployment < 5 minutes",
                    "priority": "critical",
                },
                {
                    "name": "Concurrent Users",
                    "type": "capacity",
                    "description": "Support 50,000 concurrent users",
                    "priority": "high",
                },
                {
                    "name": "Database Flexibility",
                    "type": "technical",
                    "description": "Support SQL Server, Oracle, PostgreSQL, MySQL",
                    "priority": "high",
                },
                {
                    "name": "Security Standards",
                    "type": "security",
                    "description": "Meet OWASP Top 10 requirements",
                    "priority": "critical",
                },
                {
                    "name": "Compliance",
                    "type": "compliance",
                    "description": "GDPR, HIPAA, SOC 2, ISO 27001 certified",
                    "priority": "critical",
                },
                {
                    "name": "Disaster Recovery",
                    "type": "continuity",
                    "description": "RPO < 15 minutes, RTO < 1 hour",
                    "priority": "critical",
                },
                {
                    "name": "Mobile Platform Support",
                    "type": "functional",
                    "description": "iOS 14+ and Android 9+",
                    "priority": "high",
                },
                {
                    "name": "API Performance",
                    "type": "performance",
                    "description": "API response < 200ms",
                    "priority": "high",
                },
                {
                    "name": "Code Quality",
                    "type": "quality",
                    "description": "AI Mentor score > 4.0 for all apps",
                    "priority": "high",
                },
                {
                    "name": "Architecture Validation",
                    "type": "quality",
                    "description": "Automated architecture checks on every deployment",
                    "priority": "high",
                },
                {
                    "name": "Browser Support",
                    "type": "functional",
                    "description": "Chrome, Firefox, Safari, Edge (latest 2 versions)",
                    "priority": "medium",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget Limit",
                    "type": "financial",
                    "description": "Platform investment capped at $1M annually",
                },
                {
                    "name": "Timeline Pressure",
                    "type": "schedule",
                    "description": "First 10 apps must deliver within 6 months",
                },
                {
                    "name": "Skill Gap",
                    "type": "resource",
                    "description": "Limited OutSystems-trained developers",
                },
                {
                    "name": "Legacy Integration Complexity",
                    "type": "technical",
                    "description": "Must integrate with 50+ legacy systems",
                },
                {
                    "name": "Windows Server Dependency",
                    "type": "technical",
                    "description": "On-premise deployment requires Windows infrastructure",
                },
                {
                    "name": "Database Licensing",
                    "type": "financial",
                    "description": "Existing SQL Server licenses must be leveraged",
                },
                {
                    "name": "Regulatory Requirements",
                    "type": "compliance",
                    "description": "Must maintain SOC 2 and ISO certifications",
                },
                {
                    "name": "Network Constraints",
                    "type": "technical",
                    "description": "Limited bandwidth to some locations",
                },
                {
                    "name": "Change Resistance",
                    "type": "organizational",
                    "description": "Developers skeptical of low-code approach",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "Platform Readiness",
                    "type": "maturity",
                    "description": "Assess readiness for OutSystems adoption",
                    "result": "Score: 78/100 - Ready with minor gaps",
                },
                {
                    "name": "Application Portfolio Analysis",
                    "type": "business",
                    "description": "Identify migration candidates",
                    "result": "40 apps suitable for OutSystems",
                },
                {
                    "name": "Technical Architecture Review",
                    "type": "technical",
                    "description": "Evaluate infrastructure requirements",
                    "result": "Infrastructure ready, minor upgrades needed",
                },
                {
                    "name": "Team Capability Assessment",
                    "type": "capability",
                    "description": "Assess team skills and training needs",
                    "result": "30 developers, 10 need training",
                },
                {
                    "name": "ROI Analysis",
                    "type": "financial",
                    "description": "Calculate expected return on investment",
                    "result": "Projected 300% ROI in 3 years",
                },
            ]
        ),
        # ==================== IMPLEMENTATION & MIGRATION LAYER ====================
        implementation_events=json.dumps(
            [
                {
                    "name": "Platform Procurement Complete",
                    "date": "2024 - 01 - 15",
                    "milestone": True,
                    "description": "OutSystems licenses acquired",
                },
                {
                    "name": "Infrastructure Setup Complete",
                    "date": "2024 - 02 - 15",
                    "milestone": True,
                    "description": "Development and production environments ready",
                },
                {
                    "name": "Team Training Certified",
                    "date": "2024 - 03 - 15",
                    "milestone": True,
                    "description": "Initial team OutSystems certified",
                },
                {
                    "name": "Factory Framework Established",
                    "date": "2024 - 04 - 30",
                    "milestone": True,
                    "description": "Reusable architecture and components ready",
                },
                {
                    "name": "First 5 Apps Deployed",
                    "date": "2024 - 06 - 30",
                    "milestone": True,
                    "description": "Pilot phase successful",
                },
                {
                    "name": "AI Mentor Studio Onboarded",
                    "date": "2024 - 07 - 15",
                    "milestone": False,
                    "description": "Architecture governance active",
                },
                {
                    "name": "20 Apps in Production",
                    "date": "2024 - 09 - 30",
                    "milestone": True,
                    "description": "Scaling phase complete",
                },
                {
                    "name": "Legacy Migration Wave 1",
                    "date": "2024 - 12 - 31",
                    "milestone": True,
                    "description": "First 10 legacy apps migrated",
                },
                {
                    "name": "100 Apps Milestone",
                    "date": "2025 - 12 - 31",
                    "milestone": True,
                    "description": "Portfolio transformation complete",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Infrastructure Provisioning",
                    "description": "Set up OutSystems environments",
                    "duration_weeks": 4,
                    "team_size": 4,
                },
                {
                    "name": "Developer Training",
                    "description": "Certify development team",
                    "duration_weeks": 6,
                    "team_size": 2,
                },
                {
                    "name": "Factory Framework Build",
                    "description": "Create reusable architecture and components",
                    "duration_weeks": 12,
                    "team_size": 6,
                },
                {
                    "name": "Integration Layer Development",
                    "description": "Build enterprise integration connectors",
                    "duration_weeks": 16,
                    "team_size": 5,
                },
                {
                    "name": "Pilot Application Development",
                    "description": "Build first 5 pilot applications",
                    "duration_weeks": 12,
                    "team_size": 10,
                },
                {
                    "name": "Architecture Governance Setup",
                    "description": "Configure AI Mentor and Architecture Dashboard",
                    "duration_weeks": 4,
                    "team_size": 2,
                },
                {
                    "name": "DevOps Pipeline Configuration",
                    "description": "Set up LifeTime and CI/CD pipelines",
                    "duration_weeks": 6,
                    "team_size": 3,
                },
                {
                    "name": "Security & Compliance Implementation",
                    "description": "Configure security policies and compliance controls",
                    "duration_weeks": 8,
                    "team_size": 3,
                },
                {
                    "name": "Legacy Migration Wave 1",
                    "description": "Migrate first 10 legacy applications",
                    "duration_weeks": 24,
                    "team_size": 12,
                },
                {
                    "name": "Mobile Center of Excellence",
                    "description": "Establish mobile development capability",
                    "duration_weeks": 8,
                    "team_size": 4,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Enterprise Architecture Blueprint",
                    "type": "document",
                    "due_phase": "planning",
                    "owner": "Solutions Architect",
                },
                {
                    "name": "Factory Framework",
                    "type": "code",
                    "due_phase": "build",
                    "owner": "Tech Lead",
                },
                {
                    "name": "Integration Connectors",
                    "type": "code",
                    "due_phase": "build",
                    "owner": "Integration Team",
                },
                {
                    "name": "Pilot Applications",
                    "type": "application",
                    "due_phase": "build",
                    "owner": "Development Team",
                },
                {
                    "name": "Architecture Standards",
                    "type": "document",
                    "due_phase": "planning",
                    "owner": "Enterprise Architect",
                },
                {
                    "name": "DevOps Playbook",
                    "type": "document",
                    "due_phase": "deploy",
                    "owner": "DevOps Engineer",
                },
                {
                    "name": "Security Configuration",
                    "type": "configuration",
                    "due_phase": "build",
                    "owner": "Security Engineer",
                },
                {
                    "name": "Training Curriculum",
                    "type": "training",
                    "due_phase": "planning",
                    "owner": "Training Lead",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "Platform Operational",
                    "date": "2024 - 03 - 31",
                    "description": "Infrastructure ready, team trained, first apps building",
                },
                {
                    "name": "Pilot Validation",
                    "date": "2024 - 06 - 30",
                    "description": "First 5 apps proven successful in production",
                },
                {
                    "name": "Factory Model Proven",
                    "date": "2024 - 09 - 30",
                    "description": "20 apps delivered using standardized approach",
                },
                {
                    "name": "Enterprise Scale",
                    "date": "2025 - 12 - 31",
                    "description": "100 apps in production, platform embedded in organization",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "Azure East US 2",
                    "location": "Virginia, USA",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "Primary production region",
                },
                {
                    "name": "Azure West Europe",
                    "location": "Netherlands",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "European data residency",
                },
                {
                    "name": "Corporate Data Center",
                    "location": "Atlanta, GA",
                    "tier": "Tier III",
                    "size_sqm": 500,
                    "description": "On-premise development environment",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "Front-End Servers",
                    "type": "virtual-machine",
                    "quantity": 4,
                    "location": "Azure",
                    "specs": "Standard_D16s_v3",
                },
                {
                    "name": "Controller Servers",
                    "type": "virtual-machine",
                    "quantity": 2,
                    "location": "Azure",
                    "specs": "Standard_D8s_v3",
                },
                {
                    "name": "SQL Server Databases",
                    "type": "database",
                    "quantity": 2,
                    "location": "Azure",
                    "specs": "Premium P4",
                },
                {
                    "name": "Redis Cache",
                    "type": "cache",
                    "quantity": 2,
                    "location": "Azure",
                    "specs": "Premium P3",
                },
                {
                    "name": "Developer Workstations",
                    "type": "desktop",
                    "quantity": 40,
                    "location": "Corporate",
                    "specs": "i7, 32GB RAM, Windows 11",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "Azure Virtual Network",
                    "type": "vpc",
                    "coverage": "Azure Regions",
                    "bandwidth_mbps": 25000,
                    "provider": "Azure",
                },
                {
                    "name": "ExpressRoute",
                    "type": "private-link",
                    "coverage": "Azure East US 2",
                    "bandwidth_mbps": 10000,
                    "provider": "Azure",
                },
                {
                    "name": "Internet Gateway",
                    "type": "internet",
                    "coverage": "Global",
                    "bandwidth_mbps": 1000,
                    "provider": "Multiple ISPs",
                },
                {
                    "name": "Azure Front Door",
                    "type": "cdn",
                    "coverage": "Global",
                    "bandwidth_mbps": 100000,
                    "provider": "Azure",
                },
            ]
        ),
    )


def seed_outsystems(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(vendor_name="OutSystems").first()
            if existing:
                print("⚠️  OutSystems template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_outsystems_template()
            db.session.add(template)
            db.session.commit()

            print("✅ OutSystems template seeded successfully!")
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
                f"   - Motivation Layer: ✅ Complete (10 stakeholders, 10 drivers, 9 goals, 8 outcomes, 10 principles, 12 requirements, 9 constraints, 5 assessments)"
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
            print(f"❌ Error seeding OutSystems template: {str(e)}")
            import traceback

            traceback.print_exc()

            raise


if __name__ == "__main__":
    seed_outsystems()
