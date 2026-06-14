"""
Microsoft Power Platform Vendor Template Seed Data

Data & Analytics support capabilities for manufacturing: Power BI (analytics), Power Apps (low-code),
Power Automate (workflow), Power Virtual Agents (chatbots), Dataverse (data platform).

Run with: python manage.py seed-vendor-microsoft-power
"""
import json

from app import create_app, db
from app.models import VendorStackTemplate
from config import DevelopmentConfig


def create_microsoft_power_template():
    """Microsoft Power Platform - Low-Code Data & Analytics Platform"""
    return VendorStackTemplate(
        vendor_name="Microsoft Power Platform",
        name="Microsoft Power Platform - Low-Code Analytics & Automation",
        description="Unified low-code platform for data analytics (Power BI), app development (Power Apps), workflow automation (Power Automate), and virtual agents for manufacturing operations",
        # ==================== TECHNOLOGY LAYER ====================
        platform="cloud",
        primary_language="powerfx",
        framework="Power Platform",
        framework_version="2024",
        primary_database="dataverse",
        database_version="latest",
        container_runtime="azure-functions",
        orchestration="azure-logic-apps",
        service_mesh="none",
        api_standard="REST",
        api_gateway="azure-api-management",
        message_broker="azure-service-bus",
        auth_provider="azure-ad",
        secrets_manager="azure-key-vault",
        logging_framework="azure-monitor",
        metrics_platform="application-insights",
        apm_tool="application-insights",
        tracing_tool="application-insights",
        build_tool="power-platform-cli",
        ci_cd_platform="azure-devops",
        sast_tool="microsoft-defender",
        dast_tool="microsoft-defender",
        dependency_scanner="microsoft-defender",
        nodes=json.dumps(
            [
                {
                    "name": "Power BI Service (Azure)",
                    "type": "cloud-platform",
                    "os": "Azure",
                    "cpu_cores": 64,
                    "ram_gb": 256,
                },
                {
                    "name": "Power Apps Environment",
                    "type": "cloud-platform",
                    "os": "Azure",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
                {
                    "name": "Dataverse Instance",
                    "type": "database-server",
                    "os": "Azure SQL",
                    "cpu_cores": 32,
                    "ram_gb": 256,
                },
                {
                    "name": "On-Premises Data Gateway",
                    "type": "vm",
                    "os": "Windows Server",
                    "cpu_cores": 8,
                    "ram_gb": 16,
                },
            ]
        ),
        devices=json.dumps(
            [
                {
                    "name": "Power BI Mobile App",
                    "type": "mobile-device",
                    "description": "iOS/Android analytics app",
                },
                {
                    "name": "Power Apps Mobile",
                    "type": "mobile-device",
                    "description": "Custom mobile apps",
                },
                {
                    "name": "Power BI Desktop",
                    "type": "desktop-software",
                    "description": "Report development tool",
                },
                {
                    "name": "Browser-Based Portal",
                    "type": "web-portal",
                    "description": "Web access to all Power Platform",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {"name": "Power BI Service", "type": "analytics-platform", "version": "2024"},
                {"name": "Power Apps", "type": "low-code-platform", "version": "2024"},
                {"name": "Power Automate", "type": "workflow-platform", "version": "2024"},
                {"name": "Power Virtual Agents", "type": "chatbot-platform", "version": "2024"},
                {"name": "Dataverse", "type": "data-platform", "version": "Latest"},
                {"name": "AI Builder", "type": "ai-platform", "version": "Latest"},
                {
                    "name": "Power BI Report Server",
                    "type": "on-premises-analytics",
                    "version": "Latest",
                },
                {
                    "name": "On-Premises Data Gateway",
                    "type": "integration-gateway",
                    "version": "Latest",
                },
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "Power BI Analytics Service",
                    "type": "analytics-service",
                    "description": "Data visualization and reporting",
                },
                {
                    "name": "Power Apps Runtime Service",
                    "type": "app-service",
                    "description": "Low-code application execution",
                },
                {
                    "name": "Power Automate Flow Service",
                    "type": "workflow-service",
                    "description": "Automated workflow execution",
                },
                {
                    "name": "Dataverse Data Service",
                    "type": "data-service",
                    "description": "Common data storage and management",
                },
                {
                    "name": "AI Builder Service",
                    "type": "ai-service",
                    "description": "Pre-built AI models",
                },
                {
                    "name": "Connector Service",
                    "type": "integration-service",
                    "description": "400+ data connectors",
                },
                {
                    "name": "Power Virtual Agents Service",
                    "type": "chatbot-service",
                    "description": "Conversational AI",
                },
                {
                    "name": "Data Gateway Service",
                    "type": "gateway-service",
                    "description": "On-premises data connectivity",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "Power BI Report",
                    "type": "report",
                    "size_mb": 50,
                    "registry": "Power BI Service",
                },
                {
                    "name": "Power Apps Solution",
                    "type": "deployment-package",
                    "size_mb": 100,
                    "registry": "Dataverse",
                },
                {
                    "name": "Power Automate Flow",
                    "type": "workflow-definition",
                    "size_mb": 5,
                    "registry": "Power Automate",
                },
                {
                    "name": "Dataverse Backup",
                    "type": "backup-archive",
                    "size_mb": 50000,
                    "registry": "Azure Backup",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "Azure Global Network",
                    "type": "cloud-network",
                    "bandwidth_mbps": 100000,
                    "latency_ms": 10,
                },
                {
                    "name": "Data Gateway Network",
                    "type": "hybrid-link",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 20,
                },
                {
                    "name": "ExpressRoute",
                    "type": "dedicated-link",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 5,
                },
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="Microsoft Corporation",
        market_position="leader",
        company_size="enterprise",
        founded_year=1975,
        headquarters="Redmond, WA",
        revenue_usd=211000000000,
        customer_count=1000000,
        market_share_percentage=35.0,
        acquisition_risk="very-low",
        financial_health="excellent",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                # DATA & ANALYTICS CAPABILITIES
                {
                    "name": "Business Intelligence & Reporting",
                    "description": "Interactive dashboards, visualizations, paginated reports",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Real-Time Analytics",
                    "description": "Streaming data analysis, real-time dashboards",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Self-Service Analytics",
                    "description": "Citizen data analyst enablement, drag-and-drop BI",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Advanced Analytics",
                    "description": "R/Python integration, AI-powered insights, forecasting",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Mobile Analytics",
                    "description": "Mobile BI apps, offline capability, touch-optimized",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Embedded Analytics",
                    "description": "BI embedded in applications, white-label analytics",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                # LOW-CODE APP DEVELOPMENT
                {
                    "name": "Rapid App Development",
                    "description": "Drag-and-drop app builder, responsive design",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Canvas Apps",
                    "description": "Pixel-perfect custom apps",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Model-Driven Apps",
                    "description": "Data-driven apps from Dataverse",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Portal Apps",
                    "description": "External-facing portals",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Offline Mobile Apps",
                    "description": "Apps that work without connectivity",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Component Library",
                    "description": "Reusable UI components, code components",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                # WORKFLOW AUTOMATION
                {
                    "name": "Business Process Automation",
                    "description": "Automated workflows, approval processes",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "RPA (Robotic Process Automation)",
                    "description": "UI automation, desktop flows",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Cloud Flows",
                    "description": "Cloud-based workflow automation",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Desktop Flows",
                    "description": "Legacy system automation via RPA",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Business Process Flows",
                    "description": "Guided workflows, stage-based processes",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Scheduled Automation",
                    "description": "Time-based triggers, batch processing",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                # DATA PLATFORM
                {
                    "name": "Common Data Model",
                    "description": "Standardized data schemas, entity relationships",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Data Integration",
                    "description": "400+ connectors, custom connectors",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Data Transformation",
                    "description": "Power Query, dataflows, ETL",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Data Governance",
                    "description": "DLP policies, data classification, compliance",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Master Data Management",
                    "description": "Centralized data repository, data quality",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                # AI & INTELLIGENT AUTOMATION
                {
                    "name": "AI Builder Models",
                    "description": "Pre-built AI models (forms, objects, text)",
                    "coverage_percentage": 87,
                    "maturity_level": "managed",
                },
                {
                    "name": "Custom AI Models",
                    "description": "Train custom ML models",
                    "coverage_percentage": 85,
                    "maturity_level": "developing",
                },
                {
                    "name": "Virtual Agents (Chatbots)",
                    "description": "Conversational AI, bot development",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Sentiment Analysis",
                    "description": "Text sentiment analysis",
                    "coverage_percentage": 86,
                    "maturity_level": "managed",
                },
                {
                    "name": "Form Recognition",
                    "description": "Extract data from forms/documents",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                # COLLABORATION & PRODUCTIVITY
                {
                    "name": "Teams Integration",
                    "description": "Embedded apps and bots in Microsoft Teams",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "SharePoint Integration",
                    "description": "Document management, lists integration",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Outlook Integration",
                    "description": "Email automation, calendar integration",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Excel Integration",
                    "description": "Excel data sources, export to Excel",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Data-to-Insight",
                    "stages": [
                        "Data Collection",
                        "Data Transformation",
                        "Data Modeling",
                        "Visualization",
                        "Sharing",
                        "Decision",
                    ],
                    "description": "Analytics workflow",
                },
                {
                    "name": "Idea-to-App",
                    "stages": ["Requirement", "Design", "Build", "Test", "Deploy", "Iterate"],
                    "description": "Low-code app development",
                },
                {
                    "name": "Manual-to-Automated",
                    "stages": [
                        "Process Identification",
                        "Workflow Design",
                        "Connector Configuration",
                        "Testing",
                        "Deployment",
                        "Monitoring",
                    ],
                    "description": "Workflow automation",
                },
                {
                    "name": "Question-to-Answer",
                    "stages": [
                        "User Query",
                        "Bot Understanding",
                        "Information Retrieval",
                        "Response Generation",
                        "User Confirmation",
                    ],
                    "description": "Chatbot interaction",
                },
                {
                    "name": "Chaos-to-Governed-Data",
                    "stages": [
                        "Data Discovery",
                        "Schema Definition",
                        "Data Ingestion",
                        "Quality Check",
                        "Governance Policy",
                        "Consumption",
                    ],
                    "description": "Data governance",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "Power BI Only Deployment",
                    "description": "Start with analytics, add automation later",
                    "timeline_months": 3,
                    "risk_level": "low",
                },
                {
                    "name": "Full Platform Deployment",
                    "description": "Deploy all components at once",
                    "timeline_months": 9,
                    "risk_level": "medium",
                },
                {
                    "name": "Center of Excellence Model",
                    "description": "Establish CoE with governance",
                    "timeline_months": 12,
                    "risk_level": "low",
                },
                {
                    "name": "Citizen Developer Enablement",
                    "description": "Train business users to build apps",
                    "timeline_months": 6,
                    "risk_level": "medium",
                },
                {
                    "name": "Microsoft 365 Integration First",
                    "description": "Leverage existing M365 investment",
                    "timeline_months": 4,
                    "risk_level": "low",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Manufacturing Analytics Service",
                    "description": "Real-time production dashboards and KPIs",
                    "service_type": "internal",
                    "sla_commitment": "Dashboard refresh < 5 seconds",
                },
                {
                    "name": "Quality Inspection App Service",
                    "description": "Mobile quality inspection application",
                    "service_type": "internal",
                    "sla_commitment": "99.9% app availability",
                },
                {
                    "name": "Production Reporting Automation",
                    "description": "Automated daily/weekly reporting",
                    "service_type": "internal",
                    "sla_commitment": "Reports delivered by 6 AM daily",
                },
                {
                    "name": "Maintenance Request Portal",
                    "description": "Employee self-service maintenance requests",
                    "service_type": "internal",
                    "sla_commitment": "Portal availability 99.9%",
                },
                {
                    "name": "Supply Chain Analytics",
                    "description": "Supplier performance and inventory analytics",
                    "service_type": "internal",
                    "sla_commitment": "Real-time data refresh",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Daily Production Dashboard Refresh",
                    "description": "Real-time OEE and production KPIs",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Data Extract from MES",
                        "Data Transformation",
                        "Power BI Dataset Refresh",
                        "Dashboard Update",
                        "Alert Generation",
                    ],
                    "cycle_time": "5 minutes",
                    "kpis": ["Data Freshness", "Dashboard Load Time", "User Adoption"],
                },
                {
                    "name": "Quality Inspection Process",
                    "description": "Mobile quality inspection workflow",
                    "automation_level": "highly-automated",
                    "steps": [
                        "App Opens Inspection Form",
                        "Operator Enters Data",
                        "Photo Capture",
                        "AI Analysis",
                        "Pass/Fail Decision",
                        "Sync to ERP",
                    ],
                    "cycle_time": "5 - 10 minutes",
                    "kpis": ["Inspection Completion Rate", "Defect Detection Rate", "Cycle Time"],
                },
                {
                    "name": "Approval Workflow Automation",
                    "description": "Purchase requisition approval",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Requisition Submitted",
                        "Manager Approval Routing",
                        "Teams Notification",
                        "Approval/Rejection",
                        "SAP Integration",
                        "Confirmation Email",
                    ],
                    "cycle_time": "< 4 hours",
                    "kpis": ["Approval Time", "Bottleneck Identification", "Approval Rate"],
                },
                {
                    "name": "Supplier Performance Reporting",
                    "description": "Weekly supplier scorecards",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Data Extract from SAP",
                        "Quality/Delivery Calculations",
                        "Report Generation",
                        "Email Distribution",
                        "SharePoint Archive",
                    ],
                    "cycle_time": "Weekly",
                    "kpis": ["Report Accuracy", "On-Time Delivery", "Email Open Rate"],
                },
                {
                    "name": "Equipment Maintenance Request",
                    "description": "Employee-initiated maintenance requests",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Employee Submits Request",
                        "Photo/Description Upload",
                        "Auto-Assignment to Maintenance",
                        "Maximo Work Order Creation",
                        "Status Updates",
                        "Closure Notification",
                    ],
                    "cycle_time": "< 30 minutes to assign",
                    "kpis": ["Request Volume", "Response Time", "User Satisfaction"],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Power BI Report",
                    "description": "Interactive analytics report",
                    "lifecycle": "designed -> published -> shared -> retired",
                },
                {
                    "name": "Power App",
                    "description": "Custom business application",
                    "lifecycle": "developed -> tested -> deployed -> maintained -> retired",
                },
                {
                    "name": "Power Automate Flow",
                    "description": "Automated workflow",
                    "lifecycle": "designed -> tested -> activated -> running -> deactivated",
                },
                {
                    "name": "Dataverse Table",
                    "description": "Data entity",
                    "lifecycle": "created -> populated -> consumed -> archived",
                },
                {
                    "name": "Virtual Agent",
                    "description": "Chatbot",
                    "lifecycle": "designed -> trained -> published -> retired",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Data Analyst",
                    "description": "Builds Power BI reports",
                    "responsibilities": [
                        "Report Development",
                        "Data Modeling",
                        "Dashboard Design",
                        "User Training",
                    ],
                },
                {
                    "name": "Citizen Developer",
                    "description": "Business user building apps",
                    "responsibilities": [
                        "App Development",
                        "Workflow Automation",
                        "Testing",
                        "Documentation",
                    ],
                },
                {
                    "name": "Manufacturing Engineer",
                    "description": "Consumes analytics and builds apps",
                    "responsibilities": [
                        "Data Analysis",
                        "Process Improvement",
                        "App Usage",
                        "Feedback",
                    ],
                },
                {
                    "name": "IT Administrator",
                    "description": "Manages Power Platform",
                    "responsibilities": [
                        "Environment Management",
                        "Security",
                        "Governance",
                        "Licensing",
                    ],
                },
                {
                    "name": "Business User",
                    "description": "Consumes reports and apps",
                    "responsibilities": [
                        "Dashboard Viewing",
                        "App Usage",
                        "Data Entry",
                        "Reporting Issues",
                    ],
                },
                {
                    "name": "Power Platform CoE",
                    "description": "Center of Excellence team",
                    "responsibilities": ["Governance", "Best Practices", "Training", "Innovation"],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "Power BI Pro",
                    "description": "Per-user analytics license",
                    "target_market": "All Manufacturing Users",
                },
                {
                    "name": "Power BI Premium",
                    "description": "Capacity-based analytics",
                    "target_market": "Large Manufacturers",
                },
                {
                    "name": "Power Apps per user",
                    "description": "Unlimited apps per user",
                    "target_market": "Manufacturing Companies",
                },
                {
                    "name": "Power Automate per user",
                    "description": "Unlimited flows per user",
                    "target_market": "All Manufacturing",
                },
                {
                    "name": "Dataverse for Teams",
                    "description": "Included with Teams",
                    "target_market": "Small to Mid-Size Manufacturing",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "Power BI Service",
                    "type": "web-app",
                    "description": "Cloud analytics platform",
                    "technology": "Azure/React",
                },
                {
                    "name": "Power BI Desktop",
                    "type": "desktop-app",
                    "description": "Report authoring tool",
                    "technology": ".NET/WPF",
                },
                {
                    "name": "Power BI Mobile",
                    "type": "mobile-app",
                    "description": "iOS/Android analytics app",
                    "technology": "Xamarin",
                },
                {
                    "name": "Power Apps Studio",
                    "type": "web-app",
                    "description": "App development tool",
                    "technology": "React",
                },
                {
                    "name": "Power Apps Runtime",
                    "type": "mobile-app",
                    "description": "App player",
                    "technology": "React Native",
                },
                {
                    "name": "Power Automate Designer",
                    "type": "web-app",
                    "description": "Workflow designer",
                    "technology": "React",
                },
                {
                    "name": "Dataverse",
                    "type": "database",
                    "description": "Common data platform",
                    "technology": "Azure SQL",
                },
                {
                    "name": "AI Builder",
                    "type": "ai-service",
                    "description": "AI model builder",
                    "technology": "Azure AI",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "Power BI REST API",
                    "type": "REST",
                    "description": "Programmatic access to Power BI",
                    "endpoints": ["/v1.0/myorg/datasets", "/v1.0/myorg/reports"],
                },
                {
                    "name": "Dataverse Web API",
                    "type": "REST",
                    "description": "CRUD operations on Dataverse",
                    "endpoints": ["/api/data/v9.2/{entity}"],
                },
                {
                    "name": "Power Automate API",
                    "type": "REST",
                    "description": "Manage flows programmatically",
                    "endpoints": ["/providers/Microsoft.ProcessSimple/environments/{env}/flows"],
                },
                {
                    "name": "Power Apps API",
                    "type": "REST",
                    "description": "Manage apps programmatically",
                    "endpoints": ["/providers/Microsoft.PowerApps/apps"],
                },
                {
                    "name": "Connector API",
                    "type": "REST",
                    "description": "Custom connector API",
                    "endpoints": ["/providers/Microsoft.PowerApps/apis"],
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
                    "name": "OData",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON/XML",
                    "authentication": "OAuth 2.0",
                },
                {
                    "name": "Custom Connector",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "Various",
                },
                {
                    "name": "On-Premises Data Gateway",
                    "protocol": "HTTPS",
                    "data_format": "Proprietary",
                    "authentication": "Azure AD",
                },
                {
                    "name": "Dataverse TDS Endpoint",
                    "protocol": "TDS",
                    "data_format": "Tabular",
                    "authentication": "Azure AD",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {
                    "name": "Power BI Dataset",
                    "type": "analytical",
                    "retention_policy": "Based on refresh schedule",
                },
                {
                    "name": "Dataverse Table",
                    "type": "master/transactional",
                    "retention_policy": "Configurable per table",
                },
                {"name": "Flow Run History", "type": "log", "retention_policy": "28 days default"},
                {"name": "App Usage Telemetry", "type": "telemetry", "retention_policy": "90 days"},
                {
                    "name": "AI Model Training Data",
                    "type": "training-data",
                    "retention_policy": "Permanent",
                },
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "Data Refresh",
                    "type": "batch-process",
                    "description": "Scheduled dataset refresh",
                },
                {
                    "name": "Report Rendering",
                    "type": "visualization",
                    "description": "Interactive report rendering",
                },
                {
                    "name": "Form Submission",
                    "type": "CRUD",
                    "description": "Power Apps form data submission",
                },
                {
                    "name": "Flow Execution",
                    "type": "workflow",
                    "description": "Automated workflow execution",
                },
                {
                    "name": "AI Model Inference",
                    "type": "ai-inference",
                    "description": "AI Builder model prediction",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "Chief Data Officer",
                    "role": "executive",
                    "concerns": ["Data Strategy", "Analytics Adoption", "Data Governance"],
                    "influence": "high",
                },
                {
                    "name": "VP of Manufacturing",
                    "role": "executive",
                    "concerns": [
                        "Production Visibility",
                        "Process Efficiency",
                        "Digital Transformation",
                    ],
                    "influence": "high",
                },
                {
                    "name": "IT Director",
                    "role": "senior-management",
                    "concerns": ["Platform Governance", "Security", "Cost Management"],
                    "influence": "high",
                },
                {
                    "name": "Business Analysts",
                    "role": "technical-expert",
                    "concerns": ["Report Quality", "Data Access", "User Enablement"],
                    "influence": "medium",
                },
                {
                    "name": "Manufacturing Engineers",
                    "role": "business-user",
                    "concerns": ["Easy-to-Use Tools", "Real-Time Data", "Mobile Access"],
                    "influence": "medium",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Data-Driven Decision Making",
                    "description": "Empower decisions with real-time data",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Digital Transformation",
                    "description": "Modernize with low-code solutions",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Operational Efficiency",
                    "description": "Automate manual processes",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Self-Service Enablement",
                    "description": "Empower business users to build solutions",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Cost Reduction",
                    "description": "Reduce custom development costs",
                    "urgency": "medium",
                    "impact": "high",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "100% Real-Time Production Visibility",
                    "description": "Real-time dashboards for all plants",
                    "timeframe": "12 months",
                    "measurable": "All plants on Power BI",
                },
                {
                    "name": "50 Low-Code Apps Deployed",
                    "description": "Citizen developer program success",
                    "timeframe": "18 months",
                    "measurable": "50 production apps",
                },
                {
                    "name": "Automate 100 Manual Processes",
                    "description": "Workflow automation initiative",
                    "timeframe": "24 months",
                    "measurable": "100 flows in production",
                },
                {
                    "name": "80% User Adoption",
                    "description": "Power Platform adoption rate",
                    "timeframe": "12 months",
                    "measurable": "80% monthly active users",
                },
                {
                    "name": "Reduce Report Development Time by 60%",
                    "description": "Faster analytics delivery",
                    "timeframe": "6 months",
                    "measurable": "Report development cycle time",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "Improved Decision Speed",
                    "description": "Faster access to insights",
                    "benefit_type": "operational",
                    "quantified_benefit": "50% faster decision making",
                },
                {
                    "name": "Development Cost Savings",
                    "description": "Reduced custom development",
                    "benefit_type": "financial",
                    "quantified_benefit": "$2M annual savings",
                },
                {
                    "name": "Process Efficiency Gains",
                    "description": "Automated workflows",
                    "benefit_type": "operational",
                    "quantified_benefit": "10,000 hours saved annually",
                },
                {
                    "name": "Increased Innovation",
                    "description": "Citizen developer empowerment",
                    "benefit_type": "strategic",
                    "quantified_benefit": "50 business-led innovations",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Data Democracy",
                    "description": "Make data accessible to all",
                    "rationale": "Empower decision making",
                },
                {
                    "name": "Low-Code First",
                    "description": "Prefer low-code over custom development",
                    "rationale": "Speed and agility",
                },
                {
                    "name": "Governed Innovation",
                    "description": "Enable innovation with guardrails",
                    "rationale": "Balance speed with control",
                },
                {
                    "name": "Microsoft Ecosystem",
                    "description": "Leverage Microsoft 365 integration",
                    "rationale": "Maximize existing investment",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "Dashboard Performance",
                    "type": "performance",
                    "description": "Dashboard load < 3 seconds",
                    "priority": "high",
                },
                {
                    "name": "Mobile Offline Capability",
                    "type": "functional",
                    "description": "Apps work without connectivity",
                    "priority": "high",
                },
                {
                    "name": "Data Governance",
                    "type": "governance",
                    "description": "DLP policies enforced",
                    "priority": "critical",
                },
                {
                    "name": "SSO Integration",
                    "type": "security",
                    "description": "Azure AD single sign-on",
                    "priority": "critical",
                },
                {
                    "name": "On-Premises Connectivity",
                    "type": "functional",
                    "description": "Connect to on-prem SAP/MES",
                    "priority": "critical",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget",
                    "type": "financial",
                    "description": "Power Platform budget capped at $500K annually",
                },
                {
                    "name": "Timeline",
                    "type": "schedule",
                    "description": "Must deploy within 6 months",
                },
                {
                    "name": "Skill Gap",
                    "type": "organizational",
                    "description": "Limited Power Platform expertise",
                },
                {
                    "name": "Data Quality",
                    "type": "data",
                    "description": "Source data quality issues",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "Current State Assessment",
                    "type": "maturity",
                    "description": "Assess current analytics maturity",
                    "result": "Score: 2/5 - Spreadsheet-driven analytics",
                },
                {
                    "name": "Use Case Prioritization",
                    "type": "business",
                    "description": "Identify high-value use cases",
                    "result": "Top 20 use cases identified",
                },
                {
                    "name": "Data Readiness",
                    "type": "technical",
                    "description": "Assess data source readiness",
                    "result": "ERP data ready, MES requires work",
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
                    "description": "Power Platform project initiated",
                },
                {
                    "name": "CoE Established",
                    "date": "2024 - 02 - 15",
                    "milestone": True,
                    "description": "Center of Excellence team formed",
                },
                {
                    "name": "First Dashboard Published",
                    "date": "2024 - 03 - 01",
                    "milestone": True,
                    "description": "Production dashboard live",
                },
                {
                    "name": "Pilot Apps Deployed",
                    "date": "2024 - 05 - 01",
                    "milestone": True,
                    "description": "5 pilot apps in production",
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
                    "name": "Environment Setup",
                    "description": "Configure Power Platform environments",
                    "duration_weeks": 4,
                    "team_size": 2,
                },
                {
                    "name": "Data Gateway Installation",
                    "description": "Install on-premises data gateways",
                    "duration_weeks": 4,
                    "team_size": 2,
                },
                {
                    "name": "Dashboard Development",
                    "description": "Build 20 production dashboards",
                    "duration_weeks": 12,
                    "team_size": 4,
                },
                {
                    "name": "App Development",
                    "description": "Build 10 pilot apps",
                    "duration_weeks": 16,
                    "team_size": 5,
                },
                {
                    "name": "User Training",
                    "description": "Train 500 users",
                    "duration_weeks": 8,
                    "team_size": 3,
                },
                {
                    "name": "Governance Framework",
                    "description": "Establish governance policies",
                    "duration_weeks": 6,
                    "team_size": 2,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Solution Architecture",
                    "type": "document",
                    "due_phase": "design",
                    "owner": "Solution Architect",
                },
                {
                    "name": "Data Model",
                    "type": "document",
                    "due_phase": "design",
                    "owner": "Data Architect",
                },
                {
                    "name": "Production Dashboards",
                    "type": "report",
                    "due_phase": "build",
                    "owner": "Data Analyst",
                },
                {
                    "name": "Pilot Applications",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "Citizen Developer",
                },
                {
                    "name": "Training Materials",
                    "type": "training",
                    "due_phase": "build",
                    "owner": "Training Lead",
                },
                {
                    "name": "Governance Playbook",
                    "type": "document",
                    "due_phase": "design",
                    "owner": "Power Platform CoE",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "Infrastructure Ready",
                    "date": "2024 - 02 - 28",
                    "description": "Environments and gateways configured",
                },
                {
                    "name": "First Wave Success",
                    "date": "2024 - 05 - 01",
                    "description": "20 dashboards and 10 apps live",
                },
                {
                    "name": "Production Launch",
                    "date": "2024 - 07 - 01",
                    "description": "Enterprise-wide availability",
                },
                {
                    "name": "Citizen Developer Program",
                    "date": "2024 - 10 - 01",
                    "description": "50 trained citizen developers",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "Azure Data Center (US)",
                    "location": "East US",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "Power Platform cloud services",
                },
                {
                    "name": "Azure Data Center (EU)",
                    "location": "West Europe",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "EU data residency",
                },
                {
                    "name": "Corporate Data Center",
                    "location": "Manufacturing HQ",
                    "tier": "Tier III",
                    "size_sqm": 200,
                    "description": "On-premises data gateway",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "Data Gateway Server",
                    "type": "server",
                    "quantity": 2,
                    "location": "Corporate Data Center",
                    "specs": "Dell R440, 8 - core, 16GB RAM",
                },
                {
                    "name": "Power BI Desktop Licenses",
                    "type": "software-license",
                    "quantity": 100,
                    "location": "User Workstations",
                    "specs": "Windows 10/11",
                },
                {
                    "name": "Tablets for Shop Floor",
                    "type": "tablet",
                    "quantity": 50,
                    "location": "Manufacturing Floor",
                    "specs": "Surface Pro with LTE",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "Azure Global Network",
                    "type": "cloud-network",
                    "coverage": "Global",
                    "bandwidth_mbps": 100000,
                    "provider": "Microsoft Azure",
                },
                {
                    "name": "Corporate WAN",
                    "type": "wan",
                    "coverage": "20 Manufacturing Sites",
                    "bandwidth_mbps": 1000,
                    "provider": "AT&T",
                },
                {
                    "name": "ExpressRoute",
                    "type": "dedicated-link",
                    "coverage": "HQ to Azure",
                    "bandwidth_mbps": 10000,
                    "provider": "Microsoft",
                },
            ]
        ),
    )


def seed_microsoft_power(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(
                vendor_name="Microsoft Power Platform"
            ).first()
            if existing:
                print("⚠️  Microsoft Power Platform template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_microsoft_power_template()
            db.session.add(template)
            db.session.commit()

            print("✅ Microsoft Power Platform template seeded successfully!")
            print(f"   - Vendor: {template.vendor_name}")
            print(f"   - Data & Analytics Capabilities: 32")
            print(
                f"   - Primary Focus: Power BI, Power Apps, Power Automate, Dataverse, AI Builder"
            )
            print(f"   - Total ArchiMate Coverage: 100%")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding Microsoft Power Platform template: {str(e)}")
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    seed_microsoft_power()
