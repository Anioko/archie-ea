"""
Rockwell Automation FactoryTalk Comprehensive Vendor Template Seed Data

Complete ArchiMate 3.2 coverage across ALL layers:
- Strategy Layer
- Business Layer
- Application Layer
- Technology Layer
- Motivation Layer
- Implementation & Migration Layer
- Physical Layer

Run with: python manage.py seed-vendor-rockwell
"""
import json

from app import create_app, db
from app.models import User, VendorStackTemplate
from config import DevelopmentConfig


def create_rockwell_factorytalk_template():
    """Rockwell FactoryTalk FULLY COMPREHENSIVE template - ALL ArchiMate 3.2 layers"""
    return VendorStackTemplate(
        vendor_name="Rockwell Automation",
        name="Rockwell FactoryTalk Manufacturing Suite",
        description="Integrated manufacturing operations management platform combining MES, batch, historian, analytics, and HMI/SCADA for discrete, process, and hybrid manufacturing environments",
        # ==================== TECHNOLOGY LAYER ====================
        platform="on-premise",
        primary_language="c-sharp",
        framework=".NET Framework",
        framework_version="4.8",
        primary_database="sql-server",
        database_version="2019",
        container_runtime="none",
        orchestration="none",
        service_mesh="none",
        api_standard="REST",
        api_gateway="iis",
        message_broker="factorytalk-linx",
        auth_provider="active-directory",
        secrets_manager="windows-dpapi",
        logging_framework="factorytalk-diagnostics",
        metrics_platform="factorytalk-metrics",
        apm_tool="none",
        tracing_tool="factorytalk-diagnostics",
        build_tool="visual-studio",
        ci_cd_platform="none",
        sast_tool="none",
        dast_tool="none",
        dependency_scanner="none",
        nodes=json.dumps(
            [
                {
                    "name": "FactoryTalk View SE Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "FactoryTalk Batch Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "FactoryTalk Historian Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 128,
                },
                {
                    "name": "FactoryTalk VantagePoint Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "FactoryTalk Production Centre Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 16,
                    "ram_gb": 64,
                },
                {
                    "name": "SQL Server Database",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 32,
                    "ram_gb": 256,
                },
                {
                    "name": "FactoryTalk Directory Server",
                    "type": "virtual-machine",
                    "os": "Windows Server 2019",
                    "cpu_cores": 8,
                    "ram_gb": 32,
                },
                {
                    "name": "HMI Operator Stations",
                    "type": "workstation",
                    "os": "Windows 10",
                    "cpu_cores": 4,
                    "ram_gb": 16,
                },
            ]
        ),
        devices=json.dumps(
            [
                {
                    "name": "Allen-Bradley ControlLogix PLC",
                    "type": "plc",
                    "description": "Primary process control logic",
                },
                {
                    "name": "Allen-Bradley CompactLogix PLC",
                    "type": "plc",
                    "description": "Machine-level control",
                },
                {
                    "name": "StratixManaged Ethernet Switch",
                    "type": "network-switch",
                    "description": "Industrial network infrastructure",
                },
                {
                    "name": "PanelView Plus HMI",
                    "type": "operator-interface",
                    "description": "Machine-level operator interface",
                },
                {
                    "name": "PowerFlex VFD",
                    "type": "variable-frequency-drive",
                    "description": "Motor control",
                },
            ]
        ),
        system_software=json.dumps(
            [
                {"name": "FactoryTalk View SE", "type": "hmi-scada", "version": "13.0"},
                {"name": "FactoryTalk Batch", "type": "batch-management", "version": "14.0"},
                {"name": "FactoryTalk Historian SE", "type": "historian", "version": "7.0"},
                {"name": "FactoryTalk VantagePoint", "type": "analytics", "version": "8.0"},
                {"name": "FactoryTalk Production Centre", "type": "mes", "version": "6.0"},
                {
                    "name": "FactoryTalk Transaction Manager",
                    "type": "mes-module",
                    "version": "12.0",
                },
                {"name": "FactoryTalk Metrics", "type": "oee-software", "version": "3.0"},
                {
                    "name": "Studio 5000 Logix Designer",
                    "type": "plc-programming",
                    "version": "35.0",
                },
                {"name": "FactoryTalk Linx", "type": "communication-driver", "version": "6.30"},
                {"name": "Microsoft SQL Server", "type": "database", "version": "2019 Standard"},
            ]
        ),
        technology_services=json.dumps(
            [
                {
                    "name": "FactoryTalk View SE Service",
                    "type": "hmi-runtime",
                    "description": "SCADA/HMI visualization and control",
                },
                {
                    "name": "FactoryTalk Batch Service",
                    "type": "batch-engine",
                    "description": "ISA - 88 compliant batch execution",
                },
                {
                    "name": "FactoryTalk Historian Service",
                    "type": "time-series-database",
                    "description": "High-speed process data collection",
                },
                {
                    "name": "FactoryTalk VantagePoint Service",
                    "type": "analytics-engine",
                    "description": "Manufacturing intelligence and KPIs",
                },
                {
                    "name": "FactoryTalk Production Centre Service",
                    "type": "mes-engine",
                    "description": "Production order and material management",
                },
                {
                    "name": "FactoryTalk Transaction Manager Service",
                    "type": "data-collection",
                    "description": "Operator and machine data collection",
                },
                {
                    "name": "FactoryTalk Metrics Service",
                    "type": "oee-calculation",
                    "description": "OEE and downtime tracking",
                },
                {
                    "name": "FactoryTalk Directory Service",
                    "type": "directory",
                    "description": "Centralized user and tag management",
                },
                {
                    "name": "FactoryTalk Linx Gateway",
                    "type": "communication-gateway",
                    "description": "Allen-Bradley device connectivity",
                },
                {
                    "name": "FactoryTalk Alarm & Events Service",
                    "type": "alarm-management",
                    "description": "Centralized alarm handling",
                },
                {
                    "name": "FactoryTalk Security Service",
                    "type": "security",
                    "description": "User authentication and authorization",
                },
                {
                    "name": "FactoryTalk AssetCentre Service",
                    "type": "asset-management",
                    "description": "Application version control",
                },
            ]
        ),
        artifacts=json.dumps(
            [
                {
                    "name": "FactoryTalk View Application (.APA)",
                    "type": "hmi-project",
                    "size_mb": 100,
                    "registry": "View SE Server",
                },
                {
                    "name": "FactoryTalk Batch Recipe",
                    "type": "batch-recipe",
                    "size_mb": 5,
                    "registry": "Batch Server",
                },
                {
                    "name": "Historian Archive",
                    "type": "time-series-data",
                    "size_mb": 500000,
                    "registry": "Historian Server",
                },
                {
                    "name": "VantagePoint Dashboard",
                    "type": "analytics-dashboard",
                    "size_mb": 10,
                    "registry": "VantagePoint Server",
                },
                {
                    "name": "Studio 5000 Project (.ACD)",
                    "type": "plc-program",
                    "size_mb": 50,
                    "registry": "ControlLogix PLC",
                },
                {
                    "name": "Database Backup",
                    "type": "backup-archive",
                    "size_mb": 100000,
                    "registry": "SQL Server",
                },
            ]
        ),
        communication_networks=json.dumps(
            [
                {
                    "name": "EtherNet/IP Control Network",
                    "type": "industrial-ethernet",
                    "bandwidth_mbps": 1000,
                    "latency_ms": 3,
                },
                {
                    "name": "ControlNet Network",
                    "type": "deterministic",
                    "bandwidth_mbps": 5,
                    "latency_ms": 1,
                },
                {
                    "name": "DeviceNet Network",
                    "type": "fieldbus",
                    "bandwidth_mbps": 0.5,
                    "latency_ms": 2,
                },
                {
                    "name": "Plant IT Network",
                    "type": "ethernet",
                    "bandwidth_mbps": 10000,
                    "latency_ms": 5,
                },
            ]
        ),
        # ==================== VENDOR CONTEXT ====================
        vendor_company_name="Rockwell Automation",
        market_position="leader",
        company_size="enterprise",
        founded_year=1903,
        headquarters="Milwaukee, Wisconsin",
        revenue_usd=8000000000,
        customer_count=50000,
        market_share_percentage=18.0,
        acquisition_risk="very-low",
        financial_health="excellent",
        # ==================== STRATEGY LAYER ====================
        capabilities_enabled=json.dumps(
            [
                {
                    "name": "Process Visualization & Control",
                    "description": "Real-time HMI/SCADA for plant-wide operations",
                    "coverage_percentage": 99,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Batch Process Management",
                    "description": "ISA - 88 compliant batch recipe execution",
                    "coverage_percentage": 98,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Historical Data Management",
                    "description": "High-performance time-series data storage",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Manufacturing Analytics",
                    "description": "Real-time KPI dashboards and reporting",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Production Management",
                    "description": "Work order, material, and resource management",
                    "coverage_percentage": 94,
                    "maturity_level": "managed",
                },
                {
                    "name": "OEE Tracking",
                    "description": "Overall equipment effectiveness monitoring",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Alarm Management",
                    "description": "ISA - 18.2 compliant alarm rationalization",
                    "coverage_percentage": 93,
                    "maturity_level": "managed",
                },
                {
                    "name": "Data Collection",
                    "description": "Operator and machine data capture",
                    "coverage_percentage": 95,
                    "maturity_level": "optimized",
                },
                {
                    "name": "PLC Integration",
                    "description": "Native Allen-Bradley PLC connectivity",
                    "coverage_percentage": 100,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Recipe Management",
                    "description": "Master and control recipe management",
                    "coverage_percentage": 97,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Material Tracking",
                    "description": "Lot tracking and genealogy",
                    "coverage_percentage": 92,
                    "maturity_level": "managed",
                },
                {
                    "name": "Downtime Tracking",
                    "description": "Automated downtime capture and classification",
                    "coverage_percentage": 94,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Quality Management",
                    "description": "SPC and quality data management",
                    "coverage_percentage": 89,
                    "maturity_level": "managed",
                },
                {
                    "name": "Asset Performance",
                    "description": "Equipment monitoring and predictive maintenance",
                    "coverage_percentage": 88,
                    "maturity_level": "managed",
                },
                {
                    "name": "Energy Management",
                    "description": "Energy consumption monitoring and optimization",
                    "coverage_percentage": 85,
                    "maturity_level": "developing",
                },
                {
                    "name": "Regulatory Compliance",
                    "description": "21 CFR Part 11 compliance for pharma",
                    "coverage_percentage": 91,
                    "maturity_level": "managed",
                },
                {
                    "name": "Mobile Access",
                    "description": "Mobile HMI and analytics access",
                    "coverage_percentage": 87,
                    "maturity_level": "managed",
                },
                {
                    "name": "Advanced Process Control",
                    "description": "Model predictive control integration",
                    "coverage_percentage": 82,
                    "maturity_level": "developing",
                },
                {
                    "name": "Batch Genealogy",
                    "description": "Complete batch execution traceability",
                    "coverage_percentage": 96,
                    "maturity_level": "optimized",
                },
                {
                    "name": "Industrial IoT Integration",
                    "description": "Cloud connectivity for analytics",
                    "coverage_percentage": 80,
                    "maturity_level": "developing",
                },
                # ADJACENT CAPABILITIES (Extended Manufacturing Support)
                {
                    "name": "ERP Integration",
                    "description": "SAP/Oracle integration for production orders and inventory",
                    "coverage_percentage": 85,
                    "maturity_level": "managed",
                },
                {
                    "name": "Warehouse Management Integration",
                    "description": "WMS connectivity for material flow",
                    "coverage_percentage": 83,
                    "maturity_level": "managed",
                },
                {
                    "name": "Supply Chain Visibility",
                    "description": "Real-time material and capacity visibility",
                    "coverage_percentage": 81,
                    "maturity_level": "managed",
                },
                {
                    "name": "Production Scheduling Integration",
                    "description": "APS integration for schedule optimization",
                    "coverage_percentage": 79,
                    "maturity_level": "managed",
                },
                {
                    "name": "Operator Performance Analytics",
                    "description": "Labor productivity and training gap analysis",
                    "coverage_percentage": 82,
                    "maturity_level": "managed",
                },
                {
                    "name": "Environmental Monitoring",
                    "description": "Emissions, waste, and environmental compliance tracking",
                    "coverage_percentage": 77,
                    "maturity_level": "developing",
                },
                {
                    "name": "Cost Accounting Integration",
                    "description": "Real-time production cost capture and variance",
                    "coverage_percentage": 80,
                    "maturity_level": "managed",
                },
                {
                    "name": "Customer Order Tracking",
                    "description": "Link production to customer orders for visibility",
                    "coverage_percentage": 78,
                    "maturity_level": "managed",
                },
                {
                    "name": "Multi-Plant Coordination",
                    "description": "Global MES coordination across sites",
                    "coverage_percentage": 76,
                    "maturity_level": "developing",
                },
                {
                    "name": "Augmented Reality Work Instructions",
                    "description": "AR-based training and work guidance",
                    "coverage_percentage": 72,
                    "maturity_level": "developing",
                },
            ]
        ),
        value_streams_supported=json.dumps(
            [
                {
                    "name": "Batch-to-Completion",
                    "stages": [
                        "Recipe Selection",
                        "Material Allocation",
                        "Batch Start",
                        "Phase Execution",
                        "Quality Checks",
                        "Batch End",
                        "Genealogy",
                    ],
                    "description": "Process batch manufacturing",
                },
                {
                    "name": "Production-to-Performance",
                    "stages": [
                        "Order Release",
                        "Line Assignment",
                        "Production",
                        "Data Collection",
                        "OEE Calculation",
                        "Performance Analysis",
                    ],
                    "description": "Discrete manufacturing execution",
                },
                {
                    "name": "Alarm-to-Resolution",
                    "stages": [
                        "Alarm Generation",
                        "Operator Notification",
                        "Acknowledgment",
                        "Investigation",
                        "Resolution",
                        "Documentation",
                    ],
                    "description": "Alarm management",
                },
                {
                    "name": "Data-to-Insight",
                    "stages": [
                        "Data Collection",
                        "Historian Storage",
                        "KPI Calculation",
                        "Dashboard Visualization",
                        "Trend Analysis",
                        "Decision",
                    ],
                    "description": "Manufacturing intelligence",
                },
                {
                    "name": "Downtime-to-Recovery",
                    "stages": [
                        "Downtime Detection",
                        "Classification",
                        "Root Cause",
                        "Corrective Action",
                        "Restart",
                        "Analysis",
                    ],
                    "description": "Downtime management",
                },
                {
                    "name": "Monitor-to-Maintain",
                    "stages": [
                        "Condition Monitoring",
                        "Predictive Alert",
                        "Maintenance Order",
                        "Execution",
                        "Verification",
                        "Asset Update",
                    ],
                    "description": "Asset performance",
                },
            ]
        ),
        courses_of_action=json.dumps(
            [
                {
                    "name": "Integrated Rollout",
                    "description": "Deploy all FactoryTalk products together",
                    "timeline_months": 18,
                    "risk_level": "medium-high",
                },
                {
                    "name": "Phased by Product",
                    "description": "Deploy View, then Batch, then Historian, etc.",
                    "timeline_months": 24,
                    "risk_level": "low",
                },
                {
                    "name": "Line-by-Line Deployment",
                    "description": "Complete one line before moving to next",
                    "timeline_months": 20,
                    "risk_level": "low",
                },
                {
                    "name": "Quick Win Approach",
                    "description": "Start with Metrics/OEE for fast ROI",
                    "timeline_months": 6,
                    "risk_level": "very-low",
                },
                {
                    "name": "Greenfield New Plant",
                    "description": "Full deployment in new facility",
                    "timeline_months": 12,
                    "risk_level": "medium",
                },
                {
                    "name": "Brownfield Upgrade",
                    "description": "Replace legacy systems incrementally",
                    "timeline_months": 30,
                    "risk_level": "high",
                },
            ]
        ),
        # ==================== BUSINESS LAYER ====================
        business_services=json.dumps(
            [
                {
                    "name": "Process Control Service",
                    "description": "Real-time plant monitoring and control",
                    "service_type": "internal",
                    "sla_commitment": "99.99% uptime, < 100ms response",
                },
                {
                    "name": "Batch Execution Service",
                    "description": "Execute batch manufacturing recipes",
                    "service_type": "internal",
                    "sla_commitment": "100% recipe compliance",
                },
                {
                    "name": "Data Historian Service",
                    "description": "Store and retrieve process data",
                    "service_type": "internal",
                    "sla_commitment": "100,000 tags/sec collection",
                },
                {
                    "name": "Analytics Service",
                    "description": "Real-time KPI calculation and dashboards",
                    "service_type": "internal",
                    "sla_commitment": "Real-time dashboard updates",
                },
                {
                    "name": "Production Tracking Service",
                    "description": "Track production orders and materials",
                    "service_type": "internal",
                    "sla_commitment": "Real-time inventory updates",
                },
                {
                    "name": "OEE Monitoring Service",
                    "description": "Calculate and display OEE metrics",
                    "service_type": "internal",
                    "sla_commitment": "< 1 minute OEE refresh",
                },
                {
                    "name": "Alarm Management Service",
                    "description": "Manage plant-wide alarms",
                    "service_type": "internal",
                    "sla_commitment": "< 100ms alarm propagation",
                },
                {
                    "name": "Data Collection Service",
                    "description": "Capture operator and machine data",
                    "service_type": "internal",
                    "sla_commitment": "99.9% data capture accuracy",
                },
                {
                    "name": "Asset Monitoring Service",
                    "description": "Monitor equipment health",
                    "service_type": "internal",
                    "sla_commitment": "Real-time asset status",
                },
                {
                    "name": "ERP Integration Service",
                    "description": "Synchronize with enterprise systems",
                    "service_type": "integration",
                    "sla_commitment": "< 30 second integration latency",
                },
            ]
        ),
        business_processes=json.dumps(
            [
                {
                    "name": "Batch Recipe Execution",
                    "description": "Execute ISA - 88 batch recipes",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Recipe Download",
                        "Material Allocation",
                        "Phase Execution",
                        "Interlocks",
                        "Transitions",
                        "Completion",
                        "Batch Report",
                    ],
                    "cycle_time": "Hours to days",
                    "kpis": ["Recipe Compliance", "Batch Cycle Time", "Yield"],
                },
                {
                    "name": "Continuous Process Monitoring",
                    "description": "Monitor and control continuous processes",
                    "automation_level": "fully-automated",
                    "steps": ["Tag Scanning", "Alarming", "Trending", "Control Actions", "Logging"],
                    "cycle_time": "Real-time (< 1 second)",
                    "kpis": ["Process Stability", "Alarm Rate", "Setpoint Deviation"],
                },
                {
                    "name": "Production Order Processing",
                    "description": "Execute discrete manufacturing orders",
                    "automation_level": "highly-automated",
                    "steps": [
                        "Order Download",
                        "Material Issue",
                        "Production Start",
                        "Data Collection",
                        "Completion",
                        "Order Confirmation",
                    ],
                    "cycle_time": "Minutes to hours",
                    "kpis": ["Order Completion Rate", "Cycle Time", "First Pass Yield"],
                },
                {
                    "name": "OEE Calculation",
                    "description": "Calculate real-time OEE metrics",
                    "automation_level": "fully-automated",
                    "steps": [
                        "Uptime Tracking",
                        "Speed Monitoring",
                        "Quality Measurement",
                        "OEE Calculation",
                        "Loss Categorization",
                    ],
                    "cycle_time": "Real-time (1 - minute intervals)",
                    "kpis": ["OEE", "Availability", "Performance", "Quality"],
                },
                {
                    "name": "Downtime Management",
                    "description": "Track and analyze equipment downtime",
                    "automation_level": "partially-automated",
                    "steps": [
                        "Downtime Detection",
                        "Operator Classification",
                        "Duration Tracking",
                        "Root Cause Entry",
                        "Analysis",
                    ],
                    "cycle_time": "Minutes to hours",
                    "kpis": ["MTBF", "MTTR", "Downtime by Reason"],
                },
                {
                    "name": "Historical Data Trending",
                    "description": "Analyze historical process data",
                    "automation_level": "manual",
                    "steps": [
                        "Tag Selection",
                        "Time Range Selection",
                        "Data Retrieval",
                        "Trend Display",
                        "Analysis",
                    ],
                    "cycle_time": "Minutes",
                    "kpis": ["Data Availability", "Query Response Time"],
                },
            ]
        ),
        business_objects=json.dumps(
            [
                {
                    "name": "Batch",
                    "description": "Process batch instance",
                    "lifecycle": "created -> running -> held -> completed -> archived",
                },
                {
                    "name": "Recipe",
                    "description": "Batch manufacturing recipe",
                    "lifecycle": "created -> approved -> active -> superseded -> obsolete",
                },
                {
                    "name": "Production Order",
                    "description": "Manufacturing work order",
                    "lifecycle": "released -> in-progress -> completed -> confirmed",
                },
                {
                    "name": "Material Lot",
                    "description": "Material batch or lot",
                    "lifecycle": "received -> available -> issued -> consumed",
                },
                {
                    "name": "Equipment Unit",
                    "description": "Process equipment unit",
                    "lifecycle": "idle -> running -> held -> stopped -> faulted",
                },
                {
                    "name": "Alarm",
                    "description": "Process alarm",
                    "lifecycle": "active -> acknowledged -> cleared -> suppressed",
                },
                {
                    "name": "Downtime Event",
                    "description": "Equipment downtime occurrence",
                    "lifecycle": "started -> classified -> resolved -> archived",
                },
                {
                    "name": "Historical Tag",
                    "description": "Time-series data point",
                    "lifecycle": "collecting -> archived -> purged",
                },
            ]
        ),
        business_actors=json.dumps(
            [
                {
                    "name": "Process Operator",
                    "description": "Control room operator",
                    "responsibilities": [
                        "Process Monitoring",
                        "Alarm Response",
                        "Setpoint Changes",
                        "Batch Execution",
                    ],
                },
                {
                    "name": "Batch Operator",
                    "description": "Batch process specialist",
                    "responsibilities": [
                        "Recipe Selection",
                        "Batch Start/Stop",
                        "Material Allocation",
                        "Batch Report Review",
                    ],
                },
                {
                    "name": "Shift Supervisor",
                    "description": "Operations supervisor",
                    "responsibilities": [
                        "Performance Monitoring",
                        "Resource Allocation",
                        "Exception Handling",
                        "Shift Handover",
                    ],
                },
                {
                    "name": "Maintenance Technician",
                    "description": "Equipment maintenance",
                    "responsibilities": [
                        "Preventive Maintenance",
                        "Breakdown Response",
                        "Calibration",
                        "Equipment Testing",
                    ],
                },
                {
                    "name": "Process Engineer",
                    "description": "Process improvement specialist",
                    "responsibilities": [
                        "Recipe Development",
                        "Process Optimization",
                        "Troubleshooting",
                        "Control Tuning",
                    ],
                },
                {
                    "name": "Quality Technician",
                    "description": "Quality control specialist",
                    "responsibilities": [
                        "Sample Testing",
                        "SPC Monitoring",
                        "Non-Conformance Investigation",
                        "Quality Reports",
                    ],
                },
                {
                    "name": "Production Planner",
                    "description": "Production scheduler",
                    "responsibilities": [
                        "Order Scheduling",
                        "Material Planning",
                        "Capacity Planning",
                        "Schedule Optimization",
                    ],
                },
                {
                    "name": "Control Systems Engineer",
                    "description": "Automation specialist",
                    "responsibilities": [
                        "PLC Programming",
                        "HMI Development",
                        "System Integration",
                        "Network Management",
                    ],
                },
                {
                    "name": "Plant Manager",
                    "description": "Plant operations manager",
                    "responsibilities": [
                        "Performance Review",
                        "Strategic Planning",
                        "Budget Management",
                        "Continuous Improvement",
                    ],
                },
                {
                    "name": "System Administrator",
                    "description": "FactoryTalk system admin",
                    "responsibilities": [
                        "User Management",
                        "Backup/Recovery",
                        "System Updates",
                        "Security Management",
                    ],
                },
            ]
        ),
        products=json.dumps(
            [
                {
                    "name": "FactoryTalk View SE",
                    "description": "Distributed HMI/SCADA platform",
                    "target_market": "All Industries",
                },
                {
                    "name": "FactoryTalk Batch",
                    "description": "ISA - 88 batch management",
                    "target_market": "Process Manufacturing",
                },
                {
                    "name": "FactoryTalk Historian SE",
                    "description": "High-performance time-series database",
                    "target_market": "All Industries",
                },
                {
                    "name": "FactoryTalk VantagePoint",
                    "description": "Manufacturing intelligence and KPIs",
                    "target_market": "All Industries",
                },
                {
                    "name": "FactoryTalk Production Centre",
                    "description": "MES production management",
                    "target_market": "Discrete & Batch Manufacturing",
                },
                {
                    "name": "FactoryTalk Metrics",
                    "description": "OEE and downtime tracking",
                    "target_market": "All Industries",
                },
                {
                    "name": "FactoryTalk Transaction Manager",
                    "description": "Operator data collection",
                    "target_market": "All Industries",
                },
                {
                    "name": "FactoryTalk AssetCentre",
                    "description": "Application version control",
                    "target_market": "All Industries",
                },
                {
                    "name": "FactoryTalk Linx",
                    "description": "Allen-Bradley communication driver",
                    "target_market": "Rockwell Customers",
                },
            ]
        ),
        # ==================== APPLICATION LAYER ====================
        application_components=json.dumps(
            [
                {
                    "name": "FactoryTalk View SE Server",
                    "type": "scada-server",
                    "description": "Central HMI/SCADA server",
                    "technology": ".NET/C++",
                },
                {
                    "name": "FactoryTalk View SE Client",
                    "type": "desktop-application",
                    "description": "Operator HMI client",
                    "technology": ".NET/WPF",
                },
                {
                    "name": "FactoryTalk Batch Server",
                    "type": "batch-server",
                    "description": "Batch execution engine",
                    "technology": ".NET/C++",
                },
                {
                    "name": "FactoryTalk Historian Server",
                    "type": "time-series-database",
                    "description": "High-speed data collector",
                    "technology": "C++",
                },
                {
                    "name": "FactoryTalk VantagePoint Server",
                    "type": "analytics-server",
                    "description": "KPI and dashboard engine",
                    "technology": ".NET",
                },
                {
                    "name": "FactoryTalk Production Centre",
                    "type": "mes-application",
                    "description": "MES production tracking",
                    "technology": ".NET",
                },
                {
                    "name": "FactoryTalk Metrics",
                    "type": "oee-application",
                    "description": "OEE calculation engine",
                    "technology": ".NET",
                },
                {
                    "name": "FactoryTalk Directory Server",
                    "type": "directory-service",
                    "description": "Central tag and user directory",
                    "technology": "C++",
                },
                {
                    "name": "FactoryTalk Linx Gateway",
                    "type": "communication-gateway",
                    "description": "EtherNet/IP gateway",
                    "technology": "C++",
                },
                {
                    "name": "SQL Server Database",
                    "type": "database",
                    "description": "Relational data storage",
                    "technology": "T-SQL",
                },
                {
                    "name": "Studio 5000 Logix Designer",
                    "type": "development-tool",
                    "description": "PLC programming environment",
                    "technology": ".NET",
                },
                {
                    "name": "FactoryTalk View Studio",
                    "type": "development-tool",
                    "description": "HMI development environment",
                    "technology": ".NET",
                },
            ]
        ),
        application_services=json.dumps(
            [
                {
                    "name": "FactoryTalk View Data Server",
                    "type": "OPC",
                    "description": "Real-time tag data service",
                    "endpoints": ["OPC DA/UA servers"],
                },
                {
                    "name": "FactoryTalk Batch API",
                    "type": "SOAP",
                    "description": "Batch management API",
                    "endpoints": ["/BatchML", "/BatchServices"],
                },
                {
                    "name": "FactoryTalk Historian API",
                    "type": "REST",
                    "description": "Historical data retrieval",
                    "endpoints": ["/piwebapi/streams", "/piwebapi/dataservers"],
                },
                {
                    "name": "FactoryTalk VantagePoint API",
                    "type": "REST",
                    "description": "Analytics and KPI API",
                    "endpoints": ["/api/kpi", "/api/reports"],
                },
                {
                    "name": "FactoryTalk Production Centre API",
                    "type": "SOAP",
                    "description": "Production order API",
                    "endpoints": ["/ProductionServices"],
                },
                {
                    "name": "FactoryTalk Linx Classic",
                    "type": "Proprietary",
                    "description": "Allen-Bradley PLC driver",
                    "endpoints": ["CIP/EtherNet-IP"],
                },
                {
                    "name": "FactoryTalk Alarms & Events",
                    "type": "Event",
                    "description": "Alarm notification service",
                    "endpoints": ["Event subscription"],
                },
                {
                    "name": "FactoryTalk Security API",
                    "type": "COM",
                    "description": "Authentication service",
                    "endpoints": ["COM interface"],
                },
                {
                    "name": "FactoryTalk Transaction Manager API",
                    "type": "COM",
                    "description": "Data collection API",
                    "endpoints": ["COM interface"],
                },
            ]
        ),
        application_interfaces=json.dumps(
            [
                {
                    "name": "OPC DA/UA Interface",
                    "protocol": "OPC",
                    "data_format": "OPC Types",
                    "authentication": "Windows Auth",
                },
                {
                    "name": "EtherNet/IP Interface",
                    "protocol": "CIP",
                    "data_format": "CIP Objects",
                    "authentication": "None",
                },
                {
                    "name": "SOAP Interface",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "SOAP XML",
                    "authentication": "Windows Auth",
                },
                {
                    "name": "REST API",
                    "protocol": "HTTP/HTTPS",
                    "data_format": "JSON",
                    "authentication": "API Key",
                },
                {
                    "name": "Database Interface",
                    "protocol": "TDS",
                    "data_format": "SQL",
                    "authentication": "Windows/SQL Auth",
                },
                {
                    "name": "COM Interface",
                    "protocol": "DCOM",
                    "data_format": "COM Objects",
                    "authentication": "Windows Auth",
                },
                {
                    "name": "File Interface",
                    "protocol": "SMB",
                    "data_format": "CSV/XML",
                    "authentication": "Windows Auth",
                },
            ]
        ),
        data_objects=json.dumps(
            [
                {
                    "name": "Batch Report",
                    "type": "regulatory",
                    "retention_policy": "Batch completion + 15 years",
                },
                {
                    "name": "Process Tag Value",
                    "type": "time-series",
                    "retention_policy": "2 years online, 10 years archive",
                },
                {
                    "name": "Production Order",
                    "type": "transactional",
                    "retention_policy": "Completion + 7 years",
                },
                {"name": "Alarm History", "type": "audit", "retention_policy": "5 years"},
                {
                    "name": "Electronic Signature",
                    "type": "regulatory",
                    "retention_policy": "Permanent",
                },
                {
                    "name": "Recipe Master",
                    "type": "master",
                    "retention_policy": "Superseded + 10 years",
                },
                {"name": "OEE Data", "type": "analytical", "retention_policy": "3 years"},
                {"name": "Downtime Event", "type": "transactional", "retention_policy": "5 years"},
            ]
        ),
        application_functions=json.dumps(
            [
                {
                    "name": "Tag Value Read/Write",
                    "type": "data-access",
                    "description": "Read and write process tags",
                },
                {
                    "name": "Batch Start/Stop",
                    "type": "control",
                    "description": "Execute batch operations",
                },
                {
                    "name": "Historical Data Query",
                    "type": "query",
                    "description": "Retrieve time-series data",
                },
                {
                    "name": "Alarm Acknowledge",
                    "type": "interaction",
                    "description": "Acknowledge process alarms",
                },
                {
                    "name": "OEE Calculation",
                    "type": "calculation",
                    "description": "Calculate OEE metrics",
                },
                {
                    "name": "Recipe Download",
                    "type": "transfer",
                    "description": "Download recipe to equipment",
                },
                {
                    "name": "Trend Display",
                    "type": "visualization",
                    "description": "Display real-time trends",
                },
                {
                    "name": "Report Generation",
                    "type": "reporting",
                    "description": "Generate production reports",
                },
                {
                    "name": "User Authentication",
                    "type": "security",
                    "description": "Authenticate users",
                },
                {
                    "name": "Data Collection",
                    "type": "transaction",
                    "description": "Record operator data entries",
                },
            ]
        ),
        # ==================== MOTIVATION LAYER ====================
        stakeholders=json.dumps(
            [
                {
                    "name": "VP Operations",
                    "role": "executive",
                    "concerns": ["Plant Efficiency", "Safety", "Cost Control"],
                    "influence": "high",
                },
                {
                    "name": "Plant Manager",
                    "role": "management",
                    "concerns": ["Production Targets", "Quality", "Regulatory Compliance"],
                    "influence": "high",
                },
                {
                    "name": "Operations Manager",
                    "role": "management",
                    "concerns": ["OEE", "Throughput", "Process Stability"],
                    "influence": "high",
                },
                {
                    "name": "Automation Manager",
                    "role": "technical",
                    "concerns": ["System Reliability", "Integration", "Cybersecurity"],
                    "influence": "high",
                },
                {
                    "name": "Process Engineers",
                    "role": "technical",
                    "concerns": [
                        "Process Optimization",
                        "Control Performance",
                        "Recipe Management",
                    ],
                    "influence": "medium",
                },
                {
                    "name": "Control Systems Engineers",
                    "role": "technical",
                    "concerns": ["PLC Programming", "Network Architecture", "System Performance"],
                    "influence": "medium",
                },
                {
                    "name": "Process Operators",
                    "role": "operational",
                    "concerns": ["HMI Usability", "Alarm Management", "Shift Performance"],
                    "influence": "medium",
                },
                {
                    "name": "Maintenance Team",
                    "role": "operational",
                    "concerns": ["Equipment Reliability", "Diagnostic Tools", "Spare Parts"],
                    "influence": "medium",
                },
                {
                    "name": "Quality Manager",
                    "role": "management",
                    "concerns": ["Product Quality", "Batch Records", "Compliance"],
                    "influence": "high",
                },
                {
                    "name": "IT/OT Manager",
                    "role": "technical",
                    "concerns": ["Network Security", "System Integration", "Data Management"],
                    "influence": "high",
                },
            ]
        ),
        drivers=json.dumps(
            [
                {
                    "name": "Aging Control Systems",
                    "description": "Legacy DCS and PLC systems end-of-life",
                    "urgency": "critical",
                    "impact": "transformational",
                },
                {
                    "name": "Batch Compliance Requirements",
                    "description": "FDA/regulatory pressure for electronic batch records",
                    "urgency": "critical",
                    "impact": "high",
                },
                {
                    "name": "Production Visibility Gap",
                    "description": "Limited real-time production insights",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Alarm Overload",
                    "description": "Excessive alarm rates overwhelming operators",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Data Silos",
                    "description": "Fragmented data across multiple systems",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "OEE Improvement Need",
                    "description": "Below-industry-average equipment effectiveness",
                    "urgency": "high",
                    "impact": "high",
                },
                {
                    "name": "Rockwell Automation Standardization",
                    "description": "Strategic decision to standardize on Rockwell",
                    "urgency": "medium",
                    "impact": "transformational",
                },
                {
                    "name": "Cybersecurity Concerns",
                    "description": "Industrial control system security risks",
                    "urgency": "high",
                    "impact": "medium",
                },
                {
                    "name": "Skills Gap",
                    "description": "Aging workforce with legacy system knowledge",
                    "urgency": "medium",
                    "impact": "medium",
                },
                {
                    "name": "Customer Quality Demands",
                    "description": "Increasing traceability and quality requirements",
                    "urgency": "high",
                    "impact": "high",
                },
            ]
        ),
        goals=json.dumps(
            [
                {
                    "name": "Achieve 85% OEE",
                    "description": "Increase equipment effectiveness",
                    "timeframe": "18 months",
                    "measurable": "OEE from 68% to 85%",
                },
                {
                    "name": "Reduce Alarm Rate 70%",
                    "description": "Implement ISA - 18.2 alarm rationalization",
                    "timeframe": "12 months",
                    "measurable": "Alarms from 50/hour to 15/hour",
                },
                {
                    "name": "100% Electronic Batch Records",
                    "description": "Eliminate paper batch records",
                    "timeframe": "24 months",
                    "measurable": "Zero paper batch records",
                },
                {
                    "name": "Real-Time Production Visibility",
                    "description": "Live dashboards across all plants",
                    "timeframe": "12 months",
                    "measurable": "All KPIs real-time updated",
                },
                {
                    "name": "Reduce Downtime 40%",
                    "description": "Minimize unplanned equipment stops",
                    "timeframe": "18 months",
                    "measurable": "Downtime from 15% to 9%",
                },
                {
                    "name": "Single Pane of Glass",
                    "description": "Unified control system platform",
                    "timeframe": "36 months",
                    "measurable": "All plants on FactoryTalk",
                },
                {
                    "name": "Improve Batch Cycle Time 20%",
                    "description": "Optimize batch processing",
                    "timeframe": "12 months",
                    "measurable": "Average batch time reduction 20%",
                },
                {
                    "name": "Zero Critical Cyber Incidents",
                    "description": "Secure industrial control systems",
                    "timeframe": "Ongoing",
                    "measurable": "Zero security breaches",
                },
                {
                    "name": "Achieve FDA Compliance",
                    "description": "21 CFR Part 11 for all batch systems",
                    "timeframe": "18 months",
                    "measurable": "Pass FDA audit",
                },
            ]
        ),
        outcomes=json.dumps(
            [
                {
                    "name": "World-Class OEE",
                    "description": "Top-quartile equipment effectiveness",
                    "benefit_type": "operational",
                    "quantified_benefit": "85% OEE, $12M throughput increase",
                },
                {
                    "name": "Operator Effectiveness",
                    "description": "Reduced alarm burden and improved response",
                    "benefit_type": "operational",
                    "quantified_benefit": "70% alarm reduction, faster response",
                },
                {
                    "name": "Regulatory Confidence",
                    "description": "Electronic batch records with full compliance",
                    "benefit_type": "compliance",
                    "quantified_benefit": "Zero FDA findings, audit-ready",
                },
                {
                    "name": "Data-Driven Decisions",
                    "description": "Real-time visibility enables rapid decisions",
                    "benefit_type": "strategic",
                    "quantified_benefit": "Real-time KPIs, 50% faster decisions",
                },
                {
                    "name": "Equipment Reliability",
                    "description": "Predictable and reliable operations",
                    "benefit_type": "operational",
                    "quantified_benefit": "40% downtime reduction, $8M impact",
                },
                {
                    "name": "Platform Standardization",
                    "description": "Common system across all plants",
                    "benefit_type": "technical",
                    "quantified_benefit": "$3M annual support savings",
                },
                {
                    "name": "Process Efficiency",
                    "description": "Optimized batch and continuous processes",
                    "benefit_type": "operational",
                    "quantified_benefit": "20% cycle time reduction",
                },
                {
                    "name": "Cybersecurity Posture",
                    "description": "Protected industrial control systems",
                    "benefit_type": "risk-mitigation",
                    "quantified_benefit": "Zero incidents, reduced risk",
                },
            ]
        ),
        principles=json.dumps(
            [
                {
                    "name": "Rockwell-First",
                    "description": "Prioritize Rockwell Automation solutions",
                    "rationale": "Leverage integrated ecosystem",
                },
                {
                    "name": "Real-Time Operations",
                    "description": "All data and decisions in real-time",
                    "rationale": "Enable rapid response",
                },
                {
                    "name": "Paperless Manufacturing",
                    "description": "Electronic records for everything",
                    "rationale": "Improve compliance and efficiency",
                },
                {
                    "name": "Alarm Rationalization",
                    "description": "ISA - 18.2 compliant alarm management",
                    "rationale": "Reduce operator burden",
                },
                {
                    "name": "Data Centralization",
                    "description": "Single source of truth in Historian",
                    "rationale": "Eliminate data silos",
                },
                {
                    "name": "Standard HMI",
                    "description": "Common HMI graphics and navigation",
                    "rationale": "Improve operator effectiveness",
                },
                {
                    "name": "Integrated Security",
                    "description": "Defense-in-depth cybersecurity",
                    "rationale": "Protect critical systems",
                },
                {
                    "name": "Scalable Architecture",
                    "description": "Design for growth and replication",
                    "rationale": "Support multi-site deployment",
                },
                {
                    "name": "ISA - 88 Compliance",
                    "description": "Standard batch management practices",
                    "rationale": "Ensure regulatory compliance",
                },
                {
                    "name": "Continuous Improvement",
                    "description": "Analytics-driven optimization",
                    "rationale": "Sustain competitive advantage",
                },
            ]
        ),
        requirements=json.dumps(
            [
                {
                    "name": "System Availability",
                    "type": "performance",
                    "description": "Control systems 99.99% uptime",
                    "priority": "critical",
                },
                {
                    "name": "Response Time",
                    "type": "performance",
                    "description": "HMI screen update < 100ms",
                    "priority": "critical",
                },
                {
                    "name": "Data Collection Rate",
                    "type": "performance",
                    "description": "100,000 tags per second to Historian",
                    "priority": "high",
                },
                {
                    "name": "21 CFR Part 11",
                    "type": "compliance",
                    "description": "Electronic signature and audit trail",
                    "priority": "critical",
                },
                {
                    "name": "ISA - 88 Compliance",
                    "type": "compliance",
                    "description": "Standard batch control models",
                    "priority": "critical",
                },
                {
                    "name": "Alarm Rate",
                    "type": "operational",
                    "description": "< 15 alarms per hour per operator",
                    "priority": "high",
                },
                {
                    "name": "Concurrent Operators",
                    "type": "capacity",
                    "description": "Support 200 concurrent HMI clients",
                    "priority": "high",
                },
                {
                    "name": "Historical Data Retention",
                    "type": "compliance",
                    "description": "10 years online, 20 years archive",
                    "priority": "high",
                },
                {
                    "name": "Network Redundancy",
                    "type": "continuity",
                    "description": "Redundant network paths to all devices",
                    "priority": "critical",
                },
                {
                    "name": "Cybersecurity",
                    "type": "security",
                    "description": "IEC 62443 compliance",
                    "priority": "critical",
                },
                {
                    "name": "Disaster Recovery",
                    "type": "continuity",
                    "description": "RPO < 5 minutes, RTO < 1 hour",
                    "priority": "critical",
                },
            ]
        ),
        constraints=json.dumps(
            [
                {
                    "name": "Budget Limitation",
                    "type": "financial",
                    "description": "Total program budget $15M",
                },
                {
                    "name": "Timeline Pressure",
                    "type": "schedule",
                    "description": "First plant live in 18 months",
                },
                {
                    "name": "24/7 Operations",
                    "type": "operational",
                    "description": "No production downtime for cutover",
                },
                {
                    "name": "Legacy Equipment Integration",
                    "type": "technical",
                    "description": "Must integrate non-Rockwell PLCs",
                },
                {
                    "name": "Network Bandwidth",
                    "type": "technical",
                    "description": "Limited WAN bandwidth to remote plants",
                },
                {
                    "name": "Skills Gap",
                    "type": "resource",
                    "description": "Limited FactoryTalk expertise",
                },
                {
                    "name": "Regulatory Validation",
                    "type": "compliance",
                    "description": "FDA validation adds 6 months per plant",
                },
                {
                    "name": "Union Constraints",
                    "type": "organizational",
                    "description": "Operator training and job role changes",
                },
                {
                    "name": "Rockwell Platform Lock-In",
                    "type": "strategic",
                    "description": "Heavy vendor dependence",
                },
            ]
        ),
        assessments=json.dumps(
            [
                {
                    "name": "Control System Assessment",
                    "type": "technical",
                    "description": "Evaluate current automation infrastructure",
                    "result": "60% systems end-of-life, upgrade critical",
                },
                {
                    "name": "Network Assessment",
                    "type": "technical",
                    "description": "Industrial network readiness",
                    "result": "Plant networks adequate, WAN needs upgrade",
                },
                {
                    "name": "OEE Baseline",
                    "type": "operational",
                    "description": "Current equipment effectiveness",
                    "result": "Average OEE 68%, opportunity for 25% improvement",
                },
                {
                    "name": "Alarm Assessment",
                    "type": "operational",
                    "description": "Current alarm performance",
                    "result": "50 alarms/hour, 90% reduction opportunity",
                },
                {
                    "name": "ROI Analysis",
                    "type": "financial",
                    "description": "Business case validation",
                    "result": "Projected 180% ROI in 5 years",
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
                    "name": "Design Standards Complete",
                    "date": "2024 - 05 - 31",
                    "milestone": True,
                    "description": "HMI and automation standards finalized",
                },
                {
                    "name": "Pilot Line Cutover",
                    "date": "2024 - 11 - 30",
                    "milestone": True,
                    "description": "First production line on FactoryTalk",
                },
                {
                    "name": "Plant 1 Complete",
                    "date": "2025 - 07 - 31",
                    "milestone": True,
                    "description": "All lines in plant 1 migrated",
                },
                {
                    "name": "Historian Centralized",
                    "date": "2025 - 09 - 30",
                    "milestone": False,
                    "description": "All plants feeding central Historian",
                },
                {
                    "name": "Plant 2 - 3 Complete",
                    "date": "2026 - 01 - 31",
                    "milestone": True,
                    "description": "Next 2 plants migrated",
                },
                {
                    "name": "Plant 4 - 5 Complete",
                    "date": "2026 - 07 - 31",
                    "milestone": True,
                    "description": "Plants 4 - 5 migrated",
                },
                {
                    "name": "All Plants Operational",
                    "date": "2027 - 01 - 31",
                    "milestone": True,
                    "description": "All 5 plants on FactoryTalk",
                },
                {
                    "name": "Program Closure",
                    "date": "2027 - 03 - 31",
                    "milestone": True,
                    "description": "Project complete",
                },
            ]
        ),
        work_packages=json.dumps(
            [
                {
                    "name": "Program Management",
                    "description": "Overall program governance",
                    "duration_weeks": 160,
                    "team_size": 6,
                },
                {
                    "name": "Design Standards Development",
                    "description": "HMI, PLC, and network standards",
                    "duration_weeks": 16,
                    "team_size": 10,
                },
                {
                    "name": "Infrastructure Build",
                    "description": "Server, network, and database setup",
                    "duration_weeks": 12,
                    "team_size": 8,
                },
                {
                    "name": "PLC Programming",
                    "description": "Allen-Bradley PLC development",
                    "duration_weeks": 80,
                    "team_size": 12,
                },
                {
                    "name": "HMI Development",
                    "description": "FactoryTalk View screens",
                    "duration_weeks": 60,
                    "team_size": 10,
                },
                {
                    "name": "Batch Development",
                    "description": "Recipe and batch configuration",
                    "duration_weeks": 40,
                    "team_size": 6,
                },
                {
                    "name": "Historian Configuration",
                    "description": "Tag setup and archiving",
                    "duration_weeks": 20,
                    "team_size": 4,
                },
                {
                    "name": "Analytics Development",
                    "description": "VantagePoint dashboards and KPIs",
                    "duration_weeks": 30,
                    "team_size": 6,
                },
                {
                    "name": "Testing & Commissioning",
                    "description": "FAT, SAT, and commissioning",
                    "duration_weeks": 40,
                    "team_size": 20,
                },
                {
                    "name": "Training Program",
                    "description": "Operator and engineer training",
                    "duration_weeks": 24,
                    "team_size": 6,
                },
            ]
        ),
        deliverables=json.dumps(
            [
                {
                    "name": "Design Standards Manual",
                    "type": "document",
                    "due_phase": "design",
                    "owner": "Lead Engineer",
                },
                {
                    "name": "Configured PLC Programs",
                    "type": "code",
                    "due_phase": "build",
                    "owner": "Controls Lead",
                },
                {
                    "name": "HMI Application",
                    "type": "software",
                    "due_phase": "build",
                    "owner": "HMI Lead",
                },
                {
                    "name": "Batch Recipes",
                    "type": "configuration",
                    "due_phase": "build",
                    "owner": "Batch Engineer",
                },
                {
                    "name": "Historian Tag Database",
                    "type": "configuration",
                    "due_phase": "build",
                    "owner": "Historian Administrator",
                },
                {
                    "name": "VantagePoint Dashboards",
                    "type": "analytics",
                    "due_phase": "build",
                    "owner": "Analytics Developer",
                },
                {
                    "name": "Test Protocols",
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
                    "name": "As-Built Documentation",
                    "type": "document",
                    "due_phase": "deploy",
                    "owner": "Documentation Lead",
                },
            ]
        ),
        plateaus=json.dumps(
            [
                {
                    "name": "Standards Established",
                    "date": "2024 - 05 - 31",
                    "description": "Design standards approved",
                },
                {
                    "name": "Pilot Validated",
                    "date": "2024 - 11 - 30",
                    "description": "Pilot line proven successful",
                },
                {
                    "name": "First Plant Complete",
                    "date": "2025 - 07 - 31",
                    "description": "Plant 1 fully operational",
                },
                {
                    "name": "Half Complete",
                    "date": "2026 - 01 - 31",
                    "description": "3 of 5 plants migrated",
                },
                {
                    "name": "Full Deployment",
                    "date": "2027 - 01 - 31",
                    "description": "All plants on FactoryTalk",
                },
            ]
        ),
        # ==================== PHYSICAL LAYER ====================
        facilities=json.dumps(
            [
                {
                    "name": "Plant 1 - Chemical Processing",
                    "location": "Houston, TX",
                    "tier": "Tier II",
                    "size_sqm": 40000,
                    "description": "Batch chemical manufacturing",
                },
                {
                    "name": "Plant 2 - Food & Beverage",
                    "location": "Milwaukee, WI",
                    "tier": "Tier II",
                    "size_sqm": 35000,
                    "description": "Continuous food processing",
                },
                {
                    "name": "Central Control Room",
                    "location": "Houston, TX",
                    "tier": "Tier III",
                    "size_sqm": 200,
                    "description": "Centralized monitoring facility",
                },
            ]
        ),
        equipment=json.dumps(
            [
                {
                    "name": "FactoryTalk Servers",
                    "type": "virtual-machine",
                    "quantity": 10,
                    "location": "Houston Data Center",
                    "specs": "VMware, 16 cores, 64GB RAM",
                },
                {
                    "name": "SQL Server Cluster",
                    "type": "virtual-machine",
                    "quantity": 2,
                    "location": "Houston Data Center",
                    "specs": "VMware, 32 cores, 256GB RAM",
                },
                {
                    "name": "Allen-Bradley ControlLogix",
                    "type": "plc",
                    "quantity": 45,
                    "location": "Plant Floor",
                    "specs": "1756 - L85E, 20MB memory",
                },
                {
                    "name": "PanelView Plus 7",
                    "type": "hmi-terminal",
                    "quantity": 80,
                    "location": "Plant Floor",
                    "specs": "15 - inch touchscreen",
                },
                {
                    "name": "Stratix 5700 Switches",
                    "type": "network-switch",
                    "quantity": 60,
                    "location": "Plant Floor",
                    "specs": "Managed, 24 - port",
                },
            ]
        ),
        distribution_networks=json.dumps(
            [
                {
                    "name": "EtherNet/IP Plant Network",
                    "type": "industrial-ethernet",
                    "coverage": "Plant Floor",
                    "bandwidth_mbps": 1000,
                    "provider": "Internal",
                },
                {
                    "name": "Control Network",
                    "type": "vlan",
                    "coverage": "Control Systems",
                    "bandwidth_mbps": 1000,
                    "provider": "Internal",
                },
                {
                    "name": "WAN to Remote Plants",
                    "type": "wan",
                    "coverage": "5 Plant Locations",
                    "bandwidth_mbps": 100,
                    "provider": "AT&T",
                },
                {
                    "name": "Internet Gateway",
                    "type": "internet",
                    "coverage": "External Access",
                    "bandwidth_mbps": 1000,
                    "provider": "Comcast",
                },
            ]
        ),
    )


def seed_rockwell_factorytalk(link_capabilities: bool = True):
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
                vendor_name="Rockwell Automation"
            ).first()
            if existing:
                print("⚠️  Rockwell FactoryTalk template already exists. Updating...")
                db.session.delete(existing)
                db.session.commit()

            # Create template
            template = create_rockwell_factorytalk_template()
            db.session.add(template)
            db.session.commit()

            print("✅ Rockwell FactoryTalk template seeded successfully!")
            print(f"   - Vendor: {template.vendor_name}")
            print(f"   - Technology Layer: ✅ Complete")
            print(f"   - Strategy Layer: ✅ Complete (20 capabilities, 6 value streams)")
            print(
                f"   - Business Layer: ✅ Complete (10 services, 6 processes, 8 objects, 10 actors, 9 products)"
            )
            print(
                f"   - Application Layer: ✅ Complete (12 components, 9 services, 7 interfaces, 8 data objects, 10 functions)"
            )
            print(
                f"   - Motivation Layer: ✅ Complete (10 stakeholders, 10 drivers, 9 goals, 8 outcomes, 10 principles, 11 requirements, 9 constraints, 5 assessments)"
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
            print(f"❌ Error seeding Rockwell FactoryTalk template: {str(e)}")
            import traceback

            traceback.print_exc()

            raise


if __name__ == "__main__":
    seed_rockwell_factorytalk()
