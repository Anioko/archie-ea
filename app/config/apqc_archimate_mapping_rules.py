"""
APQC to ArchiMate Mapping Rules Configuration

Phase 2.2: Defines how APQC Process Classification Framework hierarchy levels
map to ArchiMate 3.2 elements. This configuration provides the foundation for
intelligent derivation of enterprise architecture elements from APQC processes.

Mapping Logic:
- Level 1 (Category): Maps to high-level BusinessFunction/Capability elements
- Level 2 (Process Group): Maps to BusinessProcess with service derivation
- Level 3 (Process): Maps to detailed BusinessProcess with role/object context
- Level 4 (Activity): Too granular - metadata extracted for parent enrichment
- Level 5 (Task): Skipped - operational detail not suitable for EA modeling

Reference: APQC PCF 8.0 and ArchiMate 3.2 Specification
"""

from typing import Any, Dict, List, Optional

# =============================================================================
# APQC LEVEL MAPPING RULES
# =============================================================================

APQC_LEVEL_MAPPING_RULES: Dict[int, Dict[str, Any]] = {
    1: {
        # Category level (e.g., "4.0 Supply Chain")
        # Highest abstraction - represents major business functions
        "primary_element": "BusinessFunction",
        "secondary_elements": ["Capability", "ValueStream"],
        "derive_relationships": True,
        "aggregation_behavior": "container",  # Contains child processes
        "description": "APQC Category - maps to high-level business functions",
        "example_codes": ["1.0", "4.0", "7.0", "13.0"],
        "archimate_layer": "business",
        "relationship_patterns": [
            {"type": "composition", "target_level": 2},  # Contains Process Groups
            {"type": "realization", "target_element": "Capability"},  # Realizes capabilities
        ],
    },
    2: {
        # Process Group level (e.g., "4.1 Plan supply chain")
        # Mid-level abstraction - represents coherent process groups
        "primary_element": "BusinessProcess",
        "secondary_elements": ["BusinessService"],
        "derive_relationships": True,
        "aggregation_behavior": "parent",  # Parent of detailed processes
        "description": "APQC Process Group - maps to major business processes",
        "example_codes": ["1.1", "4.1", "7.2", "13.3"],
        "archimate_layer": "business",
        "relationship_patterns": [
            {"type": "composition", "target_level": 3},  # Contains Processes
            {"type": "realization", "target_element": "BusinessService"},  # Realizes services
            {"type": "triggering", "target_level": 2},  # Triggers other process groups
        ],
    },
    3: {
        # Process level (e.g., "4.1.1 Develop production plan")
        # Detailed process - primary target for EA process modeling
        "primary_element": "BusinessProcess",
        "secondary_elements": ["BusinessRole", "BusinessObject"],
        "derive_relationships": True,
        "aggregation_behavior": "standard",  # Standard process modeling
        "description": "APQC Process - maps to detailed business processes",
        "example_codes": ["1.1.1", "4.1.1", "7.2.1", "13.3.1"],
        "archimate_layer": "business",
        "relationship_patterns": [
            {"type": "assignment", "target_element": "BusinessRole"},  # Assigned roles
            {"type": "access", "target_element": "BusinessObject"},  # Accesses objects
            {"type": "triggering", "target_level": 3},  # Triggers other processes
            {"type": "flow", "target_element": "BusinessObject"},  # Flows information
        ],
    },
    4: {
        # Activity level (e.g., "4.1.1.1 Assess demand")
        # Too granular for main mapping - extract metadata for parent enrichment
        "primary_element": None,  # Not mapped directly
        "secondary_elements": ["BusinessEvent"],
        "derive_relationships": False,
        "aggregation_behavior": "metadata",  # Roll up to parent
        "description": "APQC Activity - too granular, extract metadata for parent",
        "example_codes": ["1.1.1.1", "4.1.1.1", "7.2.1.1", "13.3.1.1"],
        "archimate_layer": None,
        "extract_for_parent": ["triggers", "inputs", "outputs", "events"],
        "metadata_extraction": {
            "trigger_keywords": ["initiate", "start", "begin", "receive", "detect"],
            "input_keywords": ["review", "analyze", "assess", "evaluate", "examine"],
            "output_keywords": ["produce", "create", "generate", "deliver", "send"],
        },
    },
    5: {
        # Task level (e.g., "4.1.1.1.1 Gather historical data")
        # Operational detail - skip for EA modeling
        "primary_element": None,
        "secondary_elements": [],
        "derive_relationships": False,
        "aggregation_behavior": "skip",  # Do not process
        "description": "APQC Task - too detailed for EA, skip",
        "example_codes": ["1.1.1.1.1", "4.1.1.1.1", "7.2.1.1.1"],
        "archimate_layer": None,
    },
}


# =============================================================================
# APQC CATEGORY ELEMENT PATTERNS
# =============================================================================

APQC_CATEGORY_ELEMENT_PATTERNS: Dict[str, Dict[str, Any]] = {
    "1.0": {
        # Develop Vision and Strategy
        "category_name": "Develop Vision and Strategy",
        "category_type": "Management",
        "business_elements": ["Goal", "Driver", "Capability", "CourseOfAction"],
        "motivation_elements": ["Stakeholder", "Value", "Outcome", "Principle"],
        "strategy_elements": ["Resource", "ValueStream"],
        "typical_roles": [
            "Strategy Analyst",
            "Business Planner",
            "Chief Strategy Officer",
            "Strategic Planning Manager",
            "Business Architect",
        ],
        "typical_objects": [
            "Strategic Plan",
            "Business Case",
            "Vision Statement",
            "Mission Statement",
            "Strategic Roadmap",
            "Market Analysis Report",
            "Competitive Analysis",
        ],
        "key_relationships": ["influence", "realization", "association"],
        "cross_layer_connections": {
            "application": ["Strategic Planning System", "Portfolio Management Tool"],
            "technology": [],
        },
    },
    "2.0": {
        # Develop and Manage Products and Services
        "category_name": "Develop and Manage Products and Services",
        "category_type": "Operating",
        "business_elements": ["BusinessProcess", "Product", "BusinessService", "Requirement"],
        "application_elements": ["ApplicationComponent", "ApplicationService"],
        "typical_roles": [
            "Product Manager",
            "Product Owner",
            "Service Designer",
            "R&D Manager",
            "Innovation Manager",
            "Product Development Engineer",
        ],
        "typical_objects": [
            "Product Specification",
            "Service Catalog",
            "Product Roadmap",
            "Design Document",
            "Prototype",
            "Product Requirements Document",
            "Market Requirements Document",
        ],
        "key_relationships": ["realization", "composition", "serving"],
        "cross_layer_connections": {
            "application": ["PLM System", "CAD Software", "Product Configurator"],
            "technology": ["Design Workstation", "Rendering Server"],
        },
    },
    "3.0": {
        # Market and Sell Products and Services
        "category_name": "Market and Sell Products and Services",
        "category_type": "Operating",
        "business_elements": [
            "BusinessProcess",
            "BusinessService",
            "BusinessInterface",
            "BusinessEvent",
        ],
        "application_elements": ["ApplicationComponent", "ApplicationService"],
        "typical_roles": [
            "Sales Manager",
            "Marketing Manager",
            "Account Executive",
            "Business Development Manager",
            "Marketing Analyst",
            "Sales Representative",
            "Channel Manager",
        ],
        "typical_objects": [
            "Sales Order",
            "Marketing Campaign",
            "Customer Proposal",
            "Quote",
            "Lead",
            "Opportunity Record",
            "Marketing Content",
            "Price List",
        ],
        "key_relationships": ["serving", "triggering", "flow"],
        "cross_layer_connections": {
            "application": ["CRM System", "Marketing Automation Platform", "E-commerce Platform"],
            "technology": ["Web Server", "Email Server"],
        },
    },
    "4.0": {
        # Deliver Physical Products (Supply Chain)
        "category_name": "Deliver Physical Products",
        "category_type": "Operating",
        "business_elements": ["BusinessProcess", "Material", "Facility"],
        "physical_elements": ["Equipment", "DistributionNetwork", "Material"],
        "typical_roles": [
            "Supply Chain Manager",
            "Logistics Coordinator",
            "Procurement Manager",
            "Warehouse Manager",
            "Transportation Manager",
            "Inventory Analyst",
            "Demand Planner",
        ],
        "typical_objects": [
            "Purchase Order",
            "Inventory Record",
            "Shipping Document",
            "Bill of Lading",
            "Warehouse Receipt",
            "Demand Forecast",
            "Supply Plan",
            "Delivery Schedule",
        ],
        "key_relationships": ["triggering", "access", "flow"],
        "cross_layer_connections": {
            "application": ["ERP System", "WMS", "TMS", "Procurement System"],
            "technology": ["Barcode Scanner", "RFID Reader", "IoT Sensors"],
        },
    },
    "5.0": {
        # Deliver Services
        "category_name": "Deliver Services",
        "category_type": "Operating",
        "business_elements": [
            "BusinessService",
            "BusinessProcess",
            "BusinessInterface",
            "Contract",
        ],
        "application_elements": ["ApplicationService", "ApplicationComponent"],
        "typical_roles": [
            "Service Delivery Manager",
            "Service Operations Manager",
            "Service Engineer",
            "Field Service Technician",
            "Service Coordinator",
            "Service Account Manager",
        ],
        "typical_objects": [
            "Service Request",
            "Work Order",
            "Service Level Agreement",
            "Service Report",
            "Service Contract",
            "Service Schedule",
            "Service Knowledge Article",
        ],
        "key_relationships": ["serving", "realization", "assignment"],
        "cross_layer_connections": {
            "application": ["Service Management System", "Field Service App", "Knowledge Base"],
            "technology": ["Mobile Device", "GPS Tracker"],
        },
    },
    "6.0": {
        # Manage Customer Service
        "category_name": "Manage Customer Service",
        "category_type": "Operating",
        "business_elements": [
            "BusinessProcess",
            "BusinessRole",
            "BusinessActor",
            "BusinessInterface",
            "BusinessEvent",
        ],
        "application_elements": ["ApplicationComponent", "ApplicationService"],
        "typical_roles": [
            "Customer Service Manager",
            "Customer Service Representative",
            "Call Center Agent",
            "Customer Success Manager",
            "Support Specialist",
            "Customer Experience Manager",
        ],
        "typical_objects": [
            "Customer Inquiry",
            "Support Ticket",
            "Customer Complaint",
            "Customer Record",
            "Interaction History",
            "Resolution Record",
            "Customer Feedback",
        ],
        "key_relationships": ["assignment", "serving", "triggering"],
        "cross_layer_connections": {
            "application": ["CRM System", "Helpdesk System", "Call Center Platform", "Chatbot"],
            "technology": ["Phone System", "IVR System"],
        },
    },
    "7.0": {
        # Develop and Manage IT
        "category_name": "Develop and Manage IT",
        "category_type": "Management",
        "business_elements": ["BusinessProcess", "BusinessService"],
        "application_elements": [
            "ApplicationComponent",
            "ApplicationService",
            "ApplicationInterface",
            "DataObject",
        ],
        "technology_elements": [
            "Node",
            "SystemSoftware",
            "TechnologyService",
            "CommunicationNetwork",
            "Artifact",
        ],
        "typical_roles": [
            "IT Manager",
            "System Administrator",
            "Software Developer",
            "Solution Architect",
            "DevOps Engineer",
            "Database Administrator",
            "IT Service Manager",
            "Security Analyst",
        ],
        "typical_objects": [
            "System Specification",
            "Technical Design Document",
            "Deployment Package",
            "Configuration Item",
            "Incident Record",
            "Change Request",
            "IT Asset Record",
            "System Documentation",
        ],
        "key_relationships": ["serving", "realization", "composition"],
        "cross_layer_connections": {
            "application": ["ITSM Tool", "CI/CD Pipeline", "Monitoring Platform", "CMDB"],
            "technology": ["Server", "Cloud Platform", "Network Infrastructure"],
        },
    },
    "8.0": {
        # Manage Enterprise Information
        "category_name": "Manage Enterprise Information",
        "category_type": "Management",
        "business_elements": ["BusinessProcess", "BusinessObject", "Representation"],
        "application_elements": ["DataObject", "ApplicationComponent", "ApplicationService"],
        "motivation_elements": ["Meaning"],
        "typical_roles": [
            "Data Architect",
            "Data Steward",
            "Information Manager",
            "Master Data Manager",
            "Data Quality Analyst",
            "Data Governance Manager",
            "Business Intelligence Analyst",
        ],
        "typical_objects": [
            "Data Catalog",
            "Data Dictionary",
            "Information Asset",
            "Data Quality Report",
            "Master Data Record",
            "Metadata Repository",
            "Data Governance Policy",
        ],
        "key_relationships": ["access", "realization", "association"],
        "cross_layer_connections": {
            "application": ["MDM System", "Data Catalog", "BI Platform", "Data Lake"],
            "technology": ["Database Server", "Data Warehouse", "ETL Server"],
        },
    },
    "9.0": {
        # Manage Financial Resources
        "category_name": "Manage Financial Resources",
        "category_type": "Management",
        "business_elements": ["BusinessProcess", "BusinessObject", "BusinessRole", "Contract"],
        "motivation_elements": ["Principle", "Constraint", "Requirement"],
        "typical_roles": [
            "Finance Manager",
            "Accountant",
            "Financial Controller",
            "Treasury Manager",
            "Tax Manager",
            "Accounts Payable Specialist",
            "Accounts Receivable Specialist",
            "Budget Analyst",
        ],
        "typical_objects": [
            "Financial Statement",
            "Budget",
            "Invoice",
            "Payment Record",
            "Tax Return",
            "General Ledger Entry",
            "Financial Report",
            "Audit Trail",
        ],
        "key_relationships": ["access", "assignment", "influence"],
        "cross_layer_connections": {
            "application": [
                "ERP Finance Module",
                "Treasury System",
                "Tax Software",
                "Budgeting Tool",
            ],
            "technology": ["Financial Database Server"],
        },
    },
    "10.0": {
        # Acquire, Construct, and Manage Assets
        "category_name": "Acquire, Construct, and Manage Assets",
        "category_type": "Management",
        "business_elements": ["BusinessProcess", "BusinessObject", "Contract"],
        "physical_elements": ["Facility", "Equipment", "Material"],
        "strategy_elements": ["Resource"],
        "motivation_elements": ["Constraint", "Assessment"],
        "typical_roles": [
            "Asset Manager",
            "Facilities Manager",
            "Property Manager",
            "Maintenance Manager",
            "Real Estate Manager",
            "Capital Projects Manager",
            "Equipment Manager",
        ],
        "typical_objects": [
            "Asset Register",
            "Maintenance Schedule",
            "Work Order",
            "Lease Agreement",
            "Capital Budget",
            "Asset Valuation Report",
            "Depreciation Schedule",
            "Facility Plan",
        ],
        "key_relationships": ["access", "aggregation", "association"],
        "cross_layer_connections": {
            "application": ["EAM System", "CMMS", "Facilities Management System"],
            "technology": ["Building Management System", "IoT Sensors"],
        },
    },
    "11.0": {
        # Manage Enterprise Risk, Compliance, Remediation, and Resiliency
        "category_name": "Manage Enterprise Risk, Compliance, Remediation, and Resiliency",
        "category_type": "Management",
        "business_elements": ["BusinessProcess", "BusinessObject", "Contract"],
        "motivation_elements": [
            "Assessment",
            "Constraint",
            "Requirement",
            "Stakeholder",
            "Principle",
            "Driver",
        ],
        "typical_roles": [
            "Risk Manager",
            "Compliance Officer",
            "Internal Auditor",
            "Business Continuity Manager",
            "Legal Counsel",
            "Privacy Officer",
            "Security Manager",
            "Ethics Officer",
        ],
        "typical_objects": [
            "Risk Register",
            "Compliance Report",
            "Audit Finding",
            "Control Assessment",
            "Policy Document",
            "Business Continuity Plan",
            "Incident Report",
            "Regulatory Filing",
        ],
        "key_relationships": ["influence", "realization", "association"],
        "cross_layer_connections": {
            "application": ["GRC Platform", "Audit Management System", "Policy Management System"],
            "technology": ["Security Information System", "Backup System"],
        },
    },
    "12.0": {
        # Manage External Relationships
        "category_name": "Manage External Relationships",
        "category_type": "Management",
        "business_elements": [
            "BusinessProcess",
            "BusinessActor",
            "BusinessCollaboration",
            "BusinessInterface",
            "Contract",
        ],
        "motivation_elements": ["Meaning", "Stakeholder"],
        "typical_roles": [
            "Investor Relations Manager",
            "Government Affairs Manager",
            "Public Relations Manager",
            "Community Relations Manager",
            "Partner Manager",
            "Stakeholder Engagement Manager",
            "Corporate Communications Manager",
        ],
        "typical_objects": [
            "Stakeholder Communication",
            "Press Release",
            "Investor Report",
            "Partnership Agreement",
            "Public Statement",
            "Government Filing",
            "Community Impact Report",
            "Annual Report",
        ],
        "key_relationships": ["association", "serving", "flow"],
        "cross_layer_connections": {
            "application": ["PR Management System", "Investor Portal", "Partner Portal"],
            "technology": ["Website", "Social Media Platform"],
        },
    },
    "13.0": {
        # Develop and Manage Human Capital
        "category_name": "Develop and Manage Human Capital",
        "category_type": "Management",
        "business_elements": ["BusinessProcess", "BusinessRole", "BusinessActor", "BusinessObject"],
        "strategy_elements": ["Resource", "Capability"],
        "motivation_elements": ["Goal"],
        "typical_roles": [
            "HR Manager",
            "Recruiter",
            "Training Manager",
            "Compensation Analyst",
            "HR Business Partner",
            "Talent Acquisition Manager",
            "Learning & Development Manager",
            "Employee Relations Manager",
        ],
        "typical_objects": [
            "Employee Record",
            "Job Description",
            "Performance Review",
            "Training Record",
            "Compensation Plan",
            "Organizational Chart",
            "Talent Profile",
            "Workforce Plan",
        ],
        "key_relationships": ["assignment", "realization", "access"],
        "cross_layer_connections": {
            "application": ["HRIS", "LMS", "Performance Management System", "Recruiting System"],
            "technology": ["Employee Portal Server"],
        },
    },
}


# =============================================================================
# AGGREGATION BEHAVIOR DEFINITIONS
# =============================================================================

AGGREGATION_BEHAVIORS: Dict[str, Dict[str, Any]] = {
    "container": {
        "description": "Acts as container for child elements",
        "create_element": True,
        "create_composition_relationships": True,
        "inherit_child_relationships": False,
        "archimate_relationship": "composition",
    },
    "parent": {
        "description": "Parent of detailed processes",
        "create_element": True,
        "create_composition_relationships": True,
        "inherit_child_relationships": True,
        "archimate_relationship": "aggregation",
    },
    "standard": {
        "description": "Standard element creation and relationship derivation",
        "create_element": True,
        "create_composition_relationships": False,
        "inherit_child_relationships": False,
        "archimate_relationship": None,
    },
    "metadata": {
        "description": "Extract metadata to enrich parent element",
        "create_element": False,
        "create_composition_relationships": False,
        "inherit_child_relationships": False,
        "archimate_relationship": None,
        "extract_triggers": True,
        "extract_inputs_outputs": True,
    },
    "skip": {
        "description": "Skip processing - too granular",
        "create_element": False,
        "create_composition_relationships": False,
        "inherit_child_relationships": False,
        "archimate_relationship": None,
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_mapping_rule_for_level(level: int) -> Optional[Dict[str, Any]]:
    """
    Get the mapping rule configuration for a specific APQC hierarchy level.

    Args:
        level: The APQC hierarchy level (1 - 5)

    Returns:
        Dictionary containing the mapping rule configuration, or None if level is invalid.

    Example:
        >>> rule = get_mapping_rule_for_level(1)
        >>> print(rule['primary_element'])
        'BusinessFunction'
    """
    if not isinstance(level, int) or level < 1 or level > 5:
        return None
    return APQC_LEVEL_MAPPING_RULES.get(level)


def get_element_pattern_for_category(apqc_category: str) -> Optional[Dict[str, Any]]:
    """
    Get the element pattern configuration for a specific APQC category.

    Args:
        apqc_category: The APQC category code (e.g., '1.0', '4.0', '7.0')

    Returns:
        Dictionary containing the element pattern configuration, or None if category is invalid.

    Example:
        >>> pattern = get_element_pattern_for_category('4.0')
        >>> print(pattern['category_name'])
        'Deliver Physical Products'
    """
    # Normalize category code (ensure it ends with .0)
    if apqc_category and not apqc_category.endswith(".0"):
        # Extract the main category number
        parts = apqc_category.split(".")
        if parts:
            apqc_category = f"{parts[0]}.0"

    return APQC_CATEGORY_ELEMENT_PATTERNS.get(apqc_category)


def should_create_element(apqc_level: int) -> bool:
    """
    Determine whether an ArchiMate element should be created for the given APQC level.

    Args:
        apqc_level: The APQC hierarchy level (1 - 5)

    Returns:
        True if an element should be created, False otherwise.

    Note:
        Levels 1 - 3 create elements; Levels 4 - 5 do not (too granular).

    Example:
        >>> should_create_element(3)
        True
        >>> should_create_element(5)
        False
    """
    rule = get_mapping_rule_for_level(apqc_level)
    if rule is None:
        return False
    return rule.get("primary_element") is not None


def get_aggregation_behavior(apqc_level: int) -> Optional[str]:
    """
    Get the aggregation behavior for the given APQC level.

    Args:
        apqc_level: The APQC hierarchy level (1 - 5)

    Returns:
        String indicating the aggregation behavior ('container', 'parent', 'standard',
        'metadata', or 'skip'), or None if level is invalid.

    Example:
        >>> get_aggregation_behavior(1)
        'container'
        >>> get_aggregation_behavior(4)
        'metadata'
    """
    rule = get_mapping_rule_for_level(apqc_level)
    if rule is None:
        return None
    return rule.get("aggregation_behavior")


def get_primary_element_type(apqc_level: int) -> Optional[str]:
    """
    Get the primary ArchiMate element type for the given APQC level.

    Args:
        apqc_level: The APQC hierarchy level (1 - 5)

    Returns:
        String indicating the primary ArchiMate element type, or None if not applicable.

    Example:
        >>> get_primary_element_type(1)
        'BusinessFunction'
        >>> get_primary_element_type(3)
        'BusinessProcess'
    """
    rule = get_mapping_rule_for_level(apqc_level)
    if rule is None:
        return None
    return rule.get("primary_element")


def get_secondary_elements(apqc_level: int) -> List[str]:
    """
    Get the secondary ArchiMate element types for the given APQC level.

    Args:
        apqc_level: The APQC hierarchy level (1 - 5)

    Returns:
        List of secondary ArchiMate element types that can be derived.

    Example:
        >>> get_secondary_elements(1)
        ['Capability', 'ValueStream']
    """
    rule = get_mapping_rule_for_level(apqc_level)
    if rule is None:
        return []
    return rule.get("secondary_elements", [])


def should_derive_relationships(apqc_level: int) -> bool:
    """
    Determine whether relationships should be derived for the given APQC level.

    Args:
        apqc_level: The APQC hierarchy level (1 - 5)

    Returns:
        True if relationships should be derived, False otherwise.

    Example:
        >>> should_derive_relationships(2)
        True
        >>> should_derive_relationships(5)
        False
    """
    rule = get_mapping_rule_for_level(apqc_level)
    if rule is None:
        return False
    return rule.get("derive_relationships", False)


def get_typical_roles_for_category(apqc_category: str) -> List[str]:
    """
    Get the typical business roles associated with an APQC category.

    Args:
        apqc_category: The APQC category code (e.g., '1.0', '4.0')

    Returns:
        List of typical role names for the category.

    Example:
        >>> roles = get_typical_roles_for_category('4.0')
        >>> 'Supply Chain Manager' in roles
        True
    """
    pattern = get_element_pattern_for_category(apqc_category)
    if pattern is None:
        return []
    return pattern.get("typical_roles", [])


def get_typical_objects_for_category(apqc_category: str) -> List[str]:
    """
    Get the typical business objects associated with an APQC category.

    Args:
        apqc_category: The APQC category code (e.g., '1.0', '4.0')

    Returns:
        List of typical business object names for the category.

    Example:
        >>> objects = get_typical_objects_for_category('4.0')
        >>> 'Purchase Order' in objects
        True
    """
    pattern = get_element_pattern_for_category(apqc_category)
    if pattern is None:
        return []
    return pattern.get("typical_objects", [])


def get_cross_layer_connections(apqc_category: str, target_layer: str) -> List[str]:
    """
    Get typical cross-layer application or technology connections for a category.

    Args:
        apqc_category: The APQC category code (e.g., '1.0', '4.0')
        target_layer: The target layer ('application' or 'technology')

    Returns:
        List of typical application or technology element names.

    Example:
        >>> apps = get_cross_layer_connections('4.0', 'application')
        >>> 'ERP System' in apps
        True
    """
    pattern = get_element_pattern_for_category(apqc_category)
    if pattern is None:
        return []
    connections = pattern.get("cross_layer_connections", {})
    return connections.get(target_layer, [])


def get_all_business_elements_for_category(apqc_category: str) -> List[str]:
    """
    Get all business layer element types applicable to an APQC category.

    Args:
        apqc_category: The APQC category code (e.g., '1.0', '4.0')

    Returns:
        List of all business layer ArchiMate element types for the category.

    Example:
        >>> elements = get_all_business_elements_for_category('4.0')
        >>> 'BusinessProcess' in elements
        True
    """
    pattern = get_element_pattern_for_category(apqc_category)
    if pattern is None:
        return []
    return pattern.get("business_elements", [])


def get_motivation_elements_for_category(apqc_category: str) -> List[str]:
    """
    Get motivation layer element types applicable to an APQC category.

    Args:
        apqc_category: The APQC category code (e.g., '1.0', '11.0')

    Returns:
        List of motivation layer ArchiMate element types for the category.

    Example:
        >>> elements = get_motivation_elements_for_category('1.0')
        >>> 'Goal' in elements
        True
    """
    pattern = get_element_pattern_for_category(apqc_category)
    if pattern is None:
        return []
    return pattern.get("motivation_elements", [])


def get_category_type(apqc_category: str) -> Optional[str]:
    """
    Get the category type (Operating or Management) for an APQC category.

    Args:
        apqc_category: The APQC category code (e.g., '1.0', '4.0')

    Returns:
        'Operating' or 'Management' indicating the category type, or None if invalid.

    Note:
        - Operating categories (2.0 - 6.0): Core value-creating processes
        - Management categories (1.0, 7.0 - 13.0): Support and management processes

    Example:
        >>> get_category_type('4.0')
        'Operating'
        >>> get_category_type('7.0')
        'Management'
    """
    pattern = get_element_pattern_for_category(apqc_category)
    if pattern is None:
        return None
    return pattern.get("category_type")


def get_aggregation_behavior_details(behavior: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed configuration for an aggregation behavior type.

    Args:
        behavior: The aggregation behavior type ('container', 'parent', 'standard',
                 'metadata', or 'skip')

    Returns:
        Dictionary with behavior configuration details, or None if invalid.

    Example:
        >>> details = get_aggregation_behavior_details('container')
        >>> details['create_composition_relationships']
        True
    """
    return AGGREGATION_BEHAVIORS.get(behavior)


def get_extract_fields_for_level(apqc_level: int) -> List[str]:
    """
    Get the fields to extract from an APQC level for parent enrichment.

    Args:
        apqc_level: The APQC hierarchy level (typically 4)

    Returns:
        List of field names to extract (e.g., ['triggers', 'inputs', 'outputs']).

    Example:
        >>> fields = get_extract_fields_for_level(4)
        >>> 'triggers' in fields
        True
    """
    rule = get_mapping_rule_for_level(apqc_level)
    if rule is None:
        return []
    return rule.get("extract_for_parent", [])


def get_all_categories() -> List[str]:
    """
    Get all APQC category codes.

    Returns:
        List of all 13 APQC category codes (1.0 through 13.0).

    Example:
        >>> categories = get_all_categories()
        >>> len(categories)
        13
    """
    return list(APQC_CATEGORY_ELEMENT_PATTERNS.keys())


def get_category_name(apqc_category: str) -> Optional[str]:
    """
    Get the full name of an APQC category.

    Args:
        apqc_category: The APQC category code (e.g., '1.0', '4.0')

    Returns:
        The full category name, or None if invalid.

    Example:
        >>> get_category_name('4.0')
        'Deliver Physical Products'
    """
    pattern = get_element_pattern_for_category(apqc_category)
    if pattern is None:
        return None
    return pattern.get("category_name")


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def validate_apqc_level(level: int) -> bool:
    """
    Validate that a level value is a valid APQC hierarchy level.

    Args:
        level: The level value to validate

    Returns:
        True if valid (1 - 5), False otherwise.
    """
    return isinstance(level, int) and 1 <= level <= 5


def validate_apqc_category(category: str) -> bool:
    """
    Validate that a category code is a valid APQC category.

    Args:
        category: The category code to validate (e.g., '4.0')

    Returns:
        True if valid, False otherwise.
    """
    if not category:
        return False

    # Normalize
    if not category.endswith(".0"):
        parts = category.split(".")
        if parts:
            category = f"{parts[0]}.0"

    return category in APQC_CATEGORY_ELEMENT_PATTERNS


def validate_aggregation_behavior(behavior: str) -> bool:
    """
    Validate that a behavior value is a valid aggregation behavior.

    Args:
        behavior: The behavior value to validate

    Returns:
        True if valid, False otherwise.
    """
    return behavior in AGGREGATION_BEHAVIORS
