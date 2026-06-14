"""
IBM Maximo Vendor Template Seed Data

Maintenance & Asset Management capabilities for manufacturing: Preventive Maintenance,
Work Order Management, Asset Lifecycle, MRO Inventory, Reliability Engineering.

Run with: python manage.py seed-vendor-ibm-maximo
"""
import json

from app import create_app, db
from app.models import VendorStackTemplate
from config import DevelopmentConfig


def create_ibm_maximo_template():
    """IBM Maximo - Enterprise Asset Management Platform"""
    return VendorStackTemplate(
        vendor_name="IBM Maximo",
        name="IBM Maximo Application Suite - Enterprise Asset Management",
        description="Comprehensive enterprise asset management platform for manufacturing covering maintenance, reliability, asset lifecycle, MRO inventory, and predictive analytics",
        # ==================== TECHNOLOGY LAYER ====================
        platform="hybrid",
        primary_language="java",
        framework="Spring Boot",
        framework_version="2.7",
        primary_database="db2",
        database_version="11.5",
        container_runtime="openshift",
        orchestration="kubernetes",
        service_mesh="istio",
        api_standard="REST",
        api_gateway="api-connect",
        message_broker="kafka",
        auth_provider="ibm-security-verify",
        secrets_manager="ibm-secrets-manager",
        logging_framework="elastic-logstash",
        metrics_platform="prometheus",
        apm_tool="instana",
        tracing_tool="instana",
        build_tool="maven",
        ci_cd_platform="ibm-cloud-continuous-delivery",
        sast_tool="appscan",
        dast_tool="appscan",
        dependency_scanner="xforce-exchange",
        nodes=json.dumps(
            [
                {
                    "name": "Maximo Application Server",
                    "type": "vm",
                    "os": "Red Hat Enterprise Linux",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "DB2 Database Server",
                    "type": "vm",
                    "os": "Red Hat Enterprise Linux",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
                {
                    "name": "Integration Server",
                    "type": "vm",
                    "os": "Red Hat Enterprise Linux",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "Maximo Monitor (IoT) Server",
                    "type": "vm",
                    "os": "Red Hat Enterprise Linux",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "Maximo Health/Predict AI Server",
                    "type": "vm",
                    "os": "Red Hat Enterprise Linux",
                    "cpu_cores": 32,
                    "ram_gb": 128,
                },
            ]
        ),
        devices=json.dumps(
            [
                {
                    "name": "Maximo Mobile (Technician App)",
                    "type": "mobile-device",
                    "description": "iOS/Android work order management",
                },
                {
                    "name": "Barcode Scanner",
                    "type": "scanner",
                    "description": "Asset tagging and inventory",
                },
                {
                    "name": "IoT Sensors",
                    "type": "iot-device",
                    "description": "Equipment condition monitoring",
                },
                {
                    "name": "CMMS Kiosk",
                    "type": "industrial-pc",
                    "description": "Shop floor work order interface",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {"name": "IBM Maximo Manage", "type": "eam-platform", "version": "8.11"},
                {"name": "IBM Maximo Monitor", "type": "iot-platform", "version": "8.11"},
                {"name": "IBM Maximo Health", "type": "asset-health", "version": "8.11"},
                {"name": "IBM Maximo Predict", "type": "predictive-maintenance", "version": "8.11"},
                {"name": "IBM Maximo Visual Inspection", "type": "ai-vision", "version": "8.11"},
                {"name": "IBM Maximo Mobile", "type": "mobile-app", "version": "8.11"},
                {"name": "IBM DB2 Database", "type": "database", "version": "11.5"},
                {"name": "Red Hat OpenShift", "type": "container-platform", "version": "4.12"},
                {"name": "IBM Watson Studio", "type": "ai-platform", "version": "Latest"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "Work Order Management Service",
                    "type": "cmms-service",
                    "description": "Work order creation, scheduling, execution",
                },
                {
                    "name": "Preventive Maintenance Service",
                    "type": "pm-service",
                    "description": "PM schedule generation and execution",
                },
                {
                    "name": "Asset Management Service",
                    "type": "asset-service",
                    "description": "Asset registry, lifecycle, and hierarchy",
                },
                {
                    "name": "Inventory Management Service",
                    "type": "inventory-service",
                    "description": "MRO parts and storeroom management",
                },
                {
                    "name": "Predictive Analytics Service",
                    "type": "ai-service",
                    "description": "Asset failure prediction",
                },
                {
                    "name": "IoT Data Ingestion Service",
                    "type": "iot-service",
                    "description": "Sensor data collection and processing",
                },
                {
                    "name": "Integration Service",
                    "type": "integration-service",
                    "description": "ERP/MES integration",
                },
                {
                    "name": "Mobile Sync Service",
                    "type": "mobile-service",
                    "description": "Offline mobile synchronization",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "Maximo EAR File",
                    "type": "deployment-package",
                    "size_mb": 500,
                    "registry": "IBM Repository",
                },
                {
                    "name": "Integration Object Structure",
                    "type": "api-definition",
                    "size_mb": 5,
                    "registry": "Maximo Repository",
                },
                {
                    "name": "Automation Script",
                    "type": "script",
                    "size_mb": 1,
                    "registry": "Maximo Repository",
                },
                {
                    "name": "DB2 Backup",
                    "type": "backup-archive",
                    "size_mb": 100000,
                    "registry": "Backup Storage",
                },
                {
                    "name": "Mobile App Package",
                    "type": "mobile-app",
                    "size_mb": 50,
                    "registry": "App Store",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {"name": "Plant Network", "type": "lan", "bandwidth_mbps": 10000, "latency_ms": 1},
                {
                    "name": "IoT Network",
                    "type": "industrial-network",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 5,
                },
                {"name": "WAN to ERP", "type": "wan", "bandwidth_mbps": 1000, "latency_ms": 10},
                {
                    "name": "Cloud Pak Network",
                    "type": "cloud-network",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 20,
                },
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="IBM Corporation",
        market_position="leader",
        company_size="enterprise",
        founded_year=1911,
        headquarters="Armonk, NY",
        revenue_usd=60500000000,
        customer_count=50000,
        market_share_percentage=15.0,
        acquisition_risk="very-low",
        financial_health="excellent",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                # MAINTENANCE & ASSET MANAGEMENT CAPABILITIES
                {
                    "name": "Work Order Management",
                    "description": "Create, schedule, dispatch, execute, and close work orders",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Preventive Maintenance",
                    "description": "PM schedule generation, route-based maintenance, meter-based triggers",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Predictive Maintenance",
                    "description": "AI-powered failure prediction, anomaly detection, condition-based maintenance",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Asset Lifecycle Management",
                    "description": "Asset registry, commissioning, operation, maintenance, retirement",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Asset Health & Criticality",
                    "description": "Asset health scoring, criticality ranking, risk assessment",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "MRO Inventory Management",
                    "description": "Storeroom management, parts cataloging, reorder point, ABC analysis",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Procurement & Purchasing",
                    "description": "Purchase requisitions, POs, vendor management, receiving",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Reliability Engineering",
                    "description": "RCM, FMEA, root cause analysis, failure tracking",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Calibration Management",
                    "description": "Instrument calibration schedules, due date tracking, compliance",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Failure & Downtime Tracking",
                    "description": "Equipment failure recording, downtime analysis, MTBF/MTTR metrics",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Mobile Work Order Execution",
                    "description": "Mobile app for technicians with offline capability",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Condition Monitoring",
                    "description": "IoT sensor integration, vibration analysis, temperature monitoring",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Work Planning & Scheduling",
                    "description": "Work plan templates, labor/material planning, scheduling optimization",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Service Level Agreements (SLA)",
                    "description": "SLA tracking, breach alerting, vendor performance",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Warranty Management",
                    "description": "Equipment warranty tracking, claim submission, recovery",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "Safety Management",
                    "description": "Lock-out/tag-out, safety permits, hazard tracking",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Document Management",
                    "description": "Equipment manuals, procedures, drawings, as-built documentation",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Labor Management",
                    "description": "Craft tracking, labor hours, crew scheduling, skill certifications",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "KPI & Analytics",
                    "description": "OEE, equipment availability, PM compliance, cost analysis",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Asset Mobility & Transfer",
                    "description": "Equipment moves, transfers between locations, asset tracking",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "Compliance & Audit",
                    "description": "Regulatory compliance tracking, audit trails, e-signature",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Visual Inspection AI",
                    "description": "AI-powered image analysis for asset inspection",
                    "coverage_percentage": 85,
                    "maturity_level": "developing",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Breakdown-to-Repair",
                    "stages": [
                        "Equipment Failure",
                        "Work Order Creation",
                        "Diagnosis",
                        "Parts Procurement",
                        "Repair",
                        "Testing",
                        "Return to Service",
                    ],
                    "description": "Reactive maintenance workflow",
                },
                {
                    "name": "PM-Schedule-to-Completion",
                    "stages": [
                        "PM Generation",
                        "Planning",
                        "Scheduling",
                        "Execution",
                        "Confirmation",
                        "PM History",
                    ],
                    "description": "Preventive maintenance lifecycle",
                },
                {
                    "name": "Predict-to-Prevent",
                    "stages": [
                        "Condition Monitoring",
                        "Anomaly Detection",
                        "Failure Prediction",
                        "Proactive Work Order",
                        "Execution",
                        "Validation",
                    ],
                    "description": "Predictive maintenance workflow",
                },
                {
                    "name": "Asset-Acquisition-to-Disposal",
                    "stages": [
                        "Procurement",
                        "Commissioning",
                        "Operation",
                        "Maintenance",
                        "Decommission",
                        "Disposal",
                    ],
                    "description": "Complete asset lifecycle",
                },
                {
                    "name": "Requisition-to-Receipt",
                    "stages": [
                        "Parts Request",
                        "Approval",
                        "PO Creation",
                        "Vendor Delivery",
                        "Receiving",
                        "Storeroom Entry",
                    ],
                    "description": "MRO procurement",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "Maximo On-Premises Deployment",
                    "description": "Traditional on-premises installation",
                    "timeline_months": 12,
                    "risk_level": "medium",
                },
                {
                    "name": "Maximo Application Suite (SaaS)",
                    "description": "Cloud-hosted Maximo",
                    "timeline_months": 6,
                    "risk_level": "low",
                },
                {
                    "name": "Hybrid Deployment",
                    "description": "Core on-prem, Monitor/Predict in cloud",
                    "timeline_months": 9,
                    "risk_level": "medium",
                },
                {
                    "name": "Phased Rollout by Site",
                    "description": "Deploy plant-by-plant",
                    "timeline_months": 24,
                    "risk_level": "low",
                },
                {
                    "name": "AI-First Approach",
                    "description": "Deploy Predict/Health alongside Manage",
                    "timeline_months": 15,
                    "risk_level": "high",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Maintenance Management Service",
                    "description": "Work order lifecycle management",
                    "service_type": "internal",
                    "sla_commitment": "P1: 1 hour response, P2: 4 hours, P3: 24 hours",
                },
                {
                    "name": "Asset Registry Service",
                    "description": "Centralized asset information",
                    "service_type": "internal",
                    "sla_commitment": "Real-time asset data accuracy 99%",
                },
                {
                    "name": "MRO Storeroom Service",
                    "description": "Spare parts availability",
                    "service_type": "internal",
                    "sla_commitment": "Critical parts stock-out < 2%",
                },
                {
                    "name": "Predictive Analytics Service",
                    "description": "Failure prediction and prevention",
                    "service_type": "internal",
                    "sla_commitment": "Prediction accuracy > 80%",
                },
                {
                    "name": "Mobile Field Service",
                    "description": "Mobile work order execution",
                    "service_type": "internal",
                    "sla_commitment": "99% mobile app availability",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Corrective Maintenance",
                    "description": "Respond to equipment failures",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Failure Report",
                        "Work Order Creation",
                        "Technician Assignment",
                        "Diagnosis",
                        "Repair",
                        "Testing",
                        "Close",
                    ],
                    "cycle_time": "4 - 24 hours",
                    "kpis": ["MTTR", "First Time Fix Rate", "Equipment Availability"],
                },
                {
                    "name": "Preventive Maintenance",
                    "description": "Scheduled maintenance execution",
                    "automation_level": "fully-automated",
                    "steps": [
                        "PM Generation",
                        "Work Plan Assignment",
                        "Material Reservation",
                        "Scheduling",
                        "Execution",
                        "Confirmation",
                        "Next PM Schedule",
                    ],
                    "cycle_time": "1 - 8 hours per PM",
                    "kpis": ["PM Compliance", "PM Overdue %", "Equipment Uptime"],
                },
                {
                    "name": "Predictive Maintenance",
                    "description": "Condition-based maintenance",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Sensor Data Collection",
                        "Anomaly Detection",
                        "Health Score Calculation",
                        "Prediction Trigger",
                        "Work Order Creation",
                        "Repair",
                        "Model Feedback",
                    ],
                    "cycle_time": "Varies",
                    "kpis": [
                        "Prediction Accuracy",
                        "Unplanned Downtime Reduction",
                        "Cost Avoidance",
                    ],
                },
                {
                    "name": "Parts Replenishment",
                    "description": "MRO inventory management",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Usage Tracking",
                        "Reorder Point Trigger",
                        "PR Creation",
                        "PO Generation",
                        "Receiving",
                        "Storeroom Update",
                    ],
                    "cycle_time": "3 - 7 days",
                    "kpis": ["Inventory Turns", "Stock-Out Rate", "Carrying Cost"],
                },
                {
                    "name": "Asset Commissioning",
                    "description": "New equipment setup",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Asset Creation",
                        "Hierarchy Assignment",
                        "PM Schedule Setup",
                        "Spare Parts Catalog",
                        "Baseline Recording",
                        "Go-Live",
                    ],
                    "cycle_time": "1 - 2 weeks",
                    "kpis": ["Time to Commission", "Data Quality", "PM Schedule Accuracy"],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Work Order",
                    "description": "Maintenance work order",
                    "lifecycle": "draft -> approved -> assigned -> in-progress -> completed -> closed",
                },
                {
                    "name": "Asset",
                    "description": "Equipment or facility component",
                    "lifecycle": "commissioned -> operating -> maintenance -> decommissioned",
                },
                {
                    "name": "PM Record",
                    "description": "Preventive maintenance schedule",
                    "lifecycle": "active -> generated -> executed -> forecast",
                },
                {
                    "name": "Inventory Item",
                    "description": "MRO spare part",
                    "lifecycle": "cataloged -> stocked -> issued -> reordered",
                },
                {
                    "name": "Purchase Order",
                    "description": "MRO procurement",
                    "lifecycle": "draft -> approved -> sent -> received -> closed",
                },
                {
                    "name": "Failure Report",
                    "description": "Equipment failure record",
                    "lifecycle": "reported -> diagnosed -> resolved -> analyzed",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Maintenance Technician",
                    "description": "Executes maintenance work orders",
                    "responsibilities": [
                        "Work Order Execution",
                        "Failure Diagnosis",
                        "Parts Usage Recording",
                        "Mobile App Usage",
                    ],
                },
                {
                    "name": "Maintenance Planner",
                    "description": "Plans maintenance work",
                    "responsibilities": [
                        "Work Planning",
                        "Material Planning",
                        "Job Plan Creation",
                        "Work Prioritization",
                    ],
                },
                {
                    "name": "Maintenance Scheduler",
                    "description": "Schedules maintenance activities",
                    "responsibilities": [
                        "Work Scheduling",
                        "Resource Allocation",
                        "Shutdown Planning",
                        "Schedule Optimization",
                    ],
                },
                {
                    "name": "Reliability Engineer",
                    "description": "Analyzes failure patterns",
                    "responsibilities": [
                        "RCA",
                        "FMEA",
                        "PM Optimization",
                        "Predictive Model Tuning",
                    ],
                },
                {
                    "name": "Storeroom Attendant",
                    "description": "Manages MRO inventory",
                    "responsibilities": [
                        "Parts Issuing",
                        "Receiving",
                        "Cycle Counting",
                        "Reorder Processing",
                    ],
                },
                {
                    "name": "Maintenance Supervisor",
                    "description": "Oversees maintenance operations",
                    "responsibilities": [
                        "Work Approval",
                        "Crew Management",
                        "KPI Monitoring",
                        "Escalation Handling",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "Maximo Manage",
                    "description": "Core EAM platform",
                    "target_market": "All Manufacturing",
                },
                {
                    "name": "Maximo Monitor",
                    "description": "IoT and condition monitoring",
                    "target_market": "Process and Discrete Manufacturing",
                },
                {
                    "name": "Maximo Health",
                    "description": "Asset health scoring",
                    "target_market": "Asset-Intensive Industries",
                },
                {
                    "name": "Maximo Predict",
                    "description": "Predictive maintenance AI",
                    "target_market": "Large Manufacturers",
                },
                {
                    "name": "Maximo Visual Inspection",
                    "description": "AI-powered visual inspection",
                    "target_market": "Quality-Critical Manufacturing",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "Maximo UI (Work Centers)",
                    "type": "web-app",
                    "description": "Main Maximo user interface",
                    "technology": "Java/JSP",
                },
                {
                    "name": "Maximo Mobile App",
                    "type": "mobile-app",
                    "description": "Technician mobile application",
                    "technology": "React Native",
                },
                {
                    "name": "Maximo Monitor Dashboard",
                    "type": "web-app",
                    "description": "IoT monitoring dashboard",
                    "technology": "Node.js/React",
                },
                {
                    "name": "Maximo Health Insights",
                    "type": "web-app",
                    "description": "Asset health analytics",
                    "technology": "Python/React",
                },
                {
                    "name": "Maximo Predict Engine",
                    "type": "ai-service",
                    "description": "Predictive analytics engine",
                    "technology": "Python/Watson Studio",
                },
                {
                    "name": "Integration Framework",
                    "type": "integration-middleware",
                    "description": "MIF/MEA integration layer",
                    "technology": "Java",
                },
                {
                    "name": "REST API Gateway",
                    "type": "api-gateway",
                    "description": "OSLC/REST API",
                    "technology": "Java/Spring",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "OSLC REST API",
                    "type": "REST",
                    "description": "Object Structure API",
                    "endpoints": ["/maximo/oslc/os/{objectstructure}"],
                },
                {
                    "name": "Standard API",
                    "type": "REST",
                    "description": "Standard Maximo API",
                    "endpoints": ["/maximo/api/os/{objectstructure}"],
                },
                {
                    "name": "Custom Integration API",
                    "type": "REST",
                    "description": "Custom integration endpoints",
                    "endpoints": ["/maximo/oslc/os/custom"],
                },
                {
                    "name": "Mobile API",
                    "type": "REST",
                    "description": "Mobile synchronization API",
                    "endpoints": ["/maximo/api/mobile/sync"],
                },
                {
                    "name": "IoT Data Ingestion API",
                    "type": "REST",
                    "description": "Sensor data ingestion",
                    "endpoints": ["/maximo/api/iot/ingest"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "OSLC REST API",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON/XML",
                    "authentication": "LDAP/SAML",
                },
                {
                    "name": "Web Services",
                    "protocol": "SOAP",
                    "data_format": "XML",
                    "authentication": "Basic Auth",
                },
                {
                    "name": "Integration Framework",
                    "protocol": "JMS/HTTP",
                    "data_format": "XML",
                    "authentication": "System Auth",
                },
                {
                    "name": "JDBC Connection",
                    "protocol": "JDBC",
                    "data_format": "SQL",
                    "authentication": "Database",
                },
                {
                    "name": "Kafka Streaming",
                    "protocol": "Kafka",
                    "data_format": "JSON",
                    "authentication": "SASL",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {"name": "WORKORDER", "type": "transactional", "retention_policy": "7 years"},
                {"name": "ASSET", "type": "master", "retention_policy": "Permanent"},
                {"name": "PM", "type": "master", "retention_policy": "Permanent while active"},
                {"name": "INVENTORY", "type": "master", "retention_policy": "Permanent"},
                {"name": "INVUSAGE", "type": "transactional", "retention_policy": "3 years"},
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "Work Order CRUD",
                    "type": "CRUD",
                    "description": "Create, read, update, delete work orders",
                },
                {
                    "name": "PM Generation",
                    "type": "batch-process",
                    "description": "Generate preventive maintenance work orders",
                },
                {
                    "name": "Failure Prediction",
                    "type": "ai-inference",
                    "description": "Predict asset failures using ML models",
                },
                {
                    "name": "Auto-Replenishment",
                    "type": "business-logic",
                    "description": "Automatically generate reorder requisitions",
                },
                {
                    "name": "Workflow Routing",
                    "type": "workflow",
                    "description": "Route approvals based on business rules",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "VP of Manufacturing",
                    "role": "executive",
                    "concerns": ["Equipment Uptime", "Maintenance Cost", "Asset Performance"],
                    "influence": "high",
                },
                {
                    "name": "Maintenance Manager",
                    "role": "senior-management",
                    "concerns": ["PM Compliance", "MTTR", "Technician Productivity"],
                    "influence": "high",
                },
                {
                    "name": "Reliability Engineer",
                    "role": "technical-expert",
                    "concerns": ["Asset Reliability", "Failure Analysis", "RCM"],
                    "influence": "medium",
                },
                {
                    "name": "Plant Manager",
                    "role": "operations",
                    "concerns": ["Production Uptime", "Maintenance Schedule Impact", "Safety"],
                    "influence": "high",
                },
                {
                    "name": "CFO",
                    "role": "executive",
                    "concerns": ["Maintenance Budget", "Asset Depreciation", "ROI"],
                    "influence": "high",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Equipment Uptime Maximization",
                    "description": "Minimize unplanned downtime",
                    "urgency": "critical",
                    "impact": "high",
                },
                {
                    "name": "Maintenance Cost Reduction",
                    "description": "Optimize maintenance spend",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Shift to Predictive Maintenance",
                    "description": "Move from reactive to predictive",
                    "urgency": "medium",
                    "impact": "transformational",
                },
                {
                    "name": "Regulatory Compliance",
                    "description": "Maintain calibration and safety compliance",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Asset Life Extension",
                    "description": "Extend equipment useful life",
                    "urgency": "medium",
                    "impact": "high",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "Achieve 95% Equipment Availability",
                    "description": "Maximize production uptime",
                    "timeframe": "12 months",
                    "measurable": "OEE Availability > 95%",
                },
                {
                    "name": "Reduce Maintenance Cost by 20%",
                    "description": "Optimize maintenance spend",
                    "timeframe": "24 months",
                    "measurable": "Cost per unit produced",
                },
                {
                    "name": "85% PM Compliance",
                    "description": "Execute preventive maintenance on time",
                    "timeframe": "12 months",
                    "measurable": "PM compliance > 85%",
                },
                {
                    "name": "50% Reduction in Unplanned Downtime",
                    "description": "Shift to predictive maintenance",
                    "timeframe": "18 months",
                    "measurable": "Unplanned downtime hours",
                },
                {
                    "name": "MTTR < 4 Hours",
                    "description": "Fast failure resolution",
                    "timeframe": "12 months",
                    "measurable": "Mean time to repair",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "Increased Production Uptime",
                    "description": "More available production hours",
                    "benefit_type": "operational",
                    "quantified_benefit": "500 additional production hours/year",
                },
                {
                    "name": "Maintenance Cost Savings",
                    "description": "Reduced maintenance spend",
                    "benefit_type": "financial",
                    "quantified_benefit": "$5M annual savings",
                },
                {
                    "name": "Extended Asset Life",
                    "description": "Deferred capital expenditure",
                    "benefit_type": "financial",
                    "quantified_benefit": "$10M capex deferral",
                },
                {
                    "name": "Improved Safety",
                    "description": "Fewer equipment-related incidents",
                    "benefit_type": "safety",
                    "quantified_benefit": "50% reduction in maintenance incidents",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Maintenance as Strategic Asset",
                    "description": "Maintenance drives production performance",
                    "rationale": "Competitive advantage",
                },
                {
                    "name": "Data-Driven Decision Making",
                    "description": "Use analytics to optimize maintenance",
                    "rationale": "Continuous improvement",
                },
                {
                    "name": "Predictive Over Reactive",
                    "description": "Predict and prevent failures",
                    "rationale": "Cost and uptime optimization",
                },
                {
                    "name": "Total Cost of Ownership",
                    "description": "Optimize lifecycle costs, not just acquisition",
                    "rationale": "Financial stewardship",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "System Availability",
                    "type": "performance",
                    "description": "99.5% uptime for Maximo application",
                    "priority": "critical",
                },
                {
                    "name": "Mobile Offline Capability",
                    "type": "functional",
                    "description": "Mobile app works without connectivity",
                    "priority": "high",
                },
                {
                    "name": "IoT Data Ingestion",
                    "type": "performance",
                    "description": "Process 10K sensor readings/second",
                    "priority": "high",
                },
                {
                    "name": "ERP Integration",
                    "type": "functional",
                    "description": "Real-time sync with SAP for procurement",
                    "priority": "critical",
                },
                {
                    "name": "21 CFR Part 11 Compliance",
                    "type": "compliance",
                    "description": "Electronic signature and audit trail",
                    "priority": "critical",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget",
                    "type": "financial",
                    "description": "EAM budget capped at $3M annually",
                },
                {
                    "name": "Timeline",
                    "type": "schedule",
                    "description": "Must deploy within 12 months",
                },
                {
                    "name": "Legacy Integration",
                    "type": "technical",
                    "description": "Integrate with 15 - year-old SCADA",
                },
                {
                    "name": "Data Migration",
                    "type": "data",
                    "description": "Migrate 20 years of maintenance history",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "Current State Assessment",
                    "type": "maturity",
                    "description": "Assess current maintenance maturity",
                    "result": "Score: 2/5 - Reactive maintenance mode",
                },
                {
                    "name": "Asset Criticality Analysis",
                    "type": "risk",
                    "description": "Identify critical assets",
                    "result": "150 critical assets requiring predictive maintenance",
                },
                {
                    "name": "Data Quality Assessment",
                    "type": "technical",
                    "description": "Assess equipment master data quality",
                    "result": "60% data quality - requires cleansing",
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
                    "description": "EAM project initiated",
                },
                {
                    "name": "Asset Data Migration Complete",
                    "date": "2024 - 04 - 01",
                    "milestone": True,
                    "description": "Equipment master data loaded",
                },
                {
                    "name": "Pilot Launch",
                    "date": "2024 - 05 - 01",
                    "milestone": True,
                    "description": "Pilot at one plant",
                },
                {
                    "name": "Full Production",
                    "date": "2024 - 12 - 01",
                    "milestone": True,
                    "description": "Enterprise-wide rollout",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Maximo Configuration",
                    "description": "Configure Maximo application",
                    "duration_weeks": 12,
                    "team_size": 5,
                },
                {
                    "name": "Data Migration",
                    "description": "Migrate asset and maintenance history",
                    "duration_weeks": 16,
                    "team_size": 4,
                },
                {
                    "name": "ERP Integration",
                    "description": "Build SAP integration for procurement",
                    "duration_weeks": 14,
                    "team_size": 3,
                },
                {
                    "name": "Predictive Analytics Setup",
                    "description": "Deploy Health/Predict modules",
                    "duration_weeks": 10,
                    "team_size": 3,
                },
                {
                    "name": "User Training",
                    "description": "Train maintenance staff",
                    "duration_weeks": 8,
                    "team_size": 2,
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
                    "name": "Data Migration Plan",
                    "type": "document",
                    "due_phase": "design",
                    "owner": "Data Architect",
                },
                {
                    "name": "Configured Maximo System",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "Maximo Administrator",
                },
                {
                    "name": "Training Materials",
                    "type": "training",
                    "due_phase": "build",
                    "owner": "Training Lead",
                },
                {
                    "name": "Predictive Models",
                    "type": "ai-model",
                    "due_phase": "build",
                    "owner": "Data Scientist",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "Maximo Manage Ready",
                    "date": "2024 - 04 - 30",
                    "description": "Core EAM configured and tested",
                },
                {
                    "name": "Pilot Success",
                    "date": "2024 - 07 - 01",
                    "description": "Pilot validated with positive ROI",
                },
                {
                    "name": "Production Launch",
                    "date": "2024 - 12 - 01",
                    "description": "All plants on Maximo",
                },
                {
                    "name": "Predictive Maintenance Operational",
                    "date": "2025 - 03 - 01",
                    "description": "Health/Predict deployed",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "Corporate Data Center",
                    "location": "Manufacturing HQ",
                    "tier": "Tier III",
                    "size_sqm": 200,
                    "description": "On-premises Maximo servers",
                },
                {
                    "name": "IBM Cloud Pak",
                    "location": "IBM Cloud",
                    "tier": "Cloud",
                    "size_sqm": "N/A",
                    "description": "Cloud-hosted Monitor/Predict",
                },
                {
                    "name": "Plant Server Room",
                    "location": "Each Manufacturing Site",
                    "tier": "Tier II",
                    "size_sqm": 30,
                    "description": "Local caching servers",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "Maximo Application Server",
                    "type": "server",
                    "quantity": 3,
                    "location": "Data Center",
                    "specs": "Dell R640, 16 - core, 64GB RAM",
                },
                {
                    "name": "DB2 Database Server",
                    "type": "server",
                    "quantity": 2,
                    "location": "Data Center",
                    "specs": "Dell R740, 32 - core, 128GB RAM",
                },
                {
                    "name": "Technician Tablets",
                    "type": "tablet",
                    "quantity": 200,
                    "location": "Field Technicians",
                    "specs": "Samsung Galaxy Tab Active Pro",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "Corporate Network",
                    "type": "lan",
                    "coverage": "HQ",
                    "bandwidth_mbps": 10000,
                    "provider": "Internal",
                },
                {
                    "name": "WAN to Plants",
                    "type": "wan",
                    "coverage": "20 Manufacturing Sites",
                    "bandwidth_mbps": 1000,
                    "provider": "AT&T",
                },
                {
                    "name": "Cloud Connection",
                    "type": "hybrid-cloud",
                    "coverage": "IBM Cloud",
                    "bandwidth_mbps": 10000,
                    "provider": "IBM DirectLink",
                },
            ]
        ),
    )


def seed_ibm_maximo(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(vendor_name="IBM Maximo").first()
            if existing:
                print("⚠️  IBM Maximo template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_ibm_maximo_template()
            db.session.add(template)
            db.session.commit()

            print("✅ IBM Maximo EAM template seeded successfully!")
            print(f"   - Vendor: {template.vendor_name}")
            print(f"   - Maintenance Capabilities: 22")
            print(
                f"   - Primary Focus: Work Orders, PM, Predictive, Asset Lifecycle, MRO Inventory"
            )
            print(f"   - Total ArchiMate Coverage: 100%")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding IBM Maximo template: {str(e)}")
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    seed_ibm_maximo()
