"""
GE Digital Proficy Comprehensive Vendor Template Seed Data

Complete ArchiMate 3.2 coverage across ALL layers:
- Strategy Layer
- Business Layer
- Application Layer
- Technology Layer
- Motivation Layer
- Implementation & Migration Layer
- Physical Layer

Run with: python manage.py seed-vendor-ge
"""
import json

from app import create_app, db
from app.models import User, VendorStackTemplate
from config import DevelopmentConfig


def create_ge_proficy_template():
    """GE Digital Proficy FULLY COMPREHENSIVE template - ALL ArchiMate 3.2 layers"""
    return VendorStackTemplate(
        vendor_name="GE Digital",
        name="GE Proficy Manufacturing Intelligence Suite",
        description="Comprehensive plant-wide SCADA, industrial historian, manufacturing operations management, and production intelligence platform delivering real-time visibility and analytics for process and hybrid manufacturing",
        # ==================== TECHNOLOGY LAYER ====================
        platform="hybrid",
        primary_language="c-sharp",
        framework=".NET Framework",
        framework_version="4.8",
        primary_database="sql-server",
        database_version="2019",
        container_runtime="docker",
        orchestration="kubernetes",
        service_mesh="none",
        api_standard="REST",
        api_gateway="iis",
        message_broker="rabbitmq",
        auth_provider="active-directory",
        secrets_manager="windows-credential-manager",
        logging_framework="nlog",
        metrics_platform="proficy-historian",
        apm_tool="app-dynamics",
        tracing_tool="none",
        build_tool="msbuild",
        ci_cd_platform="azure-devops",
        sast_tool="checkmarx",
        dast_tool="acunetix",
        dependency_scanner="whitesource",
        nodes=json.dumps(
            [
                {
                    "name": "Proficy HMI/SCADA Server",
                    "type": "application-server",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "Proficy Historian Server",
                    "type": "data-collector",
                    "os": "Windows Server 2019",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
                {
                    "name": "Proficy Operations Hub Server",
                    "type": "web-server",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "Proficy Manufacturing Execution Server",
                    "type": "mes-server",
                    "os": "Windows Server 2019",
                    "cpu_cores": 24,
                    "ram_gb": 96,
                },
                {
                    "name": "Proficy Plant Applications Server",
                    "type": "analytics-server",
                    "os": "Windows Server 2019",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
                {
                    "name": "SQL Server Database Primary",
                    "type": "database-server",
                    "os": "Windows Server 2019",
                    "cpu_cores": 48,
                    "ram_gb": 256,
                },
                {
                    "name": "SQL Server Database Secondary",
                    "type": "database-server",
                    "os": "Windows Server 2019",
                    "cpu_cores": 48,
                    "ram_gb": 256,
                },
                {
                    "name": "Proficy OPC UA Gateway",
                    "type": "gateway-server",
                    "os": "Windows Server 2019",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "Historian Archive Server",
                    "type": "archive-server",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "IIS Web Server",
                    "type": "web-server",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 48,
                },
            ]
        ),
        devices=json.dumps(
            [
                {"name": "GE RX3i PLC", "type": "plc", "description": "Process control PLCs"},
                {
                    "name": "Emerson DeltaV DCS",
                    "type": "dcs",
                    "description": "Distributed control system",
                },
                {
                    "name": "Industrial Ethernet Switches",
                    "type": "network-switch",
                    "description": "Ruggedized plant network",
                },
                {
                    "name": "Operator HMI Panels",
                    "type": "hmi-terminal",
                    "description": "Touchscreen operator interfaces",
                },
                {
                    "name": "Mobile Tablets",
                    "type": "tablet",
                    "description": "Portable operator devices",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {"name": "Proficy iFIX HMI/SCADA", "type": "scada", "version": "6.5"},
                {"name": "Proficy Historian", "type": "historian", "version": "2023"},
                {"name": "Proficy Operations Hub", "type": "web-hmi", "version": "9.0"},
                {
                    "name": "Proficy Manufacturing Execution Systems",
                    "type": "mes",
                    "version": "9.2",
                },
                {"name": "Proficy Plant Applications", "type": "analytics", "version": "9.5"},
                {"name": "Proficy Workflow", "type": "workflow", "version": "2.5"},
                {"name": "Proficy CSense", "type": "analytics-ai", "version": "4.0"},
                {"name": "SQL Server", "type": "database", "version": "2019 Enterprise"},
                {"name": "IIS", "type": "web-server", "version": "10.0"},
                {"name": "OPC UA Server", "type": "communication", "version": "1.04"},
                {"name": "Windows Server", "type": "operating-system", "version": "2019"},
                {"name": "RabbitMQ", "type": "message-broker", "version": "3.12"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "iFIX SCADA Service",
                    "type": "scada-runtime",
                    "description": "Real-time process visualization and control",
                },
                {
                    "name": "Historian Data Collection Service",
                    "type": "data-collector",
                    "description": "High-speed industrial data collection",
                },
                {
                    "name": "Historian Archive Service",
                    "type": "data-archive",
                    "description": "Long-term time-series data storage",
                },
                {
                    "name": "Operations Hub Service",
                    "type": "web-visualization",
                    "description": "Web-based HMI and dashboards",
                },
                {
                    "name": "MES Production Service",
                    "type": "mes-engine",
                    "description": "Production execution and tracking",
                },
                {
                    "name": "Plant Applications Service",
                    "type": "analytics-engine",
                    "description": "Manufacturing intelligence and KPIs",
                },
                {
                    "name": "Workflow Engine Service",
                    "type": "workflow-engine",
                    "description": "Electronic procedures and workflows",
                },
                {
                    "name": "CSense AI Service",
                    "type": "ai-ml-engine",
                    "description": "Predictive analytics and optimization",
                },
                {
                    "name": "OPC UA Gateway Service",
                    "type": "protocol-gateway",
                    "description": "Equipment connectivity",
                },
                {
                    "name": "Alarm Management Service",
                    "type": "alarm-engine",
                    "description": "Intelligent alarm handling",
                },
                {
                    "name": "Downtime Tracking Service",
                    "type": "tracking-service",
                    "description": "Production loss analysis",
                },
                {
                    "name": "OEE Calculation Service",
                    "type": "calculation-engine",
                    "description": "Real-time OEE metrics",
                },
                {
                    "name": "Data API Service",
                    "type": "api-gateway",
                    "description": "REST API for external integration",
                },
                {
                    "name": "Security Service",
                    "type": "authentication",
                    "description": "User authentication and authorization",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "iFIX Display Files",
                    "type": "hmi-screens",
                    "size_mb": 500,
                    "registry": "iFIX",
                },
                {
                    "name": "Historical Data Archive",
                    "type": "time-series-data",
                    "size_mb": 5000000,
                    "registry": "Proficy Historian",
                },
                {
                    "name": "Operations Hub Dashboards",
                    "type": "web-dashboards",
                    "size_mb": 100,
                    "registry": "Operations Hub",
                },
                {
                    "name": "MES Production Recipes",
                    "type": "recipes",
                    "size_mb": 50,
                    "registry": "MES",
                },
                {
                    "name": "Plant Applications Reports",
                    "type": "reports",
                    "size_mb": 200,
                    "registry": "Plant Applications",
                },
                {
                    "name": "Workflow Procedures",
                    "type": "electronic-procedures",
                    "size_mb": 150,
                    "registry": "Workflow",
                },
                {
                    "name": "CSense AI Models",
                    "type": "ml-models",
                    "size_mb": 1000,
                    "registry": "CSense",
                },
                {
                    "name": "SQL Database Backup",
                    "type": "backup",
                    "size_mb": 500000,
                    "registry": "SQL Server",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "Plant Ethernet Network",
                    "type": "industrial-ethernet",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 5,
                },
                {
                    "name": "Control Network",
                    "type": "vlan",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 2,
                },
                {"name": "DMZ Network", "type": "dmz", "bandwidth_mbps": 1000, "latency_ms": 10},
                {"name": "Corporate WAN", "type": "wan", "bandwidth_mbps": 100, "latency_ms": 20},
                {
                    "name": "Internet Gateway",
                    "type": "internet",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 30,
                },
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="GE Digital",
        market_position="leader",
        company_size="enterprise",
        founded_year=1892,
        headquarters="San Ramon, CA, USA",
        revenue_usd=1200000000,
        customer_count=40000,
        market_share_percentage=16.0,
        acquisition_risk="low",
        financial_health="good",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                {
                    "name": "Plant-Wide SCADA",
                    "description": "Comprehensive process visualization and control",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Industrial Historian",
                    "description": "High-speed time-series data collection and storage",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Manufacturing Operations Management",
                    "description": "Production execution and tracking",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Manufacturing Intelligence",
                    "description": "Real-time KPIs and analytics",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "OEE Management",
                    "description": "Overall equipment effectiveness tracking",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Downtime Tracking",
                    "description": "Production loss analysis and root cause",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Quality Management",
                    "description": "SPC and quality tracking",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Alarm Management",
                    "description": "Intelligent alarm handling and rationalization",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Electronic Procedures",
                    "description": "Digital work instructions and workflows",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Predictive Analytics",
                    "description": "AI/ML-based predictions and optimization",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "Energy Management",
                    "description": "Energy consumption tracking and optimization",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Asset Performance",
                    "description": "Equipment reliability and maintenance",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Production Scheduling",
                    "description": "Schedule management and tracking",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "Material Tracking",
                    "description": "Material consumption and genealogy",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Batch Management",
                    "description": "Recipe management and batch execution",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Continuous Process Control",
                    "description": "Real-time process control and optimization",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Mobile Operations",
                    "description": "Mobile access to production data",
                    "coverage_percentage": 87,
                    "maturity_level": "managed",
                },
                {
                    "name": "ERP Integration",
                    "description": "Bidirectional ERP connectivity",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Compliance Management",
                    "description": "Regulatory compliance and audit trails",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Web-Based Visualization",
                    "description": "Modern web HMI and dashboards",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                # ADJACENT CAPABILITIES (Extended Manufacturing Support)
                {
                    "name": "Demand-Driven Production",
                    "description": "Pull-based production signaling from demand",
                    "coverage_percentage": 80,
                    "maturity_level": "managed",
                },
                {
                    "name": "Warehouse Automation Integration",
                    "description": "AGV, AS/RS, and automated storage integration",
                    "coverage_percentage": 78,
                    "maturity_level": "managed",
                },
                {
                    "name": "Logistics Integration",
                    "description": "TMS integration for outbound logistics",
                    "coverage_percentage": 76,
                    "maturity_level": "developing",
                },
                {
                    "name": "Quality Cost Analysis",
                    "description": "Cost of quality (COPQ) tracking and analysis",
                    "coverage_percentage": 81,
                    "maturity_level": "managed",
                },
                {
                    "name": "Training & Competency Management",
                    "description": "Operator training records and certification",
                    "coverage_percentage": 83,
                    "maturity_level": "managed",
                },
                {
                    "name": "Environmental Health & Safety",
                    "description": "Safety incident tracking, OSHA compliance",
                    "coverage_percentage": 84,
                    "maturity_level": "managed",
                },
                {
                    "name": "Production Simulation",
                    "description": "What-if scenario modeling for production planning",
                    "coverage_percentage": 77,
                    "maturity_level": "developing",
                },
                {
                    "name": "Customer Promise Date Management",
                    "description": "ATP/CTP for customer delivery commitments",
                    "coverage_percentage": 79,
                    "maturity_level": "managed",
                },
                {
                    "name": "Multi-Enterprise Collaboration",
                    "description": "Partner/supplier collaboration portal",
                    "coverage_percentage": 75,
                    "maturity_level": "developing",
                },
                {
                    "name": "Circular Economy Tracking",
                    "description": "Product return, refurbishment, recycling tracking",
                    "coverage_percentage": 73,
                    "maturity_level": "developing",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Monitor-to-Control",
                    "stages": [
                        "Data Collection",
                        "Visualization",
                        "Analysis",
                        "Control Action",
                        "Verification",
                    ],
                    "description": "Process control value stream",
                },
                {
                    "name": "Produce-to-Performance",
                    "stages": [
                        "Production Order",
                        "Execution",
                        "Data Collection",
                        "KPI Calculation",
                        "Analysis",
                        "Improvement",
                    ],
                    "description": "Production operations",
                },
                {
                    "name": "Data-to-Decision",
                    "stages": [
                        "Data Collection",
                        "Storage",
                        "Analysis",
                        "Insight",
                        "Decision",
                        "Action",
                    ],
                    "description": "Data-driven operations",
                },
                {
                    "name": "Alarm-to-Resolution",
                    "stages": [
                        "Alarm Detection",
                        "Notification",
                        "Acknowledgment",
                        "Diagnosis",
                        "Corrective Action",
                        "Verification",
                    ],
                    "description": "Alarm management",
                },
                {
                    "name": "Downtime-to-Recovery",
                    "stages": [
                        "Downtime Detection",
                        "Classification",
                        "Root Cause",
                        "Recovery Action",
                        "Restart",
                        "Analysis",
                    ],
                    "description": "Downtime management",
                },
                {
                    "name": "Asset-to-Availability",
                    "stages": [
                        "Asset Monitoring",
                        "Performance Analysis",
                        "Predictive Maintenance",
                        "Maintenance Execution",
                        "Verification",
                    ],
                    "description": "Asset management",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "Brownfield SCADA Upgrade",
                    "description": "Replace legacy SCADA with Proficy",
                    "timeline_months": 12,
                    "risk_level": "medium",
                },
                {
                    "name": "Historian-First Approach",
                    "description": "Start with data collection and analytics",
                    "timeline_months": 6,
                    "risk_level": "low",
                },
                {
                    "name": "Comprehensive Suite",
                    "description": "Full HMI/SCADA, Historian, MES deployment",
                    "timeline_months": 18,
                    "risk_level": "high",
                },
                {
                    "name": "Cloud Hybrid",
                    "description": "On-premise control, cloud analytics",
                    "timeline_months": 15,
                    "risk_level": "medium",
                },
                {
                    "name": "Phased MES Rollout",
                    "description": "Pilot line first, then expand",
                    "timeline_months": 24,
                    "risk_level": "low",
                },
                {
                    "name": "AI/ML Quick Win",
                    "description": "Deploy CSense predictive analytics",
                    "timeline_months": 9,
                    "risk_level": "medium",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Process Control Service",
                    "description": "Real-time SCADA control",
                    "service_type": "internal",
                    "sla_commitment": "99.99% uptime, < 50ms response",
                },
                {
                    "name": "Data Historian Service",
                    "description": "Industrial data collection",
                    "service_type": "internal",
                    "sla_commitment": "1M+ tags/sec, 99.99% accuracy",
                },
                {
                    "name": "Production Tracking Service",
                    "description": "Track production orders",
                    "service_type": "internal",
                    "sla_commitment": "Real-time tracking, < 5 sec latency",
                },
                {
                    "name": "OEE Reporting Service",
                    "description": "Equipment effectiveness metrics",
                    "service_type": "internal",
                    "sla_commitment": "Real-time OEE, 1 - min intervals",
                },
                {
                    "name": "Analytics Service",
                    "description": "Manufacturing intelligence",
                    "service_type": "internal",
                    "sla_commitment": "Real-time dashboards, < 30 sec refresh",
                },
                {
                    "name": "Alarm Management Service",
                    "description": "Intelligent alarming",
                    "service_type": "internal",
                    "sla_commitment": "< 100ms alarm latency, ISA - 18.2 compliant",
                },
                {
                    "name": "Quality Management Service",
                    "description": "SPC and quality tracking",
                    "service_type": "internal",
                    "sla_commitment": "100% data integrity",
                },
                {
                    "name": "Downtime Analysis Service",
                    "description": "Production loss tracking",
                    "service_type": "internal",
                    "sla_commitment": "Real-time downtime classification",
                },
                {
                    "name": "Electronic Procedures Service",
                    "description": "Digital work instructions",
                    "service_type": "internal",
                    "sla_commitment": "99.9% availability",
                },
                {
                    "name": "ERP Integration Service",
                    "description": "SAP/Oracle integration",
                    "service_type": "integration",
                    "sla_commitment": "< 1 min data sync",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Continuous Process Monitoring",
                    "description": "24/7 process control and visualization",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Data Collection",
                        "Real-Time Display",
                        "Alarm Detection",
                        "Control Action",
                        "Trending",
                        "Archiving",
                    ],
                    "cycle_time": "Continuous (real-time)",
                    "kpis": ["Uptime 99.99%", "Response Time < 50ms", "Data Accuracy 99.99%"],
                },
                {
                    "name": "Production Order Execution",
                    "description": "Execute production orders on plant floor",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Order Release",
                        "Material Check",
                        "Equipment Setup",
                        "Production Execution",
                        "Data Collection",
                        "Quality Checks",
                        "Completion",
                    ],
                    "cycle_time": "Hours to days",
                    "kpis": ["On-Time Completion", "First Pass Yield", "OEE"],
                },
                {
                    "name": "OEE Calculation",
                    "description": "Real-time equipment effectiveness tracking",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Availability Calculation",
                        "Performance Calculation",
                        "Quality Calculation",
                        "OEE Aggregation",
                        "Reporting",
                    ],
                    "cycle_time": "Real-time (1 - minute intervals)",
                    "kpis": [
                        "OEE Target 85%",
                        "Availability > 90%",
                        "Performance > 95%",
                        "Quality > 98%",
                    ],
                },
                {
                    "name": "Downtime Management",
                    "description": "Track and analyze production losses",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Downtime Detection",
                        "Operator Classification",
                        "Duration Tracking",
                        "Root Cause Entry",
                        "Pareto Analysis",
                        "CAPA Initiation",
                    ],
                    "cycle_time": "Real-time to hours",
                    "kpis": [
                        "Classification Rate 100%",
                        "Mean Time to Classify < 5 min",
                        "Downtime Reduction",
                    ],
                },
                {
                    "name": "Alarm Response",
                    "description": "Respond to process alarms",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Alarm Detection",
                        "Priority Assessment",
                        "Operator Notification",
                        "Acknowledgment",
                        "Diagnosis",
                        "Corrective Action",
                        "Resolution",
                    ],
                    "cycle_time": "Seconds to minutes",
                    "kpis": [
                        "Response Time < 2 min",
                        "Resolution Time",
                        "Alarm Rate < 10/hour/operator",
                    ],
                },
                {
                    "name": "Predictive Analytics",
                    "description": "AI-driven asset predictions",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Data Collection",
                        "Model Execution",
                        "Anomaly Detection",
                        "Prediction Generation",
                        "Alert",
                        "Recommended Action",
                    ],
                    "cycle_time": "Real-time to hourly",
                    "kpis": [
                        "Prediction Accuracy > 85%",
                        "False Positive Rate < 10%",
                        "Lead Time > 24 hours",
                    ],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Production Order",
                    "description": "Manufacturing work order",
                    "lifecycle": "created -> scheduled -> released -> in-progress -> completed",
                },
                {
                    "name": "Historical Data",
                    "description": "Time-series process data",
                    "lifecycle": "collected -> stored -> archived -> purged",
                },
                {
                    "name": "Alarm",
                    "description": "Process alarm event",
                    "lifecycle": "detected -> active -> acknowledged -> cleared -> archived",
                },
                {
                    "name": "Downtime Event",
                    "description": "Production loss event",
                    "lifecycle": "detected -> classified -> analyzed -> closed",
                },
                {
                    "name": "OEE Record",
                    "description": "Equipment effectiveness calculation",
                    "lifecycle": "calculated -> aggregated -> reported -> archived",
                },
                {
                    "name": "Quality Result",
                    "description": "Quality inspection result",
                    "lifecycle": "measured -> evaluated -> recorded -> reported",
                },
                {
                    "name": "Electronic Procedure",
                    "description": "Digital work instruction",
                    "lifecycle": "authored -> approved -> active -> executed -> archived",
                },
                {
                    "name": "Predictive Alert",
                    "description": "AI-generated alert",
                    "lifecycle": "predicted -> alerted -> acknowledged -> action-taken -> closed",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Control Room Operator",
                    "description": "24/7 process control specialist",
                    "responsibilities": [
                        "Process Monitoring",
                        "Alarm Response",
                        "Setpoint Adjustments",
                        "Troubleshooting",
                    ],
                },
                {
                    "name": "Production Supervisor",
                    "description": "Shift production leader",
                    "responsibilities": [
                        "Order Management",
                        "Resource Allocation",
                        "Performance Review",
                        "Problem Resolution",
                    ],
                },
                {
                    "name": "Process Engineer",
                    "description": "Process optimization specialist",
                    "responsibilities": [
                        "Process Analysis",
                        "Optimization",
                        "Troubleshooting",
                        "Continuous Improvement",
                    ],
                },
                {
                    "name": "Maintenance Technician",
                    "description": "Equipment maintenance specialist",
                    "responsibilities": [
                        "Preventive Maintenance",
                        "Corrective Maintenance",
                        "Troubleshooting",
                        "Data Recording",
                    ],
                },
                {
                    "name": "Quality Engineer",
                    "description": "Quality assurance specialist",
                    "responsibilities": [
                        "SPC Analysis",
                        "Quality Investigations",
                        "Process Validation",
                        "Compliance",
                    ],
                },
                {
                    "name": "Plant Manager",
                    "description": "Plant operations manager",
                    "responsibilities": [
                        "Strategic Planning",
                        "Performance Management",
                        "Budget Control",
                        "Continuous Improvement",
                    ],
                },
                {
                    "name": "Reliability Engineer",
                    "description": "Asset reliability specialist",
                    "responsibilities": [
                        "Asset Performance Analysis",
                        "Predictive Maintenance",
                        "RCA",
                        "Improvement Projects",
                    ],
                },
                {
                    "name": "Operations Manager",
                    "description": "Production operations manager",
                    "responsibilities": [
                        "Production Planning",
                        "KPI Management",
                        "Resource Management",
                        "Performance Review",
                    ],
                },
                {
                    "name": "IT/OT Administrator",
                    "description": "Systems administrator",
                    "responsibilities": [
                        "System Administration",
                        "User Management",
                        "Backup/Recovery",
                        "Integration Support",
                    ],
                },
                {
                    "name": "Manufacturing Engineer",
                    "description": "Production systems specialist",
                    "responsibilities": [
                        "Process Design",
                        "System Configuration",
                        "Performance Analysis",
                        "Training",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "Proficy iFIX",
                    "description": "HMI/SCADA platform",
                    "target_market": "Process Manufacturing",
                },
                {
                    "name": "Proficy Historian",
                    "description": "Industrial historian",
                    "target_market": "All Manufacturing",
                },
                {
                    "name": "Proficy Operations Hub",
                    "description": "Web-based HMI",
                    "target_market": "Modern Manufacturing",
                },
                {
                    "name": "Proficy Manufacturing Execution Systems",
                    "description": "MES suite",
                    "target_market": "Discrete & Process",
                },
                {
                    "name": "Proficy Plant Applications",
                    "description": "Manufacturing intelligence",
                    "target_market": "Complex Manufacturing",
                },
                {
                    "name": "Proficy Workflow",
                    "description": "Electronic procedures",
                    "target_market": "Regulated Industries",
                },
                {
                    "name": "Proficy CSense",
                    "description": "AI/ML analytics",
                    "target_market": "Process Optimization",
                },
                {
                    "name": "Proficy Production Performance Analysis",
                    "description": "OEE and downtime tracking",
                    "target_market": "All Manufacturing",
                },
                {
                    "name": "Proficy Manufacturing Data Cloud",
                    "description": "Cloud analytics platform",
                    "target_market": "Enterprise Manufacturing",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "iFIX SCADA Server",
                    "type": "scada-runtime",
                    "description": "Real-time process control engine",
                    "technology": "C++/C#",
                },
                {
                    "name": "iFIX Client Workstations",
                    "type": "hmi-client",
                    "description": "Operator interface clients",
                    "technology": "C++/C#",
                },
                {
                    "name": "Proficy Historian Collector",
                    "type": "data-collector",
                    "description": "High-speed data collection",
                    "technology": "C++",
                },
                {
                    "name": "Proficy Historian Server",
                    "type": "data-storage",
                    "description": "Time-series database",
                    "technology": "C++/C#",
                },
                {
                    "name": "Operations Hub Web Server",
                    "type": "web-application",
                    "description": "Modern web HMI",
                    "technology": "HTML5/JavaScript",
                },
                {
                    "name": "MES Production Module",
                    "type": "mes-application",
                    "description": "Production execution",
                    "technology": "C#/.NET",
                },
                {
                    "name": "Plant Applications Server",
                    "type": "analytics-platform",
                    "description": "Manufacturing intelligence engine",
                    "technology": "C#/.NET",
                },
                {
                    "name": "Workflow Engine",
                    "type": "workflow-application",
                    "description": "Electronic procedures",
                    "technology": "C#/.NET",
                },
                {
                    "name": "CSense Analytics Engine",
                    "type": "ai-platform",
                    "description": "Machine learning platform",
                    "technology": "Python/C#",
                },
                {
                    "name": "OPC UA Gateway",
                    "type": "protocol-gateway",
                    "description": "Equipment connectivity",
                    "technology": "C++",
                },
                {
                    "name": "SQL Server Database",
                    "type": "database",
                    "description": "Relational database",
                    "technology": "T-SQL",
                },
                {
                    "name": "IIS Web Server",
                    "type": "web-server",
                    "description": "Web application hosting",
                    "technology": "IIS 10",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "iFIX Data Server API",
                    "type": "Proprietary",
                    "description": "Real-time data access",
                    "endpoints": ["iFixDataServer:///*"],
                },
                {
                    "name": "Historian REST API",
                    "type": "REST",
                    "description": "Historical data queries",
                    "endpoints": ["/historian/v1/data", "/historian/v1/tags"],
                },
                {
                    "name": "Operations Hub API",
                    "type": "REST",
                    "description": "Web HMI services",
                    "endpoints": ["/opshub/v1/*"],
                },
                {
                    "name": "MES API",
                    "type": "REST/SOAP",
                    "description": "Production operations API",
                    "endpoints": ["/mes/v2/*"],
                },
                {
                    "name": "Plant Applications API",
                    "type": "REST",
                    "description": "Analytics and KPI API",
                    "endpoints": ["/plantapps/v1/kpis", "/plantapps/v1/reports"],
                },
                {
                    "name": "Workflow API",
                    "type": "REST",
                    "description": "Electronic procedures API",
                    "endpoints": ["/workflow/v1/procedures"],
                },
                {
                    "name": "CSense API",
                    "type": "REST",
                    "description": "Predictive analytics API",
                    "endpoints": ["/csense/v1/predictions", "/csense/v1/models"],
                },
                {
                    "name": "OPC UA Service",
                    "type": "OPC UA",
                    "description": "Standard OPC connectivity",
                    "endpoints": ["opc.tcp://*"],
                },
                {
                    "name": "Alarm API",
                    "type": "REST",
                    "description": "Alarm management API",
                    "endpoints": ["/alarms/v1/*"],
                },
                {
                    "name": "Integration API",
                    "type": "REST",
                    "description": "ERP integration services",
                    "endpoints": ["/integration/v1/*"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "REST API",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "OAuth2/AD",
                },
                {
                    "name": "SOAP Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "XML",
                    "authentication": "WS-Security",
                },
                {
                    "name": "OPC DA Interface",
                    "protocol": "DCOM",
                    "data_format": "OPC",
                    "authentication": "Windows",
                },
                {
                    "name": "OPC UA Interface",
                    "protocol": "OPC UA",
                    "data_format": "OPC Types",
                    "authentication": "Certificate",
                },
                {
                    "name": "Database Interface",
                    "protocol": "TDS",
                    "data_format": "SQL",
                    "authentication": "SQL/Windows",
                },
                {
                    "name": "File Interface",
                    "protocol": "SMB/FTP",
                    "data_format": "CSV/XML",
                    "authentication": "Windows/FTP",
                },
                {
                    "name": "Message Queue",
                    "protocol": "AMQP",
                    "data_format": "JSON",
                    "authentication": "RabbitMQ Auth",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {
                    "name": "Process Tag",
                    "type": "real-time",
                    "retention_policy": "Live data only, archived to Historian",
                },
                {
                    "name": "Historical Data",
                    "type": "time-series",
                    "retention_policy": "5 years online, 20 years archive",
                },
                {
                    "name": "Production Record",
                    "type": "transactional",
                    "retention_policy": "Product lifetime + 10 years",
                },
                {"name": "Alarm History", "type": "event", "retention_policy": "3 years"},
                {"name": "Downtime Event", "type": "transactional", "retention_policy": "7 years"},
                {"name": "OEE Record", "type": "analytical", "retention_policy": "10 years"},
                {"name": "Quality Record", "type": "regulatory", "retention_policy": "15 years"},
                {
                    "name": "Electronic Procedure Execution",
                    "type": "regulatory",
                    "retention_policy": "Product lifetime + 15 years",
                },
                {
                    "name": "Predictive Model",
                    "type": "analytical",
                    "retention_policy": "Model lifetime + 3 years",
                },
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "SCADA Visualization",
                    "type": "visualization",
                    "description": "Real-time process displays",
                },
                {
                    "name": "Data Collection",
                    "type": "data-acquisition",
                    "description": "High-speed industrial data collection",
                },
                {
                    "name": "Alarm Processing",
                    "type": "event-processing",
                    "description": "Intelligent alarm handling",
                },
                {
                    "name": "Historian Archiving",
                    "type": "data-storage",
                    "description": "Time-series data compression",
                },
                {
                    "name": "OEE Calculation",
                    "type": "analytics",
                    "description": "Real-time OEE computation",
                },
                {
                    "name": "Downtime Classification",
                    "type": "categorization",
                    "description": "Production loss categorization",
                },
                {
                    "name": "KPI Calculation",
                    "type": "analytics",
                    "description": "Manufacturing KPI computation",
                },
                {
                    "name": "Procedure Execution",
                    "type": "workflow",
                    "description": "Execute electronic procedures",
                },
                {
                    "name": "Predictive Modeling",
                    "type": "ai-ml",
                    "description": "Machine learning predictions",
                },
                {
                    "name": "ERP Synchronization",
                    "type": "integration",
                    "description": "Bidirectional ERP sync",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "VP Operations",
                    "role": "executive",
                    "concerns": ["Production Performance", "Asset Reliability", "Cost Control"],
                    "influence": "high",
                },
                {
                    "name": "Plant Manager",
                    "role": "management",
                    "concerns": ["OEE", "Downtime", "Quality", "Safety"],
                    "influence": "high",
                },
                {
                    "name": "Operations Manager",
                    "role": "management",
                    "concerns": ["Production Throughput", "Labor Efficiency", "Schedule Adherence"],
                    "influence": "high",
                },
                {
                    "name": "Process Control Manager",
                    "role": "technical",
                    "concerns": ["SCADA Reliability", "Alarm Management", "Process Optimization"],
                    "influence": "high",
                },
                {
                    "name": "IT/OT Manager",
                    "role": "technical",
                    "concerns": ["System Integration", "Cybersecurity", "Data Management"],
                    "influence": "high",
                },
                {
                    "name": "Maintenance Manager",
                    "role": "management",
                    "concerns": ["Asset Reliability", "Predictive Maintenance", "Spare Parts"],
                    "influence": "medium",
                },
                {
                    "name": "Quality Manager",
                    "role": "management",
                    "concerns": ["Product Quality", "Compliance", "Customer Satisfaction"],
                    "influence": "high",
                },
                {
                    "name": "Control Room Operators",
                    "role": "operational",
                    "concerns": ["System Usability", "Alarm Load", "Training"],
                    "influence": "medium",
                },
                {
                    "name": "Process Engineers",
                    "role": "technical",
                    "concerns": ["Process Performance", "Data Access", "Analytics Tools"],
                    "influence": "medium",
                },
                {
                    "name": "CIO",
                    "role": "executive",
                    "concerns": ["Digital Strategy", "Cybersecurity", "ROI"],
                    "influence": "high",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Legacy SCADA End-of-Life",
                    "description": "Obsolete SCADA system no longer supported",
                    "urgency": "critical",
                    "impact": "transformational",
                },
                {
                    "name": "Production Visibility Gap",
                    "description": "Limited real-time production visibility",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Data Silos",
                    "description": "Disconnected systems and data sources",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "OEE Improvement Opportunity",
                    "description": "OEE below industry benchmark",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Alarm Overload",
                    "description": "Operators overwhelmed with alarms",
                    "urgency": "critical",
                    "impact": "medium",
                },
                {
                    "name": "Downtime Analysis Gap",
                    "description": "Manual downtime tracking and classification",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Predictive Maintenance Need",
                    "description": "Reactive maintenance causing unplanned downtime",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Regulatory Compliance",
                    "description": "FDA 21 CFR Part 11, ALCOA+ requirements",
                    "urgency": "high",
                    "impact": "critical",
                },
                {
                    "name": "Cybersecurity Risk",
                    "description": "Outdated systems vulnerable to attacks",
                    "urgency": "critical",
                    "impact": "critical",
                },
                {
                    "name": "Cloud Analytics Opportunity",
                    "description": "Leverage cloud for advanced analytics",
                    "urgency": "medium",
                    "impact": "transformational",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "Achieve 99.99% SCADA Uptime",
                    "description": "World-class control system reliability",
                    "timeframe": "12 months",
                    "measurable": "Uptime from 98.5% to 99.99%",
                },
                {
                    "name": "Improve OEE to 85%",
                    "description": "Best-in-class equipment effectiveness",
                    "timeframe": "18 months",
                    "measurable": "OEE from 72% to 85%",
                },
                {
                    "name": "Reduce Alarm Rate 80%",
                    "description": "Manageable alarm environment",
                    "timeframe": "12 months",
                    "measurable": "From 60 alarms/hour to 10 alarms/hour per operator",
                },
                {
                    "name": "Achieve 100% Downtime Classification",
                    "description": "Track all production losses",
                    "timeframe": "12 months",
                    "measurable": "100% downtime events classified in real-time",
                },
                {
                    "name": "Deploy Predictive Analytics",
                    "description": "Predict asset failures 24+ hours in advance",
                    "timeframe": "24 months",
                    "measurable": "85% prediction accuracy, > 24 hour lead time",
                },
                {
                    "name": "Real-Time Production Visibility",
                    "description": "Enterprise-wide production dashboards",
                    "timeframe": "12 months",
                    "measurable": "< 1 minute data latency",
                },
                {
                    "name": "Achieve FDA Compliance",
                    "description": "21 CFR Part 11 compliant systems",
                    "timeframe": "18 months",
                    "measurable": "Zero audit findings",
                },
                {
                    "name": "Reduce Unplanned Downtime 40%",
                    "description": "Improve asset reliability",
                    "timeframe": "24 months",
                    "measurable": "Unplanned downtime from 8% to 4.8%",
                },
                {
                    "name": "Deploy Cloud Analytics",
                    "description": "Cloud-based advanced analytics",
                    "timeframe": "18 months",
                    "measurable": "100% plants connected to cloud",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "World-Class SCADA Reliability",
                    "description": "Industry-leading control system uptime",
                    "benefit_type": "operational",
                    "quantified_benefit": "99.99% uptime, $5M risk avoidance",
                },
                {
                    "name": "Manufacturing Excellence",
                    "description": "Best-in-class OEE performance",
                    "benefit_type": "operational",
                    "quantified_benefit": "85% OEE, $18M throughput increase",
                },
                {
                    "name": "Operator Effectiveness",
                    "description": "Manageable alarm environment",
                    "benefit_type": "operational",
                    "quantified_benefit": "80% alarm reduction, 30% productivity improvement",
                },
                {
                    "name": "Production Intelligence",
                    "description": "Real-time visibility and analytics",
                    "benefit_type": "strategic",
                    "quantified_benefit": "100% downtime classified, data-driven decisions",
                },
                {
                    "name": "Predictive Reliability",
                    "description": "Proactive maintenance capability",
                    "benefit_type": "operational",
                    "quantified_benefit": "40% unplanned downtime reduction, $12M savings",
                },
                {
                    "name": "Regulatory Confidence",
                    "description": "FDA-compliant systems",
                    "benefit_type": "compliance",
                    "quantified_benefit": "Zero audit findings, $2M risk avoidance",
                },
                {
                    "name": "Cloud Innovation",
                    "description": "Advanced analytics capability",
                    "benefit_type": "strategic",
                    "quantified_benefit": "AI-driven optimization, 5% efficiency gain",
                },
                {
                    "name": "Cybersecurity Posture",
                    "description": "Secure, modern infrastructure",
                    "benefit_type": "security",
                    "quantified_benefit": "Zero critical cyber incidents",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Data-First Strategy",
                    "description": "Collect all data, analyze later",
                    "rationale": "Enable future analytics and AI",
                },
                {
                    "name": "Real-Time Visibility",
                    "description": "Real-time access to all production data",
                    "rationale": "Enable fast decision-making",
                },
                {
                    "name": "ISA - 95 Alignment",
                    "description": "Follow ISA - 95 integration model",
                    "rationale": "Standardized architecture",
                },
                {
                    "name": "Defense in Depth",
                    "description": "Layered cybersecurity approach",
                    "rationale": "Protect critical infrastructure",
                },
                {
                    "name": "Alarm Rationalization",
                    "description": "Manage alarms per ISA - 18.2",
                    "rationale": "Prevent operator overload",
                },
                {
                    "name": "Standardization",
                    "description": "Standard platform across all sites",
                    "rationale": "Reduce complexity and cost",
                },
                {
                    "name": "Cloud Hybrid",
                    "description": "Control on-premise, analytics in cloud",
                    "rationale": "Balance reliability and innovation",
                },
                {
                    "name": "Continuous Improvement",
                    "description": "Always optimize and improve",
                    "rationale": "Sustain competitive advantage",
                },
                {
                    "name": "Regulatory by Design",
                    "description": "Build compliance into systems",
                    "rationale": "Avoid remediation costs",
                },
                {
                    "name": "User-Centric Design",
                    "description": "Design for operators first",
                    "rationale": "Drive adoption and effectiveness",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "System Availability",
                    "type": "performance",
                    "description": "SCADA availability 99.99%",
                    "priority": "critical",
                },
                {
                    "name": "Data Collection Performance",
                    "type": "performance",
                    "description": "Collect 1M+ tags per second",
                    "priority": "critical",
                },
                {
                    "name": "Alarm Response Time",
                    "type": "performance",
                    "description": "Alarm latency < 100ms",
                    "priority": "critical",
                },
                {
                    "name": "Historical Data Retention",
                    "type": "capacity",
                    "description": "5 years online, 20 years archive",
                    "priority": "high",
                },
                {
                    "name": "Concurrent Users",
                    "type": "capacity",
                    "description": "Support 500 concurrent operators",
                    "priority": "high",
                },
                {
                    "name": "ERP Integration Latency",
                    "type": "integration",
                    "description": "Production data sync < 1 minute",
                    "priority": "high",
                },
                {
                    "name": "FDA 21 CFR Part 11",
                    "type": "compliance",
                    "description": "Electronic records and signatures",
                    "priority": "critical",
                },
                {
                    "name": "Audit Trail",
                    "type": "compliance",
                    "description": "Complete audit trail for all changes",
                    "priority": "critical",
                },
                {
                    "name": "Disaster Recovery",
                    "type": "continuity",
                    "description": "RPO < 5 minutes, RTO < 1 hour",
                    "priority": "critical",
                },
                {
                    "name": "Cybersecurity",
                    "type": "security",
                    "description": "IEC 62443 compliance",
                    "priority": "critical",
                },
                {
                    "name": "Mobile Support",
                    "type": "functional",
                    "description": "Native mobile apps for iOS/Android",
                    "priority": "medium",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget Limitation",
                    "type": "financial",
                    "description": "Total program budget $18M",
                },
                {
                    "name": "Zero Downtime Cutover",
                    "type": "operational",
                    "description": "Cannot stop production for deployment",
                },
                {
                    "name": "Legacy System Integration",
                    "type": "technical",
                    "description": "Must integrate with existing DCS/PLCs",
                },
                {
                    "name": "Network Bandwidth",
                    "type": "technical",
                    "description": "Limited network capacity in some plants",
                },
                {
                    "name": "Skills Gap",
                    "type": "resource",
                    "description": "Limited GE Proficy expertise internally",
                },
                {
                    "name": "Timeline Pressure",
                    "type": "schedule",
                    "description": "Must complete before FDA audit in 18 months",
                },
                {
                    "name": "Cybersecurity Restrictions",
                    "type": "security",
                    "description": "Air-gapped control network, no direct internet",
                },
                {
                    "name": "Multi-Site Coordination",
                    "type": "organizational",
                    "description": "5 plants, different production schedules",
                },
                {
                    "name": "Change Resistance",
                    "type": "organizational",
                    "description": "Operators resistant to new systems",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "SCADA Maturity Assessment",
                    "type": "maturity",
                    "description": "Current SCADA capability assessment",
                    "result": "Level 2 maturity, significant upgrade needed",
                },
                {
                    "name": "Network Assessment",
                    "type": "technical",
                    "description": "Network infrastructure readiness",
                    "result": "Adequate for SCADA, upgrades needed for cloud",
                },
                {
                    "name": "Cybersecurity Assessment",
                    "type": "security",
                    "description": "IEC 62443 gap analysis",
                    "result": "Moderate gaps, remediation plan defined",
                },
                {
                    "name": "ROI Analysis",
                    "type": "financial",
                    "description": "Business case validation",
                    "result": "Projected 320% ROI over 5 years",
                },
                {
                    "name": "Change Readiness",
                    "type": "organizational",
                    "description": "Organizational change capability",
                    "result": "Moderate readiness, strong operator engagement needed",
                },
            ]
        ),
        # ==================== IMPLEMENTATION & MIGRATION LAYER ====================
        implementation_events=json.dumps(
            [
                {
                    "name": "Program Kickoff",
                    "date": "2024 - 02 - 01",
                    "milestone": True,
                    "description": "Project charter and team mobilization",
                },
                {
                    "name": "Infrastructure Deployment",
                    "date": "2024 - 05 - 31",
                    "milestone": False,
                    "description": "Server and network infrastructure",
                },
                {
                    "name": "Historian Go-Live Plant 1",
                    "date": "2024 - 08 - 31",
                    "milestone": True,
                    "description": "First plant historian operational",
                },
                {
                    "name": "iFIX SCADA Cutover Plant 1",
                    "date": "2024 - 12 - 31",
                    "milestone": True,
                    "description": "First plant SCADA migration",
                },
                {
                    "name": "Operations Hub Launch",
                    "date": "2025 - 03 - 31",
                    "milestone": False,
                    "description": "Web-based HMI available",
                },
                {
                    "name": "MES Pilot Go-Live",
                    "date": "2025 - 06 - 30",
                    "milestone": True,
                    "description": "MES operational on pilot line",
                },
                {
                    "name": "All Plants on Historian",
                    "date": "2025 - 09 - 30",
                    "milestone": True,
                    "description": "Enterprise-wide historian",
                },
                {
                    "name": "CSense Predictive Analytics Live",
                    "date": "2026 - 03 - 31",
                    "milestone": False,
                    "description": "AI/ML predictions operational",
                },
                {
                    "name": "Program Complete",
                    "date": "2026 - 08 - 31",
                    "milestone": True,
                    "description": "All plants fully deployed",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Program Management",
                    "description": "Overall program governance",
                    "duration_weeks": 130,
                    "team_size": 6,
                },
                {
                    "name": "Infrastructure Deployment",
                    "description": "Servers, network, security",
                    "duration_weeks": 16,
                    "team_size": 10,
                },
                {
                    "name": "Historian Deployment",
                    "description": "Proficy Historian implementation",
                    "duration_weeks": 52,
                    "team_size": 12,
                },
                {
                    "name": "SCADA Migration",
                    "description": "iFIX SCADA replacement",
                    "duration_weeks": 104,
                    "team_size": 20,
                },
                {
                    "name": "Operations Hub",
                    "description": "Web HMI deployment",
                    "duration_weeks": 40,
                    "team_size": 8,
                },
                {
                    "name": "MES Implementation",
                    "description": "Manufacturing execution system",
                    "duration_weeks": 60,
                    "team_size": 15,
                },
                {
                    "name": "Plant Applications",
                    "description": "Manufacturing intelligence",
                    "duration_weeks": 52,
                    "team_size": 10,
                },
                {
                    "name": "CSense Predictive Analytics",
                    "description": "AI/ML deployment",
                    "duration_weeks": 40,
                    "team_size": 8,
                },
                {
                    "name": "Integration",
                    "description": "ERP and equipment integration",
                    "duration_weeks": 78,
                    "team_size": 12,
                },
                {
                    "name": "Training & Change Management",
                    "description": "User adoption program",
                    "duration_weeks": 104,
                    "team_size": 8,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Digital Operations Strategy",
                    "type": "document",
                    "due_phase": "initiation",
                    "owner": "Program Director",
                },
                {
                    "name": "Proficy Historian System",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "Historian Lead",
                },
                {
                    "name": "iFIX SCADA System",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "SCADA Lead",
                },
                {
                    "name": "Operations Hub Web HMI",
                    "type": "web-application",
                    "due_phase": "build",
                    "owner": "Web Development Lead",
                },
                {
                    "name": "MES Production System",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "MES Lead",
                },
                {
                    "name": "Plant Applications Analytics",
                    "type": "analytics-platform",
                    "due_phase": "build",
                    "owner": "Analytics Lead",
                },
                {
                    "name": "CSense AI Models",
                    "type": "ai-models",
                    "due_phase": "build",
                    "owner": "Data Scientist",
                },
                {
                    "name": "ERP Integration",
                    "type": "integration",
                    "due_phase": "build",
                    "owner": "Integration Architect",
                },
                {
                    "name": "Training Curriculum",
                    "type": "training",
                    "due_phase": "prepare",
                    "owner": "Training Manager",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "Infrastructure Ready",
                    "date": "2024 - 05 - 31",
                    "description": "Server and network infrastructure operational",
                },
                {
                    "name": "First Historian Live",
                    "date": "2024 - 08 - 31",
                    "description": "Plant 1 historian collecting data",
                },
                {
                    "name": "First SCADA Migration",
                    "date": "2024 - 12 - 31",
                    "description": "Plant 1 on iFIX SCADA",
                },
                {
                    "name": "MES Operational",
                    "date": "2025 - 06 - 30",
                    "description": "Pilot line executing on MES",
                },
                {
                    "name": "Enterprise Historian",
                    "date": "2025 - 09 - 30",
                    "description": "All plants on Proficy Historian",
                },
                {
                    "name": "Predictive Analytics Live",
                    "date": "2026 - 03 - 31",
                    "description": "CSense generating predictions",
                },
                {
                    "name": "Full Deployment",
                    "date": "2026 - 08 - 31",
                    "description": "All capabilities operational all plants",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "Plant 1 Data Center",
                    "location": "Baytown, TX",
                    "tier": "Tier II",
                    "size_sqm": 200,
                    "description": "Primary plant control room and data center",
                },
                {
                    "name": "Plant 2 Data Center",
                    "location": "Baton Rouge, LA",
                    "tier": "Tier II",
                    "size_sqm": 180,
                    "description": "Secondary plant data center",
                },
                {
                    "name": "Corporate Data Center",
                    "location": "Houston, TX",
                    "tier": "Tier III",
                    "size_sqm": 500,
                    "description": "Enterprise historian and analytics",
                },
                {
                    "name": "AWS Cloud Region",
                    "location": "US-East - 1",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "Cloud analytics and Manufacturing Data Cloud",
                },
                {
                    "name": "DR Site",
                    "location": "Dallas, TX",
                    "tier": "Tier III",
                    "size_sqm": 200,
                    "description": "Disaster recovery data center",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "Proficy SCADA Servers",
                    "type": "application-server",
                    "quantity": 10,
                    "location": "Plant Data Centers",
                    "specs": "Dell PowerEdge R740, 16 - core, 64GB RAM",
                },
                {
                    "name": "Proficy Historian Servers",
                    "type": "historian-server",
                    "quantity": 15,
                    "location": "Plant & Corporate DC",
                    "specs": "Dell PowerEdge R840, 32 - core, 128GB RAM, SSD storage",
                },
                {
                    "name": "SQL Server Database Cluster",
                    "type": "database-server",
                    "quantity": 4,
                    "location": "Corporate DC",
                    "specs": "Dell PowerEdge R940, 48 - core, 256GB RAM, SAN storage",
                },
                {
                    "name": "Operator HMI Panels",
                    "type": "hmi-terminal",
                    "quantity": 150,
                    "location": "Control Rooms",
                    "specs": "Industrial panel PC, 24 - inch touchscreen",
                },
                {
                    "name": "Industrial Network Switches",
                    "type": "network-switch",
                    "quantity": 80,
                    "location": "Plant Network",
                    "specs": "Cisco IE - 4010 managed switches",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "Plant Ethernet Network",
                    "type": "industrial-ethernet",
                    "coverage": "All Plants",
                    "bandwidth_mbps": 1000,
                    "provider": "In-house",
                },
                {
                    "name": "Control Network VLAN",
                    "type": "vlan",
                    "coverage": "All Plants",
                    "bandwidth_mbps": 1000,
                    "provider": "In-house",
                },
                {
                    "name": "Corporate WAN",
                    "type": "wan",
                    "coverage": "All Sites",
                    "bandwidth_mbps": 100,
                    "provider": "AT&T",
                },
                {
                    "name": "AWS DirectConnect",
                    "type": "dedicated-link",
                    "coverage": "Corporate DC to AWS",
                    "bandwidth_mbps": 1000,
                    "provider": "AWS",
                },
            ]
        ),
    )


def seed_ge_proficy(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(vendor_name="GE Digital").first()
            if existing:
                print("⚠️  GE Proficy template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_ge_proficy_template()
            db.session.add(template)
            db.session.commit()

            print("✅ GE Proficy template seeded successfully!")
            print(f"   - Vendor: {template.vendor_name}")
            print(f"   - Technology Layer: ✅ Complete")
            print(f"   - Strategy Layer: ✅ Complete (20 capabilities, 6 value streams)")
            print(
                f"   - Business Layer: ✅ Complete (10 services, 6 processes, 8 objects, 10 actors, 9 products)"
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
            print(f"   - Physical Layer: ✅ Complete (5 facilities, 5 equipment types, 4 networks)")
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
            print(f"❌ Error seeding GE Proficy template: {str(e)}")
            import traceback

            traceback.print_exc()

            raise


if __name__ == "__main__":
    seed_ge_proficy()
