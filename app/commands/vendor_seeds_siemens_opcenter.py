"""
Siemens OPCenter MES Comprehensive Vendor Template Seed Data

Complete ArchiMate 3.2 coverage across ALL layers:
- Strategy Layer
- Business Layer
- Application Layer
- Technology Layer
- Motivation Layer
- Implementation & Migration Layer
- Physical Layer

Run with: python manage.py seed-vendor-siemens
"""
import json

from app import create_app, db
from app.models import User, VendorStackTemplate
from config import DevelopmentConfig


def create_siemens_opcenter_template():
    """Siemens OPCenter MES FULLY COMPREHENSIVE template - ALL ArchiMate 3.2 layers"""
    return VendorStackTemplate(
        vendor_name="Siemens",
        name="Siemens OPCenter Manufacturing Execution System",
        description="Comprehensive MES solution for discrete, process, and hybrid manufacturing with real-time production tracking, quality management, and complete shop floor control",
        # ==================== TECHNOLOGY LAYER ====================
        platform="on-premise",
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
        secrets_manager="windows-credential-store",
        logging_framework="nlog",
        metrics_platform="prometheus",
        apm_tool="application-insights",
        tracing_tool="opencensus",
        build_tool="msbuild",
        ci_cd_platform="azure-devops",
        sast_tool="sonarqube",
        dast_tool="owasp-zap",
        dependency_scanner="whitesource",
        nodes=json.dumps(
            [
                {
                    "name": "OPCenter Execution Core Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "OPCenter Execution Discrete Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "OPCenter Quality Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "OPCenter Intelligence Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 128,
                },
                {
                    "name": "SQL Server Database",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 32,
                    "ram_gb": 256,
                },
                {
                    "name": "Application Gateway",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "Edge Server (Plant Floor)",
                    "type": "industrial-pc",
                    "os": "Windows 10 IoT Enterprise",
                    "cpu_cores": 8,
                    "ram_gb": 16,
                },
            ]
        ),
        devices=json.dumps(
            [
                {
                    "name": "Industrial Ethernet Switch",
                    "type": "network-switch",
                    "description": "Shop floor network connectivity",
                },
                {
                    "name": "PLC Gateway",
                    "type": "plc-gateway",
                    "description": "Programmable logic controller integration",
                },
                {
                    "name": "SCADA Server",
                    "type": "scada-system",
                    "description": "Supervisory control and data acquisition",
                },
                {
                    "name": "Barcode Scanner",
                    "type": "data-collection",
                    "description": "Material and work order tracking",
                },
                {
                    "name": "HMI Panels",
                    "type": "operator-interface",
                    "description": "Operator touchscreen terminals",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {
                    "name": "Siemens OPCenter Execution Core",
                    "type": "mes-platform",
                    "version": "2023.1",
                },
                {
                    "name": "Siemens OPCenter Execution Discrete",
                    "type": "mes-discrete",
                    "version": "2023.1",
                },
                {"name": "Siemens OPCenter Quality", "type": "qms", "version": "11.0"},
                {"name": "Siemens OPCenter Intelligence", "type": "analytics", "version": "11.0"},
                {"name": "Microsoft SQL Server", "type": "database", "version": "2019 Enterprise"},
                {"name": "IIS Web Server", "type": "web-server", "version": "10.0"},
                {"name": ".NET Framework", "type": "runtime", "version": "4.8"},
                {"name": "OPC UA Server", "type": "industrial-protocol", "version": "1.04"},
                {"name": "RabbitMQ", "type": "message-broker", "version": "3.12"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "OPCenter Execution Service",
                    "type": "application-runtime",
                    "description": "Core MES execution engine",
                },
                {
                    "name": "Material Tracking Service",
                    "type": "tracking-service",
                    "description": "Real-time material genealogy and location",
                },
                {
                    "name": "Production Execution Service",
                    "type": "execution-service",
                    "description": "Work order and routing execution",
                },
                {
                    "name": "Quality Management Service",
                    "type": "quality-service",
                    "description": "SPC, inspection, and non-conformance management",
                },
                {
                    "name": "Equipment Integration Service",
                    "type": "integration-service",
                    "description": "Machine and PLC connectivity",
                },
                {
                    "name": "Intelligence & Analytics Service",
                    "type": "analytics-service",
                    "description": "Real-time KPI calculation and dashboards",
                },
                {
                    "name": "Document Management Service",
                    "type": "document-service",
                    "description": "Electronic work instructions and SOPs",
                },
                {
                    "name": "Label Printing Service",
                    "type": "printing-service",
                    "description": "Automated label generation",
                },
                {
                    "name": "Genealogy Service",
                    "type": "traceability-service",
                    "description": "Forward/backward traceability",
                },
                {
                    "name": "Dispatching Service",
                    "type": "scheduling-service",
                    "description": "Work order dispatching and sequencing",
                },
                {
                    "name": "Data Collection Service",
                    "type": "data-service",
                    "description": "Operator and machine data collection",
                },
                {
                    "name": "Integration Gateway Service",
                    "type": "integration-gateway",
                    "description": "ERP and PLM integration",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "OPCenter Package",
                    "type": "deployment-package",
                    "size_mb": 200,
                    "registry": "Deployment Manager",
                },
                {
                    "name": "Custom Extension DLL",
                    "type": "library",
                    "size_mb": 5,
                    "registry": "Extension Folder",
                },
                {
                    "name": "Report Template",
                    "type": "report",
                    "size_mb": 2,
                    "registry": "Report Server",
                },
                {
                    "name": "Database Backup",
                    "type": "backup-archive",
                    "size_mb": 50000,
                    "registry": "Backup Storage",
                },
                {
                    "name": "Label Template",
                    "type": "template",
                    "size_mb": 1,
                    "registry": "Label Designer",
                },
                {
                    "name": "Dashboard Configuration",
                    "type": "configuration",
                    "size_mb": 5,
                    "registry": "Intelligence Server",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "Plant Floor Network",
                    "type": "industrial-ethernet",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 5,
                },
                {
                    "name": "IT/OT Integration Network",
                    "type": "private",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 2,
                },
                {
                    "name": "SQL Replication Network",
                    "type": "private",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 1,
                },
                {"name": "Corporate WAN", "type": "wan", "bandwidth_mbps": 1000, "latency_ms": 15},
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="Siemens AG",
        market_position="leader",
        company_size="enterprise",
        founded_year=1847,
        headquarters="Munich, Germany",
        revenue_usd=72000000000,
        customer_count=25000,
        market_share_percentage=15.0,
        acquisition_risk="very-low",
        financial_health="excellent",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                # CORE MES CAPABILITIES (Shop Floor Operations)
                {
                    "name": "Production Execution",
                    "description": "Work order execution, routing, and operations management",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Material Traceability",
                    "description": "Complete genealogy tracking forward and backward",
                    "coverage_percentage": 100,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Quality Management",
                    "description": "SPC, inspection plans, non-conformance, CAPA",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Equipment Integration",
                    "description": "PLC, SCADA, machine integration via OPC UA",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Real-Time Analytics",
                    "description": "Live KPI dashboards, OEE, downtime analysis",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Electronic Work Instructions",
                    "description": "Paperless manufacturing with electronic SOPs",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Batch Management",
                    "description": "Process manufacturing batch control and genealogy",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Labor Management",
                    "description": "Time tracking, skill verification, labor optimization",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Maintenance Integration",
                    "description": "Predictive and preventive maintenance workflows",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "Supply Chain Visibility",
                    "description": "Material consumption and inventory tracking",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Advanced Planning & Scheduling",
                    "description": "Finite capacity scheduling and dispatching",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "Serialization & Track-Trace",
                    "description": "Unit-level serialization for pharma/medical",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Regulatory Compliance",
                    "description": "21 CFR Part 11, GAMP 5, ISO compliance",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Performance Management",
                    "description": "OEE, availability, performance, quality metrics",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Document Control",
                    "description": "Version-controlled electronic documents",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Non-Conformance Management",
                    "description": "Defect tracking, containment, root cause",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Change Management",
                    "description": "ECO/ECN integration and shop floor change control",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Resource Management",
                    "description": "Tool, fixture, and equipment management",
                    "coverage_percentage": 87,
                    "maturity_level": "managed",
                },
                {
                    "name": "Energy Management",
                    "description": "Real-time energy consumption tracking",
                    "coverage_percentage": 85,
                    "maturity_level": "developing",
                },
                {
                    "name": "Digital Twin Integration",
                    "description": "Integration with PLM digital twin models",
                    "coverage_percentage": 82,
                    "maturity_level": "developing",
                },
                # ADJACENT CAPABILITIES (Extended Manufacturing Support)
                {
                    "name": "Warehouse Integration",
                    "description": "WMS integration for material staging and finished goods",
                    "coverage_percentage": 86,
                    "maturity_level": "managed",
                },
                {
                    "name": "Customer Order Visibility",
                    "description": "Link production to customer orders and delivery schedules",
                    "coverage_percentage": 83,
                    "maturity_level": "managed",
                },
                {
                    "name": "Supplier Collaboration",
                    "description": "Supplier portal for material forecasts and delivery coordination",
                    "coverage_percentage": 78,
                    "maturity_level": "developing",
                },
                {
                    "name": "Quality Analytics & AI",
                    "description": "Predictive quality analytics and ML-based defect prediction",
                    "coverage_percentage": 81,
                    "maturity_level": "managed",
                },
                {
                    "name": "Environmental Compliance",
                    "description": "Emissions tracking, waste management, environmental reporting",
                    "coverage_percentage": 79,
                    "maturity_level": "managed",
                },
                {
                    "name": "Sustainability Metrics",
                    "description": "Carbon footprint, water usage, sustainability KPIs",
                    "coverage_percentage": 76,
                    "maturity_level": "developing",
                },
                {
                    "name": "Operator Training Management",
                    "description": "Training records, certification tracking, skill gap analysis",
                    "coverage_percentage": 84,
                    "maturity_level": "managed",
                },
                {
                    "name": "Production Costing",
                    "description": "Real-time production cost calculation and variance analysis",
                    "coverage_percentage": 82,
                    "maturity_level": "managed",
                },
                {
                    "name": "Multi-Site Orchestration",
                    "description": "Global production coordination across multiple plants",
                    "coverage_percentage": 80,
                    "maturity_level": "managed",
                },
                {
                    "name": "IoT & Smart Sensors",
                    "description": "IIoT sensor integration, condition monitoring, predictive alerts",
                    "coverage_percentage": 87,
                    "maturity_level": "managed",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Order-to-Execution",
                    "stages": [
                        "Work Order Release",
                        "Material Staging",
                        "Production Start",
                        "Operations Execution",
                        "Quality Checks",
                        "Completion",
                        "Goods Receipt",
                    ],
                    "description": "Manufacturing order execution",
                },
                {
                    "name": "Material-to-Genealogy",
                    "stages": [
                        "Material Receipt",
                        "Lot Assignment",
                        "Consumption Tracking",
                        "Component Assembly",
                        "Final Product",
                        "Genealogy Record",
                    ],
                    "description": "Complete traceability",
                },
                {
                    "name": "Defect-to-Resolution",
                    "stages": [
                        "Defect Detection",
                        "Non-Conformance",
                        "Containment",
                        "Root Cause Analysis",
                        "Corrective Action",
                        "Verification",
                    ],
                    "description": "Quality management",
                },
                {
                    "name": "Machine-to-Insight",
                    "stages": [
                        "Data Collection",
                        "Real-Time Processing",
                        "KPI Calculation",
                        "Dashboard Update",
                        "Alert Generation",
                        "Action",
                    ],
                    "description": "Real-time analytics",
                },
                {
                    "name": "Plan-to-Execute",
                    "stages": [
                        "Schedule Receipt",
                        "Dispatching",
                        "Resource Allocation",
                        "Execution",
                        "Confirmation",
                        "Performance Analysis",
                    ],
                    "description": "Production scheduling",
                },
                {
                    "name": "Maintain-to-Operate",
                    "stages": [
                        "Condition Monitoring",
                        "Maintenance Alert",
                        "Work Order",
                        "Execution",
                        "Confirmation",
                        "Asset Update",
                    ],
                    "description": "Maintenance management",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "Phased Plant Rollout",
                    "description": "Deploy one line at a time per plant",
                    "timeline_months": 24,
                    "risk_level": "low",
                },
                {
                    "name": "Big Bang Implementation",
                    "description": "Deploy entire plant simultaneously",
                    "timeline_months": 12,
                    "risk_level": "high",
                },
                {
                    "name": "Pilot-Scale-Replicate",
                    "description": "Pilot line, then scale across plants",
                    "timeline_months": 18,
                    "risk_level": "medium",
                },
                {
                    "name": "Cloud-Based Deployment",
                    "description": "Deploy on Azure using Siemens Cloud",
                    "timeline_months": 9,
                    "risk_level": "medium",
                },
                {
                    "name": "Hybrid Approach",
                    "description": "Core on-premise, analytics in cloud",
                    "timeline_months": 15,
                    "risk_level": "medium",
                },
                {
                    "name": "Template-Based Deployment",
                    "description": "Pre-configured template for similar lines",
                    "timeline_months": 8,
                    "risk_level": "low",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Production Execution Service",
                    "description": "Execute manufacturing operations",
                    "service_type": "internal",
                    "sla_commitment": "99.9% uptime, < 2 second response",
                },
                {
                    "name": "Material Tracking Service",
                    "description": "Track material location and genealogy",
                    "service_type": "internal",
                    "sla_commitment": "100% traceability accuracy",
                },
                {
                    "name": "Quality Control Service",
                    "description": "Manage quality inspections and SPC",
                    "service_type": "internal",
                    "sla_commitment": "Real-time quality alerts",
                },
                {
                    "name": "Equipment Monitoring Service",
                    "description": "Monitor machine performance",
                    "service_type": "internal",
                    "sla_commitment": "< 1 second data collection",
                },
                {
                    "name": "Performance Analytics Service",
                    "description": "Calculate and display KPIs",
                    "service_type": "internal",
                    "sla_commitment": "Real-time KPI updates",
                },
                {
                    "name": "Document Management Service",
                    "description": "Provide electronic work instructions",
                    "service_type": "internal",
                    "sla_commitment": "99.99% document availability",
                },
                {
                    "name": "Label Printing Service",
                    "description": "Generate serialized labels",
                    "service_type": "internal",
                    "sla_commitment": "< 3 second label print",
                },
                {
                    "name": "Genealogy Service",
                    "description": "Maintain product genealogy records",
                    "service_type": "internal",
                    "sla_commitment": "Instant genealogy retrieval",
                },
                {
                    "name": "Dispatching Service",
                    "description": "Dispatch work orders to lines",
                    "service_type": "internal",
                    "sla_commitment": "Real-time dispatch updates",
                },
                {
                    "name": "ERP Integration Service",
                    "description": "Synchronize with SAP/ERP",
                    "service_type": "integration",
                    "sla_commitment": "< 10 second integration latency",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Work Order Execution",
                    "description": "Execute manufacturing operations step-by-step",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Order Start",
                        "Material Assignment",
                        "Operation Execution",
                        "Data Collection",
                        "Quality Check",
                        "Completion",
                    ],
                    "cycle_time": "Hours to days",
                    "kpis": ["Cycle Time", "First Pass Yield", "OEE"],
                },
                {
                    "name": "Material Consumption & Traceability",
                    "description": "Consume and track materials in production",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Lot Selection",
                        "Consumption Recording",
                        "Genealogy Update",
                        "Inventory Deduction",
                    ],
                    "cycle_time": "< 5 seconds",
                    "kpis": ["Traceability Completeness", "Inventory Accuracy"],
                },
                {
                    "name": "Quality Inspection",
                    "description": "Perform in-process and final inspections",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Inspection Plan",
                        "Characteristic Measurement",
                        "SPC Analysis",
                        "Pass/Fail Decision",
                        "NCR if Failed",
                    ],
                    "cycle_time": "Minutes to hours",
                    "kpis": ["First Pass Yield", "Defect Rate", "Inspection Time"],
                },
                {
                    "name": "Equipment Data Collection",
                    "description": "Collect machine data in real-time",
                    "automation_level": "fully-automated",
                    "steps": [
                        "OPC UA Connection",
                        "Data Streaming",
                        "Validation",
                        "Storage",
                        "KPI Calculation",
                    ],
                    "cycle_time": "Real-time (1 - second intervals)",
                    "kpis": ["Data Completeness", "Equipment Uptime", "OEE"],
                },
                {
                    "name": "Non-Conformance Management",
                    "description": "Manage defects and CAPAs",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Defect Detection",
                        "NCR Creation",
                        "Containment",
                        "Root Cause Analysis",
                        "Corrective Action",
                        "Verification",
                    ],
                    "cycle_time": "Days to weeks",
                    "kpis": ["CAPA Closure Time", "Repeat Defects"],
                },
                {
                    "name": "Production Scheduling & Dispatching",
                    "description": "Schedule and dispatch work orders",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Schedule Import",
                        "Constraint Evaluation",
                        "Sequence Optimization",
                        "Dispatch",
                        "Monitoring",
                    ],
                    "cycle_time": "Minutes",
                    "kpis": ["Schedule Adherence", "Line Utilization"],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Work Order",
                    "description": "Manufacturing order to produce products",
                    "lifecycle": "released -> in-progress -> completed -> closed",
                },
                {
                    "name": "Material Lot",
                    "description": "Batch or lot of material",
                    "lifecycle": "received -> available -> consumed -> depleted",
                },
                {
                    "name": "Operation",
                    "description": "Manufacturing step in routing",
                    "lifecycle": "pending -> in-progress -> completed",
                },
                {
                    "name": "Inspection Lot",
                    "description": "Quality inspection instance",
                    "lifecycle": "created -> in-inspection -> completed -> archived",
                },
                {
                    "name": "Non-Conformance Record",
                    "description": "Quality defect record",
                    "lifecycle": "created -> under-investigation -> corrective-action -> closed",
                },
                {
                    "name": "Container",
                    "description": "Material container or carrier",
                    "lifecycle": "empty -> loaded -> in-process -> empty",
                },
                {
                    "name": "Equipment",
                    "description": "Production machine or tool",
                    "lifecycle": "available -> in-use -> maintenance -> available",
                },
                {
                    "name": "Product Genealogy",
                    "description": "Complete as-built record",
                    "lifecycle": "in-creation -> completed -> archived",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Production Operator",
                    "description": "Shop floor operator",
                    "responsibilities": [
                        "Start/Complete Operations",
                        "Record Data",
                        "Quality Checks",
                        "Material Handling",
                    ],
                },
                {
                    "name": "Line Supervisor",
                    "description": "Production line supervisor",
                    "responsibilities": [
                        "Work Order Management",
                        "Resource Allocation",
                        "Problem Resolution",
                        "Performance Monitoring",
                    ],
                },
                {
                    "name": "Quality Inspector",
                    "description": "Quality control specialist",
                    "responsibilities": [
                        "Inspections",
                        "SPC Monitoring",
                        "NCR Creation",
                        "CAPA Management",
                    ],
                },
                {
                    "name": "Maintenance Technician",
                    "description": "Equipment maintenance",
                    "responsibilities": [
                        "Preventive Maintenance",
                        "Breakdown Response",
                        "Equipment Setup",
                        "Calibration",
                    ],
                },
                {
                    "name": "Production Planner",
                    "description": "Production scheduler",
                    "responsibilities": [
                        "Work Order Release",
                        "Material Planning",
                        "Capacity Planning",
                        "Schedule Optimization",
                    ],
                },
                {
                    "name": "Materials Handler",
                    "description": "Material movement specialist",
                    "responsibilities": [
                        "Material Staging",
                        "Kitting",
                        "Inventory Transactions",
                        "Label Printing",
                    ],
                },
                {
                    "name": "Process Engineer",
                    "description": "Manufacturing engineer",
                    "responsibilities": [
                        "Routing Definition",
                        "BOM Management",
                        "Process Improvement",
                        "Training",
                    ],
                },
                {
                    "name": "MES Administrator",
                    "description": "System administrator",
                    "responsibilities": [
                        "User Management",
                        "Configuration",
                        "System Monitoring",
                        "Integration Support",
                    ],
                },
                {
                    "name": "Quality Manager",
                    "description": "Quality assurance manager",
                    "responsibilities": [
                        "Quality Strategy",
                        "Audit Compliance",
                        "CAPA Review",
                        "Metrics Analysis",
                    ],
                },
                {
                    "name": "Plant Manager",
                    "description": "Plant operations manager",
                    "responsibilities": [
                        "Performance Review",
                        "Strategic Decisions",
                        "Resource Management",
                        "Continuous Improvement",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "Siemens OPCenter Execution Core",
                    "description": "Core MES platform",
                    "target_market": "All Manufacturing",
                },
                {
                    "name": "Siemens OPCenter Execution Discrete",
                    "description": "Discrete manufacturing MES",
                    "target_market": "Discrete Manufacturing",
                },
                {
                    "name": "Siemens OPCenter Execution Process",
                    "description": "Process manufacturing MES",
                    "target_market": "Process Manufacturing",
                },
                {
                    "name": "Siemens OPCenter Quality",
                    "description": "Quality management system",
                    "target_market": "Quality-Critical Industries",
                },
                {
                    "name": "Siemens OPCenter Intelligence",
                    "description": "Analytics and dashboards",
                    "target_market": "All Manufacturing",
                },
                {
                    "name": "Siemens OPCenter APS",
                    "description": "Advanced planning & scheduling",
                    "target_market": "Complex Scheduling Needs",
                },
                {
                    "name": "Siemens OPCenter RD&L",
                    "description": "Research, development & laboratory",
                    "target_market": "Process Industries",
                },
                {
                    "name": "Siemens OPCenter Intra Plant Logistics",
                    "description": "Material movement tracking",
                    "target_market": "Large Plants",
                },
                {
                    "name": "Siemens Opcenter Connect",
                    "description": "IoT and machine integration",
                    "target_market": "All Manufacturing",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "OPCenter Execution Core Engine",
                    "type": "application-server",
                    "description": "Core MES execution engine",
                    "technology": ".NET/C#",
                },
                {
                    "name": "Material Tracking Module",
                    "type": "application-module",
                    "description": "Material genealogy and tracking",
                    "technology": ".NET/C#",
                },
                {
                    "name": "Production Operations Module",
                    "type": "application-module",
                    "description": "Work order and routing execution",
                    "technology": ".NET/C#",
                },
                {
                    "name": "Quality Management Module",
                    "type": "application-module",
                    "description": "SPC and inspection management",
                    "technology": ".NET/C#",
                },
                {
                    "name": "OPCenter Web Portal",
                    "type": "web-application",
                    "description": "Browser-based operator interface",
                    "technology": "ASP.NET/Angular",
                },
                {
                    "name": "Intelligence Analytics Engine",
                    "type": "analytics-platform",
                    "description": "Real-time KPI engine",
                    "technology": ".NET/C#",
                },
                {
                    "name": "Integration Gateway",
                    "type": "integration-service",
                    "description": "ERP and PLM integration",
                    "technology": ".NET/C#",
                },
                {
                    "name": "OPC UA Client",
                    "type": "protocol-adapter",
                    "description": "Equipment connectivity",
                    "technology": "C++/.NET",
                },
                {
                    "name": "SQL Server Database",
                    "type": "database",
                    "description": "Relational data store",
                    "technology": "T-SQL",
                },
                {
                    "name": "Document Server",
                    "type": "document-repository",
                    "description": "Work instruction storage",
                    "technology": ".NET/C#",
                },
                {
                    "name": "Label Designer",
                    "type": "desktop-application",
                    "description": "Label template designer",
                    "technology": ".NET/WPF",
                },
                {
                    "name": "Report Designer",
                    "type": "reporting-tool",
                    "description": "Custom report builder",
                    "technology": ".NET/WPF",
                },
                {
                    "name": "Mobile App",
                    "type": "mobile-application",
                    "description": "Operator mobile interface",
                    "technology": "Xamarin",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "Execution API",
                    "type": "REST",
                    "description": "Core MES operations API",
                    "endpoints": ["/api/workorders", "/api/operations", "/api/materials"],
                },
                {
                    "name": "Material API",
                    "type": "REST",
                    "description": "Material tracking and genealogy",
                    "endpoints": ["/api/lots", "/api/genealogy", "/api/containers"],
                },
                {
                    "name": "Quality API",
                    "type": "REST",
                    "description": "Quality management",
                    "endpoints": ["/api/inspections", "/api/ncr", "/api/spc"],
                },
                {
                    "name": "Equipment API",
                    "type": "REST",
                    "description": "Equipment data collection",
                    "endpoints": ["/api/equipment", "/api/datapoints"],
                },
                {
                    "name": "Intelligence API",
                    "type": "REST",
                    "description": "Analytics and KPI",
                    "endpoints": ["/api/kpi", "/api/dashboards"],
                },
                {
                    "name": "Integration API",
                    "type": "SOAP/REST",
                    "description": "ERP integration services",
                    "endpoints": ["/api/integration/sap", "/api/integration/orders"],
                },
                {
                    "name": "OPC UA Interface",
                    "type": "OPC UA",
                    "description": "Machine connectivity",
                    "endpoints": ["OPC UA endpoints"],
                },
                {
                    "name": "Document API",
                    "type": "REST",
                    "description": "Document management",
                    "endpoints": ["/api/documents", "/api/workInstructions"],
                },
                {
                    "name": "Label API",
                    "type": "REST",
                    "description": "Label printing",
                    "endpoints": ["/api/labels/print"],
                },
                {
                    "name": "Authentication API",
                    "type": "REST",
                    "description": "User authentication",
                    "endpoints": ["/api/auth/login", "/api/auth/token"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "REST API",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "JWT Token",
                },
                {
                    "name": "SOAP Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "XML",
                    "authentication": "WS-Security",
                },
                {
                    "name": "OPC UA",
                    "protocol": "OPC UA",
                    "data_format": "OPC UA Types",
                    "authentication": "Certificate",
                },
                {
                    "name": "Database Interface",
                    "protocol": "TDS",
                    "data_format": "SQL",
                    "authentication": "Windows Auth",
                },
                {
                    "name": "File Interface",
                    "protocol": "SMB/FTP",
                    "data_format": "CSV/XML",
                    "authentication": "Windows Auth",
                },
                {
                    "name": "Message Queue",
                    "protocol": "AMQP",
                    "data_format": "JSON",
                    "authentication": "Credentials",
                },
                {
                    "name": "SAP RFC Interface",
                    "protocol": "RFC",
                    "data_format": "IDoc/BAPI",
                    "authentication": "SAP Credentials",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {
                    "name": "Work Order Data",
                    "type": "transactional",
                    "retention_policy": "Completion + 7 years",
                },
                {
                    "name": "Material Genealogy",
                    "type": "regulatory",
                    "retention_policy": "Product lifetime + 15 years",
                },
                {"name": "Quality Record", "type": "regulatory", "retention_policy": "15 years"},
                {"name": "Equipment Data", "type": "time-series", "retention_policy": "2 years"},
                {"name": "Audit Trail", "type": "audit", "retention_policy": "10 years"},
                {"name": "Electronic Signature", "type": "audit", "retention_policy": "Permanent"},
                {
                    "name": "Non-Conformance Record",
                    "type": "quality",
                    "retention_policy": "10 years",
                },
                {"name": "SPC Data", "type": "quality", "retention_policy": "5 years"},
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "Start Operation",
                    "type": "transaction",
                    "description": "Begin production operation",
                },
                {
                    "name": "Consume Material",
                    "type": "transaction",
                    "description": "Record material consumption",
                },
                {
                    "name": "Complete Operation",
                    "type": "transaction",
                    "description": "Finish production operation",
                },
                {
                    "name": "Record Measurement",
                    "type": "data-entry",
                    "description": "Enter quality measurement",
                },
                {
                    "name": "Calculate OEE",
                    "type": "calculation",
                    "description": "Compute overall equipment effectiveness",
                },
                {
                    "name": "Generate Genealogy",
                    "type": "reporting",
                    "description": "Create product genealogy report",
                },
                {
                    "name": "Dispatch Work Order",
                    "type": "workflow",
                    "description": "Assign work order to line",
                },
                {
                    "name": "Validate Material",
                    "type": "validation",
                    "description": "Check material validity for use",
                },
                {
                    "name": "Print Label",
                    "type": "output",
                    "description": "Generate and print serialized label",
                },
                {
                    "name": "Synchronize ERP",
                    "type": "integration",
                    "description": "Sync data with ERP system",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "VP Manufacturing",
                    "role": "executive",
                    "concerns": ["Production Efficiency", "Quality Excellence", "Cost Control"],
                    "influence": "high",
                },
                {
                    "name": "Plant Manager",
                    "role": "management",
                    "concerns": ["Plant Performance", "Regulatory Compliance", "Safety"],
                    "influence": "high",
                },
                {
                    "name": "Production Manager",
                    "role": "management",
                    "concerns": ["OEE", "Throughput", "Schedule Adherence"],
                    "influence": "high",
                },
                {
                    "name": "Quality Director",
                    "role": "executive",
                    "concerns": ["Quality Metrics", "FDA Compliance", "Customer Satisfaction"],
                    "influence": "high",
                },
                {
                    "name": "IT/OT Manager",
                    "role": "technical",
                    "concerns": ["System Integration", "Uptime", "Cybersecurity"],
                    "influence": "medium",
                },
                {
                    "name": "Manufacturing Engineers",
                    "role": "technical",
                    "concerns": ["Process Efficiency", "Standardization", "Continuous Improvement"],
                    "influence": "medium",
                },
                {
                    "name": "Production Operators",
                    "role": "operational",
                    "concerns": [
                        "System Usability",
                        "Clear Instructions",
                        "Performance Visibility",
                    ],
                    "influence": "medium",
                },
                {
                    "name": "Maintenance Team",
                    "role": "operational",
                    "concerns": ["Equipment Health", "Downtime Minimization", "Spare Parts"],
                    "influence": "medium",
                },
                {
                    "name": "Regulatory Affairs",
                    "role": "compliance",
                    "concerns": ["Audit Readiness", "Traceability", "Data Integrity"],
                    "influence": "high",
                },
                {
                    "name": "Supply Chain Manager",
                    "role": "management",
                    "concerns": ["Material Availability", "Inventory Accuracy", "Lead Times"],
                    "influence": "medium",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Traceability Mandate",
                    "description": "Regulatory requirement for complete genealogy",
                    "urgency": "critical",
                    "impact": "transformational",
                },
                {
                    "name": "Quality Improvement Need",
                    "description": "Reduce defects and improve yield",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Paperless Manufacturing",
                    "description": "Eliminate paper-based processes",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Real-Time Visibility",
                    "description": "Instant production performance insights",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "ERP Integration Gap",
                    "description": "Manual data entry between shop floor and ERP",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Regulatory Audit Risk",
                    "description": "FDA/audit compliance concerns",
                    "urgency": "critical",
                    "impact": "high",
                },
                {
                    "name": "Equipment Downtime",
                    "description": "Unplanned downtime impacting production",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Manual Processes",
                    "description": "Labor-intensive data collection",
                    "urgency": "medium",
                    "impact": "medium",
                },
                {
                    "name": "Lack of Standardization",
                    "description": "Inconsistent processes across plants",
                    "urgency": "medium",
                    "impact": "high",
                },
                {
                    "name": "Customer Quality Complaints",
                    "description": "Increasing quality issues from customers",
                    "urgency": "high",
                    "impact": "high",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "100% Traceability",
                    "description": "Complete forward/backward genealogy",
                    "timeframe": "12 months",
                    "measurable": "100% product genealogy coverage",
                },
                {
                    "name": "Improve OEE to 85%",
                    "description": "Increase overall equipment effectiveness",
                    "timeframe": "18 months",
                    "measurable": "OEE from 72% to 85%",
                },
                {
                    "name": "Reduce Defects by 50%",
                    "description": "Cut defect rate in half",
                    "timeframe": "12 months",
                    "measurable": "Defect PPM from 500 to 250",
                },
                {
                    "name": "Eliminate Paper",
                    "description": "100% electronic work instructions",
                    "timeframe": "9 months",
                    "measurable": "Zero paper on shop floor",
                },
                {
                    "name": "Real-Time ERP Integration",
                    "description": "Automated SAP synchronization",
                    "timeframe": "6 months",
                    "measurable": "< 5 minute data latency",
                },
                {
                    "name": "Pass FDA Audit",
                    "description": "Zero 483 observations",
                    "timeframe": "Ongoing",
                    "measurable": "Zero critical findings",
                },
                {
                    "name": "Reduce Downtime 30%",
                    "description": "Minimize unplanned equipment stops",
                    "timeframe": "12 months",
                    "measurable": "Downtime from 12% to 8%",
                },
                {
                    "name": "Increase First Pass Yield",
                    "description": "Reduce scrap and rework",
                    "timeframe": "12 months",
                    "measurable": "FPY from 92% to 97%",
                },
                {
                    "name": "Standardize Across Plants",
                    "description": "Common MES in all 8 plants",
                    "timeframe": "24 months",
                    "measurable": "8 plants on OPCenter",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "Complete Traceability",
                    "description": "Instant genealogy for any product",
                    "benefit_type": "compliance",
                    "quantified_benefit": "100% traceability in < 30 seconds",
                },
                {
                    "name": "Manufacturing Excellence",
                    "description": "World-class OEE performance",
                    "benefit_type": "operational",
                    "quantified_benefit": "OEE 85%, top quartile",
                },
                {
                    "name": "Quality Leadership",
                    "description": "Industry-leading quality metrics",
                    "benefit_type": "quality",
                    "quantified_benefit": "50% defect reduction, 97% FPY",
                },
                {
                    "name": "Digital Transformation",
                    "description": "Paperless, connected factory",
                    "benefit_type": "operational",
                    "quantified_benefit": "100% paperless, $2M savings",
                },
                {
                    "name": "System Integration",
                    "description": "Seamless ERP-MES integration",
                    "benefit_type": "technical",
                    "quantified_benefit": "Real-time data sync, zero manual entry",
                },
                {
                    "name": "Regulatory Confidence",
                    "description": "Audit-ready at all times",
                    "benefit_type": "compliance",
                    "quantified_benefit": "Zero FDA 483 observations",
                },
                {
                    "name": "Equipment Reliability",
                    "description": "Predictable and reliable assets",
                    "benefit_type": "operational",
                    "quantified_benefit": "30% downtime reduction, $3M impact",
                },
                {
                    "name": "Operational Efficiency",
                    "description": "Labor productivity improvement",
                    "benefit_type": "financial",
                    "quantified_benefit": "$5M annual savings",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Paperless Operations",
                    "description": "All instructions and records electronic",
                    "rationale": "Eliminate errors and improve efficiency",
                },
                {
                    "name": "Real-Time Data",
                    "description": "Instant visibility into operations",
                    "rationale": "Enable rapid decision-making",
                },
                {
                    "name": "Complete Traceability",
                    "description": "Track everything, everywhere",
                    "rationale": "Regulatory compliance and quality",
                },
                {
                    "name": "Automated Integration",
                    "description": "No manual data entry between systems",
                    "rationale": "Eliminate errors and delays",
                },
                {
                    "name": "Operator-Centric Design",
                    "description": "Easy-to-use interfaces",
                    "rationale": "Drive user adoption",
                },
                {
                    "name": "Quality by Design",
                    "description": "Quality checks embedded in process",
                    "rationale": "Prevent defects proactively",
                },
                {
                    "name": "Standardized Processes",
                    "description": "Common workflows across plants",
                    "rationale": "Consistency and scalability",
                },
                {
                    "name": "Equipment Integration",
                    "description": "Connect all machines",
                    "rationale": "Eliminate manual data collection",
                },
                {
                    "name": "Audit-Ready",
                    "description": "Always compliant and audit-ready",
                    "rationale": "Reduce regulatory risk",
                },
                {
                    "name": "Continuous Improvement",
                    "description": "Data-driven optimization",
                    "rationale": "Sustain competitive advantage",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "System Availability",
                    "type": "performance",
                    "description": "MES available 99.9% of time",
                    "priority": "critical",
                },
                {
                    "name": "Response Time",
                    "type": "performance",
                    "description": "Screen response < 2 seconds",
                    "priority": "critical",
                },
                {
                    "name": "Data Collection Frequency",
                    "type": "performance",
                    "description": "Equipment data every 1 second",
                    "priority": "high",
                },
                {
                    "name": "21 CFR Part 11 Compliance",
                    "type": "compliance",
                    "description": "Electronic signature and audit trail",
                    "priority": "critical",
                },
                {
                    "name": "Genealogy Depth",
                    "type": "functional",
                    "description": "Unlimited forward/backward traceability",
                    "priority": "critical",
                },
                {
                    "name": "Concurrent Users",
                    "type": "capacity",
                    "description": "Support 500 concurrent operators",
                    "priority": "high",
                },
                {
                    "name": "Data Retention",
                    "type": "compliance",
                    "description": "15 years for regulated data",
                    "priority": "critical",
                },
                {
                    "name": "Equipment Connectivity",
                    "type": "integration",
                    "description": "Support OPC UA, Modbus, proprietary protocols",
                    "priority": "high",
                },
                {
                    "name": "ERP Integration",
                    "type": "integration",
                    "description": "Real-time SAP S/4HANA integration",
                    "priority": "high",
                },
                {
                    "name": "Mobile Support",
                    "type": "functional",
                    "description": "Operator mobile app for Android/iOS",
                    "priority": "medium",
                },
                {
                    "name": "Disaster Recovery",
                    "type": "continuity",
                    "description": "RPO < 15 minutes, RTO < 2 hours",
                    "priority": "high",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget Cap",
                    "type": "financial",
                    "description": "Total project budget $8M",
                },
                {
                    "name": "Tight Timeline",
                    "type": "schedule",
                    "description": "First plant go-live in 9 months",
                },
                {
                    "name": "Legacy Equipment",
                    "type": "technical",
                    "description": "Old machines with limited connectivity",
                },
                {
                    "name": "Skills Gap",
                    "type": "resource",
                    "description": "Limited MES expertise internally",
                },
                {
                    "name": "Network Limitations",
                    "type": "technical",
                    "description": "Plant floor network bandwidth constraints",
                },
                {
                    "name": "Change Resistance",
                    "type": "organizational",
                    "description": "Operators accustomed to paper",
                },
                {
                    "name": "Regulatory Validation",
                    "type": "compliance",
                    "description": "FDA validation adds 4 months",
                },
                {
                    "name": "24/7 Operations",
                    "type": "operational",
                    "description": "No downtime for cutover",
                },
                {
                    "name": "Multi-Site Complexity",
                    "type": "organizational",
                    "description": "8 plants with different processes",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "MES Readiness",
                    "type": "maturity",
                    "description": "Assess plant readiness for MES",
                    "result": "Score: 65/100 - Moderate preparation needed",
                },
                {
                    "name": "Equipment Connectivity",
                    "type": "technical",
                    "description": "Evaluate machine integration feasibility",
                    "result": "70% machines connectable, 30% require upgrades",
                },
                {
                    "name": "Process Standardization",
                    "type": "business",
                    "description": "Assess process variation across plants",
                    "result": "High variation, standardization project required",
                },
                {
                    "name": "Network Infrastructure",
                    "type": "technical",
                    "description": "Evaluate plant network capabilities",
                    "result": "5 of 8 plants need network upgrades",
                },
                {
                    "name": "ROI Analysis",
                    "type": "financial",
                    "description": "Calculate expected return",
                    "result": "Projected 200% ROI in 4 years",
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
                    "description": "Project charter and team formation",
                },
                {
                    "name": "Pilot Line Selected",
                    "date": "2024 - 02 - 01",
                    "milestone": False,
                    "description": "Pilot production line identified",
                },
                {
                    "name": "Detailed Design Complete",
                    "date": "2024 - 04 - 30",
                    "milestone": True,
                    "description": "Functional design and configuration specs",
                },
                {
                    "name": "Pilot Line Cutover",
                    "date": "2024 - 09 - 30",
                    "milestone": True,
                    "description": "First production line live",
                },
                {
                    "name": "Pilot Validated",
                    "date": "2024 - 11 - 30",
                    "milestone": True,
                    "description": "Pilot line validation complete",
                },
                {
                    "name": "Plant 1 Rollout Complete",
                    "date": "2025 - 03 - 31",
                    "milestone": True,
                    "description": "All lines in plant 1 on MES",
                },
                {
                    "name": "Plants 2 - 4 Complete",
                    "date": "2025 - 09 - 30",
                    "milestone": True,
                    "description": "Next 3 plants deployed",
                },
                {
                    "name": "Plants 5 - 8 Complete",
                    "date": "2026 - 03 - 31",
                    "milestone": True,
                    "description": "All plants on OPCenter",
                },
                {
                    "name": "Project Closure",
                    "date": "2026 - 06 - 30",
                    "milestone": True,
                    "description": "Project complete and handed to operations",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Project Management",
                    "description": "Overall program governance",
                    "duration_weeks": 130,
                    "team_size": 4,
                },
                {
                    "name": "Functional Design",
                    "description": "Process mapping and requirements",
                    "duration_weeks": 16,
                    "team_size": 12,
                },
                {
                    "name": "System Configuration",
                    "description": "OPCenter configuration",
                    "duration_weeks": 20,
                    "team_size": 8,
                },
                {
                    "name": "Equipment Integration",
                    "description": "PLC and SCADA connectivity",
                    "duration_weeks": 24,
                    "team_size": 6,
                },
                {
                    "name": "ERP Integration",
                    "description": "SAP S/4HANA integration",
                    "duration_weeks": 16,
                    "team_size": 4,
                },
                {
                    "name": "Testing & Validation",
                    "description": "IQ/OQ/PQ validation",
                    "duration_weeks": 20,
                    "team_size": 10,
                },
                {
                    "name": "Training Program",
                    "description": "Operator and engineer training",
                    "duration_weeks": 12,
                    "team_size": 4,
                },
                {
                    "name": "Change Management",
                    "description": "User adoption program",
                    "duration_weeks": 52,
                    "team_size": 3,
                },
                {
                    "name": "Pilot Deployment",
                    "description": "First line deployment",
                    "duration_weeks": 32,
                    "team_size": 15,
                },
                {
                    "name": "Multi-Site Rollout",
                    "description": "Replicate to 8 plants",
                    "duration_weeks": 78,
                    "team_size": 20,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Functional Design Specification",
                    "type": "document",
                    "due_phase": "design",
                    "owner": "Solution Architect",
                },
                {
                    "name": "Configured MES System",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "Configuration Lead",
                },
                {
                    "name": "Equipment Interfaces",
                    "type": "integration",
                    "due_phase": "build",
                    "owner": "Integration Engineer",
                },
                {
                    "name": "SAP Integration",
                    "type": "integration",
                    "due_phase": "build",
                    "owner": "ERP Integration Lead",
                },
                {
                    "name": "Validation Documentation (IQ/OQ/PQ)",
                    "type": "compliance",
                    "due_phase": "test",
                    "owner": "Validation Lead",
                },
                {
                    "name": "Training Curriculum",
                    "type": "training",
                    "due_phase": "prepare",
                    "owner": "Training Manager",
                },
                {
                    "name": "Standard Operating Procedures",
                    "type": "document",
                    "due_phase": "prepare",
                    "owner": "Process Engineer",
                },
                {
                    "name": "Cutover Plan",
                    "type": "document",
                    "due_phase": "deploy",
                    "owner": "Deployment Manager",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "Design Complete",
                    "date": "2024 - 04 - 30",
                    "description": "Requirements and design finalized",
                },
                {
                    "name": "Pilot Operational",
                    "date": "2024 - 11 - 30",
                    "description": "Pilot line validated and stable",
                },
                {
                    "name": "First Plant Complete",
                    "date": "2025 - 03 - 31",
                    "description": "Plant 1 fully deployed",
                },
                {
                    "name": "Half Plants Deployed",
                    "date": "2025 - 09 - 30",
                    "description": "4 of 8 plants on MES",
                },
                {
                    "name": "Full Deployment",
                    "date": "2026 - 03 - 31",
                    "description": "All 8 plants operational",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "Manufacturing Plant 1",
                    "location": "Detroit, MI",
                    "tier": "Tier II",
                    "size_sqm": 25000,
                    "description": "Assembly plant with 6 production lines",
                },
                {
                    "name": "Manufacturing Plant 2",
                    "location": "Atlanta, GA",
                    "tier": "Tier II",
                    "size_sqm": 30000,
                    "description": "Process manufacturing facility",
                },
                {
                    "name": "Central Data Center",
                    "location": "Chicago, IL",
                    "tier": "Tier III",
                    "size_sqm": 500,
                    "description": "Centralized MES servers",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "MES Application Servers",
                    "type": "virtual-machine",
                    "quantity": 4,
                    "location": "Chicago DC",
                    "specs": "VMware, 16 cores, 64GB RAM",
                },
                {
                    "name": "SQL Server Cluster",
                    "type": "virtual-machine",
                    "quantity": 2,
                    "location": "Chicago DC",
                    "specs": "VMware, 32 cores, 256GB RAM",
                },
                {
                    "name": "Edge Servers",
                    "type": "industrial-pc",
                    "quantity": 8,
                    "location": "Plant Floor",
                    "specs": "Advantech IPC, 8 cores, 16GB RAM",
                },
                {
                    "name": "HMI Terminals",
                    "type": "operator-station",
                    "quantity": 120,
                    "location": "Plant Floor",
                    "specs": "15 - inch touchscreen, Windows 10 IoT",
                },
                {
                    "name": "Industrial Switches",
                    "type": "network-switch",
                    "quantity": 24,
                    "location": "Plant Floor",
                    "specs": "Cisco IE - 4000, 24 - port",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "Plant Floor Network",
                    "type": "industrial-ethernet",
                    "coverage": "Plant",
                    "bandwidth_mbps": 1000,
                    "provider": "Internal",
                },
                {
                    "name": "WAN to Data Center",
                    "type": "wan",
                    "coverage": "8 Plants",
                    "bandwidth_mbps": 1000,
                    "provider": "AT&T",
                },
                {
                    "name": "SQL Replication Network",
                    "type": "private",
                    "coverage": "Data Center",
                    "bandwidth_mbps": 10000,
                    "provider": "Internal",
                },
                {
                    "name": "Internet Gateway",
                    "type": "internet",
                    "coverage": "External",
                    "bandwidth_mbps": 1000,
                    "provider": "Comcast",
                },
            ]
        ),
    )


def seed_siemens_opcenter(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(vendor_name="Siemens").first()
            if existing:
                print("⚠️  Siemens OPCenter template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_siemens_opcenter_template()
            db.session.add(template)
            db.session.commit()

            print("✅ Siemens OPCenter template seeded successfully!")
            print(f"   - Vendor: {template.vendor_name}")
            print(f"   - Technology Layer: ✅ Complete")
            print(f"   - Strategy Layer: ✅ Complete (20 capabilities, 6 value streams)")
            print(
                f"   - Business Layer: ✅ Complete (10 services, 6 processes, 8 objects, 10 actors, 9 products)"
            )
            print(
                f"   - Application Layer: ✅ Complete (13 components, 10 services, 7 interfaces, 8 data objects, 10 functions)"
            )
            print(
                f"   - Motivation Layer: ✅ Complete (10 stakeholders, 10 drivers, 9 goals, 8 outcomes, 10 principles, 11 requirements, 9 constraints, 5 assessments)"
            )
            print(
                f"   - Implementation Layer: ✅ Complete (9 events, 10 work packages, 8 deliverables, 5 plateaus)"
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
            print(f"❌ Error seeding Siemens OPCenter template: {str(e)}")
            import traceback

            traceback.print_exc()

            raise


if __name__ == "__main__":
    seed_siemens_opcenter()
