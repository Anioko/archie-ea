"""
Vendor Catalogue for ReqArchitect
Comprehensive mapping of vendors to COBIT 2019, ITIL 4, and custom capabilities.

This replaces the vendor_catalogue.ts TypeScript file with native Python data structures.
"""

from typing import Dict, List, Literal, TypedDict

# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

VendorCategory = Literal[
    "ITSM",
    "EA_TOOLS",
    "GRC",
    "ITAM",
    "APM",
    "SECURITY",
    "CLOUD_PLATFORM",
    "DEVOPS",
    "DATA_GOVERNANCE",
    "BPM",
]

VendorType = Literal["SOFTWARE", "SAAS", "CLOUD_SERVICE", "MANAGED_SERVICE", "CONSULTING"]

DeploymentModel = Literal["CLOUD", "ON_PREMISE", "HYBRID"]

COBITDomain = Literal["EDM", "APO", "BAI", "DSS", "MEA"]

MarketPosition = Literal["LEADER", "CHALLENGER", "NICHE", "VISIONARY"]

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]

MarketShare = Literal["DOMINANT", "MAJOR", "MODERATE", "EMERGING"]


class VendorInfo(TypedDict, total=False):
    """Vendor information structure."""

    id: str
    name: str
    category: VendorCategory
    vendorType: VendorType
    description: str
    website: str

    # Deployment & Licensing
    deploymentModel: List[DeploymentModel]
    licenseModel: str
    typicalAnnualCost: str

    # Framework Support
    cobitProcesses: List[str]
    cobitDomains: List[COBITDomain]
    itilProcesses: List[str]
    apqcProcesses: List[str]  # APQC PCF process codes

    # Capability Support
    capabilities: List[str]

    # Vendor Attributes
    marketPosition: MarketPosition
    complianceFrameworks: List[str]
    integrations: List[str]

    # Risk & Performance
    riskLevel: RiskLevel
    marketShare: MarketShare

    # Additional metadata
    founded: int
    headquarters: str
    publicCompany: bool


# ============================================================================
# CAPABILITY TAXONOMY
# ============================================================================

CAPABILITY_TAXONOMY: Dict[str, str] = {
    # ITIL Core Capabilities
    "service-desk": "Service Desk Operations",
    "incident-management": "Incident Management",
    "problem-management": "Problem Management",
    "change-management": "Change Management",
    "release-management": "Release & Deployment Management",
    "service-request": "Service Request Management",
    "configuration-management": "Configuration Management",
    "asset-management": "IT Asset Management",
    "knowledge-management": "Knowledge Management",
    "service-catalog": "Service Catalog Management",
    # COBIT Core Capabilities
    "governance-framework": "IT Governance Framework",
    "risk-management": "Enterprise Risk Management",
    "compliance-management": "Compliance Management",
    "portfolio-management": "Portfolio Management",
    "architecture-management": "Enterprise Architecture Management",
    "vendor-management": "Vendor Management",
    "security-management": "Security Management",
    "performance-management": "Performance Management",
    "resource-optimization": "Resource Optimization",
    # Technical Capabilities
    "monitoring-alerting": "Monitoring & Alerting",
    "automation": "Process Automation",
    "reporting-analytics": "Reporting & Analytics",
    "workflow-orchestration": "Workflow Orchestration",
    "integration-platform": "Integration Platform",
    "ai-ml": "AI/ML Capabilities",
    # Additional Capabilities
    "project-management": "Project Management",
    "financial-management": "Financial Management",
    "audit-compliance": "Audit & Compliance",
    "business-continuity": "Business Continuity",
    "capacity-planning": "Capacity Planning",
}


# ============================================================================
# COBIT 2019 PROCESS REFERENCE
# ============================================================================

COBIT_PROCESSES: Dict[str, str] = {
    # EDM - Evaluate, Direct and Monitor (5 processes)
    "EDM01": "Ensure Governance Framework Setting and Maintenance",
    "EDM02": "Ensure Benefits Delivery",
    "EDM03": "Ensure Risk Optimisation",
    "EDM04": "Ensure Resource Optimisation",
    "EDM05": "Ensure Stakeholder Transparency",
    # APO - Align, Plan and Organise (13 processes)
    "APO01": "Manage the IT Management Framework",
    "APO02": "Manage Strategy",
    "APO03": "Manage Enterprise Architecture",
    "APO04": "Manage Innovation",
    "APO05": "Manage Portfolio",
    "APO06": "Manage Budget and Costs",
    "APO07": "Manage Human Resources",
    "APO08": "Manage Relationships",
    "APO09": "Manage Service Agreements",
    "APO10": "Manage Suppliers",
    "APO11": "Manage Quality",
    "APO12": "Manage Risk",
    "APO13": "Manage Security",
    # BAI - Build, Acquire and Implement (10 processes)
    "BAI01": "Manage Programmes and Projects",
    "BAI02": "Manage Requirements Definition",
    "BAI03": "Manage Solutions Identification and Build",
    "BAI04": "Manage Availability and Capacity",
    "BAI05": "Manage Organisational Change",
    "BAI06": "Manage IT Changes",
    "BAI07": "Manage IT Change Acceptance and Transitioning",
    "BAI08": "Manage Knowledge",
    "BAI09": "Manage Assets",
    "BAI10": "Manage Configuration",
    # DSS - Deliver, Service and Support (6 processes)
    "DSS01": "Manage Operations",
    "DSS02": "Manage Service Requests and Incidents",
    "DSS03": "Manage Problems",
    "DSS04": "Manage Continuity",
    "DSS05": "Manage Security Services",
    "DSS06": "Manage Business Process Controls",
    # MEA - Monitor, Evaluate and Assess (3 processes)
    "MEA01": "Monitor, Evaluate and Assess Performance and Conformance",
    "MEA02": "Monitor, Evaluate and Assess the System of Internal Control",
    "MEA03": "Monitor, Evaluate and Assess Compliance with External Requirements",
}


# ============================================================================
# APQC PCF 8.0 PROCESS REFERENCE
# ============================================================================

APQC_PROCESSES: Dict[str, Dict] = {
    # 1.0 DEVELOP VISION AND STRATEGY
    "1.0": {
        "name": "Develop Vision and Strategy",
        "level": 1,
        "category": "Strategic",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Enterprise", "Business"],
    },
    "1.1": {
        "name": "Define the business concept and long-term vision",
        "level": 2,
        "parent": "1.0",
        "category": "Strategic",
    },
    "1.2": {
        "name": "Develop business strategy",
        "level": 2,
        "parent": "1.0",
        "category": "Strategic",
    },
    "1.3": {
        "name": "Manage strategic initiatives",
        "level": 2,
        "parent": "1.0",
        "category": "Strategic",
    },
    # 2.0 DEVELOP AND MANAGE PRODUCTS AND SERVICES
    "2.0": {
        "name": "Develop and Manage Products and Services",
        "level": 1,
        "category": "Operational",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Solutions", "Application", "Business"],
    },
    "2.1": {
        "name": "Manage product and service portfolio",
        "level": 2,
        "parent": "2.0",
        "category": "Operational",
    },
    "2.2": {
        "name": "Develop products and services",
        "level": 2,
        "parent": "2.0",
        "category": "Operational",
    },
    # 3.0 MARKET AND SELL PRODUCTS AND SERVICES
    "3.0": {
        "name": "Market and Sell Products and Services",
        "level": 1,
        "category": "Operational",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Business", "Application"],
    },
    "3.1": {
        "name": "Understand markets, customers, and capabilities",
        "level": 2,
        "parent": "3.0",
        "category": "Operational",
    },
    "3.2": {
        "name": "Develop marketing strategy",
        "level": 2,
        "parent": "3.0",
        "category": "Operational",
    },
    "3.3": {
        "name": "Develop and manage sales strategy",
        "level": 2,
        "parent": "3.0",
        "category": "Operational",
    },
    "3.4": {
        "name": "Develop and manage sales plans",
        "level": 2,
        "parent": "3.0",
        "category": "Operational",
    },
    "3.5": {
        "name": "Manage customer relationships",
        "level": 2,
        "parent": "3.0",
        "category": "Operational",
    },
    # 4.0 DELIVER PHYSICAL PRODUCTS
    "4.0": {
        "name": "Deliver Physical Products",
        "level": 1,
        "category": "Operational",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Business", "Application"],
    },
    "4.1": {
        "name": "Plan for and acquire necessary resources",
        "level": 2,
        "parent": "4.0",
        "category": "Operational",
    },
    "4.2": {
        "name": "Procure materials and services",
        "level": 2,
        "parent": "4.0",
        "category": "Operational",
    },
    "4.3": {
        "name": "Produce/Manufacture/Deliver product",
        "level": 2,
        "parent": "4.0",
        "category": "Operational",
    },
    "4.4": {
        "name": "Deliver products to customers",
        "level": 2,
        "parent": "4.0",
        "category": "Operational",
    },
    "4.5": {
        "name": "Manage logistics and warehousing",
        "level": 2,
        "parent": "4.0",
        "category": "Operational",
    },
    # 5.0 DELIVER SERVICES
    "5.0": {
        "name": "Deliver Services",
        "level": 1,
        "category": "Operational",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Business", "Application"],
    },
    "5.1": {
        "name": "Establish service delivery governance",
        "level": 2,
        "parent": "5.0",
        "category": "Operational",
    },
    "5.2": {
        "name": "Manage service delivery resources",
        "level": 2,
        "parent": "5.0",
        "category": "Operational",
    },
    "5.3": {
        "name": "Deliver services to customers",
        "level": 2,
        "parent": "5.0",
        "category": "Operational",
    },
    # 6.0 MANAGE CUSTOMER SERVICE
    "6.0": {
        "name": "Manage Customer Service",
        "level": 1,
        "category": "Operational",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Application", "Integration", "Business"],
    },
    "6.1": {
        "name": "Develop customer care/customer service strategy",
        "level": 2,
        "parent": "6.0",
        "category": "Operational",
    },
    "6.2": {
        "name": "Plan and manage customer service operations",
        "level": 2,
        "parent": "6.0",
        "category": "Operational",
    },
    "6.3": {
        "name": "Measure and evaluate customer service operations",
        "level": 2,
        "parent": "6.0",
        "category": "Operational",
    },
    "6.4": {
        "name": "Manage customer service requests",
        "level": 2,
        "parent": "6.0",
        "category": "Operational",
    },
    "6.5": {
        "name": "Manage customer complaints",
        "level": 2,
        "parent": "6.0",
        "category": "Operational",
    },
    # 7.0 DEVELOP AND MANAGE HUMAN CAPITAL
    "7.0": {
        "name": "Develop and Manage Human Capital",
        "level": 1,
        "category": "Support",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Business", "Application"],
    },
    "7.1": {
        "name": "Develop and manage HR planning, policies, and strategies",
        "level": 2,
        "parent": "7.0",
        "category": "Support",
    },
    "7.2": {
        "name": "Recruit, source, and select employees",
        "level": 2,
        "parent": "7.0",
        "category": "Support",
    },
    "7.3": {
        "name": "Develop and counsel employees",
        "level": 2,
        "parent": "7.0",
        "category": "Support",
    },
    "7.4": {
        "name": "Manage employee relations",
        "level": 2,
        "parent": "7.0",
        "category": "Support",
    },
    "7.5": {
        "name": "Reward and retain employees",
        "level": 2,
        "parent": "7.0",
        "category": "Support",
    },
    "7.6": {
        "name": "Redeploy and retire employees",
        "level": 2,
        "parent": "7.0",
        "category": "Support",
    },
    "7.7": {
        "name": "Manage employee information and analytics",
        "level": 2,
        "parent": "7.0",
        "category": "Support",
    },
    # 8.0 MANAGE INFORMATION TECHNOLOGY
    "8.0": {
        "name": "Manage Information Technology",
        "level": 1,
        "category": "Support",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Application", "Data", "Integration", "Technology"],
    },
    "8.1": {
        "name": "Manage the business of information technology",
        "level": 2,
        "parent": "8.0",
        "category": "Support",
    },
    "8.2": {
        "name": "Develop and manage IT customer relationships",
        "level": 2,
        "parent": "8.0",
        "category": "Support",
    },
    "8.3": {
        "name": "Manage IT resilience and risk",
        "level": 2,
        "parent": "8.0",
        "category": "Support",
    },
    "8.4": {"name": "Manage IT security", "level": 2, "parent": "8.0", "category": "Support"},
    "8.5": {
        "name": "Manage enterprise information",
        "level": 2,
        "parent": "8.0",
        "category": "Support",
    },
    "8.6": {
        "name": "Develop and maintain IT solutions",
        "level": 2,
        "parent": "8.0",
        "category": "Support",
    },
    "8.7": {"name": "Deploy IT solutions", "level": 2, "parent": "8.0", "category": "Support"},
    "8.8": {
        "name": "Deliver and support IT services",
        "level": 2,
        "parent": "8.0",
        "category": "Support",
    },
    # 9.0 MANAGE FINANCIAL RESOURCES
    "9.0": {
        "name": "Manage Financial Resources",
        "level": 1,
        "category": "Support",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Business", "Application"],
    },
    "9.1": {
        "name": "Perform planning and management accounting",
        "level": 2,
        "parent": "9.0",
        "category": "Support",
    },
    "9.2": {
        "name": "Perform revenue accounting",
        "level": 2,
        "parent": "9.0",
        "category": "Support",
    },
    "9.3": {
        "name": "Perform general accounting and reporting",
        "level": 2,
        "parent": "9.0",
        "category": "Support",
    },
    "9.4": {
        "name": "Manage fixed asset project accounting",
        "level": 2,
        "parent": "9.0",
        "category": "Support",
    },
    "9.5": {"name": "Process payroll", "level": 2, "parent": "9.0", "category": "Support"},
    "9.6": {
        "name": "Process accounts payable and expense reimbursements",
        "level": 2,
        "parent": "9.0",
        "category": "Support",
    },
    "9.7": {
        "name": "Manage treasury operations",
        "level": 2,
        "parent": "9.0",
        "category": "Support",
    },
    "9.8": {"name": "Manage internal controls", "level": 2, "parent": "9.0", "category": "Support"},
    "9.9": {"name": "Manage taxes", "level": 2, "parent": "9.0", "category": "Support"},
    # 10.0 ACQUIRE, CONSTRUCT, AND MANAGE ASSETS
    "10.0": {
        "name": "Acquire, Construct, and Manage Assets",
        "level": 1,
        "category": "Support",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Business"],
    },
    "10.1": {
        "name": "Plan and manage capital assets",
        "level": 2,
        "parent": "10.0",
        "category": "Support",
    },
    "10.2": {
        "name": "Acquire and construct productive assets",
        "level": 2,
        "parent": "10.0",
        "category": "Support",
    },
    "10.3": {"name": "Manage facilities", "level": 2, "parent": "10.0", "category": "Support"},
    "10.4": {"name": "Manage physical risk", "level": 2, "parent": "10.0", "category": "Support"},
    # 11.0 MANAGE ENTERPRISE RISK, COMPLIANCE, REMEDIATION, AND RESILIENCY
    "11.0": {
        "name": "Manage Enterprise Risk, Compliance, Remediation, and Resiliency",
        "level": 1,
        "category": "Management",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Enterprise", "Business"],
    },
    "11.1": {
        "name": "Manage enterprise risk",
        "level": 2,
        "parent": "11.0",
        "category": "Management",
    },
    "11.2": {"name": "Manage compliance", "level": 2, "parent": "11.0", "category": "Management"},
    "11.3": {
        "name": "Manage remediation efforts",
        "level": 2,
        "parent": "11.0",
        "category": "Management",
    },
    "11.4": {
        "name": "Manage business resiliency",
        "level": 2,
        "parent": "11.0",
        "category": "Management",
    },
    # 12.0 MANAGE EXTERNAL RELATIONSHIPS
    "12.0": {
        "name": "Manage External Relationships",
        "level": 1,
        "category": "Management",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Business", "Integration"],
    },
    "12.1": {
        "name": "Build investor relationships",
        "level": 2,
        "parent": "12.0",
        "category": "Management",
    },
    "12.2": {
        "name": "Manage government and industry relationships",
        "level": 2,
        "parent": "12.0",
        "category": "Management",
    },
    "12.3": {
        "name": "Manage relations with board of directors",
        "level": 2,
        "parent": "12.0",
        "category": "Management",
    },
    "12.4": {
        "name": "Manage legal and ethical issues",
        "level": 2,
        "parent": "12.0",
        "category": "Management",
    },
    "12.5": {
        "name": "Manage public relations program",
        "level": 2,
        "parent": "12.0",
        "category": "Management",
    },
    # 13.0 DEVELOP AND MANAGE BUSINESS CAPABILITIES
    "13.0": {
        "name": "Develop and Manage Business Capabilities",
        "level": 1,
        "category": "Management",
        "archimate": "BusinessFunction",
        "architecture_domains": ["Enterprise", "Business"],
    },
    "13.1": {
        "name": "Manage business processes",
        "level": 2,
        "parent": "13.0",
        "category": "Management",
    },
    "13.2": {
        "name": "Manage portfolio, program, and project",
        "level": 2,
        "parent": "13.0",
        "category": "Management",
    },
    "13.3": {
        "name": "Manage enterprise quality",
        "level": 2,
        "parent": "13.0",
        "category": "Management",
    },
    "13.4": {"name": "Manage change", "level": 2, "parent": "13.0", "category": "Management"},
    "13.5": {
        "name": "Develop and manage enterprise-wide knowledge management",
        "level": 2,
        "parent": "13.0",
        "category": "Management",
    },
    "13.6": {
        "name": "Measure and benchmark",
        "level": 2,
        "parent": "13.0",
        "category": "Management",
    },
}

APQC_CATEGORIES: Dict[str, str] = {
    "1.0": "Develop Vision and Strategy",
    "2.0": "Develop and Manage Products and Services",
    "3.0": "Market and Sell Products and Services",
    "4.0": "Deliver Physical Products",
    "5.0": "Deliver Services",
    "6.0": "Manage Customer Service",
    "7.0": "Develop and Manage Human Capital",
    "8.0": "Manage Information Technology",
    "9.0": "Manage Financial Resources",
    "10.0": "Acquire, Construct, and Manage Assets",
    "11.0": "Manage Enterprise Risk, Compliance, Remediation, and Resiliency",
    "12.0": "Manage External Relationships",
    "13.0": "Develop and Manage Business Capabilities",
}


# ============================================================================
# ITIL 4 PROCESS REFERENCE
# ============================================================================

ITIL_PROCESSES: Dict[str, str] = {
    # Service Strategy
    "strategy-management": "Strategy Management for IT Services",
    "service-portfolio": "Service Portfolio Management",
    "financial-management": "Financial Management for IT Services",
    "demand-management": "Demand Management",
    "business-relationship": "Business Relationship Management",
    # Service Design
    "design-coordination": "Design Coordination",
    "service-catalog-mgmt": "Service Catalog Management",
    "service-level": "Service Level Management",
    "availability-management": "Availability Management",
    "capacity-management": "Capacity Management",
    "it-service-continuity": "IT Service Continuity Management",
    "information-security": "Information Security Management",
    "supplier-management": "Supplier Management",
    # Service Transition
    "transition-planning": "Transition Planning and Support",
    "change-management": "Change Management",
    "change-evaluation": "Change Evaluation",
    "service-validation": "Service Validation and Testing",
    "release-deployment": "Release and Deployment Management",
    "service-asset-config": "Service Asset and Configuration Management",
    "knowledge-management": "Knowledge Management",
    # Service Operation
    "event-management": "Event Management",
    "incident-management": "Incident Management",
    "request-fulfillment": "Request Fulfillment",
    "problem-management": "Problem Management",
    "access-management": "Access Management",
    # Continual Service Improvement
    "seven-step-improvement": "7 - Step Improvement Process",
    "service-measurement": "Service Measurement",
    "service-reporting": "Service Reporting",
}


# ============================================================================
# VENDOR CATALOGUE
# ============================================================================

VENDOR_CATALOGUE: List[VendorInfo] = [
    {
        "id": "servicenow",
        "name": "ServiceNow",
        "category": "ITSM",
        "vendorType": "SAAS",
        "description": "Enterprise ITSM platform with comprehensive ITIL and COBIT support. Market leader in IT service management with extensive automation and AI capabilities.",
        "website": "https://www.servicenow.com",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription per user",
        "typicalAnnualCost": "$100K-$1M+",
        "cobitProcesses": [
            "DSS01",
            "DSS02",
            "DSS03",
            "DSS04",
            "DSS05",
            "DSS06",
            "BAI06",
            "BAI07",
            "BAI08",
            "BAI09",
            "BAI10",
            "APO09",
            "APO10",
            "APO11",
        ],
        "cobitDomains": ["DSS", "BAI", "APO"],
        "itilProcesses": [
            "incident-management",
            "problem-management",
            "change-management",
            "release-deployment",
            "service-asset-config",
            "knowledge-management",
            "request-fulfillment",
            "event-management",
            "service-catalog-mgmt",
            "service-level",
            "availability-management",
            "capacity-management",
        ],
        "apqcProcesses": [
            "6.0",
            "6.1",
            "6.2",
            "6.3",
            "6.4",
            "6.5",  # Manage Customer Service
            "8.0",
            "8.1",
            "8.2",
            "8.3",
            "8.4",
            "8.6",
            "8.7",
            "8.8",  # Manage IT
            "11.0",
            "11.1",
            "11.2",  # Risk & Compliance (GRC module)
            "13.1",
            "13.2",
            "13.4",
            "13.5",  # Business Capabilities, Change, Knowledge
        ],
        "capabilities": [
            "service-desk",
            "incident-management",
            "problem-management",
            "change-management",
            "release-management",
            "service-request",
            "configuration-management",
            "asset-management",
            "knowledge-management",
            "service-catalog",
            "workflow-orchestration",
            "automation",
            "ai-ml",
            "reporting-analytics",
            "integration-platform",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "HIPAA",
            "GDPR",
            "FedRAMP",
        ],
        "integrations": [
            "Slack",
            "Microsoft Teams",
            "Jira",
            "Salesforce",
            "AWS",
            "Azure",
        ],
        "riskLevel": "LOW",
        "marketShare": "DOMINANT",
        "founded": 2003,
        "headquarters": "Santa Clara, CA",
        "publicCompany": True,
    },
    {
        "id": "bmc-remedy",
        "name": "BMC Helix (Remedy)",
        "category": "ITSM",
        "vendorType": "SOFTWARE",
        "description": "Comprehensive ITSM suite with strong ITIL alignment. Legacy leader with modern cloud capabilities through BMC Helix platform.",
        "website": "https://www.bmc.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE", "HYBRID"],
        "licenseModel": "Perpetual or Subscription",
        "typicalAnnualCost": "$75K-$500K",
        "cobitProcesses": [
            "DSS01",
            "DSS02",
            "DSS03",
            "DSS04",
            "DSS06",
            "BAI06",
            "BAI07",
            "BAI09",
            "BAI10",
            "APO09",
            "APO10",
        ],
        "cobitDomains": ["DSS", "BAI", "APO"],
        "itilProcesses": [
            "incident-management",
            "problem-management",
            "change-management",
            "service-asset-config",
            "knowledge-management",
            "request-fulfillment",
            "event-management",
            "service-catalog-mgmt",
        ],
        "apqcProcesses": [
            "6.0",
            "6.2",
            "6.4",  # Customer Service
            "8.0",
            "8.1",
            "8.2",
            "8.6",
            "8.7",
            "8.8",  # IT Management
            "13.4",
            "13.5",  # Change, Knowledge
        ],
        "capabilities": [
            "service-desk",
            "incident-management",
            "problem-management",
            "change-management",
            "configuration-management",
            "asset-management",
            "knowledge-management",
            "automation",
            "reporting-analytics",
        ],
        "marketPosition": "CHALLENGER",
        "complianceFrameworks": ["SOC2", "ISO27001", "HIPAA"],
        "integrations": [
            "Jira",
            "Salesforce",
            "ServiceNow",
            "AWS",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 1980,
        "headquarters": "Houston, TX",
        "publicCompany": True,
    },
    {
        "id": "ivanti",
        "name": "Ivanti Neurons",
        "category": "ITSM",
        "vendorType": "SAAS",
        "description": "ITSM platform with strong automation and endpoint management integration. Focuses on employee experience and IT asset management.",
        "website": "https://www.ivanti.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$50K-$300K",
        "cobitProcesses": [
            "DSS01",
            "DSS02",
            "DSS03",
            "DSS05",
            "BAI06",
            "BAI09",
            "BAI10",
            "APO10",
        ],
        "cobitDomains": ["DSS", "BAI", "APO"],
        "itilProcesses": [
            "incident-management",
            "problem-management",
            "change-management",
            "service-asset-config",
            "request-fulfillment",
        ],
        "capabilities": [
            "service-desk",
            "incident-management",
            "problem-management",
            "change-management",
            "asset-management",
            "automation",
            "security-management",
        ],
        "marketPosition": "NICHE",
        "complianceFrameworks": ["SOC2", "ISO27001"],
        "integrations": ["Microsoft SCCM", "Active Directory", "Slack"],
        "riskLevel": "MEDIUM",
        "marketShare": "MODERATE",
        "founded": 2010,
        "headquarters": "South Jordan, UT",
        "publicCompany": False,
    },
    {
        "id": "freshservice",
        "name": "Freshservice",
        "category": "ITSM",
        "vendorType": "SAAS",
        "description": "Modern, user-friendly ITSM platform for SMB and mid-market. Part of Freshworks suite with strong integration capabilities.",
        "website": "https://freshservice.com",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription per agent",
        "typicalAnnualCost": "$10K-$100K",
        "cobitProcesses": [
            "DSS01",
            "DSS02",
            "DSS03",
            "BAI06",
            "BAI09",
        ],
        "cobitDomains": ["DSS", "BAI"],
        "itilProcesses": [
            "incident-management",
            "problem-management",
            "change-management",
            "service-asset-config",
            "request-fulfillment",
            "service-catalog-mgmt",
        ],
        "capabilities": [
            "service-desk",
            "incident-management",
            "problem-management",
            "change-management",
            "asset-management",
            "service-catalog",
            "automation",
        ],
        "marketPosition": "CHALLENGER",
        "complianceFrameworks": ["SOC2", "GDPR"],
        "integrations": [
            "Slack",
            "Microsoft Teams",
            "Jira",
            "Okta",
        ],
        "riskLevel": "LOW",
        "marketShare": "EMERGING",
        "founded": 2011,
        "headquarters": "San Mateo, CA",
        "publicCompany": True,
    },
    {
        "id": "cherwell",
        "name": "Ivanti Cherwell Service Management",
        "category": "ITSM",
        "vendorType": "SOFTWARE",
        "description": "Flexible, codeless ITSM platform with strong customization capabilities. Now part of Ivanti portfolio.",
        "website": "https://www.ivanti.com/products/service-manager",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$40K-$250K",
        "cobitProcesses": [
            "DSS01",
            "DSS02",
            "DSS03",
            "BAI06",
            "BAI10",
        ],
        "cobitDomains": ["DSS", "BAI"],
        "itilProcesses": [
            "incident-management",
            "problem-management",
            "change-management",
            "request-fulfillment",
            "knowledge-management",
        ],
        "capabilities": [
            "service-desk",
            "incident-management",
            "problem-management",
            "change-management",
            "workflow-orchestration",
            "automation",
        ],
        "marketPosition": "NICHE",
        "complianceFrameworks": ["SOC2", "ISO27001"],
        "integrations": ["Active Directory", "ServiceNow", "Slack"],
        "riskLevel": "MEDIUM",
        "marketShare": "MODERATE",
    },
    {
        "id": "sparx-ea",
        "name": "Sparx Enterprise Architect",
        "category": "EA_TOOLS",
        "vendorType": "SOFTWARE",
        "description": "Comprehensive EA modeling tool with UML, ArchiMate, BPMN, and code generation. Industry standard for architecture documentation.",
        "website": "https://sparxsystems.com",
        "deploymentModel": ["ON_PREMISE", "CLOUD"],
        "licenseModel": "Perpetual license",
        "typicalAnnualCost": "$5K-$50K",
        "cobitProcesses": [
            "APO01",
            "APO03",
            "APO04",
            "BAI01",
            "BAI02",
            "BAI03",
        ],
        "cobitDomains": ["APO", "BAI"],
        "itilProcesses": ["design-coordination", "service-portfolio"],
        "capabilities": [
            "architecture-management",
            "governance-framework",
            "portfolio-management",
            "reporting-analytics",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["ISO27001", "TOGAF", "ArchiMate"],
        "integrations": [
            "Jira",
            "Azure DevOps",
            "Git",
            "databases",
        ],
        "riskLevel": "LOW",
        "marketShare": "DOMINANT",
        "founded": 1996,
        "headquarters": "Creswick, Australia",
        "publicCompany": False,
    },
    {
        "id": "bizzdesign",
        "name": "BiZZdesign Horizzon",
        "category": "EA_TOOLS",
        "vendorType": "SAAS",
        "description": "Enterprise architecture platform with AI-powered relationship mapping and strong ArchiMate support. Excellent for EA governance.",
        "website": "https://bizzdesign.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$50K-$300K",
        "cobitProcesses": [
            "APO01",
            "APO03",
            "APO05",
            "EDM01",
            "EDM04",
            "BAI01",
            "BAI02",
        ],
        "cobitDomains": ["APO", "EDM", "BAI"],
        "itilProcesses": ["design-coordination", "service-portfolio", "strategy-management"],
        "capabilities": [
            "architecture-management",
            "governance-framework",
            "portfolio-management",
            "risk-management",
            "compliance-management",
            "ai-ml",
            "reporting-analytics",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["TOGAF", "ArchiMate", "COBIT"],
        "integrations": [
            "ServiceNow",
            "Jira",
            "Azure DevOps",
            "Salesforce",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2000,
        "headquarters": "Enschede, Netherlands",
        "publicCompany": False,
    },
    {
        "id": "leanix",
        "name": "LeanIX",
        "category": "EA_TOOLS",
        "vendorType": "SAAS",
        "description": "Modern cloud-native EA platform focused on application portfolio management and technology stack rationalization.",
        "website": "https://www.leanix.net",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$75K-$400K",
        "cobitProcesses": [
            "APO03",
            "APO05",
            "APO06",
            "EDM04",
            "BAI09",
        ],
        "cobitDomains": ["APO", "EDM", "BAI"],
        "itilProcesses": ["service-portfolio", "design-coordination"],
        "capabilities": [
            "architecture-management",
            "portfolio-management",
            "resource-optimization",
            "reporting-analytics",
            "integration-platform",
        ],
        "marketPosition": "CHALLENGER",
        "complianceFrameworks": ["SOC2", "GDPR", "ISO27001"],
        "integrations": [
            "ServiceNow",
            "Jira",
            "Confluence",
            "Azure",
            "AWS",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2012,
        "headquarters": "Bonn, Germany",
        "publicCompany": False,
    },
    {
        "id": "ardoq",
        "name": "Ardoq",
        "category": "EA_TOOLS",
        "vendorType": "SAAS",
        "description": "Data-driven EA platform with graph database and automated data discovery. Strong integration capabilities for automated architecture mapping.",
        "website": "https://www.ardoq.com",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$60K-$350K",
        "cobitProcesses": [
            "APO03",
            "APO05",
            "BAI09",
            "BAI10",
            "EDM04",
        ],
        "cobitDomains": ["APO", "BAI", "EDM"],
        "itilProcesses": ["service-portfolio", "service-asset-config"],
        "capabilities": [
            "architecture-management",
            "portfolio-management",
            "configuration-management",
            "integration-platform",
            "reporting-analytics",
            "automation",
        ],
        "marketPosition": "VISIONARY",
        "complianceFrameworks": ["SOC2", "GDPR", "ISO27001"],
        "integrations": [
            "ServiceNow",
            "Jira",
            "Azure AD",
            "AWS",
            "Slack",
        ],
        "riskLevel": "MEDIUM",
        "marketShare": "EMERGING",
        "founded": 2013,
        "headquarters": "Oslo, Norway",
        "publicCompany": False,
    },
    {
        "id": "servicenow-grc",
        "name": "ServiceNow GRC",
        "category": "GRC",
        "vendorType": "SAAS",
        "description": "Integrated GRC platform within ServiceNow ecosystem. Comprehensive risk, policy, audit, and compliance management.",
        "website": "https://www.servicenow.com/products/governance-risk-compliance.html",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$100K-$800K",
        "cobitProcesses": [
            "EDM01",
            "EDM03",
            "EDM05",
            "APO01",
            "APO12",
            "APO13",
            "MEA01",
            "MEA02",
            "MEA03",
            "DSS05",
        ],
        "cobitDomains": [
            "EDM",
            "APO",
            "MEA",
            "DSS",
        ],
        "itilProcesses": ["information-security", "it-service-continuity", "supplier-management"],
        "capabilities": [
            "governance-framework",
            "risk-management",
            "compliance-management",
            "audit-compliance",
            "security-management",
            "vendor-management",
            "reporting-analytics",
            "workflow-orchestration",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "NIST",
            "COBIT",
            "GDPR",
            "HIPAA",
        ],
        "integrations": ["ServiceNow ITSM", "Archer", "MetricStream"],
        "riskLevel": "LOW",
        "marketShare": "DOMINANT",
        "founded": 2003,
        "headquarters": "Santa Clara, CA",
        "publicCompany": True,
    },
    {
        "id": "archer",
        "name": "RSA Archer (Archer Technologies)",
        "category": "GRC",
        "vendorType": "SOFTWARE",
        "description": "Enterprise GRC suite with comprehensive risk and compliance management. Industry standard for financial services and healthcare.",
        "website": "https://www.archerirm.com",
        "deploymentModel": ["ON_PREMISE", "CLOUD"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$150K-$1M+",
        "cobitProcesses": [
            "EDM01",
            "EDM03",
            "EDM05",
            "APO12",
            "APO13",
            "MEA01",
            "MEA02",
            "MEA03",
        ],
        "cobitDomains": ["EDM", "APO", "MEA"],
        "itilProcesses": ["information-security", "it-service-continuity"],
        "capabilities": [
            "governance-framework",
            "risk-management",
            "compliance-management",
            "audit-compliance",
            "security-management",
            "reporting-analytics",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "NIST",
            "COBIT",
            "Basel III",
        ],
        "integrations": ["ServiceNow", "Splunk", "QRadar"],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2001,
        "headquarters": "Austin, TX",
        "publicCompany": False,
    },
    {
        "id": "metricstream",
        "name": "MetricStream",
        "category": "GRC",
        "vendorType": "SAAS",
        "description": "Comprehensive GRC platform with strong regulatory compliance focus. Leader in quality management and audit management.",
        "website": "https://www.metricstream.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$100K-$750K",
        "cobitProcesses": [
            "EDM01",
            "EDM03",
            "EDM05",
            "APO11",
            "APO12",
            "APO13",
            "MEA01",
            "MEA02",
            "MEA03",
        ],
        "cobitDomains": ["EDM", "APO", "MEA"],
        "itilProcesses": ["information-security", "service-level"],
        "capabilities": [
            "governance-framework",
            "risk-management",
            "compliance-management",
            "audit-compliance",
            "performance-management",
            "reporting-analytics",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "NIST",
            "GDPR",
            "FDA",
        ],
        "integrations": ["ServiceNow", "SAP", "Salesforce"],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 1999,
        "headquarters": "San Jose, CA",
        "publicCompany": False,
    },
    {
        "id": "logicmanager",
        "name": "LogicManager",
        "category": "GRC",
        "vendorType": "SAAS",
        "description": "Modern GRC platform for mid-market organizations. Focus on enterprise risk management and compliance automation.",
        "website": "https://www.logicmanager.com",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$30K-$200K",
        "cobitProcesses": [
            "EDM03",
            "APO12",
            "APO13",
            "MEA01",
            "MEA02",
        ],
        "cobitDomains": ["EDM", "APO", "MEA"],
        "itilProcesses": ["information-security"],
        "capabilities": [
            "risk-management",
            "compliance-management",
            "audit-compliance",
            "reporting-analytics",
            "workflow-orchestration",
        ],
        "marketPosition": "CHALLENGER",
        "complianceFrameworks": ["SOC2", "ISO27001", "NIST"],
        "integrations": ["Microsoft 365", "Salesforce", "Jira"],
        "riskLevel": "MEDIUM",
        "marketShare": "MODERATE",
        "founded": 2005,
        "headquarters": "Boston, MA",
        "publicCompany": False,
    },
    {
        "id": "snow-software",
        "name": "Snow Software",
        "category": "ITAM",
        "vendorType": "SOFTWARE",
        "description": "Leading SAM and ITAM platform with comprehensive license optimization. Strong support for software compliance and cloud cost management.",
        "website": "https://www.snowsoftware.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$50K-$500K",
        "cobitProcesses": [
            "BAI09",
            "BAI10",
            "APO06",
            "APO10",
            "EDM04",
            "DSS01",
        ],
        "cobitDomains": [
            "BAI",
            "APO",
            "EDM",
            "DSS",
        ],
        "itilProcesses": ["service-asset-config", "financial-management", "supplier-management"],
        "capabilities": [
            "asset-management",
            "configuration-management",
            "vendor-management",
            "financial-management",
            "resource-optimization",
            "reporting-analytics",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["ISO19770", "ISO27001", "SOC2"],
        "integrations": [
            "ServiceNow",
            "Microsoft SCCM",
            "Azure",
            "AWS",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 1997,
        "headquarters": "Stockholm, Sweden",
        "publicCompany": False,
    },
    {
        "id": "flexera",
        "name": "Flexera One",
        "category": "ITAM",
        "vendorType": "SAAS",
        "description": "Comprehensive ITAM and FinOps platform. Industry leader in software asset management and cloud cost optimization.",
        "website": "https://www.flexera.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$75K-$600K",
        "cobitProcesses": [
            "BAI09",
            "BAI10",
            "APO06",
            "APO10",
            "EDM04",
        ],
        "cobitDomains": ["BAI", "APO", "EDM"],
        "itilProcesses": ["service-asset-config", "financial-management", "supplier-management"],
        "capabilities": [
            "asset-management",
            "configuration-management",
            "vendor-management",
            "financial-management",
            "resource-optimization",
            "reporting-analytics",
            "compliance-management",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["ISO19770", "ISO27001"],
        "integrations": [
            "ServiceNow",
            "BMC",
            "Microsoft",
            "SAP",
        ],
        "riskLevel": "LOW",
        "marketShare": "DOMINANT",
        "founded": 1988,
        "headquarters": "Itasca, IL",
        "publicCompany": False,
    },
    {
        "id": "servicenow-itam",
        "name": "ServiceNow ITAM",
        "category": "ITAM",
        "vendorType": "SAAS",
        "description": "Native ITAM capabilities within ServiceNow platform. Integrated asset lifecycle management with CMDB and ITSM.",
        "website": "https://www.servicenow.com/products/it-asset-management.html",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$50K-$400K",
        "cobitProcesses": [
            "BAI09",
            "BAI10",
            "APO06",
            "APO10",
            "DSS01",
        ],
        "cobitDomains": ["BAI", "APO", "DSS"],
        "itilProcesses": ["service-asset-config", "financial-management"],
        "capabilities": [
            "asset-management",
            "configuration-management",
            "financial-management",
            "workflow-orchestration",
            "reporting-analytics",
            "integration-platform",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["ISO19770", "SOC2", "ISO27001"],
        "integrations": ["ServiceNow ITSM", "CMDB", "Procurement"],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2003,
        "headquarters": "Santa Clara, CA",
        "publicCompany": True,
    },
    {
        "id": "dynatrace",
        "name": "Dynatrace",
        "category": "APM",
        "vendorType": "SAAS",
        "description": "AI-powered observability platform with automatic discovery and root cause analysis. Leader in application performance monitoring.",
        "website": "https://www.dynatrace.com",
        "deploymentModel": ["CLOUD", "HYBRID"],
        "licenseModel": "Subscription based on consumption",
        "typicalAnnualCost": "$100K-$1M+",
        "cobitProcesses": [
            "DSS01",
            "DSS02",
            "DSS03",
            "BAI04",
            "APO11",
            "MEA01",
        ],
        "cobitDomains": [
            "DSS",
            "BAI",
            "APO",
            "MEA",
        ],
        "itilProcesses": [
            "event-management",
            "incident-management",
            "problem-management",
            "availability-management",
            "capacity-management",
        ],
        "capabilities": [
            "monitoring-alerting",
            "performance-management",
            "automation",
            "ai-ml",
            "reporting-analytics",
            "problem-management",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "HIPAA",
            "PCI-DSS",
        ],
        "integrations": [
            "ServiceNow",
            "Jira",
            "Slack",
            "PagerDuty",
            "AWS",
            "Azure",
            "GCP",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2005,
        "headquarters": "Waltham, MA",
        "publicCompany": True,
    },
    {
        "id": "appdynamics",
        "name": "AppDynamics (Cisco)",
        "category": "APM",
        "vendorType": "SAAS",
        "description": "Full-stack APM with business transaction monitoring. Now part of Cisco with strong network integration.",
        "website": "https://www.appdynamics.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$80K-$800K",
        "cobitProcesses": [
            "DSS01",
            "DSS02",
            "DSS03",
            "BAI04",
            "MEA01",
        ],
        "cobitDomains": ["DSS", "BAI", "MEA"],
        "itilProcesses": [
            "event-management",
            "incident-management",
            "problem-management",
            "availability-management",
            "capacity-management",
        ],
        "capabilities": [
            "monitoring-alerting",
            "performance-management",
            "reporting-analytics",
            "business-continuity",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["SOC2", "ISO27001", "HIPAA"],
        "integrations": [
            "ServiceNow",
            "Jira",
            "Splunk",
            "AWS",
            "Azure",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2008,
        "headquarters": "San Francisco, CA",
        "publicCompany": False,
    },
    {
        "id": "datadog",
        "name": "Datadog",
        "category": "APM",
        "vendorType": "SAAS",
        "description": "Modern observability platform with infrastructure monitoring, APM, and log management. Strong in cloud-native environments.",
        "website": "https://www.datadoghq.com",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Usage-based subscription",
        "typicalAnnualCost": "$50K-$500K",
        "cobitProcesses": [
            "DSS01",
            "DSS02",
            "BAI04",
            "MEA01",
        ],
        "cobitDomains": ["DSS", "BAI", "MEA"],
        "itilProcesses": ["event-management", "incident-management", "availability-management"],
        "capabilities": [
            "monitoring-alerting",
            "performance-management",
            "reporting-analytics",
            "integration-platform",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "HIPAA",
            "PCI-DSS",
        ],
        "integrations": [
            "Slack",
            "PagerDuty",
            "Jira",
            "ServiceNow",
            "AWS",
            "Azure",
            "GCP",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2010,
        "headquarters": "New York, NY",
        "publicCompany": True,
    },
    {
        "id": "new-relic",
        "name": "New Relic",
        "category": "APM",
        "vendorType": "SAAS",
        "description": "Observability platform with full-stack monitoring and AI-powered insights. Strong in developer-centric monitoring.",
        "website": "https://newrelic.com",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Usage-based subscription",
        "typicalAnnualCost": "$40K-$400K",
        "cobitProcesses": [
            "DSS01",
            "DSS02",
            "BAI04",
            "MEA01",
        ],
        "cobitDomains": ["DSS", "BAI", "MEA"],
        "itilProcesses": ["event-management", "incident-management", "availability-management"],
        "capabilities": [
            "monitoring-alerting",
            "performance-management",
            "reporting-analytics",
            "ai-ml",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["SOC2", "ISO27001", "HIPAA"],
        "integrations": [
            "Slack",
            "PagerDuty",
            "Jira",
            "AWS",
            "Azure",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2008,
        "headquarters": "San Francisco, CA",
        "publicCompany": True,
    },
    {
        "id": "splunk-enterprise-security",
        "name": "Splunk Enterprise Security",
        "category": "SECURITY",
        "vendorType": "SOFTWARE",
        "description": "SIEM platform with comprehensive security analytics. Industry leader in log management and security operations.",
        "website": "https://www.splunk.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription based on data volume",
        "typicalAnnualCost": "$100K-$1M+",
        "cobitProcesses": [
            "DSS05",
            "DSS06",
            "APO13",
            "MEA02",
            "MEA03",
        ],
        "cobitDomains": ["DSS", "APO", "MEA"],
        "itilProcesses": ["information-security", "event-management", "incident-management"],
        "capabilities": [
            "security-management",
            "monitoring-alerting",
            "compliance-management",
            "reporting-analytics",
            "ai-ml",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "NIST",
            "ISO27001",
            "PCI-DSS",
            "HIPAA",
            "SOC2",
        ],
        "integrations": [
            "ServiceNow",
            "Palo Alto",
            "CrowdStrike",
            "Microsoft Sentinel",
        ],
        "riskLevel": "LOW",
        "marketShare": "DOMINANT",
        "founded": 2003,
        "headquarters": "San Francisco, CA",
        "publicCompany": True,
    },
    {
        "id": "crowdstrike",
        "name": "CrowdStrike Falcon",
        "category": "SECURITY",
        "vendorType": "SAAS",
        "description": "Cloud-native endpoint protection platform with EDR and threat intelligence. Leader in modern endpoint security.",
        "website": "https://www.crowdstrike.com",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Subscription per endpoint",
        "typicalAnnualCost": "$50K-$500K",
        "cobitProcesses": ["DSS05", "APO13", "MEA02"],
        "cobitDomains": ["DSS", "APO", "MEA"],
        "itilProcesses": ["information-security", "event-management", "incident-management"],
        "capabilities": [
            "security-management",
            "monitoring-alerting",
            "incident-management",
            "ai-ml",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["ISO27001", "SOC2", "FedRAMP"],
        "integrations": [
            "ServiceNow",
            "Splunk",
            "Microsoft Sentinel",
            "AWS",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2011,
        "headquarters": "Austin, TX",
        "publicCompany": True,
    },
    {
        "id": "palo-alto-cortex",
        "name": "Palo Alto Cortex XSOAR",
        "category": "SECURITY",
        "vendorType": "SAAS",
        "description": "Security orchestration, automation and response (SOAR) platform. Comprehensive threat intelligence and incident response.",
        "website": "https://www.paloaltonetworks.com/cortex/cortex-xsoar",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$75K-$600K",
        "cobitProcesses": ["DSS05", "APO13", "BAI06"],
        "cobitDomains": ["DSS", "APO", "BAI"],
        "itilProcesses": ["information-security", "incident-management", "event-management"],
        "capabilities": [
            "security-management",
            "automation",
            "workflow-orchestration",
            "incident-management",
            "integration-platform",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["NIST", "ISO27001", "SOC2"],
        "integrations": [
            "Splunk",
            "ServiceNow",
            "Microsoft Sentinel",
            "CrowdStrike",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2005,
        "headquarters": "Santa Clara, CA",
        "publicCompany": True,
    },
    {
        "id": "github",
        "name": "GitHub Enterprise",
        "category": "DEVOPS",
        "vendorType": "SAAS",
        "description": "Leading software development platform with version control, CI/CD, and collaboration. Now owned by Microsoft.",
        "website": "https://github.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription per user",
        "typicalAnnualCost": "$20K-$300K",
        "cobitProcesses": [
            "BAI01",
            "BAI02",
            "BAI03",
            "BAI06",
            "BAI07",
            "APO01",
        ],
        "cobitDomains": ["BAI", "APO"],
        "itilProcesses": ["change-management", "release-deployment", "service-validation"],
        "capabilities": [
            "change-management",
            "release-management",
            "automation",
            "workflow-orchestration",
            "project-management",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["SOC2", "ISO27001", "FedRAMP"],
        "integrations": [
            "Jira",
            "Slack",
            "Microsoft Teams",
            "Azure",
            "AWS",
        ],
        "riskLevel": "LOW",
        "marketShare": "DOMINANT",
        "founded": 2008,
        "headquarters": "San Francisco, CA",
        "publicCompany": False,
    },
    {
        "id": "gitlab",
        "name": "GitLab",
        "category": "DEVOPS",
        "vendorType": "SAAS",
        "description": "Complete DevOps platform with version control, CI/CD, security, and monitoring. Open-core model with strong enterprise features.",
        "website": "https://gitlab.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription per user",
        "typicalAnnualCost": "$25K-$400K",
        "cobitProcesses": [
            "BAI01",
            "BAI02",
            "BAI03",
            "BAI06",
            "BAI07",
            "APO13",
        ],
        "cobitDomains": ["BAI", "APO"],
        "itilProcesses": ["change-management", "release-deployment", "service-validation"],
        "capabilities": [
            "change-management",
            "release-management",
            "automation",
            "security-management",
            "project-management",
            "workflow-orchestration",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["SOC2", "ISO27001"],
        "integrations": [
            "Jira",
            "ServiceNow",
            "Kubernetes",
            "AWS",
            "Azure",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2011,
        "headquarters": "San Francisco, CA",
        "publicCompany": True,
    },
    {
        "id": "jenkins",
        "name": "CloudBees (Jenkins Enterprise)",
        "category": "DEVOPS",
        "vendorType": "SOFTWARE",
        "description": "Enterprise version of Jenkins CI/CD with support and management features. Leading open-source CI/CD platform.",
        "website": "https://www.cloudbees.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$30K-$250K",
        "cobitProcesses": ["BAI03", "BAI06", "BAI07"],
        "cobitDomains": ["BAI"],
        "itilProcesses": ["release-deployment", "change-management"],
        "capabilities": [
            "automation",
            "release-management",
            "change-management",
            "workflow-orchestration",
        ],
        "marketPosition": "CHALLENGER",
        "complianceFrameworks": ["SOC2"],
        "integrations": [
            "Jira",
            "GitHub",
            "GitLab",
            "AWS",
            "Azure",
            "Kubernetes",
        ],
        "riskLevel": "MEDIUM",
        "marketShare": "MAJOR",
        "founded": 2010,
        "headquarters": "San Jose, CA",
        "publicCompany": False,
    },
    {
        "id": "aws",
        "name": "Amazon Web Services",
        "category": "CLOUD_PLATFORM",
        "vendorType": "CLOUD_SERVICE",
        "description": "Leading cloud infrastructure provider with comprehensive IaaS, PaaS, and SaaS offerings. Dominant market position.",
        "website": "https://aws.amazon.com",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Pay-as-you-go",
        "typicalAnnualCost": "$50K-$10M+",
        "cobitProcesses": [
            "BAI04",
            "BAI09",
            "DSS01",
            "DSS04",
            "DSS05",
            "APO06",
        ],
        "cobitDomains": ["BAI", "DSS", "APO"],
        "itilProcesses": [
            "capacity-management",
            "availability-management",
            "it-service-continuity",
        ],
        "capabilities": [
            "resource-optimization",
            "capacity-planning",
            "security-management",
            "business-continuity",
            "monitoring-alerting",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "HIPAA",
            "PCI-DSS",
            "FedRAMP",
        ],
        "integrations": ["All major platforms"],
        "riskLevel": "LOW",
        "marketShare": "DOMINANT",
        "founded": 2006,
        "headquarters": "Seattle, WA",
        "publicCompany": True,
    },
    {
        "id": "azure",
        "name": "Microsoft Azure",
        "category": "CLOUD_PLATFORM",
        "vendorType": "CLOUD_SERVICE",
        "description": "Microsoft's cloud platform with strong enterprise integration and hybrid cloud capabilities.",
        "website": "https://azure.microsoft.com",
        "deploymentModel": ["CLOUD", "HYBRID"],
        "licenseModel": "Pay-as-you-go",
        "typicalAnnualCost": "$50K-$10M+",
        "cobitProcesses": [
            "BAI04",
            "BAI09",
            "DSS01",
            "DSS04",
            "DSS05",
            "APO06",
        ],
        "cobitDomains": ["BAI", "DSS", "APO"],
        "itilProcesses": [
            "capacity-management",
            "availability-management",
            "it-service-continuity",
        ],
        "capabilities": [
            "resource-optimization",
            "capacity-planning",
            "security-management",
            "business-continuity",
            "integration-platform",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "HIPAA",
            "PCI-DSS",
            "FedRAMP",
        ],
        "integrations": ["Microsoft 365", "Dynamics 365", "Power Platform"],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2010,
        "headquarters": "Redmond, WA",
        "publicCompany": True,
    },
    {
        "id": "gcp",
        "name": "Google Cloud Platform",
        "category": "CLOUD_PLATFORM",
        "vendorType": "CLOUD_SERVICE",
        "description": "Google's cloud infrastructure with strength in data analytics, AI/ML, and Kubernetes.",
        "website": "https://cloud.google.com",
        "deploymentModel": ["CLOUD"],
        "licenseModel": "Pay-as-you-go",
        "typicalAnnualCost": "$30K-$8M+",
        "cobitProcesses": [
            "BAI04",
            "BAI09",
            "DSS01",
            "DSS04",
            "APO06",
        ],
        "cobitDomains": ["BAI", "DSS", "APO"],
        "itilProcesses": ["capacity-management", "availability-management"],
        "capabilities": [
            "resource-optimization",
            "capacity-planning",
            "ai-ml",
            "monitoring-alerting",
            "reporting-analytics",
        ],
        "marketPosition": "CHALLENGER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "HIPAA",
            "PCI-DSS",
        ],
        "integrations": ["Kubernetes", "Terraform", "major platforms"],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2008,
        "headquarters": "Mountain View, CA",
        "publicCompany": True,
    },
    {
        "id": "pega",
        "name": "Pega Platform",
        "category": "BPM",
        "vendorType": "SOFTWARE",
        "description": "Low-code BPM platform with strong case management and decisioning capabilities. Leader in customer service automation.",
        "website": "https://www.pega.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$150K-$1M+",
        "cobitProcesses": [
            "BAI01",
            "BAI02",
            "BAI03",
            "APO01",
            "APO09",
            "DSS01",
        ],
        "cobitDomains": ["BAI", "APO", "DSS"],
        "itilProcesses": ["design-coordination", "service-catalog-mgmt", "request-fulfillment"],
        "capabilities": [
            "workflow-orchestration",
            "automation",
            "service-catalog",
            "project-management",
            "ai-ml",
            "reporting-analytics",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": ["SOC2", "ISO27001", "HIPAA"],
        "integrations": [
            "Salesforce",
            "SAP",
            "ServiceNow",
            "Microsoft",
        ],
        "riskLevel": "MEDIUM",
        "marketShare": "MAJOR",
        "founded": 1983,
        "headquarters": "Cambridge, MA",
        "publicCompany": True,
    },
    {
        "id": "appian",
        "name": "Appian",
        "category": "BPM",
        "vendorType": "SAAS",
        "description": "Low-code automation platform with strong process mining and RPA capabilities. Focus on enterprise-grade workflow automation.",
        "website": "https://appian.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$100K-$800K",
        "cobitProcesses": [
            "BAI01",
            "BAI02",
            "BAI03",
            "APO01",
            "DSS01",
        ],
        "cobitDomains": ["BAI", "APO", "DSS"],
        "itilProcesses": ["design-coordination", "request-fulfillment"],
        "capabilities": [
            "workflow-orchestration",
            "automation",
            "project-management",
            "reporting-analytics",
            "integration-platform",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "SOC2",
            "ISO27001",
            "HIPAA",
            "FedRAMP",
        ],
        "integrations": [
            "Salesforce",
            "SAP",
            "ServiceNow",
            "AWS",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 1999,
        "headquarters": "McLean, VA",
        "publicCompany": True,
    },
    {
        "id": "collibra",
        "name": "Collibra",
        "category": "DATA_GOVERNANCE",
        "vendorType": "SAAS",
        "description": "Data governance and catalog platform. Leader in metadata management and data lineage.",
        "website": "https://www.collibra.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$75K-$500K",
        "cobitProcesses": [
            "APO01",
            "APO11",
            "BAI08",
            "BAI10",
            "DSS06",
            "MEA01",
        ],
        "cobitDomains": [
            "APO",
            "BAI",
            "DSS",
            "MEA",
        ],
        "itilProcesses": ["knowledge-management", "service-asset-config"],
        "capabilities": [
            "governance-framework",
            "knowledge-management",
            "compliance-management",
            "reporting-analytics",
            "audit-compliance",
        ],
        "marketPosition": "LEADER",
        "complianceFrameworks": [
            "GDPR",
            "CCPA",
            "SOC2",
            "ISO27001",
        ],
        "integrations": [
            "Snowflake",
            "Databricks",
            "AWS",
            "Azure",
            "Tableau",
        ],
        "riskLevel": "LOW",
        "marketShare": "MAJOR",
        "founded": 2008,
        "headquarters": "New York, NY",
        "publicCompany": False,
    },
    {
        "id": "alation",
        "name": "Alation",
        "category": "DATA_GOVERNANCE",
        "vendorType": "SAAS",
        "description": "Data catalog and governance platform with collaborative features. Strong in data discovery and stewardship.",
        "website": "https://www.alation.com",
        "deploymentModel": ["CLOUD", "ON_PREMISE"],
        "licenseModel": "Subscription",
        "typicalAnnualCost": "$60K-$400K",
        "cobitProcesses": [
            "APO01",
            "APO11",
            "BAI08",
            "BAI10",
            "MEA01",
        ],
        "cobitDomains": ["APO", "BAI", "MEA"],
        "itilProcesses": ["knowledge-management"],
        "capabilities": [
            "knowledge-management",
            "governance-framework",
            "reporting-analytics",
            "compliance-management",
        ],
        "marketPosition": "CHALLENGER",
        "complianceFrameworks": ["SOC2", "GDPR"],
        "integrations": [
            "Snowflake",
            "Tableau",
            "AWS",
            "Azure",
            "Databricks",
        ],
        "riskLevel": "MEDIUM",
        "marketShare": "MODERATE",
        "founded": 2012,
        "headquarters": "Redwood City, CA",
        "publicCompany": False,
    },
]


# ============================================================================
# VENDOR CATEGORY TO APQC MAPPING RULES
# Auto-generates APQC process mappings based on vendor category
# ============================================================================

VENDOR_CATEGORY_APQC_MAPPING: Dict[str, Dict] = {
    "ITSM": {
        "primary_processes": ["6.0", "6.2", "6.4", "8.0", "8.2", "8.7", "8.8"],
        "secondary_processes": ["13.4", "13.5"],
        "coverage_level": "substantial",
        "architecture_domains": ["Application", "Business"],
    },
    "EA_TOOLS": {
        "primary_processes": ["1.0", "1.1", "1.2", "8.1", "13.0", "13.1", "13.2"],
        "secondary_processes": ["2.1", "11.1"],
        "coverage_level": "full",
        "architecture_domains": ["Enterprise", "Business", "Application"],
    },
    "GRC": {
        "primary_processes": ["11.0", "11.1", "11.2", "11.3", "11.4", "9.8"],
        "secondary_processes": ["8.3", "8.4", "12.4"],
        "coverage_level": "full",
        "architecture_domains": ["Enterprise", "Business"],
    },
    "ITAM": {
        "primary_processes": ["8.5", "10.0", "10.1", "10.3"],
        "secondary_processes": ["8.1", "9.4"],
        "coverage_level": "substantial",
        "architecture_domains": ["Business", "Application"],
    },
    "APM": {
        "primary_processes": ["8.0", "8.3", "8.8"],
        "secondary_processes": ["6.3", "13.6"],
        "coverage_level": "partial",
        "architecture_domains": ["Application", "Technology"],
    },
    "SECURITY": {
        "primary_processes": ["8.4", "11.0", "11.1", "11.4"],
        "secondary_processes": ["8.3"],
        "coverage_level": "substantial",
        "architecture_domains": ["Application", "Technology"],
    },
    "CLOUD_PLATFORM": {
        "primary_processes": ["8.0", "8.6", "8.7", "8.8"],
        "secondary_processes": ["4.1", "10.2"],
        "coverage_level": "partial",
        "architecture_domains": ["Technology", "Application", "Data"],
    },
    "DEVOPS": {
        "primary_processes": ["8.6", "8.7", "2.2"],
        "secondary_processes": ["13.3", "13.4"],
        "coverage_level": "substantial",
        "architecture_domains": ["Application", "Technology"],
    },
    "DATA_GOVERNANCE": {
        "primary_processes": ["8.5", "13.5"],
        "secondary_processes": ["11.2", "9.8"],
        "coverage_level": "full",
        "architecture_domains": ["Data", "Application"],
    },
    "BPM": {
        "primary_processes": ["13.0", "13.1", "13.2", "13.4"],
        "secondary_processes": ["1.3", "8.6"],
        "coverage_level": "full",
        "architecture_domains": ["Business", "Application"],
    },
}

# Capability to APQC Process mapping for fine-grained matching
CAPABILITY_APQC_MAPPING: Dict[str, List[str]] = {
    "service-desk": ["6.4", "8.8"],
    "incident-management": ["6.4", "8.8"],
    "problem-management": ["6.5", "8.8"],
    "change-management": ["8.7", "13.4"],
    "release-management": ["8.7"],
    "service-request": ["6.4"],
    "configuration-management": ["8.5"],
    "asset-management": ["10.1", "8.5"],
    "knowledge-management": ["13.5", "8.5"],
    "service-catalog": ["5.0", "8.2"],
    "governance-framework": ["11.0", "8.1"],
    "risk-management": ["11.1", "8.3"],
    "compliance-management": ["11.2"],
    "portfolio-management": ["13.2", "8.1"],
    "architecture-management": ["8.1", "1.0"],
    "vendor-management": ["4.2", "12.0"],
    "security-management": ["8.4", "11.1"],
    "performance-management": ["13.6", "8.8"],
    "resource-optimization": ["8.1", "10.1"],
    "monitoring-alerting": ["8.8", "6.3"],
    "automation": ["8.6", "13.1"],
    "reporting-analytics": ["13.6", "8.1"],
    "workflow-orchestration": ["13.1", "8.6"],
    "integration-platform": ["8.6", "12.0"],
    "ai-ml": ["8.6", "2.2"],
    "project-management": ["13.2"],
    "financial-management": ["9.0", "9.1"],
    "audit-compliance": ["11.2", "9.8"],
    "business-continuity": ["11.4", "8.3"],
    "capacity-planning": ["8.8", "4.1"],
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_vendors_by_category(category: VendorCategory) -> List[VendorInfo]:
    """Get all vendors in a specific category."""
    return [v for v in VENDOR_CATALOGUE if v["category"] == category]


def get_vendors_by_cobit_process(process_code: str) -> List[VendorInfo]:
    """Get all vendors supporting a specific COBIT process."""
    return [v for v in VENDOR_CATALOGUE if process_code in v["cobitProcesses"]]


def get_vendors_by_cobit_domain(domain: COBITDomain) -> List[VendorInfo]:
    """Get all vendors supporting a specific COBIT domain."""
    return [v for v in VENDOR_CATALOGUE if domain in v["cobitDomains"]]


def get_vendors_by_itil_process(process_name: str) -> List[VendorInfo]:
    """Get all vendors supporting a specific ITIL process."""
    return [v for v in VENDOR_CATALOGUE if process_name in v["itilProcesses"]]


def get_vendors_by_capability(capability: str) -> List[VendorInfo]:
    """Get all vendors supporting a specific capability."""
    return [v for v in VENDOR_CATALOGUE if capability in v["capabilities"]]


def get_vendor_by_id(vendor_id: str) -> VendorInfo | None:
    """Get vendor by ID."""
    for v in VENDOR_CATALOGUE:
        if v["id"] == vendor_id:
            return v
    return None


def search_vendors_by_name(query: str) -> List[VendorInfo]:
    """Search vendors by name (case-insensitive)."""
    lower_query = query.lower()
    return [v for v in VENDOR_CATALOGUE if lower_query in v["name"].lower()]


def get_vendors_by_apqc_process(process_code: str) -> List[VendorInfo]:
    """Get all vendors supporting a specific APQC process."""
    return [
        v for v in VENDOR_CATALOGUE if v.get("apqcProcesses") and process_code in v["apqcProcesses"]
    ]


def get_vendor_apqc_processes(vendor_id: str) -> List[str]:
    """
    Get APQC processes for a vendor.
    Uses explicit mapping if available, otherwise derives from category and capabilities.
    """
    vendor = get_vendor_by_id(vendor_id)
    if not vendor:
        return []

    # Check for explicit mapping
    if vendor.get("apqcProcesses"):
        return vendor["apqcProcesses"]

    # Derive from category
    apqc_processes = set()
    category = vendor.get("category")
    if category and category in VENDOR_CATEGORY_APQC_MAPPING:
        mapping = VENDOR_CATEGORY_APQC_MAPPING[category]
        apqc_processes.update(mapping.get("primary_processes", []))
        apqc_processes.update(mapping.get("secondary_processes", []))

    # Derive from capabilities
    capabilities = vendor.get("capabilities", [])
    for cap in capabilities:
        if cap in CAPABILITY_APQC_MAPPING:
            apqc_processes.update(CAPABILITY_APQC_MAPPING[cap])

    return sorted(list(apqc_processes))


def get_vendor_architecture_domains(vendor_id: str) -> List[str]:
    """Get architecture domains covered by a vendor."""
    vendor = get_vendor_by_id(vendor_id)
    if not vendor:
        return []

    category = vendor.get("category")
    if category and category in VENDOR_CATEGORY_APQC_MAPPING:
        return VENDOR_CATEGORY_APQC_MAPPING[category].get("architecture_domains", [])

    return []


def get_apqc_process_info(process_code: str) -> Dict | None:
    """Get detailed APQC process information."""
    return APQC_PROCESSES.get(process_code)


def get_apqc_processes_by_level(level: int) -> List[Dict]:
    """Get all APQC processes at a specific level (1 - 3)."""
    return [
        {"code": code, **info}
        for code, info in APQC_PROCESSES.items()
        if info.get("level") == level
    ]


def get_apqc_processes_by_architecture_domain(domain: str) -> List[Dict]:
    """Get APQC processes relevant to a specific architecture domain."""
    return [
        {"code": code, **info}
        for code, info in APQC_PROCESSES.items()
        if domain in info.get("architecture_domains", [])
    ]


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "VendorInfo",
    "VendorCategory",
    "VendorType",
    "DeploymentModel",
    "COBITDomain",
    "MarketPosition",
    "RiskLevel",
    "MarketShare",
    "CAPABILITY_TAXONOMY",
    "COBIT_PROCESSES",
    "ITIL_PROCESSES",
    "APQC_PROCESSES",
    "APQC_CATEGORIES",
    "VENDOR_CATEGORY_APQC_MAPPING",
    "CAPABILITY_APQC_MAPPING",
    "VENDOR_CATALOGUE",
    "get_vendors_by_category",
    "get_vendors_by_cobit_process",
    "get_vendors_by_cobit_domain",
    "get_vendors_by_itil_process",
    "get_vendors_by_capability",
    "get_vendors_by_apqc_process",
    "get_vendor_by_id",
    "search_vendors_by_name",
    "get_vendor_apqc_processes",
    "get_vendor_architecture_domains",
    "get_apqc_process_info",
    "get_apqc_processes_by_level",
    "get_apqc_processes_by_architecture_domain",
]
