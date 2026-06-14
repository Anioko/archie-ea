"""
SAP S/4HANA Manufacturing ERP Comprehensive Vendor Template Seed Data

Complete ArchiMate 3.2 coverage across ALL layers:
- Strategy Layer
- Business Layer
- Application Layer
- Technology Layer
- Motivation Layer
- Implementation & Migration Layer
- Physical Layer

Run with: python manage.py seed-vendor-sap
"""
import json

from app import create_app, db
from app.commands.vendor_tech_stack_creator import seed_vendor_with_tech_stack
from app.models import User, VendorStackTemplate
from config import DevelopmentConfig


def create_sap_s4hana_template():
    """SAP S/4HANA FULLY COMPREHENSIVE template - ALL ArchiMate 3.2 layers"""
    return VendorStackTemplate(
        vendor_name="SAP",
        name="SAP S/4HANA Manufacturing ERP",
        description="Enterprise resource planning system for discrete and process manufacturing with real-time analytics, intelligent automation, and end-to-end supply chain integration",
        # ==================== TECHNOLOGY LAYER ====================
        platform="hybrid",
        primary_language="abap",
        framework="SAP NetWeaver",
        framework_version="7.5",
        primary_database="sap-hana",
        database_version="2.0 SPS07",
        container_runtime="docker",
        orchestration="kubernetes",
        service_mesh="istio",
        api_standard="OData",
        api_gateway="sap-api-management",
        message_broker="sap-event-mesh",
        auth_provider="sap-identity-authentication",
        secrets_manager="sap-credential-store",
        logging_framework="sap-application-logging",
        metrics_platform="sap-cloud-alm",
        apm_tool="dynatrace",
        tracing_tool="sap-solution-manager",
        build_tool="sap-cloud-platform-sdk",
        ci_cd_platform="sap-continuous-integration",
        sast_tool="checkmarx",
        dast_tool="fortify",
        dependency_scanner="blackduck",
        nodes=json.dumps(
            [
                {
                    "name": "SAP S/4HANA Application Server 1",
                    "type": "bare-metal",
                    "os": "SUSE Linux Enterprise 15",
                    "cpu_cores": 32,
                    "ram_gb": 512,
                },
                {
                    "name": "SAP S/4HANA Application Server 2",
                    "type": "bare-metal",
                    "os": "SUSE Linux Enterprise 15",
                    "cpu_cores": 32,
                    "ram_gb": 512,
                },
                {
                    "name": "SAP HANA Primary Database",
                    "type": "bare-metal",
                    "os": "SUSE Linux Enterprise 15",
                    "cpu_cores": 64,
                    "ram_gb": 2048,
                },
                {
                    "name": "SAP HANA Secondary Database",
                    "type": "bare-metal",
                    "os": "SUSE Linux Enterprise 15",
                    "cpu_cores": 64,
                    "ram_gb": 2048,
                },
                {
                    "name": "SAP Web Dispatcher",
                    "type": "virtual-machine",
                    "os": "SUSE Linux Enterprise 15",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "SAP Solution Manager",
                    "type": "virtual-machine",
                    "os": "SUSE Linux Enterprise 15",
                    "cpu_cores": 24,
                    "ram_gb": 256,
                },
                {
                    "name": "SAP Gateway",
                    "type": "virtual-machine",
                    "os": "SUSE Linux Enterprise 15",
                    "cpu_cores": 16,
                    "ram_gb": 128,
                },
                {
                    "name": "SAP Fiori Frontend Server",
                    "type": "virtual-machine",
                    "os": "SUSE Linux Enterprise 15",
                    "cpu_cores": 16,
                    "ram_gb": 128,
                },
            ]
        ),
        devices=json.dumps(
            [
                {
                    "name": "SAP Router",
                    "type": "network-appliance",
                    "description": "Secure SAP network communication",
                },
                {
                    "name": "Hardware Security Module",
                    "type": "security-appliance",
                    "description": "Cryptographic key management",
                },
                {
                    "name": "SAN Storage Array",
                    "type": "storage",
                    "description": "High-performance storage for HANA",
                },
                {
                    "name": "Load Balancer",
                    "type": "load-balancer",
                    "description": "Application server load balancing",
                },
                {"name": "Firewall Cluster", "type": "firewall", "description": "Network security"},
            ]
        ),
        system_software=json.dumps(
            [
                {"name": "SAP S/4HANA", "type": "erp-system", "version": "2023"},
                {"name": "SAP HANA Database", "type": "in-memory-database", "version": "2.0 SPS07"},
                {"name": "SAP NetWeaver", "type": "application-server", "version": "7.5"},
                {"name": "SAP Fiori", "type": "ui-framework", "version": "3.0"},
                {"name": "SAP Gateway", "type": "api-gateway", "version": "2.0"},
                {"name": "SAP Web Dispatcher", "type": "web-server", "version": "7.85"},
                {"name": "SAP Solution Manager", "type": "alm-platform", "version": "7.2"},
                {"name": "SAP Business Technology Platform", "type": "paas", "version": "Cloud"},
                {"name": "SAP Event Mesh", "type": "message-broker", "version": "Cloud"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "SAP S/4HANA Application Server",
                    "type": "application-runtime",
                    "description": "Core ERP processing engine",
                },
                {
                    "name": "SAP HANA Database Service",
                    "type": "database",
                    "description": "In-memory database with real-time analytics",
                },
                {
                    "name": "SAP Gateway Service",
                    "type": "api-gateway",
                    "description": "OData API exposure and management",
                },
                {
                    "name": "SAP Fiori Launchpad",
                    "type": "web-portal",
                    "description": "Unified user experience",
                },
                {
                    "name": "SAP Integration Suite",
                    "type": "integration-platform",
                    "description": "Enterprise application integration",
                },
                {
                    "name": "SAP Workflow Service",
                    "type": "workflow-engine",
                    "description": "Business process automation",
                },
                {
                    "name": "SAP Master Data Governance",
                    "type": "data-governance",
                    "description": "Master data quality and consistency",
                },
                {
                    "name": "SAP Extended Warehouse Management",
                    "type": "warehouse-system",
                    "description": "Advanced warehouse operations",
                },
                {
                    "name": "SAP Manufacturing Execution",
                    "type": "mes",
                    "description": "Shop floor control and execution",
                },
                {
                    "name": "SAP Quality Management",
                    "type": "quality-system",
                    "description": "Quality planning and inspection",
                },
                {
                    "name": "SAP Plant Maintenance",
                    "type": "maintenance-system",
                    "description": "Asset and maintenance management",
                },
                {
                    "name": "SAP Product Lifecycle Management",
                    "type": "plm-system",
                    "description": "Product design and engineering",
                },
                {
                    "name": "SAP Advanced Planning",
                    "type": "planning-system",
                    "description": "Supply chain planning and optimization",
                },
                {
                    "name": "SAP Analytics Cloud",
                    "type": "analytics-platform",
                    "description": "Real-time business intelligence",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "SAP Transport Package",
                    "type": "deployment-package",
                    "size_mb": 500,
                    "registry": "SAP TMS",
                },
                {
                    "name": "ABAP Program",
                    "type": "source-code",
                    "size_mb": 1,
                    "registry": "SAP Repository",
                },
                {
                    "name": "SAP Add-On",
                    "type": "extension",
                    "size_mb": 100,
                    "registry": "SAP Component",
                },
                {
                    "name": "HANA Backup",
                    "type": "backup-archive",
                    "size_mb": 500000,
                    "registry": "Backup System",
                },
                {
                    "name": "Fiori App",
                    "type": "web-application",
                    "size_mb": 5,
                    "registry": "SAP Gateway",
                },
                {
                    "name": "Custom OData Service",
                    "type": "api-service",
                    "size_mb": 2,
                    "registry": "SAP Gateway",
                },
                {
                    "name": "BRFplus Rule",
                    "type": "business-rule",
                    "size_mb": 1,
                    "registry": "BRFplus",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "Production Data Network",
                    "type": "private",
                    "bandwidth_mbps": 100000,
                    "latency_ms": 1,
                },
                {
                    "name": "HANA Replication Network",
                    "type": "private",
                    "bandwidth_mbps": 100000,
                    "latency_ms": 1,
                },
                {
                    "name": "SAN Storage Network",
                    "type": "fiber-channel",
                    "bandwidth_mbps": 32000,
                    "latency_ms": 1,
                },
                {
                    "name": "Internet Gateway",
                    "type": "wan",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 10,
                },
                {
                    "name": "SAP Cloud Connector",
                    "type": "hybrid-link",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 20,
                },
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="SAP SE",
        market_position="leader",
        company_size="enterprise",
        founded_year=1972,
        headquarters="Walldorf, Germany",
        revenue_usd=31200000000,
        customer_count=440000,
        market_share_percentage=24.0,
        acquisition_risk="very-low",
        financial_health="excellent",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                {
                    "name": "Financial Management",
                    "description": "General ledger, accounts payable/receivable, asset accounting",
                    "coverage_percentage": 100,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Production Planning & Execution",
                    "description": "MRP, production orders, capacity planning, shop floor control",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Material Management",
                    "description": "Procurement, inventory management, goods movement",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Sales & Distribution",
                    "description": "Order-to-cash, pricing, shipping, billing",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Quality Management",
                    "description": "Inspection planning, quality control, non-conformance",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Plant Maintenance",
                    "description": "Preventive maintenance, work orders, asset management",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Warehouse Management",
                    "description": "Advanced warehouse operations, slotting, labor management",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Supply Chain Planning",
                    "description": "Demand planning, supply network planning, production scheduling",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "Product Lifecycle Management",
                    "description": "Product design, engineering change, recipe management",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Master Data Governance",
                    "description": "Material master, vendor master, customer master governance",
                    "coverage_percentage": 93,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Real-Time Analytics",
                    "description": "Embedded analytics, predictive insights, operational reporting",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Manufacturing Execution",
                    "description": "Shop floor data collection, batch management, process orders",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Regulatory Compliance",
                    "description": "FDA 21 CFR Part 11, GAMP, serialization, batch genealogy",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Asset Performance Management",
                    "description": "Predictive maintenance, IoT integration, asset health monitoring",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "Environmental Health & Safety",
                    "description": "Incident management, regulatory reporting, safety protocols",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Human Capital Management",
                    "description": "Personnel administration, time management, payroll",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Project System",
                    "description": "Project planning, execution, cost tracking",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Integrated Business Planning",
                    "description": "S&OP, demand sensing, supply response",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Trade Compliance",
                    "description": "Import/export management, customs, duty calculation",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "Digital Manufacturing",
                    "description": "IoT, machine learning, digital twin integration",
                    "coverage_percentage": 85,
                    "maturity_level": "developing",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Order-to-Cash",
                    "stages": [
                        "Sales Order",
                        "Production Planning",
                        "Manufacturing",
                        "Quality Control",
                        "Shipping",
                        "Invoicing",
                        "Payment",
                    ],
                    "description": "Complete customer order fulfillment",
                },
                {
                    "name": "Procure-to-Pay",
                    "stages": [
                        "Purchase Requisition",
                        "PO Creation",
                        "Goods Receipt",
                        "Quality Inspection",
                        "Invoice Verification",
                        "Payment",
                    ],
                    "description": "Procurement and supplier payment",
                },
                {
                    "name": "Plan-to-Produce",
                    "stages": [
                        "Demand Planning",
                        "MRP",
                        "Production Order",
                        "Material Staging",
                        "Manufacturing",
                        "Goods Receipt",
                        "Costing",
                    ],
                    "description": "Production planning and execution",
                },
                {
                    "name": "Maintain-to-Operate",
                    "stages": [
                        "Maintenance Planning",
                        "Work Order",
                        "Execution",
                        "Confirmation",
                        "Asset Update",
                        "Analysis",
                    ],
                    "description": "Asset maintenance lifecycle",
                },
                {
                    "name": "Design-to-Release",
                    "stages": [
                        "Product Design",
                        "Engineering",
                        "BOM Creation",
                        "Recipe Development",
                        "Testing",
                        "Release",
                    ],
                    "description": "Product development and launch",
                },
                {
                    "name": "Record-to-Report",
                    "stages": [
                        "Transaction Capture",
                        "Posting",
                        "Period Close",
                        "Consolidation",
                        "Reporting",
                        "Analysis",
                    ],
                    "description": "Financial accounting and reporting",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "S/4HANA Greenfield Implementation",
                    "description": "New SAP S/4HANA installation",
                    "timeline_months": 18,
                    "risk_level": "high",
                },
                {
                    "name": "Brownfield Conversion from ECC",
                    "description": "Upgrade existing SAP ECC to S/4HANA",
                    "timeline_months": 12,
                    "risk_level": "medium",
                },
                {
                    "name": "Selective Data Transition",
                    "description": "Hybrid approach with selective data migration",
                    "timeline_months": 15,
                    "risk_level": "medium",
                },
                {
                    "name": "Cloud Migration",
                    "description": "Move to SAP S/4HANA Cloud",
                    "timeline_months": 24,
                    "risk_level": "medium",
                },
                {
                    "name": "Phased Rollout",
                    "description": "Deploy by plant/business unit incrementally",
                    "timeline_months": 36,
                    "risk_level": "medium-low",
                },
                {
                    "name": "Template-Based Deployment",
                    "description": "Use pre-configured industry template",
                    "timeline_months": 10,
                    "risk_level": "low",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Financial Accounting Service",
                    "description": "Record and report financial transactions",
                    "service_type": "internal",
                    "sla_commitment": "Real-time posting, period close < 3 days",
                },
                {
                    "name": "Production Scheduling Service",
                    "description": "Plan and schedule manufacturing operations",
                    "service_type": "internal",
                    "sla_commitment": "Daily MRP run < 4 hours",
                },
                {
                    "name": "Inventory Management Service",
                    "description": "Track and manage material inventory",
                    "service_type": "internal",
                    "sla_commitment": "Real-time inventory accuracy 99.5%",
                },
                {
                    "name": "Order Fulfillment Service",
                    "description": "Process and fulfill customer orders",
                    "service_type": "customer-facing",
                    "sla_commitment": "Order processing < 1 hour",
                },
                {
                    "name": "Quality Inspection Service",
                    "description": "Perform quality checks and inspections",
                    "service_type": "internal",
                    "sla_commitment": "Inspection results < 24 hours",
                },
                {
                    "name": "Procurement Service",
                    "description": "Source and purchase materials",
                    "service_type": "supplier-facing",
                    "sla_commitment": "PO transmission < 2 hours",
                },
                {
                    "name": "Maintenance Management Service",
                    "description": "Plan and execute asset maintenance",
                    "service_type": "internal",
                    "sla_commitment": "Work order response < 4 hours",
                },
                {
                    "name": "Warehouse Operations Service",
                    "description": "Manage warehouse activities",
                    "service_type": "internal",
                    "sla_commitment": "Picking accuracy 99.8%",
                },
                {
                    "name": "Supply Chain Planning Service",
                    "description": "Plan demand and supply",
                    "service_type": "internal",
                    "sla_commitment": "Planning run < 8 hours",
                },
                {
                    "name": "Analytics & Reporting Service",
                    "description": "Provide business intelligence",
                    "service_type": "internal",
                    "sla_commitment": "Real-time dashboard refresh",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Manufacturing Order Processing",
                    "description": "Create, release, execute production orders",
                    "automation_level": "highly-automated",
                    "steps": [
                        "MRP Run",
                        "Order Creation",
                        "Material Staging",
                        "Production Confirmation",
                        "Goods Receipt",
                        "Order Settlement",
                    ],
                    "cycle_time": "2 - 10 days",
                    "kpis": ["On-Time Delivery", "First Pass Yield", "Cycle Time"],
                },
                {
                    "name": "Purchase Order Processing",
                    "description": "Procure materials from suppliers",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Requisition",
                        "PO Creation",
                        "Approval",
                        "Transmission",
                        "Goods Receipt",
                        "Invoice Verification",
                        "Payment",
                    ],
                    "cycle_time": "7 - 30 days",
                    "kpis": ["PO Cycle Time", "Supplier Performance", "Cost Savings"],
                },
                {
                    "name": "Sales Order Processing",
                    "description": "Process customer orders",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Order Entry",
                        "Credit Check",
                        "ATP Check",
                        "Order Confirmation",
                        "Picking",
                        "Shipping",
                        "Invoicing",
                    ],
                    "cycle_time": "1 - 5 days",
                    "kpis": ["Order Fill Rate", "On-Time Delivery", "Perfect Order %"],
                },
                {
                    "name": "MRP Planning Run",
                    "description": "Calculate material requirements",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Demand Calculation",
                        "BOM Explosion",
                        "Lot Sizing",
                        "Scheduling",
                        "Exception Handling",
                    ],
                    "cycle_time": "2 - 4 hours",
                    "kpis": ["Planning Accuracy", "Inventory Turns", "Service Level"],
                },
                {
                    "name": "Quality Inspection",
                    "description": "Inspect materials and products",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Inspection Lot Creation",
                        "Sample Selection",
                        "Inspection Execution",
                        "Results Recording",
                        "Usage Decision",
                    ],
                    "cycle_time": "4 - 24 hours",
                    "kpis": ["First Pass Yield", "Defect Rate", "Inspection Time"],
                },
                {
                    "name": "Preventive Maintenance",
                    "description": "Execute scheduled maintenance",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Maintenance Plan",
                        "Work Order Generation",
                        "Scheduling",
                        "Execution",
                        "Confirmation",
                        "Analysis",
                    ],
                    "cycle_time": "Varies by plan",
                    "kpis": ["Equipment Uptime", "MTBF", "Maintenance Cost"],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Material Master",
                    "description": "Material definition and attributes",
                    "lifecycle": "created -> active -> blocked -> archived",
                },
                {
                    "name": "Production Order",
                    "description": "Manufacturing work order",
                    "lifecycle": "created -> released -> in-process -> completed -> settled",
                },
                {
                    "name": "Purchase Order",
                    "description": "Procurement document",
                    "lifecycle": "created -> approved -> sent -> received -> completed",
                },
                {
                    "name": "Sales Order",
                    "description": "Customer order",
                    "lifecycle": "created -> confirmed -> in-delivery -> billed -> completed",
                },
                {
                    "name": "Bill of Material",
                    "description": "Product structure",
                    "lifecycle": "created -> released -> active -> superseded -> obsolete",
                },
                {
                    "name": "Work Center",
                    "description": "Production resource",
                    "lifecycle": "created -> active -> inactive -> archived",
                },
                {
                    "name": "Batch",
                    "description": "Material lot with unique characteristics",
                    "lifecycle": "created -> in-use -> consumed -> expired",
                },
                {
                    "name": "Equipment",
                    "description": "Maintainable asset",
                    "lifecycle": "installed -> in-operation -> under-maintenance -> decommissioned",
                },
                {
                    "name": "Inspection Lot",
                    "description": "Quality inspection document",
                    "lifecycle": "created -> in-inspection -> results-recorded -> usage-decision-made",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Production Planner",
                    "description": "Plans manufacturing operations",
                    "responsibilities": [
                        "MRP Execution",
                        "Production Order Creation",
                        "Capacity Planning",
                        "Schedule Management",
                    ],
                },
                {
                    "name": "Production Operator",
                    "description": "Executes shop floor operations",
                    "responsibilities": [
                        "Order Confirmation",
                        "Material Consumption",
                        "Yield Recording",
                        "Downtime Reporting",
                    ],
                },
                {
                    "name": "Quality Inspector",
                    "description": "Performs quality checks",
                    "responsibilities": [
                        "Inspection Execution",
                        "Results Recording",
                        "Non-Conformance Management",
                        "Certificate Creation",
                    ],
                },
                {
                    "name": "Maintenance Technician",
                    "description": "Performs equipment maintenance",
                    "responsibilities": [
                        "Work Order Execution",
                        "Time Confirmation",
                        "Parts Consumption",
                        "Technical Reporting",
                    ],
                },
                {
                    "name": "Warehouse Operator",
                    "description": "Manages warehouse operations",
                    "responsibilities": ["Goods Receipt", "Putaway", "Picking", "Shipping"],
                },
                {
                    "name": "Procurement Specialist",
                    "description": "Manages purchasing",
                    "responsibilities": [
                        "PO Creation",
                        "Supplier Management",
                        "Contract Management",
                        "Invoice Verification",
                    ],
                },
                {
                    "name": "Sales Representative",
                    "description": "Processes customer orders",
                    "responsibilities": ["Order Entry", "Quotation", "Pricing", "Customer Service"],
                },
                {
                    "name": "Financial Accountant",
                    "description": "Records financial transactions",
                    "responsibilities": [
                        "Journal Entries",
                        "Account Reconciliation",
                        "Period Close",
                        "Reporting",
                    ],
                },
                {
                    "name": "Master Data Manager",
                    "description": "Maintains master data",
                    "responsibilities": [
                        "Material Master",
                        "Vendor Master",
                        "Customer Master",
                        "BOM Maintenance",
                    ],
                },
                {
                    "name": "System Administrator",
                    "description": "Manages SAP system",
                    "responsibilities": [
                        "User Administration",
                        "Authorization",
                        "System Monitoring",
                        "Transport Management",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "SAP S/4HANA",
                    "description": "Core ERP suite",
                    "target_market": "All Manufacturing Industries",
                },
                {
                    "name": "SAP Extended Warehouse Management",
                    "description": "Advanced warehouse management",
                    "target_market": "Distribution-Intensive Industries",
                },
                {
                    "name": "SAP Manufacturing Execution",
                    "description": "Shop floor control",
                    "target_market": "Discrete & Process Manufacturing",
                },
                {
                    "name": "SAP Quality Management",
                    "description": "Quality control and compliance",
                    "target_market": "Regulated Industries",
                },
                {
                    "name": "SAP Plant Maintenance",
                    "description": "Asset and maintenance management",
                    "target_market": "Asset-Intensive Industries",
                },
                {
                    "name": "SAP Advanced Planning",
                    "description": "Supply chain planning",
                    "target_market": "Complex Supply Chains",
                },
                {
                    "name": "SAP Product Lifecycle Management",
                    "description": "Product development",
                    "target_market": "Engineering-Intensive Industries",
                },
                {
                    "name": "SAP Analytics Cloud",
                    "description": "Business intelligence",
                    "target_market": "All Industries",
                },
                {
                    "name": "SAP Fiori",
                    "description": "Modern user experience",
                    "target_market": "All Industries",
                },
                {
                    "name": "SAP Business Technology Platform",
                    "description": "Extension and integration platform",
                    "target_market": "All Industries",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "SAP S/4HANA Core",
                    "type": "erp-system",
                    "description": "Core ERP application",
                    "technology": "ABAP",
                },
                {
                    "name": "SAP HANA Database",
                    "type": "database",
                    "description": "In-memory database",
                    "technology": "C++/SQL",
                },
                {
                    "name": "SAP Fiori Launchpad",
                    "type": "web-portal",
                    "description": "User interface framework",
                    "technology": "SAPUI5/JavaScript",
                },
                {
                    "name": "SAP Gateway",
                    "type": "api-gateway",
                    "description": "OData API layer",
                    "technology": "ABAP",
                },
                {
                    "name": "SAP NetWeaver Application Server",
                    "type": "application-server",
                    "description": "Runtime environment",
                    "technology": "ABAP/Java",
                },
                {
                    "name": "SAP Web Dispatcher",
                    "type": "load-balancer",
                    "description": "HTTP request distribution",
                    "technology": "C",
                },
                {
                    "name": "SAP Solution Manager",
                    "type": "alm-platform",
                    "description": "Application lifecycle management",
                    "technology": "ABAP",
                },
                {
                    "name": "SAP Cloud Connector",
                    "type": "integration-gateway",
                    "description": "Hybrid cloud connectivity",
                    "technology": "Java",
                },
                {
                    "name": "SAP Integration Suite",
                    "type": "integration-platform",
                    "description": "Application integration",
                    "technology": "Cloud",
                },
                {
                    "name": "SAP Event Mesh",
                    "type": "message-broker",
                    "description": "Event-driven architecture",
                    "technology": "Cloud",
                },
                {
                    "name": "SAP Master Data Governance",
                    "type": "mdm-system",
                    "description": "Master data management",
                    "technology": "ABAP",
                },
                {
                    "name": "SAP BRFplus",
                    "type": "business-rules-engine",
                    "description": "Business rule management",
                    "technology": "ABAP",
                },
                {
                    "name": "SAP Workflow Engine",
                    "type": "workflow-engine",
                    "description": "Business process automation",
                    "technology": "ABAP",
                },
                {
                    "name": "SAP Transport Management System",
                    "type": "deployment-tool",
                    "description": "Change transport",
                    "technology": "ABAP",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "SAP OData API",
                    "type": "REST",
                    "description": "OData v2/v4 services",
                    "endpoints": ["/sap/opu/odata/sap/*"],
                },
                {
                    "name": "SAP RFC API",
                    "type": "RPC",
                    "description": "Remote Function Call",
                    "endpoints": ["RFC_*", "BAPI_*"],
                },
                {
                    "name": "SAP IDoc Interface",
                    "type": "EDI",
                    "description": "Electronic Data Interchange",
                    "endpoints": ["IDOC_*"],
                },
                {
                    "name": "SAP Web Services",
                    "type": "SOAP",
                    "description": "Enterprise services",
                    "endpoints": ["/sap/bc/srt/wsdl/*"],
                },
                {
                    "name": "SAP Cloud Platform Integration API",
                    "type": "REST",
                    "description": "Integration flows",
                    "endpoints": ["/http/*", "/odata/*"],
                },
                {
                    "name": "SAP HANA SQL Interface",
                    "type": "SQL",
                    "description": "Direct database access",
                    "endpoints": ["SQL queries"],
                },
                {
                    "name": "SAP Analytics API",
                    "type": "REST",
                    "description": "Analytics and reporting",
                    "endpoints": ["/sap/bc/ina/*"],
                },
                {
                    "name": "SAP Mobile Services API",
                    "type": "REST",
                    "description": "Mobile application backend",
                    "endpoints": ["/mobileservices/*"],
                },
                {
                    "name": "SAP IoT API",
                    "type": "REST",
                    "description": "IoT data ingestion",
                    "endpoints": ["/iot/*"],
                },
                {
                    "name": "SAP Workflow API",
                    "type": "REST",
                    "description": "Workflow management",
                    "endpoints": ["/sap/opu/odata/SAP/SWF_*"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "OData Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON/XML",
                    "authentication": "OAuth2/SAML",
                },
                {
                    "name": "RFC Interface",
                    "protocol": "RFC",
                    "data_format": "ABAP Structures",
                    "authentication": "SNC/User-Password",
                },
                {
                    "name": "IDoc Interface",
                    "protocol": "tRFC/qRFC",
                    "data_format": "IDoc XML",
                    "authentication": "Partner Profile",
                },
                {
                    "name": "SOAP Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "SOAP XML",
                    "authentication": "WS-Security",
                },
                {
                    "name": "Database Interface",
                    "protocol": "JDBC/ODBC",
                    "data_format": "SQL",
                    "authentication": "Database User",
                },
                {
                    "name": "File Interface",
                    "protocol": "FTP/SFTP",
                    "data_format": "Various",
                    "authentication": "SSH Keys",
                },
                {
                    "name": "Event Mesh Interface",
                    "protocol": "AMQP/MQTT",
                    "data_format": "JSON",
                    "authentication": "OAuth2",
                },
                {
                    "name": "JCo Interface",
                    "protocol": "JCo",
                    "data_format": "Java Objects",
                    "authentication": "SNC",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {
                    "name": "Material Master Record",
                    "type": "master",
                    "retention_policy": "Active + 10 years",
                },
                {
                    "name": "Production Order",
                    "type": "transactional",
                    "retention_policy": "Completion + 7 years",
                },
                {
                    "name": "Financial Document",
                    "type": "transactional",
                    "retention_policy": "10 years",
                },
                {
                    "name": "Batch Record",
                    "type": "regulatory",
                    "retention_policy": "Expiry + 20 years",
                },
                {
                    "name": "Quality Record",
                    "type": "regulatory",
                    "retention_policy": "Product lifetime + 15 years",
                },
                {"name": "Audit Log", "type": "audit", "retention_policy": "10 years"},
                {"name": "Change Document", "type": "audit", "retention_policy": "7 years"},
                {"name": "Archive Object", "type": "archive", "retention_policy": "Permanent"},
                {"name": "Temporary Data", "type": "transient", "retention_policy": "90 days"},
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "Material Requirements Planning",
                    "type": "planning",
                    "description": "Calculate material requirements",
                },
                {
                    "name": "Production Order Creation",
                    "type": "transaction",
                    "description": "Create manufacturing orders",
                },
                {
                    "name": "Goods Movement",
                    "type": "transaction",
                    "description": "Post inventory movements",
                },
                {
                    "name": "Financial Posting",
                    "type": "transaction",
                    "description": "Post financial documents",
                },
                {
                    "name": "Availability Check",
                    "type": "validation",
                    "description": "Check material availability",
                },
                {
                    "name": "Batch Determination",
                    "type": "business-logic",
                    "description": "Select appropriate batch",
                },
                {
                    "name": "Pricing Determination",
                    "type": "calculation",
                    "description": "Calculate sales prices",
                },
                {
                    "name": "Costing Calculation",
                    "type": "calculation",
                    "description": "Calculate product costs",
                },
                {
                    "name": "Schedule Agreement Release",
                    "type": "workflow",
                    "description": "Release scheduled deliveries",
                },
                {
                    "name": "Analytical Reporting",
                    "type": "reporting",
                    "description": "Generate business reports",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "Chief Operations Officer (COO)",
                    "role": "executive",
                    "concerns": [
                        "Operational Excellence",
                        "Manufacturing Efficiency",
                        "Cost Control",
                    ],
                    "influence": "high",
                },
                {
                    "name": "VP Manufacturing",
                    "role": "executive",
                    "concerns": ["Production Performance", "Quality", "Capacity Utilization"],
                    "influence": "high",
                },
                {
                    "name": "VP Supply Chain",
                    "role": "executive",
                    "concerns": [
                        "Inventory Optimization",
                        "Supplier Performance",
                        "On-Time Delivery",
                    ],
                    "influence": "high",
                },
                {
                    "name": "CFO",
                    "role": "executive",
                    "concerns": ["Financial Control", "Compliance", "Cost Visibility"],
                    "influence": "high",
                },
                {
                    "name": "Plant Manager",
                    "role": "management",
                    "concerns": ["Plant Efficiency", "Safety", "Production Targets"],
                    "influence": "medium",
                },
                {
                    "name": "Quality Director",
                    "role": "management",
                    "concerns": [
                        "Product Quality",
                        "Regulatory Compliance",
                        "Customer Satisfaction",
                    ],
                    "influence": "high",
                },
                {
                    "name": "IT Director",
                    "role": "technical",
                    "concerns": ["System Stability", "Integration", "Technology Roadmap"],
                    "influence": "high",
                },
                {
                    "name": "Maintenance Manager",
                    "role": "management",
                    "concerns": ["Equipment Uptime", "Maintenance Costs", "Asset Performance"],
                    "influence": "medium",
                },
                {
                    "name": "Production Supervisors",
                    "role": "operational",
                    "concerns": ["Daily Production", "Team Performance", "Schedule Adherence"],
                    "influence": "medium",
                },
                {
                    "name": "End Users (Operators)",
                    "role": "operational",
                    "concerns": ["System Usability", "Performance", "Training"],
                    "influence": "low",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Manufacturing Complexity",
                    "description": "Increasing product variety and customization",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Supply Chain Volatility",
                    "description": "Global disruptions and uncertainty",
                    "urgency": "critical",
                    "impact": "high",
                },
                {
                    "name": "Quality & Compliance Pressure",
                    "description": "Stricter regulations and quality standards",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Cost Reduction Mandate",
                    "description": "Need to reduce manufacturing costs",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Legacy System Limitations",
                    "description": "Aging SAP ECC system constraints",
                    "urgency": "medium",
                    "impact": "transformational",
                },
                {
                    "name": "Real-Time Visibility Gap",
                    "description": "Lack of real-time operational insights",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Digital Transformation",
                    "description": "Industry 4.0 and smart manufacturing",
                    "urgency": "medium",
                    "impact": "transformational",
                },
                {
                    "name": "Customer Experience Expectations",
                    "description": "Faster delivery and perfect orders",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Sustainability Requirements",
                    "description": "Environmental compliance and reporting",
                    "urgency": "medium",
                    "impact": "medium",
                },
                {
                    "name": "Workforce Challenges",
                    "description": "Skills gap and aging workforce",
                    "urgency": "medium",
                    "impact": "medium",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "Achieve 99.5% On-Time Delivery",
                    "description": "Meet customer commitments consistently",
                    "timeframe": "12 months",
                    "measurable": "OTD > 99.5%",
                },
                {
                    "name": "Reduce Inventory by 25%",
                    "description": "Optimize working capital",
                    "timeframe": "18 months",
                    "measurable": "Inventory turns increase 33%",
                },
                {
                    "name": "Improve First Pass Yield to 98%",
                    "description": "Minimize scrap and rework",
                    "timeframe": "12 months",
                    "measurable": "FPY > 98%",
                },
                {
                    "name": "Achieve Real-Time Visibility",
                    "description": "End-to-end supply chain transparency",
                    "timeframe": "24 months",
                    "measurable": "All KPIs real-time updated",
                },
                {
                    "name": "Reduce Manufacturing Lead Time 30%",
                    "description": "Accelerate production throughput",
                    "timeframe": "18 months",
                    "measurable": "Lead time reduction 30%",
                },
                {
                    "name": "Eliminate Manual Processes",
                    "description": "Automate repetitive tasks",
                    "timeframe": "24 months",
                    "measurable": "80% process automation",
                },
                {
                    "name": "Zero Critical Compliance Violations",
                    "description": "Maintain regulatory compliance",
                    "timeframe": "Ongoing",
                    "measurable": "0 FDA 483s or warning letters",
                },
                {
                    "name": "Increase Equipment Uptime to 95%",
                    "description": "Maximize asset utilization",
                    "timeframe": "12 months",
                    "measurable": "OEE > 85%, Uptime > 95%",
                },
                {
                    "name": "Reduce Total Cost of Ownership 20%",
                    "description": "Lower IT and operational costs",
                    "timeframe": "36 months",
                    "measurable": "20% TCO reduction",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "Perfect Order Performance",
                    "description": "Industry-leading order fulfillment",
                    "benefit_type": "operational",
                    "quantified_benefit": "99.5% perfect order rate",
                },
                {
                    "name": "Working Capital Optimization",
                    "description": "Cash freed from inventory reduction",
                    "benefit_type": "financial",
                    "quantified_benefit": "$15M cash released",
                },
                {
                    "name": "Quality Excellence",
                    "description": "Best-in-class quality performance",
                    "benefit_type": "quality",
                    "quantified_benefit": "98% FPY, 50% defect reduction",
                },
                {
                    "name": "Real-Time Decision Making",
                    "description": "Data-driven operational decisions",
                    "benefit_type": "operational",
                    "quantified_benefit": "Real-time analytics for all KPIs",
                },
                {
                    "name": "Manufacturing Agility",
                    "description": "Rapid response to demand changes",
                    "benefit_type": "strategic",
                    "quantified_benefit": "30% faster order fulfillment",
                },
                {
                    "name": "Operational Efficiency",
                    "description": "Streamlined and automated processes",
                    "benefit_type": "operational",
                    "quantified_benefit": "$8M annual labor savings",
                },
                {
                    "name": "Regulatory Confidence",
                    "description": "Audit-ready compliance",
                    "benefit_type": "risk-mitigation",
                    "quantified_benefit": "Zero compliance violations",
                },
                {
                    "name": "Asset Reliability",
                    "description": "Predictable and reliable equipment",
                    "benefit_type": "operational",
                    "quantified_benefit": "95% uptime, $5M maintenance savings",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Single Source of Truth",
                    "description": "One integrated system for all data",
                    "rationale": "Eliminate data inconsistencies",
                },
                {
                    "name": "Real-Time Processing",
                    "description": "Immediate transaction visibility",
                    "rationale": "Enable agile decision-making",
                },
                {
                    "name": "Embedded Analytics",
                    "description": "Analytics in operational context",
                    "rationale": "Democratize insights",
                },
                {
                    "name": "Process Standardization",
                    "description": "Common processes across plants",
                    "rationale": "Enable scalability and efficiency",
                },
                {
                    "name": "Master Data Excellence",
                    "description": "High-quality governed master data",
                    "rationale": "Foundation for all processes",
                },
                {
                    "name": "Integrated Quality",
                    "description": "Quality checks embedded in processes",
                    "rationale": "Prevention over detection",
                },
                {
                    "name": "Continuous Improvement",
                    "description": "Regular process optimization",
                    "rationale": "Sustain competitive advantage",
                },
                {
                    "name": "Fiori-First UX",
                    "description": "Modern consumer-grade interface",
                    "rationale": "Enhance user productivity",
                },
                {
                    "name": "API-Enabled Integration",
                    "description": "Standard APIs for all integrations",
                    "rationale": "Reduce integration complexity",
                },
                {
                    "name": "Cloud-Ready Architecture",
                    "description": "Design for cloud deployment",
                    "rationale": "Future-proof technology",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "System Availability",
                    "type": "performance",
                    "description": "ERP available 99.9% of time",
                    "priority": "critical",
                },
                {
                    "name": "Response Time",
                    "type": "performance",
                    "description": "Transaction response < 2 seconds",
                    "priority": "high",
                },
                {
                    "name": "Concurrent Users",
                    "type": "capacity",
                    "description": "Support 5,000 concurrent users",
                    "priority": "high",
                },
                {
                    "name": "Data Retention",
                    "type": "compliance",
                    "description": "Retain data per FDA/regulatory requirements",
                    "priority": "critical",
                },
                {
                    "name": "Audit Trail",
                    "type": "compliance",
                    "description": "Complete change history (21 CFR Part 11)",
                    "priority": "critical",
                },
                {
                    "name": "Disaster Recovery",
                    "type": "continuity",
                    "description": "RPO < 1 hour, RTO < 4 hours",
                    "priority": "critical",
                },
                {
                    "name": "Security",
                    "type": "security",
                    "description": "Role-based access control, encryption at rest/transit",
                    "priority": "critical",
                },
                {
                    "name": "Integration Performance",
                    "type": "performance",
                    "description": "Real-time integration < 5 second latency",
                    "priority": "high",
                },
                {
                    "name": "Scalability",
                    "type": "capacity",
                    "description": "Support 50% volume growth without re-architecture",
                    "priority": "high",
                },
                {
                    "name": "Localization",
                    "type": "functional",
                    "description": "Support 15 countries with local requirements",
                    "priority": "high",
                },
                {
                    "name": "Reporting Performance",
                    "type": "performance",
                    "description": "Standard reports < 30 seconds",
                    "priority": "medium",
                },
                {
                    "name": "Batch Processing",
                    "type": "performance",
                    "description": "MRP run < 4 hours for 500k materials",
                    "priority": "high",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget Limitation",
                    "type": "financial",
                    "description": "Total project budget capped at $25M",
                },
                {
                    "name": "Timeline Pressure",
                    "type": "schedule",
                    "description": "Go-live must complete within 18 months",
                },
                {
                    "name": "Resource Availability",
                    "type": "resource",
                    "description": "Limited SAP S/4HANA expertise internally",
                },
                {
                    "name": "Regulatory Validation",
                    "type": "compliance",
                    "description": "FDA validation required, adds 6 months",
                },
                {
                    "name": "Legacy Integration Complexity",
                    "type": "technical",
                    "description": "Must integrate with 25 legacy systems",
                },
                {
                    "name": "Data Quality Issues",
                    "type": "technical",
                    "description": "Historical data cleanup required",
                },
                {
                    "name": "Change Management",
                    "type": "organizational",
                    "description": "Significant user adoption challenge",
                },
                {
                    "name": "Network Infrastructure",
                    "type": "technical",
                    "description": "Plant networks need upgrades",
                },
                {
                    "name": "Vendor Lock-In",
                    "type": "strategic",
                    "description": "Heavy dependence on SAP ecosystem",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "Readiness Assessment",
                    "type": "maturity",
                    "description": "Assess organizational readiness",
                    "result": "Score: 72/100 - Ready with preparation needed",
                },
                {
                    "name": "Technical Assessment",
                    "type": "technical",
                    "description": "Infrastructure and architecture review",
                    "result": "Hardware upgrades needed, network sufficient",
                },
                {
                    "name": "Data Quality Assessment",
                    "type": "data",
                    "description": "Master data quality analysis",
                    "result": "60% clean, 6 - month cleanup required",
                },
                {
                    "name": "Process Assessment",
                    "type": "business",
                    "description": "Current process maturity",
                    "result": "Level 2 maturity, standardization needed",
                },
                {
                    "name": "ROI Analysis",
                    "type": "financial",
                    "description": "Business case validation",
                    "result": "Projected 250% ROI over 5 years, 3 - year payback",
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
                    "description": "Project initiation and team mobilization",
                },
                {
                    "name": "Blueprint Complete",
                    "date": "2024 - 04 - 30",
                    "milestone": True,
                    "description": "Business process design finalized",
                },
                {
                    "name": "System Build Complete",
                    "date": "2024 - 09 - 30",
                    "milestone": True,
                    "description": "Configuration and development done",
                },
                {
                    "name": "Integration Testing Complete",
                    "date": "2024 - 12 - 31",
                    "milestone": True,
                    "description": "All integrations validated",
                },
                {
                    "name": "User Acceptance Testing Complete",
                    "date": "2025 - 03 - 31",
                    "milestone": True,
                    "description": "Business users accept solution",
                },
                {
                    "name": "Data Migration Complete",
                    "date": "2025 - 05 - 31",
                    "milestone": True,
                    "description": "Historical data loaded",
                },
                {
                    "name": "Production Cutover",
                    "date": "2025 - 07 - 01",
                    "milestone": True,
                    "description": "Go-live event",
                },
                {
                    "name": "Hypercare Complete",
                    "date": "2025 - 08 - 31",
                    "milestone": False,
                    "description": "Post go-live stabilization",
                },
                {
                    "name": "Project Closure",
                    "date": "2025 - 09 - 30",
                    "milestone": True,
                    "description": "Project formally closed",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Project Management",
                    "description": "Overall project governance",
                    "duration_weeks": 78,
                    "team_size": 5,
                },
                {
                    "name": "Business Process Design",
                    "description": "Blueprint and configuration",
                    "duration_weeks": 16,
                    "team_size": 15,
                },
                {
                    "name": "System Configuration",
                    "description": "SAP configuration and setup",
                    "duration_weeks": 24,
                    "team_size": 12,
                },
                {
                    "name": "Custom Development",
                    "description": "ABAP development and enhancements",
                    "duration_weeks": 20,
                    "team_size": 8,
                },
                {
                    "name": "Data Migration",
                    "description": "Master and transactional data migration",
                    "duration_weeks": 28,
                    "team_size": 10,
                },
                {
                    "name": "Integration Development",
                    "description": "Build interfaces to external systems",
                    "duration_weeks": 32,
                    "team_size": 8,
                },
                {
                    "name": "Testing",
                    "description": "System, integration, UAT testing",
                    "duration_weeks": 24,
                    "team_size": 20,
                },
                {
                    "name": "Training",
                    "description": "End user training program",
                    "duration_weeks": 16,
                    "team_size": 6,
                },
                {
                    "name": "Change Management",
                    "description": "Organizational change management",
                    "duration_weeks": 52,
                    "team_size": 4,
                },
                {
                    "name": "Cutover Planning & Execution",
                    "description": "Go-live preparation and execution",
                    "duration_weeks": 12,
                    "team_size": 25,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Project Charter",
                    "type": "document",
                    "due_phase": "initiation",
                    "owner": "Project Manager",
                },
                {
                    "name": "Business Blueprint",
                    "type": "document",
                    "due_phase": "design",
                    "owner": "Solution Architect",
                },
                {
                    "name": "Configured System",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "Configuration Lead",
                },
                {
                    "name": "Custom Programs",
                    "type": "code",
                    "due_phase": "build",
                    "owner": "Development Lead",
                },
                {
                    "name": "Integration Interfaces",
                    "type": "integration",
                    "due_phase": "build",
                    "owner": "Integration Lead",
                },
                {
                    "name": "Test Scripts",
                    "type": "test-artifacts",
                    "due_phase": "test",
                    "owner": "Test Manager",
                },
                {
                    "name": "Training Materials",
                    "type": "training",
                    "due_phase": "prepare",
                    "owner": "Training Lead",
                },
                {
                    "name": "Cutover Runbook",
                    "type": "document",
                    "due_phase": "prepare",
                    "owner": "Cutover Manager",
                },
                {
                    "name": "Go-Live Readiness Report",
                    "type": "document",
                    "due_phase": "prepare",
                    "owner": "Project Manager",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "Foundation Established",
                    "date": "2024 - 04 - 30",
                    "description": "Infrastructure ready, blueprint complete",
                },
                {
                    "name": "System Built",
                    "date": "2024 - 09 - 30",
                    "description": "Configuration and development complete",
                },
                {
                    "name": "Solution Validated",
                    "date": "2025 - 03 - 31",
                    "description": "Testing complete, ready for migration",
                },
                {
                    "name": "Production Live",
                    "date": "2025 - 07 - 01",
                    "description": "System live and operational",
                },
                {
                    "name": "Stabilized",
                    "date": "2025 - 09 - 30",
                    "description": "System stable, project closed",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "Primary Data Center",
                    "location": "Chicago, IL",
                    "tier": "Tier III",
                    "size_sqm": 1000,
                    "description": "On-premise production SAP environment",
                },
                {
                    "name": "Disaster Recovery Site",
                    "location": "Dallas, TX",
                    "tier": "Tier III",
                    "size_sqm": 500,
                    "description": "DR failover site",
                },
                {
                    "name": "SAP Cloud Infrastructure",
                    "location": "AWS US-East - 1",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "Cloud extensions and BTP",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "SAP Application Servers",
                    "type": "bare-metal",
                    "quantity": 4,
                    "location": "Chicago DC",
                    "specs": "HP DL580, 32 cores, 512GB RAM",
                },
                {
                    "name": "SAP HANA Servers",
                    "type": "bare-metal",
                    "quantity": 2,
                    "location": "Chicago DC",
                    "specs": "HP Superdome X, 64 cores, 2TB RAM",
                },
                {
                    "name": "Storage Array",
                    "type": "san-storage",
                    "quantity": 1,
                    "location": "Chicago DC",
                    "specs": "NetApp AFF A700, 500TB",
                },
                {
                    "name": "Network Switches",
                    "type": "network",
                    "quantity": 8,
                    "location": "Chicago DC",
                    "specs": "Cisco Nexus 9000",
                },
                {
                    "name": "SAP Router",
                    "type": "appliance",
                    "quantity": 2,
                    "location": "Chicago DC",
                    "specs": "SAP Router 740",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "Data Center LAN",
                    "type": "lan",
                    "coverage": "Chicago DC",
                    "bandwidth_mbps": 100000,
                    "provider": "Internal",
                },
                {
                    "name": "SAN Fabric",
                    "type": "san",
                    "coverage": "Chicago DC",
                    "bandwidth_mbps": 32000,
                    "provider": "Internal",
                },
                {
                    "name": "WAN to Plants",
                    "type": "wan",
                    "coverage": "15 Manufacturing Sites",
                    "bandwidth_mbps": 1000,
                    "provider": "AT&T",
                },
                {
                    "name": "Internet Gateway",
                    "type": "internet",
                    "coverage": "External Access",
                    "bandwidth_mbps": 10000,
                    "provider": "Multiple ISPs",
                },
            ]
        ),
    )


def seed_sap_s4hana(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Get admin user for approval
            admin_user = User.query.filter_by(role_id=1).first()

            # Create template and auto-generate TechnologyStack
            template_data = create_sap_s4hana_template()
            template, tech_stack = seed_vendor_with_tech_stack(template_data, "SAP", admin_user)

            print("✅ SAP S/4HANA template seeded successfully!")
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
                f"   - Implementation Layer: ✅ Complete (9 events, 10 work packages, 9 deliverables, 5 plateaus)"
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
            print(f"❌ Error seeding SAP S/4HANA template: {str(e)}")
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    seed_sap_s4hana()
