"""
ServiceNow ITSM Vendor Template Seed Data

IT Support capabilities for manufacturing: Incident Management, Change Management,
Asset Management, CMDB, Service Catalog, and Knowledge Management.

Run with: python manage.py seed-vendor-servicenow
"""
import json

from app import create_app, db
from app.models import VendorStackTemplate
from config import DevelopmentConfig


def create_servicenow_template():
    """ServiceNow ITSM - IT Operations & Support Platform"""
    return VendorStackTemplate(
        vendor_name="ServiceNow",
        name="ServiceNow IT Service Management Platform",
        description="Enterprise IT service management platform for manufacturing operations covering incident, problem, change, asset, and knowledge management with CMDB foundation",
        # ==================== TECHNOLOGY LAYER ====================
        platform="cloud",
        primary_language="javascript",
        framework="ServiceNow Platform",
        framework_version="Vancouver",
        primary_database="mysql",
        database_version="8.0",
        container_runtime="proprietary",
        orchestration="servicenow-platform",
        service_mesh="none",
        api_standard="REST",
        api_gateway="api-gateway",
        message_broker="event-management",
        auth_provider="oauth2",
        secrets_manager="credential-store",
        logging_framework="system-logs",
        metrics_platform="performance-analytics",
        apm_tool="apm",
        tracing_tool="transaction-log",
        build_tool="studio",
        ci_cd_platform="ci-cd-spoke",
        sast_tool="code-scanner",
        dast_tool="security-scan",
        dependency_scanner="third-party-risk",
        nodes=json.dumps(
            [
                {
                    "name": "ServiceNow Production Instance",
                    "type": "cloud-platform",
                    "os": "Linux",
                    "cpu_cores": 64,
                    "ram_gb": 256,
                },
                {
                    "name": "ServiceNow Test Instance",
                    "type": "cloud-platform",
                    "os": "Linux",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
                {
                    "name": "MID Server (On-Prem Connector)",
                    "type": "vm",
                    "os": "Windows Server",
                    "cpu_cores": 8,
                    "ram_gb": 16,
                },
                {
                    "name": "Discovery Server",
                    "type": "vm",
                    "os": "Linux",
                    "cpu_cores": 16,
                    "ram_gb": 32,
                },
            ]
        ),
        devices=json.dumps(
            [
                {
                    "name": "Mobile ITSM App",
                    "type": "mobile-device",
                    "description": "iOS/Android service management app",
                },
                {
                    "name": "Self-Service Portal",
                    "type": "web-portal",
                    "description": "Employee self-service portal",
                },
                {
                    "name": "Virtual Agent Chatbot",
                    "type": "chatbot",
                    "description": "AI-powered service desk chatbot",
                },
                {
                    "name": "CMDB Discovery Agent",
                    "type": "discovery-tool",
                    "description": "Automated asset discovery",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {"name": "ServiceNow ITSM", "type": "cloud-platform", "version": "Vancouver"},
                {
                    "name": "IT Operations Management (ITOM)",
                    "type": "operations-platform",
                    "version": "Vancouver",
                },
                {
                    "name": "IT Asset Management (ITAM)",
                    "type": "asset-platform",
                    "version": "Vancouver",
                },
                {
                    "name": "Configuration Management Database (CMDB)",
                    "type": "configuration-database",
                    "version": "Vancouver",
                },
                {"name": "Service Portal", "type": "portal-platform", "version": "Vancouver"},
                {"name": "Virtual Agent", "type": "ai-chatbot", "version": "Vancouver"},
                {"name": "IntegrationHub", "type": "integration-platform", "version": "Vancouver"},
                {"name": "Performance Analytics", "type": "analytics", "version": "Vancouver"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "Incident Management Service",
                    "type": "itsm-service",
                    "description": "IT incident tracking and resolution",
                },
                {
                    "name": "Change Management Service",
                    "type": "itsm-service",
                    "description": "IT change control and approval",
                },
                {
                    "name": "Asset Management Service",
                    "type": "itam-service",
                    "description": "Hardware and software asset tracking",
                },
                {
                    "name": "CMDB Service",
                    "type": "configuration-service",
                    "description": "Configuration item management",
                },
                {
                    "name": "Service Catalog Service",
                    "type": "catalog-service",
                    "description": "IT service request catalog",
                },
                {
                    "name": "Knowledge Management Service",
                    "type": "km-service",
                    "description": "Knowledge base and articles",
                },
                {
                    "name": "Discovery Service",
                    "type": "discovery-service",
                    "description": "Automated IT asset discovery",
                },
                {
                    "name": "Integration Service",
                    "type": "integration-service",
                    "description": "Third-party system integration",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "Update Set",
                    "type": "deployment-package",
                    "size_mb": 10,
                    "registry": "ServiceNow Repository",
                },
                {
                    "name": "Scoped Application",
                    "type": "application-package",
                    "size_mb": 50,
                    "registry": "ServiceNow Store",
                },
                {
                    "name": "Integration Spoke",
                    "type": "integration-package",
                    "size_mb": 5,
                    "registry": "IntegrationHub",
                },
                {
                    "name": "CMDB Backup",
                    "type": "backup-archive",
                    "size_mb": 10000,
                    "registry": "Backup Storage",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "ServiceNow Cloud Network",
                    "type": "cloud-network",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 20,
                },
                {
                    "name": "MID Server Network",
                    "type": "hybrid-link",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 10,
                },
                {
                    "name": "API Gateway Network",
                    "type": "api-gateway",
                    "bandwidth_mbps": 5000,
                    "latency_ms": 15,
                },
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="ServiceNow, Inc.",
        market_position="leader",
        company_size="enterprise",
        founded_year=2004,
        headquarters="Santa Clara, CA",
        revenue_usd=8500000000,
        customer_count=7700,
        market_share_percentage=28.0,
        acquisition_risk="very-low",
        financial_health="excellent",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                # IT OPERATIONS & SUPPORT CAPABILITIES
                {
                    "name": "Incident Management",
                    "description": "IT incident tracking, prioritization, assignment, and resolution",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Problem Management",
                    "description": "Root cause analysis, known error management, problem resolution",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Change Management",
                    "description": "Change request, approval workflow, CAB, implementation tracking",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Release Management",
                    "description": "Release planning, deployment tracking, rollback procedures",
                    "coverage_percentage": 95,
                    "maturity_level": "managed",
                },
                {
                    "name": "IT Asset Management (ITAM)",
                    "description": "Hardware/software asset tracking, lifecycle, contracts, compliance",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Configuration Management (CMDB)",
                    "description": "Configuration item discovery, tracking, relationship mapping",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Service Catalog & Request",
                    "description": "Self-service portal, service catalog, request fulfillment workflow",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Knowledge Management",
                    "description": "Knowledge base, article authoring, search, AI recommendations",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Service Level Management",
                    "description": "SLA definition, monitoring, breach alerting, reporting",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Event Management",
                    "description": "Infrastructure event monitoring, correlation, alert routing",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Discovery & Service Mapping",
                    "description": "Automated infrastructure discovery, application dependency mapping",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Software Asset Management (SAM)",
                    "description": "Software license optimization, compliance, vendor management",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "IT Procurement",
                    "description": "IT purchasing, approval workflow, vendor management, PO tracking",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Contract Management",
                    "description": "Vendor contracts, renewals, compliance, cost tracking",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "IT Service Portfolio Management",
                    "description": "Service portfolio, business service mapping, service costing",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "Automated Workflows",
                    "description": "Flow Designer, workflow automation, orchestration",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Virtual Agent (AI Chatbot)",
                    "description": "Conversational AI for incident deflection and self-service",
                    "coverage_percentage": 85,
                    "maturity_level": "developing",
                },
                {
                    "name": "IT Dashboard & Reporting",
                    "description": "Performance Analytics, custom dashboards, KPI tracking",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Integration Platform",
                    "description": "IntegrationHub, pre-built spokes, API management",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Mobile Service Management",
                    "description": "Mobile app for technicians and end users",
                    "coverage_percentage": 87,
                    "maturity_level": "managed",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Incident-to-Resolution",
                    "stages": [
                        "Incident Reported",
                        "Triage",
                        "Assignment",
                        "Investigation",
                        "Resolution",
                        "Closure",
                        "Review",
                    ],
                    "description": "IT incident lifecycle",
                },
                {
                    "name": "Request-to-Fulfillment",
                    "stages": [
                        "Service Request",
                        "Approval",
                        "Fulfillment Task",
                        "Provisioning",
                        "Delivery",
                        "Confirmation",
                    ],
                    "description": "Service request processing",
                },
                {
                    "name": "Problem-to-Fix",
                    "stages": [
                        "Problem Identified",
                        "Investigation",
                        "Root Cause Analysis",
                        "Solution Development",
                        "Implementation",
                        "Validation",
                    ],
                    "description": "Problem management lifecycle",
                },
                {
                    "name": "Change-to-Deploy",
                    "stages": [
                        "Change Request",
                        "Impact Assessment",
                        "CAB Approval",
                        "Implementation Planning",
                        "Deployment",
                        "Validation",
                        "Close",
                    ],
                    "description": "Change management workflow",
                },
                {
                    "name": "Asset-to-Disposal",
                    "stages": [
                        "Asset Procurement",
                        "Receiving",
                        "Deployment",
                        "Maintenance",
                        "Refresh",
                        "Decommission",
                        "Disposal",
                    ],
                    "description": "IT asset lifecycle",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "ITSM Foundation Deployment",
                    "description": "Core ITSM modules (Incident, Problem, Change)",
                    "timeline_months": 6,
                    "risk_level": "low",
                },
                {
                    "name": "ITOM Integration",
                    "description": "Add IT Operations Management and Discovery",
                    "timeline_months": 9,
                    "risk_level": "medium",
                },
                {
                    "name": "ITAM Implementation",
                    "description": "Full IT Asset and Software Asset Management",
                    "timeline_months": 12,
                    "risk_level": "medium",
                },
                {
                    "name": "Cloud-Native Deployment",
                    "description": "ServiceNow SaaS with minimal customization",
                    "timeline_months": 4,
                    "risk_level": "low",
                },
                {
                    "name": "Phased Rollout by Plant",
                    "description": "Deploy site-by-site across manufacturing locations",
                    "timeline_months": 18,
                    "risk_level": "low",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "IT Service Desk",
                    "description": "24/7 IT support for manufacturing operations",
                    "service_type": "internal",
                    "sla_commitment": "P1: 15 min, P2: 2 hrs, P3: 8 hrs, P4: 24 hrs",
                },
                {
                    "name": "Change Advisory Board (CAB)",
                    "description": "IT change approval and governance",
                    "service_type": "internal",
                    "sla_commitment": "Weekly meetings, emergency CAB within 4 hours",
                },
                {
                    "name": "Asset Lifecycle Management",
                    "description": "IT asset tracking and compliance",
                    "service_type": "internal",
                    "sla_commitment": "Asset discovery weekly, 98% accuracy",
                },
                {
                    "name": "IT Self-Service Portal",
                    "description": "Employee self-service for IT requests",
                    "service_type": "internal",
                    "sla_commitment": "99.9% portal availability, < 3 sec load time",
                },
                {
                    "name": "Knowledge Base Service",
                    "description": "IT knowledge repository",
                    "service_type": "internal",
                    "sla_commitment": "Search results < 2 seconds, 90% article accuracy",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Incident Resolution",
                    "description": "Respond to and resolve IT incidents",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Incident Creation",
                        "Categorization",
                        "Priority Assignment",
                        "Assignment",
                        "Investigation",
                        "Resolution",
                        "Closure",
                    ],
                    "cycle_time": "P1: < 4 hrs, P2: < 8 hrs, P3: < 24 hrs",
                    "kpis": ["MTTR", "First Call Resolution", "User Satisfaction"],
                },
                {
                    "name": "Change Request Processing",
                    "description": "IT change control workflow",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Change Request",
                        "Impact Assessment",
                        "Risk Analysis",
                        "CAB Review",
                        "Approval",
                        "Scheduling",
                        "Implementation",
                        "Validation",
                        "Closure",
                    ],
                    "cycle_time": "Standard: 5 - 10 days, Emergency: < 4 hours",
                    "kpis": ["Change Success Rate", "Emergency Change %", "Rollback Rate"],
                },
                {
                    "name": "Service Request Fulfillment",
                    "description": "Fulfill IT service requests",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Request Submission",
                        "Approval",
                        "Task Assignment",
                        "Fulfillment",
                        "Delivery",
                        "Confirmation",
                        "Closure",
                    ],
                    "cycle_time": "1 - 3 days",
                    "kpis": ["Fulfillment Time", "Request Accuracy", "User Satisfaction"],
                },
                {
                    "name": "Asset Discovery & Reconciliation",
                    "description": "Discover and track IT assets",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Network Scan",
                        "Asset Identification",
                        "CMDB Update",
                        "Relationship Mapping",
                        "Reconciliation",
                        "Exception Handling",
                    ],
                    "cycle_time": "Weekly automated runs",
                    "kpis": ["Discovery Accuracy", "CMDB Completeness", "Reconciliation Rate"],
                },
                {
                    "name": "Problem Investigation",
                    "description": "Identify and fix recurring issues",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Problem Detection",
                        "Investigation",
                        "Root Cause Analysis",
                        "Known Error Creation",
                        "Workaround Development",
                        "Permanent Fix",
                        "Validation",
                    ],
                    "cycle_time": "2 - 4 weeks",
                    "kpis": [
                        "Problem Resolution Time",
                        "Incident Reduction",
                        "Known Error Database Size",
                    ],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Incident",
                    "description": "IT service disruption or degradation",
                    "lifecycle": "new -> assigned -> in-progress -> resolved -> closed",
                },
                {
                    "name": "Change Request",
                    "description": "IT infrastructure change",
                    "lifecycle": "draft -> requested -> assess -> authorize -> scheduled -> implement -> review -> closed",
                },
                {
                    "name": "Configuration Item (CI)",
                    "description": "IT asset or component",
                    "lifecycle": "ordered -> in-stock -> installed -> in-use -> in-repair -> retired",
                },
                {
                    "name": "Service Request",
                    "description": "Standard IT service request",
                    "lifecycle": "requested -> approved -> work-in-progress -> closed-complete",
                },
                {
                    "name": "Problem",
                    "description": "Underlying cause of incidents",
                    "lifecycle": "draft -> new -> assess -> root-cause-analysis -> fix-in-progress -> resolved -> closed",
                },
                {
                    "name": "Knowledge Article",
                    "description": "IT knowledge base article",
                    "lifecycle": "draft -> review -> published -> retired",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "IT Service Desk Agent",
                    "description": "Handles IT support tickets",
                    "responsibilities": ["Incident Logging", "Triage", "Resolution", "Escalation"],
                },
                {
                    "name": "IT Infrastructure Engineer",
                    "description": "Manages IT infrastructure",
                    "responsibilities": [
                        "Incident Investigation",
                        "Change Implementation",
                        "Asset Management",
                    ],
                },
                {
                    "name": "Change Manager",
                    "description": "Oversees IT changes",
                    "responsibilities": [
                        "Change Assessment",
                        "CAB Coordination",
                        "Approval Management",
                    ],
                },
                {
                    "name": "Asset Manager",
                    "description": "Manages IT asset lifecycle",
                    "responsibilities": [
                        "Asset Tracking",
                        "License Compliance",
                        "Contract Management",
                    ],
                },
                {
                    "name": "End User (Employee)",
                    "description": "Manufacturing employee using IT services",
                    "responsibilities": [
                        "Incident Reporting",
                        "Service Requests",
                        "Self-Service Portal Usage",
                    ],
                },
                {
                    "name": "Knowledge Manager",
                    "description": "Manages knowledge base",
                    "responsibilities": [
                        "Article Creation",
                        "Content Review",
                        "Knowledge Governance",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "ITSM Pro",
                    "description": "Core IT Service Management suite",
                    "target_market": "Manufacturing Companies",
                },
                {
                    "name": "ITOM",
                    "description": "IT Operations Management",
                    "target_market": "Large Manufacturers",
                },
                {
                    "name": "ITAM",
                    "description": "IT Asset Management",
                    "target_market": "All Manufacturing",
                },
                {
                    "name": "IntegrationHub",
                    "description": "Integration platform",
                    "target_market": "Enterprise Manufacturing",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "Service Portal",
                    "type": "web-portal",
                    "description": "Employee self-service portal",
                    "technology": "AngularJS",
                },
                {
                    "name": "Platform UI",
                    "type": "web-app",
                    "description": "Agent workspace interface",
                    "technology": "ServiceNow UI",
                },
                {
                    "name": "Mobile App",
                    "type": "mobile-app",
                    "description": "ITSM mobile application",
                    "technology": "React Native",
                },
                {
                    "name": "Virtual Agent",
                    "type": "chatbot",
                    "description": "AI-powered service desk bot",
                    "technology": "NLU Engine",
                },
                {
                    "name": "Discovery Engine",
                    "type": "discovery-service",
                    "description": "Automated asset discovery",
                    "technology": "Python/Java",
                },
                {
                    "name": "IntegrationHub",
                    "type": "integration-middleware",
                    "description": "Integration orchestration",
                    "technology": "Node.js",
                },
                {
                    "name": "Flow Designer",
                    "type": "workflow-engine",
                    "description": "Visual workflow builder",
                    "technology": "ServiceNow Platform",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "Table API",
                    "type": "REST",
                    "description": "CRUD operations on ServiceNow tables",
                    "endpoints": ["/api/now/table/{tableName}"],
                },
                {
                    "name": "Import Set API",
                    "type": "REST",
                    "description": "Bulk data import",
                    "endpoints": ["/api/now/import/{tableName}"],
                },
                {
                    "name": "Aggregate API",
                    "type": "REST",
                    "description": "Aggregated data queries",
                    "endpoints": ["/api/now/stats/{tableName}"],
                },
                {
                    "name": "Attachment API",
                    "type": "REST",
                    "description": "File attachments",
                    "endpoints": ["/api/now/attachment"],
                },
                {
                    "name": "Scripted REST API",
                    "type": "REST",
                    "description": "Custom API endpoints",
                    "endpoints": ["/api/x_<scope>/v1/custom"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "REST API",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "OAuth 2.0",
                },
                {
                    "name": "SOAP API",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "XML",
                    "authentication": "Basic Auth",
                },
                {
                    "name": "IntegrationHub Spoke",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "OAuth 2.0",
                },
                {
                    "name": "Email Integration",
                    "protocol": "SMTP/IMAP",
                    "data_format": "Email",
                    "authentication": "SMTP Auth",
                },
                {
                    "name": "JDBC Connection",
                    "protocol": "JDBC",
                    "data_format": "SQL",
                    "authentication": "Database Credentials",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {"name": "Incident", "type": "transactional", "retention_policy": "3 years"},
                {
                    "name": "Change Request",
                    "type": "transactional",
                    "retention_policy": "5 years for compliance",
                },
                {
                    "name": "Configuration Item",
                    "type": "master",
                    "retention_policy": "Permanent until decommissioned",
                },
                {"name": "Asset", "type": "master", "retention_policy": "7 years post-disposal"},
                {
                    "name": "Knowledge Article",
                    "type": "content",
                    "retention_policy": "Permanent until retired",
                },
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "Incident Logging",
                    "type": "CRUD",
                    "description": "Create and manage IT incidents",
                },
                {
                    "name": "Assignment Rules",
                    "type": "business-logic",
                    "description": "Intelligent ticket routing",
                },
                {
                    "name": "SLA Calculation",
                    "type": "business-logic",
                    "description": "Calculate SLA breach times",
                },
                {
                    "name": "Auto-Discovery",
                    "type": "batch-process",
                    "description": "Automated infrastructure discovery",
                },
                {
                    "name": "Workflow Automation",
                    "type": "workflow",
                    "description": "Automated process orchestration",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "CIO",
                    "role": "executive",
                    "concerns": [
                        "IT Service Quality",
                        "Cost Optimization",
                        "Digital Transformation",
                    ],
                    "influence": "high",
                },
                {
                    "name": "IT Director",
                    "role": "senior-management",
                    "concerns": ["Service Uptime", "Team Productivity", "Process Standardization"],
                    "influence": "high",
                },
                {
                    "name": "Service Desk Manager",
                    "role": "management",
                    "concerns": ["MTTR", "First Call Resolution", "User Satisfaction"],
                    "influence": "medium",
                },
                {
                    "name": "Manufacturing Operations Manager",
                    "role": "business-stakeholder",
                    "concerns": ["Production Uptime", "Fast IT Response", "Equipment Availability"],
                    "influence": "high",
                },
                {
                    "name": "IT Governance Committee",
                    "role": "governance",
                    "concerns": ["Compliance", "Risk Management", "Change Control"],
                    "influence": "high",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "IT Operational Excellence",
                    "description": "World-class IT service delivery",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Manufacturing Uptime",
                    "description": "Minimize IT-related production downtime",
                    "urgency": "critical",
                    "impact": "high",
                },
                {
                    "name": "IT Cost Optimization",
                    "description": "Reduce IT support costs",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Regulatory Compliance",
                    "description": "IT audit and compliance requirements",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Digital Transformation",
                    "description": "Enable Industry 4.0 initiatives",
                    "urgency": "medium",
                    "impact": "transformational",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "Achieve 95% First Call Resolution",
                    "description": "Resolve incidents on first contact",
                    "timeframe": "12 months",
                    "measurable": "FCR > 95%",
                },
                {
                    "name": "Reduce MTTR by 40%",
                    "description": "Mean Time To Repair reduction",
                    "timeframe": "18 months",
                    "measurable": "MTTR < 2 hours for P1",
                },
                {
                    "name": "98% Change Success Rate",
                    "description": "Successful change implementations",
                    "timeframe": "12 months",
                    "measurable": "< 2% rollback rate",
                },
                {
                    "name": "100% IT Asset Visibility",
                    "description": "Complete asset inventory accuracy",
                    "timeframe": "9 months",
                    "measurable": "CMDB accuracy > 98%",
                },
                {
                    "name": "Reduce IT Ticket Volume by 30%",
                    "description": "Self-service and automation",
                    "timeframe": "12 months",
                    "measurable": "30% reduction via self-service",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "Improved Production Uptime",
                    "description": "Reduced IT-related downtime",
                    "benefit_type": "operational",
                    "quantified_benefit": "99.5% IT service availability",
                },
                {
                    "name": "IT Cost Savings",
                    "description": "Lower IT support costs",
                    "benefit_type": "financial",
                    "quantified_benefit": "$2M annual savings",
                },
                {
                    "name": "Enhanced Compliance",
                    "description": "IT audit compliance",
                    "benefit_type": "risk",
                    "quantified_benefit": "Zero IT audit findings",
                },
                {
                    "name": "Increased User Satisfaction",
                    "description": "Better employee IT experience",
                    "benefit_type": "user-experience",
                    "quantified_benefit": "User satisfaction > 4.5/5",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Service-First Mindset",
                    "description": "Treat IT as a service to the business",
                    "rationale": "Alignment with manufacturing operations",
                },
                {
                    "name": "Automation Over Manual Work",
                    "description": "Automate repetitive IT tasks",
                    "rationale": "Efficiency and consistency",
                },
                {
                    "name": "Configuration Management Discipline",
                    "description": "Accurate CMDB is foundation",
                    "rationale": "Enables all other IT processes",
                },
                {
                    "name": "Self-Service Enablement",
                    "description": "Empower users to self-serve",
                    "rationale": "Reduce ticket volume and costs",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "System Availability",
                    "type": "performance",
                    "description": "99.9% uptime for ServiceNow platform",
                    "priority": "critical",
                },
                {
                    "name": "Incident Response Time",
                    "type": "performance",
                    "description": "P1 response < 15 minutes",
                    "priority": "critical",
                },
                {
                    "name": "Data Security",
                    "type": "security",
                    "description": "Encrypt data at rest and in transit",
                    "priority": "critical",
                },
                {
                    "name": "Integration with MES/ERP",
                    "type": "functional",
                    "description": "Integrate with SAP and Siemens systems",
                    "priority": "high",
                },
                {
                    "name": "Audit Trail",
                    "type": "compliance",
                    "description": "Complete audit log of all changes",
                    "priority": "high",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget",
                    "type": "financial",
                    "description": "ITSM budget capped at $500K annually",
                },
                {
                    "name": "Timeline",
                    "type": "schedule",
                    "description": "Must deploy within 6 months",
                },
                {
                    "name": "Integration Complexity",
                    "type": "technical",
                    "description": "Must integrate with 20+ systems",
                },
                {
                    "name": "User Adoption",
                    "type": "organizational",
                    "description": "Change management for 1500+ users",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "Current State Assessment",
                    "type": "maturity",
                    "description": "Assess current IT service maturity",
                    "result": "Score: 2/5 - Reactive service model",
                },
                {
                    "name": "CMDB Readiness",
                    "type": "technical",
                    "description": "Assess configuration management readiness",
                    "result": "Poor asset inventory accuracy",
                },
                {
                    "name": "Integration Analysis",
                    "type": "technical",
                    "description": "Catalog integration requirements",
                    "result": "25 systems require integration",
                },
            ]
        ),
        # ==================== IMPLEMENTATION & MIGRATION LAYER ====================
        implementation_events=json.dumps(
            [
                {
                    "name": "Project Kickoff",
                    "date": "2024 - 01 - 15",
                    "milestone": True,
                    "description": "ITSM project initiated",
                },
                {
                    "name": "CMDB Discovery Complete",
                    "date": "2024 - 03 - 01",
                    "milestone": True,
                    "description": "Initial asset discovery",
                },
                {
                    "name": "Pilot Launch",
                    "date": "2024 - 04 - 01",
                    "milestone": True,
                    "description": "Pilot with IT department",
                },
                {
                    "name": "Full Production",
                    "date": "2024 - 07 - 01",
                    "milestone": True,
                    "description": "Enterprise-wide rollout",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Platform Configuration",
                    "description": "Configure ServiceNow ITSM modules",
                    "duration_weeks": 8,
                    "team_size": 4,
                },
                {
                    "name": "CMDB Population",
                    "description": "Discover and populate CMDB",
                    "duration_weeks": 10,
                    "team_size": 3,
                },
                {
                    "name": "Integration Development",
                    "description": "Build integrations with manufacturing systems",
                    "duration_weeks": 12,
                    "team_size": 5,
                },
                {
                    "name": "User Training",
                    "description": "Train IT staff and end users",
                    "duration_weeks": 6,
                    "team_size": 2,
                },
                {
                    "name": "Process Redesign",
                    "description": "Redesign IT service processes",
                    "duration_weeks": 8,
                    "team_size": 3,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Solution Design Document",
                    "type": "document",
                    "due_phase": "design",
                    "owner": "Solution Architect",
                },
                {
                    "name": "Integration Specification",
                    "type": "document",
                    "due_phase": "design",
                    "owner": "Integration Architect",
                },
                {
                    "name": "Configured ITSM Platform",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "ServiceNow Admin",
                },
                {
                    "name": "CMDB with 10K+ CIs",
                    "type": "data",
                    "due_phase": "build",
                    "owner": "CMDB Manager",
                },
                {
                    "name": "Training Materials",
                    "type": "training",
                    "due_phase": "build",
                    "owner": "Training Lead",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "ITSM Foundation Ready",
                    "date": "2024 - 03 - 15",
                    "description": "Core ITSM configured and tested",
                },
                {
                    "name": "CMDB Baseline Established",
                    "date": "2024 - 04 - 30",
                    "description": "CMDB populated with critical assets",
                },
                {
                    "name": "Production Launch",
                    "date": "2024 - 07 - 01",
                    "description": "Full production rollout",
                },
                {
                    "name": "Optimization",
                    "date": "2024 - 10 - 01",
                    "description": "Process optimization based on 3 months data",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "ServiceNow US Data Center",
                    "location": "Oregon, USA",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "Primary US production instance",
                },
                {
                    "name": "ServiceNow EU Data Center",
                    "location": "Amsterdam, Netherlands",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "EU instance for data residency",
                },
                {
                    "name": "On-Prem MID Server Room",
                    "location": "Manufacturing HQ Data Center",
                    "tier": "Tier III",
                    "size_sqm": 50,
                    "description": "MID server for on-prem integration",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "MID Server (Physical)",
                    "type": "server",
                    "quantity": 3,
                    "location": "Manufacturing HQ",
                    "specs": "Dell R440, 8 - core, 32GB RAM",
                },
                {
                    "name": "Discovery Probe Server",
                    "type": "vm",
                    "quantity": 2,
                    "location": "Data Center",
                    "specs": "8 vCPU, 16GB RAM",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "ServiceNow Cloud Network",
                    "type": "cloud-network",
                    "coverage": "Global",
                    "bandwidth_mbps": 10000,
                    "provider": "ServiceNow",
                },
                {
                    "name": "Corporate WAN",
                    "type": "wan",
                    "coverage": "Global Manufacturing Sites",
                    "bandwidth_mbps": 1000,
                    "provider": "AT&T",
                },
                {
                    "name": "Internet Gateway",
                    "type": "internet",
                    "coverage": "HQ",
                    "bandwidth_mbps": 10000,
                    "provider": "Level3",
                },
            ]
        ),
    )


def seed_servicenow(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(vendor_name="ServiceNow").first()
            if existing:
                print("⚠️  ServiceNow template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_servicenow_template()
            db.session.add(template)
            db.session.commit()

            print("✅ ServiceNow ITSM template seeded successfully!")
            print(f"   - Vendor: {template.vendor_name}")
            print(f"   - IT Support Capabilities: 20")
            print(f"   - Primary Focus: Incident, Change, Asset, CMDB, Knowledge Management")
            print(f"   - Total ArchiMate Coverage: 100%")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding ServiceNow template: {str(e)}")
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    seed_servicenow()
