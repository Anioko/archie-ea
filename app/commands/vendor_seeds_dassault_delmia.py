"""
Dassault Systèmes DELMIA Comprehensive Vendor Template Seed Data

Complete ArchiMate 3.2 coverage across ALL layers:
- Strategy Layer
- Business Layer
- Application Layer
- Technology Layer
- Motivation Layer
- Implementation & Migration Layer
- Physical Layer

Run with: python manage.py seed-vendor-dassault
"""
import json

from app import create_app, db
from app.models import User, VendorStackTemplate
from config import DevelopmentConfig


def create_dassault_delmia_template():
    """Dassault DELMIA FULLY COMPREHENSIVE template - ALL ArchiMate 3.2 layers"""
    return VendorStackTemplate(
        vendor_name="Dassault Systèmes",
        name="Dassault DELMIA Digital Manufacturing & Operations",
        description="Comprehensive digital manufacturing platform integrating manufacturing planning, simulation, execution, and optimization with PLM and 3DEXPERIENCE for end-to-end virtual-to-real production management",
        # ==================== TECHNOLOGY LAYER ====================
        platform="cloud",
        primary_language="java",
        framework="3DEXPERIENCE Platform",
        framework_version="R2023x",
        primary_database="oracle",
        database_version="19c",
        container_runtime="docker",
        orchestration="kubernetes",
        service_mesh="istio",
        api_standard="REST",
        api_gateway="3dexperience-gateway",
        message_broker="kafka",
        auth_provider="3dpassport",
        secrets_manager="hashicorp-vault",
        logging_framework="elk-stack",
        metrics_platform="prometheus",
        apm_tool="dynatrace",
        tracing_tool="jaeger",
        build_tool="maven",
        ci_cd_platform="jenkins",
        sast_tool="fortify",
        dast_tool="appscanner",
        dependency_scanner="blackduck",
        nodes=json.dumps(
            [
                {
                    "name": "3DEXPERIENCE Cloud Server 1",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 32,
                    "ram_gb": 256,
                },
                {
                    "name": "3DEXPERIENCE Cloud Server 2",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 32,
                    "ram_gb": 256,
                },
                {
                    "name": "DELMIA Manufacturing Hub Server",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 64,
                    "ram_gb": 512,
                },
                {
                    "name": "ENOVIA PLM Server",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 48,
                    "ram_gb": 384,
                },
                {
                    "name": "Oracle Database RAC Node 1",
                    "type": "cloud-instance",
                    "os": "Oracle Linux 8",
                    "cpu_cores": 64,
                    "ram_gb": 1024,
                },
                {
                    "name": "Oracle Database RAC Node 2",
                    "type": "cloud-instance",
                    "os": "Oracle Linux 8",
                    "cpu_cores": 64,
                    "ram_gb": 1024,
                },
                {
                    "name": "Simulation Server Cluster",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 128,
                    "ram_gb": 2048,
                },
                {
                    "name": "API Gateway",
                    "type": "cloud-instance",
                    "os": "RHEL 8",
                    "cpu_cores": 16,
                    "ram_gb": 64,
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
                {
                    "name": "Cloud CDN",
                    "type": "cdn",
                    "description": "Content delivery for 3D models",
                },
                {
                    "name": "Edge Gateway",
                    "type": "edge-device",
                    "description": "On-premise to cloud connectivity",
                },
                {
                    "name": "3D Visualization Workstations",
                    "type": "workstation",
                    "description": "High-performance engineering workstations",
                },
                {
                    "name": "Mobile Tablets",
                    "type": "mobile-device",
                    "description": "Shop floor operator tablets",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {"name": "3DEXPERIENCE Platform", "type": "cloud-platform", "version": "R2023x"},
                {"name": "DELMIA Apriso", "type": "mes", "version": "2023x"},
                {"name": "DELMIA Ortems", "type": "scheduling", "version": "2023"},
                {"name": "DELMIA Manufacturing Planning", "type": "planning", "version": "2023x"},
                {"name": "DELMIA Robotics", "type": "simulation", "version": "2023x"},
                {"name": "DELMIA Operations", "type": "operations-management", "version": "2023x"},
                {"name": "ENOVIA", "type": "plm", "version": "2023x"},
                {"name": "Oracle Database", "type": "database", "version": "19c RAC"},
                {"name": "Apache Kafka", "type": "message-broker", "version": "3.5"},
                {"name": "Kubernetes", "type": "orchestration", "version": "1.27"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "3DEXPERIENCE Platform Service",
                    "type": "cloud-platform",
                    "description": "Unified collaboration and data management",
                },
                {
                    "name": "DELMIA Apriso MES Service",
                    "type": "mes-engine",
                    "description": "Manufacturing execution and operations",
                },
                {
                    "name": "DELMIA Ortems Scheduling Service",
                    "type": "scheduling-engine",
                    "description": "Advanced finite capacity scheduling",
                },
                {
                    "name": "Digital Twin Service",
                    "type": "simulation-engine",
                    "description": "Virtual manufacturing simulation",
                },
                {
                    "name": "Robotics Simulation Service",
                    "type": "robotics-simulator",
                    "description": "Robot path planning and validation",
                },
                {
                    "name": "Manufacturing Planning Service",
                    "type": "planning-engine",
                    "description": "Process planning and work instructions",
                },
                {
                    "name": "Quality Management Service",
                    "type": "quality-engine",
                    "description": "Quality planning and control",
                },
                {
                    "name": "ENOVIA PLM Service",
                    "type": "plm-engine",
                    "description": "Product lifecycle management",
                },
                {
                    "name": "Work Instructions Service",
                    "type": "documentation-service",
                    "description": "3D visual work instructions",
                },
                {
                    "name": "Material Management Service",
                    "type": "material-tracking",
                    "description": "Material traceability and genealogy",
                },
                {
                    "name": "Labor Management Service",
                    "type": "workforce-management",
                    "description": "Labor tracking and optimization",
                },
                {
                    "name": "Analytics & Intelligence Service",
                    "type": "analytics-platform",
                    "description": "Manufacturing intelligence and KPIs",
                },
                {
                    "name": "Integration Gateway Service",
                    "type": "integration-platform",
                    "description": "ERP and equipment integration",
                },
                {
                    "name": "3D Visualization Service",
                    "type": "visualization-engine",
                    "description": "Real-time 3D rendering",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "3DEXPERIENCE Object",
                    "type": "plm-object",
                    "size_mb": 50,
                    "registry": "ENOVIA",
                },
                {
                    "name": "Manufacturing Process Plan",
                    "type": "process-plan",
                    "size_mb": 20,
                    "registry": "DELMIA",
                },
                {
                    "name": "Robot Program",
                    "type": "simulation-model",
                    "size_mb": 100,
                    "registry": "DELMIA Robotics",
                },
                {
                    "name": "Digital Twin Model",
                    "type": "3d-model",
                    "size_mb": 500,
                    "registry": "3DEXPERIENCE",
                },
                {
                    "name": "Work Instruction Package",
                    "type": "document",
                    "size_mb": 10,
                    "registry": "Apriso",
                },
                {
                    "name": "Production Schedule",
                    "type": "schedule",
                    "size_mb": 5,
                    "registry": "Ortems",
                },
                {
                    "name": "Database Backup",
                    "type": "backup-archive",
                    "size_mb": 1000000,
                    "registry": "Oracle",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "3DEXPERIENCE Cloud Network",
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
                    "name": "ExpressRoute/DirectConnect",
                    "type": "dedicated-link",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 10,
                },
                {"name": "Global CDN", "type": "cdn", "bandwidth_mbps": 1000000, "latency_ms": 20},
                {
                    "name": "Plant Floor Gateway",
                    "type": "edge-network",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 15,
                },
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="Dassault Systèmes",
        market_position="leader",
        company_size="enterprise",
        founded_year=1981,
        headquarters="Vélizy-Villacoublay, France",
        revenue_usd=5500000000,
        customer_count=300000,
        market_share_percentage=12.0,
        acquisition_risk="very-low",
        financial_health="excellent",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                {
                    "name": "Digital Manufacturing",
                    "description": "Virtual-to-real manufacturing with digital twin",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Manufacturing Execution",
                    "description": "Real-time production execution and control",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Advanced Scheduling",
                    "description": "Finite capacity scheduling and optimization",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Process Planning",
                    "description": "Manufacturing process and work instruction authoring",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Robotics Simulation",
                    "description": "Robot programming and path optimization",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Factory Simulation",
                    "description": "Discrete event simulation of manufacturing lines",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Quality Management",
                    "description": "Integrated quality planning and execution",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Material Traceability",
                    "description": "End-to-end material genealogy",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "3D Work Instructions",
                    "description": "Visual animated work instructions",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Labor Management",
                    "description": "Workforce planning and tracking",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "Equipment Management",
                    "description": "Asset performance and maintenance",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "PLM-MES Integration",
                    "description": "Seamless engineering-to-operations",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Ergonomics Analysis",
                    "description": "Human factors and ergonomics simulation",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Line Balancing",
                    "description": "Assembly line optimization",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Facility Layout",
                    "description": "Factory floor planning and optimization",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Supply Chain Collaboration",
                    "description": "Supplier and customer collaboration",
                    "coverage_percentage": 86,
                    "maturity_level": "managed",
                },
                {
                    "name": "Manufacturing Analytics",
                    "description": "Real-time KPIs and intelligence",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Change Management",
                    "description": "Engineering change propagation to shop floor",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Compliance Management",
                    "description": "Regulatory and standards compliance",
                    "coverage_percentage": 90,
                    "maturity_level": "managed",
                },
                {
                    "name": "Virtual Commissioning",
                    "description": "Virtual factory startup and validation",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                # ADJACENT CAPABILITIES (Extended Manufacturing Support)
                {
                    "name": "Supplier Quality Management",
                    "description": "Supplier defect tracking and corrective action workflows",
                    "coverage_percentage": 83,
                    "maturity_level": "managed",
                },
                {
                    "name": "Customer Quality Portal",
                    "description": "Customer-facing quality data and certifications",
                    "coverage_percentage": 79,
                    "maturity_level": "managed",
                },
                {
                    "name": "Sustainability Reporting",
                    "description": "Carbon footprint, energy efficiency, ESG metrics",
                    "coverage_percentage": 77,
                    "maturity_level": "developing",
                },
                {
                    "name": "Workforce Management",
                    "description": "Shift planning, attendance, skill-based assignments",
                    "coverage_percentage": 85,
                    "maturity_level": "managed",
                },
                {
                    "name": "Material Requirements Integration",
                    "description": "MRP integration for material pull signals",
                    "coverage_percentage": 84,
                    "maturity_level": "managed",
                },
                {
                    "name": "Product Costing & Profitability",
                    "description": "Real-time product cost and margin analysis",
                    "coverage_percentage": 80,
                    "maturity_level": "managed",
                },
                {
                    "name": "Compliance Reporting",
                    "description": "Automated regulatory reporting (FDA, ISO, EPA)",
                    "coverage_percentage": 86,
                    "maturity_level": "managed",
                },
                {
                    "name": "Global Production Network",
                    "description": "Multi-plant production orchestration",
                    "coverage_percentage": 78,
                    "maturity_level": "managed",
                },
                {
                    "name": "AI-Driven Quality Prediction",
                    "description": "Machine learning for quality defect prediction",
                    "coverage_percentage": 75,
                    "maturity_level": "developing",
                },
                {
                    "name": "Warehouse Integration",
                    "description": "WMS integration for material staging and finished goods",
                    "coverage_percentage": 82,
                    "maturity_level": "managed",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Design-to-Manufacture",
                    "stages": [
                        "Product Design",
                        "Process Planning",
                        "Simulation Validation",
                        "Work Instructions",
                        "Shop Floor Execution",
                        "Feedback",
                    ],
                    "description": "PLM to MES integration",
                },
                {
                    "name": "Plan-to-Execute",
                    "stages": [
                        "Demand Planning",
                        "Finite Scheduling",
                        "Resource Allocation",
                        "Production Execution",
                        "Performance Analysis",
                    ],
                    "description": "Planning and execution",
                },
                {
                    "name": "Virtual-to-Real",
                    "stages": [
                        "Digital Twin Creation",
                        "Virtual Simulation",
                        "Optimization",
                        "Physical Implementation",
                        "Continuous Sync",
                    ],
                    "description": "Digital manufacturing",
                },
                {
                    "name": "Engineer-to-Order",
                    "stages": [
                        "Configuration",
                        "Process Planning",
                        "Simulation",
                        "Cost Estimation",
                        "Production",
                        "Delivery",
                    ],
                    "description": "Custom manufacturing",
                },
                {
                    "name": "Change-to-Production",
                    "stages": [
                        "ECO Initiation",
                        "Impact Analysis",
                        "Process Update",
                        "Work Instruction Revision",
                        "Shop Floor Implementation",
                    ],
                    "description": "Engineering change",
                },
                {
                    "name": "Robot-to-Production",
                    "stages": [
                        "Robot Programming",
                        "Path Simulation",
                        "Collision Detection",
                        "Cycle Time Optimization",
                        "Deployment",
                        "Monitoring",
                    ],
                    "description": "Robotics integration",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "Cloud-First Deployment",
                    "description": "Full 3DEXPERIENCE cloud implementation",
                    "timeline_months": 12,
                    "risk_level": "medium",
                },
                {
                    "name": "Hybrid Cloud Approach",
                    "description": "Cloud PLM with on-premise MES",
                    "timeline_months": 18,
                    "risk_level": "medium",
                },
                {
                    "name": "Phased Rollout",
                    "description": "Planning first, then MES, then simulation",
                    "timeline_months": 24,
                    "risk_level": "low",
                },
                {
                    "name": "Greenfield Factory",
                    "description": "New smart factory with full DELMIA suite",
                    "timeline_months": 15,
                    "risk_level": "medium",
                },
                {
                    "name": "Digital Twin First",
                    "description": "Start with simulation, then execute",
                    "timeline_months": 20,
                    "risk_level": "low",
                },
                {
                    "name": "Quick Win with Apriso",
                    "description": "MES-only rapid deployment",
                    "timeline_months": 9,
                    "risk_level": "low",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Manufacturing Execution Service",
                    "description": "Real-time production execution",
                    "service_type": "internal",
                    "sla_commitment": "99.9% uptime, < 1 second response",
                },
                {
                    "name": "Advanced Scheduling Service",
                    "description": "Optimize production schedules",
                    "service_type": "internal",
                    "sla_commitment": "Daily schedule optimization < 30 minutes",
                },
                {
                    "name": "Digital Twin Service",
                    "description": "Virtual factory simulation",
                    "service_type": "internal",
                    "sla_commitment": "Real-time digital twin sync",
                },
                {
                    "name": "Process Planning Service",
                    "description": "Manufacturing process authoring",
                    "service_type": "internal",
                    "sla_commitment": "PLM integration < 5 minutes",
                },
                {
                    "name": "Quality Management Service",
                    "description": "Quality planning and control",
                    "service_type": "internal",
                    "sla_commitment": "100% inspection traceability",
                },
                {
                    "name": "Material Tracking Service",
                    "description": "Material genealogy tracking",
                    "service_type": "internal",
                    "sla_commitment": "Real-time material visibility",
                },
                {
                    "name": "Work Instructions Service",
                    "description": "3D visual work instructions",
                    "service_type": "internal",
                    "sla_commitment": "Instant instruction retrieval",
                },
                {
                    "name": "Labor Management Service",
                    "description": "Workforce optimization",
                    "service_type": "internal",
                    "sla_commitment": "Real-time labor tracking",
                },
                {
                    "name": "Analytics Service",
                    "description": "Manufacturing intelligence",
                    "service_type": "internal",
                    "sla_commitment": "Real-time dashboard updates",
                },
                {
                    "name": "PLM Integration Service",
                    "description": "ENOVIA-DELMIA synchronization",
                    "service_type": "integration",
                    "sla_commitment": "< 1 minute ECO propagation",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Digital Manufacturing Process Planning",
                    "description": "Create manufacturing plans from 3D CAD",
                    "automation_level": "highly-automated",
                    "steps": [
                        "CAD Import",
                        "Process Definition",
                        "Resource Assignment",
                        "Time Study",
                        "Work Instruction Generation",
                        "Validation",
                        "Release",
                    ],
                    "cycle_time": "Days to weeks",
                    "kpis": ["Planning Accuracy", "Time to Release", "BOM Accuracy"],
                },
                {
                    "name": "Production Order Execution",
                    "description": "Execute manufacturing orders on shop floor",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Order Release",
                        "Scheduling",
                        "Material Staging",
                        "Work Instruction Display",
                        "Operation Execution",
                        "Quality Checks",
                        "Completion",
                    ],
                    "cycle_time": "Hours to days",
                    "kpis": ["On-Time Delivery", "First Pass Yield", "Cycle Time"],
                },
                {
                    "name": "Finite Capacity Scheduling",
                    "description": "Optimize production schedule with constraints",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Demand Load",
                        "Constraint Analysis",
                        "Optimization Algorithm",
                        "Schedule Generation",
                        "Conflict Resolution",
                        "Schedule Release",
                    ],
                    "cycle_time": "Minutes to hours",
                    "kpis": ["Schedule Adherence", "Resource Utilization", "Lead Time"],
                },
                {
                    "name": "Robot Programming & Simulation",
                    "description": "Program and validate robot operations",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Path Definition",
                        "Collision Detection",
                        "Cycle Time Optimization",
                        "Virtual Validation",
                        "Code Generation",
                        "Deployment",
                    ],
                    "cycle_time": "Days to weeks",
                    "kpis": ["Cycle Time", "Collision-Free Rate", "Programming Time"],
                },
                {
                    "name": "Engineering Change Order Execution",
                    "description": "Implement ECO on shop floor",
                    "automation_level": "highly-automated",
                    "steps": [
                        "ECO Notification",
                        "Impact Analysis",
                        "Process Update",
                        "Work Instruction Revision",
                        "Training",
                        "Implementation",
                        "Verification",
                    ],
                    "cycle_time": "Days",
                    "kpis": ["ECO Lead Time", "Implementation Accuracy", "Training Completion"],
                },
                {
                    "name": "Digital Twin Synchronization",
                    "description": "Keep virtual and physical in sync",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Real-Time Data Collection",
                        "Digital Twin Update",
                        "Deviation Detection",
                        "Analysis",
                        "Optimization Recommendation",
                    ],
                    "cycle_time": "Real-time (1 - minute intervals)",
                    "kpis": ["Sync Accuracy", "Deviation Rate", "Optimization Opportunities"],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Manufacturing Process Plan",
                    "description": "Detailed manufacturing process",
                    "lifecycle": "draft -> reviewed -> approved -> active -> superseded",
                },
                {
                    "name": "Production Order",
                    "description": "Shop floor work order",
                    "lifecycle": "created -> scheduled -> released -> in-progress -> completed",
                },
                {
                    "name": "Digital Twin",
                    "description": "Virtual representation of factory",
                    "lifecycle": "created -> calibrated -> synchronized -> optimized -> retired",
                },
                {
                    "name": "Robot Program",
                    "description": "Robot motion program",
                    "lifecycle": "created -> simulated -> validated -> deployed -> executed",
                },
                {
                    "name": "Work Instruction",
                    "description": "3D visual work instruction",
                    "lifecycle": "authored -> reviewed -> approved -> published -> executed",
                },
                {
                    "name": "Material Lot",
                    "description": "Tracked material batch",
                    "lifecycle": "received -> available -> issued -> consumed -> reported",
                },
                {
                    "name": "Quality Plan",
                    "description": "Inspection and test plan",
                    "lifecycle": "created -> approved -> active -> executed -> archived",
                },
                {
                    "name": "Production Schedule",
                    "description": "Optimized production schedule",
                    "lifecycle": "generated -> reviewed -> released -> executed -> completed",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Manufacturing Engineer",
                    "description": "Process planning specialist",
                    "responsibilities": [
                        "Process Planning",
                        "Work Instruction Authoring",
                        "Time Studies",
                        "BOM Management",
                    ],
                },
                {
                    "name": "Simulation Engineer",
                    "description": "Digital twin specialist",
                    "responsibilities": [
                        "Factory Simulation",
                        "Robot Programming",
                        "Line Balancing",
                        "Virtual Commissioning",
                    ],
                },
                {
                    "name": "Production Planner",
                    "description": "Schedule optimization specialist",
                    "responsibilities": [
                        "Demand Planning",
                        "Finite Scheduling",
                        "Capacity Analysis",
                        "Schedule Release",
                    ],
                },
                {
                    "name": "Production Operator",
                    "description": "Shop floor operator",
                    "responsibilities": [
                        "Order Execution",
                        "Material Handling",
                        "Quality Checks",
                        "Data Recording",
                    ],
                },
                {
                    "name": "Quality Engineer",
                    "description": "Quality assurance specialist",
                    "responsibilities": [
                        "Quality Planning",
                        "Inspection Execution",
                        "Non-Conformance Management",
                        "CAPA",
                    ],
                },
                {
                    "name": "Robotics Engineer",
                    "description": "Robot programming specialist",
                    "responsibilities": [
                        "Robot Programming",
                        "Path Optimization",
                        "Simulation Validation",
                        "Deployment",
                    ],
                },
                {
                    "name": "Process Engineer",
                    "description": "Process improvement specialist",
                    "responsibilities": [
                        "Process Optimization",
                        "Troubleshooting",
                        "Continuous Improvement",
                        "Best Practices",
                    ],
                },
                {
                    "name": "Production Supervisor",
                    "description": "Shop floor supervisor",
                    "responsibilities": [
                        "Order Management",
                        "Resource Allocation",
                        "Performance Monitoring",
                        "Problem Resolution",
                    ],
                },
                {
                    "name": "PLM Administrator",
                    "description": "System administrator",
                    "responsibilities": [
                        "User Management",
                        "Data Management",
                        "Integration Support",
                        "System Configuration",
                    ],
                },
                {
                    "name": "Plant Manager",
                    "description": "Plant operations manager",
                    "responsibilities": [
                        "Strategic Planning",
                        "Performance Review",
                        "Budget Management",
                        "Continuous Improvement",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "3DEXPERIENCE Platform",
                    "description": "Unified collaboration and data platform",
                    "target_market": "All Industries",
                },
                {
                    "name": "DELMIA Apriso",
                    "description": "Manufacturing execution system",
                    "target_market": "Discrete & Process Manufacturing",
                },
                {
                    "name": "DELMIA Ortems",
                    "description": "Advanced planning and scheduling",
                    "target_market": "Complex Manufacturing",
                },
                {
                    "name": "DELMIA Manufacturing Planning",
                    "description": "Process planning and work instructions",
                    "target_market": "Aerospace, Automotive, Industrial Equipment",
                },
                {
                    "name": "DELMIA Robotics",
                    "description": "Robot simulation and programming",
                    "target_market": "Automated Manufacturing",
                },
                {
                    "name": "DELMIA Operations",
                    "description": "Manufacturing operations management",
                    "target_market": "All Manufacturing",
                },
                {
                    "name": "DELMIA Virtual Twin",
                    "description": "Factory digital twin",
                    "target_market": "Smart Manufacturing",
                },
                {
                    "name": "ENOVIA",
                    "description": "Product lifecycle management",
                    "target_market": "All Industries",
                },
                {
                    "name": "CATIA",
                    "description": "3D CAD design",
                    "target_market": "Design & Engineering",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "3DEXPERIENCE Platform",
                    "type": "cloud-platform",
                    "description": "Unified platform foundation",
                    "technology": "Java/Angular",
                },
                {
                    "name": "DELMIA Apriso MES",
                    "type": "mes-application",
                    "description": "Manufacturing execution engine",
                    "technology": "Java/.NET",
                },
                {
                    "name": "DELMIA Ortems Scheduler",
                    "type": "scheduling-engine",
                    "description": "Finite capacity scheduler",
                    "technology": "C++/Java",
                },
                {
                    "name": "DELMIA Manufacturing Hub",
                    "type": "process-planning",
                    "description": "Process planning environment",
                    "technology": "Java/C++",
                },
                {
                    "name": "DELMIA Robotics Simulator",
                    "type": "simulation-engine",
                    "description": "Robot simulation and programming",
                    "technology": "C++",
                },
                {
                    "name": "ENOVIA PLM System",
                    "type": "plm-system",
                    "description": "Product lifecycle management",
                    "technology": "Java",
                },
                {
                    "name": "3D Visualization Engine",
                    "type": "rendering-engine",
                    "description": "Real-time 3D rendering",
                    "technology": "C++/WebGL",
                },
                {
                    "name": "Manufacturing Intelligence",
                    "type": "analytics-platform",
                    "description": "KPI and dashboard engine",
                    "technology": "Java/Python",
                },
                {
                    "name": "Integration Gateway",
                    "type": "integration-platform",
                    "description": "ERP and equipment integration",
                    "technology": "Java",
                },
                {
                    "name": "Mobile Work Instructions App",
                    "type": "mobile-application",
                    "description": "Operator mobile interface",
                    "technology": "React Native",
                },
                {
                    "name": "Oracle Database",
                    "type": "database",
                    "description": "Enterprise data storage",
                    "technology": "PL/SQL",
                },
                {
                    "name": "Kafka Message Bus",
                    "type": "message-broker",
                    "description": "Event streaming platform",
                    "technology": "Java",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "3DEXPERIENCE REST API",
                    "type": "REST",
                    "description": "Platform services API",
                    "endpoints": ["/resources/v1/*", "/engineering/v1/*"],
                },
                {
                    "name": "DELMIA Apriso API",
                    "type": "REST/SOAP",
                    "description": "MES operations API",
                    "endpoints": ["/AprisoAPI/v2/*"],
                },
                {
                    "name": "DELMIA Ortems API",
                    "type": "REST",
                    "description": "Scheduling API",
                    "endpoints": ["/ortems/api/v1/*"],
                },
                {
                    "name": "ENOVIA API",
                    "type": "REST",
                    "description": "PLM data services",
                    "endpoints": ["/enovia/resources/*"],
                },
                {
                    "name": "3D Visualization API",
                    "type": "WebSocket",
                    "description": "Real-time 3D streaming",
                    "endpoints": ["wss://3d.dassault.com/*"],
                },
                {
                    "name": "Manufacturing Intelligence API",
                    "type": "REST",
                    "description": "Analytics and KPI API",
                    "endpoints": ["/analytics/v1/*"],
                },
                {
                    "name": "Integration Services API",
                    "type": "REST",
                    "description": "ERP integration",
                    "endpoints": ["/integration/v1/*"],
                },
                {
                    "name": "Work Instructions API",
                    "type": "REST",
                    "description": "Digital work instructions",
                    "endpoints": ["/workInstructions/v1/*"],
                },
                {
                    "name": "Material Tracking API",
                    "type": "REST",
                    "description": "Material genealogy",
                    "endpoints": ["/materials/v1/*"],
                },
                {
                    "name": "Event Stream API",
                    "type": "Kafka",
                    "description": "Event-driven integration",
                    "endpoints": ["kafka://events/*"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "REST API",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "OAuth2/3DPassport",
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
                    "data_format": "Binary/JSON",
                    "authentication": "Token",
                },
                {
                    "name": "Kafka Interface",
                    "protocol": "Kafka",
                    "data_format": "Avro/JSON",
                    "authentication": "SASL",
                },
                {
                    "name": "Database Interface",
                    "protocol": "JDBC/OCI",
                    "data_format": "SQL",
                    "authentication": "Database User",
                },
                {
                    "name": "File Interface",
                    "protocol": "S3/SFTP",
                    "data_format": "Various",
                    "authentication": "API Key/SSH",
                },
                {
                    "name": "OPC UA Interface",
                    "protocol": "OPC UA",
                    "data_format": "OPC Types",
                    "authentication": "Certificate",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {
                    "name": "Manufacturing BOM",
                    "type": "master",
                    "retention_policy": "Product lifetime + 10 years",
                },
                {
                    "name": "Process Plan",
                    "type": "master",
                    "retention_policy": "Superseded + 7 years",
                },
                {
                    "name": "Production Order",
                    "type": "transactional",
                    "retention_policy": "Completion + 7 years",
                },
                {
                    "name": "Digital Twin Model",
                    "type": "simulation",
                    "retention_policy": "Model lifetime + 5 years",
                },
                {
                    "name": "Work Instruction",
                    "type": "document",
                    "retention_policy": "Revision + 10 years",
                },
                {
                    "name": "Material Genealogy",
                    "type": "regulatory",
                    "retention_policy": "Product lifetime + 15 years",
                },
                {"name": "Quality Record", "type": "regulatory", "retention_policy": "15 years"},
                {
                    "name": "Production Schedule",
                    "type": "transactional",
                    "retention_policy": "1 year",
                },
                {
                    "name": "Robot Program",
                    "type": "code",
                    "retention_policy": "Program lifetime + 5 years",
                },
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "Process Planning",
                    "type": "authoring",
                    "description": "Create manufacturing processes",
                },
                {
                    "name": "3D Simulation",
                    "type": "simulation",
                    "description": "Simulate factory operations",
                },
                {
                    "name": "Schedule Optimization",
                    "type": "optimization",
                    "description": "Optimize production schedule",
                },
                {
                    "name": "Order Execution",
                    "type": "transaction",
                    "description": "Execute production orders",
                },
                {
                    "name": "Material Tracking",
                    "type": "tracking",
                    "description": "Track material genealogy",
                },
                {
                    "name": "Robot Programming",
                    "type": "programming",
                    "description": "Program robot motions",
                },
                {
                    "name": "Quality Planning",
                    "type": "planning",
                    "description": "Create quality plans",
                },
                {
                    "name": "Work Instruction Display",
                    "type": "visualization",
                    "description": "Display 3D work instructions",
                },
                {
                    "name": "KPI Calculation",
                    "type": "analytics",
                    "description": "Calculate manufacturing KPIs",
                },
                {
                    "name": "PLM Synchronization",
                    "type": "integration",
                    "description": "Sync with ENOVIA PLM",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "VP Manufacturing",
                    "role": "executive",
                    "concerns": ["Digital Transformation", "Manufacturing Excellence", "ROI"],
                    "influence": "high",
                },
                {
                    "name": "VP Engineering",
                    "role": "executive",
                    "concerns": ["PLM-MES Integration", "Innovation", "Time to Market"],
                    "influence": "high",
                },
                {
                    "name": "Plant Manager",
                    "role": "management",
                    "concerns": ["Production Efficiency", "Quality", "Cost Control"],
                    "influence": "high",
                },
                {
                    "name": "Manufacturing Engineering Manager",
                    "role": "management",
                    "concerns": ["Process Planning", "Work Instructions", "Standardization"],
                    "influence": "high",
                },
                {
                    "name": "Robotics Manager",
                    "role": "technical",
                    "concerns": ["Robot Programming", "Cycle Time", "Automation"],
                    "influence": "medium",
                },
                {
                    "name": "IT/PLM Manager",
                    "role": "technical",
                    "concerns": ["System Integration", "Data Management", "Platform Strategy"],
                    "influence": "high",
                },
                {
                    "name": "Quality Director",
                    "role": "management",
                    "concerns": ["Quality Metrics", "Compliance", "Customer Satisfaction"],
                    "influence": "high",
                },
                {
                    "name": "Manufacturing Engineers",
                    "role": "technical",
                    "concerns": ["Process Efficiency", "Tool Usability", "Accuracy"],
                    "influence": "medium",
                },
                {
                    "name": "Production Supervisors",
                    "role": "operational",
                    "concerns": ["Shop Floor Performance", "System Usability", "Training"],
                    "influence": "medium",
                },
                {
                    "name": "CIO",
                    "role": "executive",
                    "concerns": ["Technology Strategy", "Cloud Migration", "Cybersecurity"],
                    "influence": "high",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Digital Transformation Mandate",
                    "description": "Company-wide Industry 4.0 initiative",
                    "urgency": "critical",
                    "impact": "transformational",
                },
                {
                    "name": "PLM-MES Gap",
                    "description": "Disconnect between engineering and operations",
                    "urgency": "high",
                    "impact": "transformational",
                },
                {
                    "name": "Manual Process Planning",
                    "description": "Time-consuming manual planning processes",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Robot Programming Bottleneck",
                    "description": "Offline programming not available",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Lack of Digital Twin",
                    "description": "No virtual validation before physical production",
                    "urgency": "medium",
                    "impact": "transformational",
                },
                {
                    "name": "Engineering Change Delays",
                    "description": "Slow ECO propagation to shop floor",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Complex Product Mix",
                    "description": "High variety and customization",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "New Plant Investment",
                    "description": "Greenfield smart factory project",
                    "urgency": "critical",
                    "impact": "transformational",
                },
                {
                    "name": "Competitive Pressure",
                    "description": "Need for faster time to market",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Quality Improvement Need",
                    "description": "Reduce defects and improve first-time quality",
                    "urgency": "high",
                    "impact": "medium",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "Achieve Digital Twin Coverage",
                    "description": "Virtual representation of all factories",
                    "timeframe": "24 months",
                    "measurable": "100% factory digital twin coverage",
                },
                {
                    "name": "Reduce Process Planning Time 60%",
                    "description": "Automate process planning",
                    "timeframe": "18 months",
                    "measurable": "Planning time from 5 days to 2 days",
                },
                {
                    "name": "100% PLM-MES Integration",
                    "description": "Seamless engineering-to-operations",
                    "timeframe": "12 months",
                    "measurable": "< 1 hour ECO propagation",
                },
                {
                    "name": "Improve Robot Programming Efficiency 70%",
                    "description": "Offline programming for all robots",
                    "timeframe": "18 months",
                    "measurable": "Programming time reduction 70%",
                },
                {
                    "name": "Achieve 95% Schedule Adherence",
                    "description": "Improve on-time delivery",
                    "timeframe": "12 months",
                    "measurable": "Schedule adherence from 78% to 95%",
                },
                {
                    "name": "Reduce New Product Introduction Time 50%",
                    "description": "Faster time to market",
                    "timeframe": "24 months",
                    "measurable": "NPI cycle time from 12 months to 6 months",
                },
                {
                    "name": "Eliminate Paper Work Instructions",
                    "description": "100% digital work instructions",
                    "timeframe": "18 months",
                    "measurable": "Zero paper on shop floor",
                },
                {
                    "name": "Improve First Time Quality to 98%",
                    "description": "Reduce defects",
                    "timeframe": "18 months",
                    "measurable": "FTQ from 92% to 98%",
                },
                {
                    "name": "Deploy Smart Factory",
                    "description": "Launch greenfield smart factory",
                    "timeframe": "36 months",
                    "measurable": "New factory operational",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "Digital Manufacturing Leadership",
                    "description": "Industry-leading virtual-to-real capability",
                    "benefit_type": "strategic",
                    "quantified_benefit": "100% digital twin coverage",
                },
                {
                    "name": "Engineering Productivity",
                    "description": "Dramatically faster process planning",
                    "benefit_type": "operational",
                    "quantified_benefit": "60% planning time reduction, $4M savings",
                },
                {
                    "name": "Seamless PLM-MES",
                    "description": "Real-time engineering-to-operations",
                    "benefit_type": "technical",
                    "quantified_benefit": "< 1 hour ECO propagation, 80% faster",
                },
                {
                    "name": "Robotics Excellence",
                    "description": "World-class robot programming efficiency",
                    "benefit_type": "operational",
                    "quantified_benefit": "70% programming time reduction",
                },
                {
                    "name": "Manufacturing Agility",
                    "description": "Rapid response to demand changes",
                    "benefit_type": "strategic",
                    "quantified_benefit": "95% schedule adherence, 50% faster NPI",
                },
                {
                    "name": "Paperless Operations",
                    "description": "Fully digital work instructions",
                    "benefit_type": "operational",
                    "quantified_benefit": "100% paperless, $2M savings",
                },
                {
                    "name": "Quality Excellence",
                    "description": "Best-in-class quality performance",
                    "benefit_type": "quality",
                    "quantified_benefit": "98% FTQ, 50% defect reduction",
                },
                {
                    "name": "Smart Factory Success",
                    "description": "Operational smart factory",
                    "benefit_type": "strategic",
                    "quantified_benefit": "New factory delivering 30% higher productivity",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Virtual Before Real",
                    "description": "Simulate and validate before physical implementation",
                    "rationale": "Reduce risk and optimize performance",
                },
                {
                    "name": "Single Source of Truth",
                    "description": "Unified 3DEXPERIENCE platform for all data",
                    "rationale": "Eliminate data silos and inconsistencies",
                },
                {
                    "name": "PLM-Driven Manufacturing",
                    "description": "Manufacturing processes derived from PLM",
                    "rationale": "Ensure engineering-operations alignment",
                },
                {
                    "name": "3D-First",
                    "description": "3D models and instructions for everything",
                    "rationale": "Improve understanding and accuracy",
                },
                {
                    "name": "Continuous Digital Thread",
                    "description": "Unbroken data flow from design to production",
                    "rationale": "Enable traceability and optimization",
                },
                {
                    "name": "Model-Based Definition",
                    "description": "3D model is the master definition",
                    "rationale": "Eliminate 2D drawings",
                },
                {
                    "name": "Cloud-Native",
                    "description": "Leverage cloud scalability and accessibility",
                    "rationale": "Enable global collaboration",
                },
                {
                    "name": "Simulation-Driven",
                    "description": "Use simulation for all decisions",
                    "rationale": "Data-driven decision making",
                },
                {
                    "name": "Continuous Optimization",
                    "description": "Always optimize processes and schedules",
                    "rationale": "Sustain competitive advantage",
                },
                {
                    "name": "Human-Centric Design",
                    "description": "Design for operator ergonomics and usability",
                    "rationale": "Improve safety and productivity",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "System Availability",
                    "type": "performance",
                    "description": "Platform available 99.9% of time",
                    "priority": "critical",
                },
                {
                    "name": "3D Rendering Performance",
                    "type": "performance",
                    "description": "Smooth 60 FPS 3D visualization",
                    "priority": "high",
                },
                {
                    "name": "Simulation Performance",
                    "type": "performance",
                    "description": "Factory simulation run < 1 hour for 1 year",
                    "priority": "high",
                },
                {
                    "name": "Concurrent Users",
                    "type": "capacity",
                    "description": "Support 5,000 global concurrent users",
                    "priority": "high",
                },
                {
                    "name": "PLM Integration Latency",
                    "type": "integration",
                    "description": "ECO propagation < 1 hour",
                    "priority": "critical",
                },
                {
                    "name": "Data Retention",
                    "type": "compliance",
                    "description": "Retain data per regulatory requirements",
                    "priority": "critical",
                },
                {
                    "name": "3D Model Size",
                    "type": "capacity",
                    "description": "Support 500MB+ assembly models",
                    "priority": "high",
                },
                {
                    "name": "Mobile Support",
                    "type": "functional",
                    "description": "Full-featured mobile app for operators",
                    "priority": "medium",
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
                    "description": "SOC 2 Type II, ISO 27001 certified",
                    "priority": "critical",
                },
                {
                    "name": "Multi-Language",
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
                    "description": "Total program budget $30M",
                },
                {
                    "name": "Timeline Pressure",
                    "type": "schedule",
                    "description": "Smart factory must launch in 36 months",
                },
                {
                    "name": "Cloud Dependency",
                    "type": "technical",
                    "description": "Requires cloud connectivity",
                },
                {
                    "name": "3D Workstation Requirements",
                    "type": "technical",
                    "description": "High-performance workstations needed",
                },
                {
                    "name": "Skills Gap",
                    "type": "resource",
                    "description": "Limited DELMIA expertise",
                },
                {
                    "name": "Change Management",
                    "type": "organizational",
                    "description": "Significant cultural transformation required",
                },
                {
                    "name": "Legacy System Integration",
                    "type": "technical",
                    "description": "Must integrate with existing ERP/PLM",
                },
                {
                    "name": "Network Bandwidth",
                    "type": "technical",
                    "description": "High bandwidth required for 3D streaming",
                },
                {
                    "name": "Vendor Lock-In",
                    "type": "strategic",
                    "description": "Heavy dependence on Dassault ecosystem",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "Digital Maturity Assessment",
                    "type": "maturity",
                    "description": "Assess digital manufacturing readiness",
                    "result": "Level 2 maturity, significant opportunity",
                },
                {
                    "name": "PLM-MES Integration Assessment",
                    "type": "technical",
                    "description": "Evaluate integration feasibility",
                    "result": "Moderate complexity, ENOVIA already deployed",
                },
                {
                    "name": "Infrastructure Assessment",
                    "type": "technical",
                    "description": "Network and workstation readiness",
                    "result": "Workstation upgrades needed, network sufficient",
                },
                {
                    "name": "ROI Analysis",
                    "type": "financial",
                    "description": "Business case validation",
                    "result": "Projected 280% ROI over 5 years",
                },
                {
                    "name": "Change Readiness",
                    "type": "organizational",
                    "description": "Organizational change capability",
                    "result": "Moderate readiness, strong executive support",
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
                    "description": "Project charter and team formation",
                },
                {
                    "name": "3DEXPERIENCE Platform Live",
                    "date": "2024 - 06 - 30",
                    "milestone": True,
                    "description": "Cloud platform operational",
                },
                {
                    "name": "ENOVIA-DELMIA Integration Complete",
                    "date": "2024 - 09 - 30",
                    "milestone": True,
                    "description": "PLM-MES integration live",
                },
                {
                    "name": "Pilot Line Digital Twin",
                    "date": "2024 - 12 - 31",
                    "milestone": True,
                    "description": "First digital twin operational",
                },
                {
                    "name": "Apriso MES Go-Live",
                    "date": "2025 - 03 - 31",
                    "milestone": True,
                    "description": "First plant on Apriso",
                },
                {
                    "name": "Robotics Simulation Operational",
                    "date": "2025 - 06 - 30",
                    "milestone": False,
                    "description": "Robot offline programming live",
                },
                {
                    "name": "Smart Factory Groundbreaking",
                    "date": "2025 - 09 - 30",
                    "milestone": True,
                    "description": "New factory construction start",
                },
                {
                    "name": "Full Digital Twin Coverage",
                    "date": "2026 - 06 - 30",
                    "milestone": True,
                    "description": "All factories have digital twins",
                },
                {
                    "name": "Smart Factory Opening",
                    "date": "2027 - 01 - 15",
                    "milestone": True,
                    "description": "New smart factory operational",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Program Management",
                    "description": "Overall program governance",
                    "duration_weeks": 156,
                    "team_size": 8,
                },
                {
                    "name": "3DEXPERIENCE Platform Setup",
                    "description": "Cloud platform deployment",
                    "duration_weeks": 24,
                    "team_size": 12,
                },
                {
                    "name": "PLM-MES Integration",
                    "description": "ENOVIA-DELMIA integration",
                    "duration_weeks": 32,
                    "team_size": 10,
                },
                {
                    "name": "Digital Twin Development",
                    "description": "Factory digital twin creation",
                    "duration_weeks": 52,
                    "team_size": 15,
                },
                {
                    "name": "Apriso MES Deployment",
                    "description": "Manufacturing execution system",
                    "duration_weeks": 40,
                    "team_size": 20,
                },
                {
                    "name": "Process Planning Implementation",
                    "description": "DELMIA Manufacturing Planning",
                    "duration_weeks": 36,
                    "team_size": 12,
                },
                {
                    "name": "Robotics Simulation",
                    "description": "DELMIA Robotics deployment",
                    "duration_weeks": 30,
                    "team_size": 8,
                },
                {
                    "name": "Ortems Scheduling",
                    "description": "Advanced scheduling implementation",
                    "duration_weeks": 28,
                    "team_size": 6,
                },
                {
                    "name": "Smart Factory Design",
                    "description": "New factory virtual design",
                    "duration_weeks": 78,
                    "team_size": 25,
                },
                {
                    "name": "Training & Change Management",
                    "description": "User adoption program",
                    "duration_weeks": 104,
                    "team_size": 10,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Digital Manufacturing Strategy",
                    "type": "document",
                    "due_phase": "initiation",
                    "owner": "Program Director",
                },
                {
                    "name": "3DEXPERIENCE Platform",
                    "type": "cloud-platform",
                    "due_phase": "build",
                    "owner": "Platform Lead",
                },
                {
                    "name": "PLM-MES Integration",
                    "type": "integration",
                    "due_phase": "build",
                    "owner": "Integration Architect",
                },
                {
                    "name": "Factory Digital Twin",
                    "type": "simulation-model",
                    "due_phase": "build",
                    "owner": "Digital Twin Lead",
                },
                {
                    "name": "Apriso MES System",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "MES Lead",
                },
                {
                    "name": "Process Plans Library",
                    "type": "content",
                    "due_phase": "build",
                    "owner": "Manufacturing Engineering",
                },
                {
                    "name": "Robot Programs",
                    "type": "code",
                    "due_phase": "build",
                    "owner": "Robotics Engineer",
                },
                {
                    "name": "Smart Factory Design",
                    "type": "design",
                    "due_phase": "design",
                    "owner": "Factory Design Lead",
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
                    "name": "Platform Operational",
                    "date": "2024 - 06 - 30",
                    "description": "3DEXPERIENCE cloud platform live",
                },
                {
                    "name": "PLM-MES Integrated",
                    "date": "2024 - 09 - 30",
                    "description": "Seamless engineering-to-operations",
                },
                {
                    "name": "First Digital Twin",
                    "date": "2024 - 12 - 31",
                    "description": "Pilot factory virtualized",
                },
                {
                    "name": "MES Deployed",
                    "date": "2025 - 03 - 31",
                    "description": "First plant on Apriso",
                },
                {
                    "name": "Full Digital Coverage",
                    "date": "2026 - 06 - 30",
                    "description": "All factories have digital twins",
                },
                {
                    "name": "Smart Factory Live",
                    "date": "2027 - 01 - 15",
                    "description": "New smart factory operational",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "AWS Cloud Region US-East - 1",
                    "location": "Virginia, USA",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "Primary cloud deployment",
                },
                {
                    "name": "AWS Cloud Region EU-West - 1",
                    "location": "Ireland",
                    "tier": "Tier IV",
                    "size_sqm": "N/A",
                    "description": "European cloud deployment",
                },
                {
                    "name": "Smart Factory (Future)",
                    "location": "Austin, TX",
                    "tier": "Tier II",
                    "size_sqm": 50000,
                    "description": "New greenfield smart factory",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "Cloud Compute Instances",
                    "type": "cloud-vm",
                    "quantity": 50,
                    "location": "AWS",
                    "specs": "m5.8xlarge, 32 vCPU, 128GB RAM",
                },
                {
                    "name": "GPU Simulation Instances",
                    "type": "cloud-gpu",
                    "quantity": 10,
                    "location": "AWS",
                    "specs": "p3.8xlarge, 4x V100 GPU",
                },
                {
                    "name": "Engineering Workstations",
                    "type": "workstation",
                    "quantity": 200,
                    "location": "Engineering Offices",
                    "specs": "Dell Precision, Xeon, 64GB RAM, Quadro RTX",
                },
                {
                    "name": "Operator Tablets",
                    "type": "tablet",
                    "quantity": 500,
                    "location": "Shop Floor",
                    "specs": "iPad Pro 12.9 - inch",
                },
                {
                    "name": "3D Visualization Displays",
                    "type": "display",
                    "quantity": 100,
                    "location": "Production Stations",
                    "specs": "4K 55 - inch touchscreen",
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
                    "coverage": "Plant to Cloud",
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
                    "name": "Corporate WAN",
                    "type": "wan",
                    "coverage": "All Sites",
                    "bandwidth_mbps": 1000,
                    "provider": "AT&T",
                },
            ]
        ),
    )


def seed_dassault_delmia(link_capabilities: bool = True):
    """
    Main execution function

    Args:
        link_capabilities: If True, automatically link capabilities to BusinessCapability records
    """
    app = create_app(DevelopmentConfig)

    with app.app_context():
        try:
            # Check if template already exists
            existing = VendorStackTemplate.query.filter_by(vendor_name="Dassault Systèmes").first()
            if existing:
                print("⚠️  Dassault DELMIA template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_dassault_delmia_template()
            db.session.add(template)
            db.session.commit()

            print("✅ Dassault DELMIA template seeded successfully!")
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
                f"   - Implementation Layer: ✅ Complete (9 events, 10 work packages, 9 deliverables, 6 plateaus)"
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
            print(f"❌ Error seeding Dassault DELMIA template: {str(e)}")
            import traceback

            traceback.print_exc()

            raise


if __name__ == "__main__":
    seed_dassault_delmia()
