#!/usr/bin/env python3
"""
Business Capability Classification and Management Utility

Provides functions to classify and organize business capabilities
for capability taxonomy management and organization.
"""


class BusinessCapabilityClassifier:
    """Classifies business capabilities into business groupings and taxonomies."""

    BUSINESS_GROUPINGS = {
        "strategic": {
            "name": "Strategic Capabilities",
            "description": "Core strategic planning and governance capabilities",
            "color": "blue",
            "icon": "target",
            "subcategories": {
                "strategy_planning": {
                    "name": "Strategy Planning",
                    "description": "Strategic planning and analysis capabilities",
                    "keywords": [
                        "strategic",
                        "planning",
                        "strategy",
                        "analysis",
                        "forecasting",
                    ],
                },
                "governance": {
                    "name": "Governance & Compliance",
                    "description": "Governance, risk, and compliance capabilities",
                    "keywords": ["governance", "compliance", "risk", "audit", "policy"],
                },
                "business_development": {
                    "name": "Business Development",
                    "description": "Business growth and development capabilities",
                    "keywords": [
                        "development",
                        "growth",
                        "expansion",
                        "innovation",
                        "transformation",
                    ],
                },
            },
        },
        "operational": {
            "name": "Operational Capabilities",
            "description": "Core business operations and delivery capabilities",
            "color": "green",
            "icon": "cog",
            "subcategories": {
                "core_operations": {
                    "name": "Core Operations",
                    "description": "Primary business operations",
                    "keywords": [
                        "operations",
                        "production",
                        "manufacturing",
                        "service",
                        "delivery",
                    ],
                },
                "supply_chain": {
                    "name": "Supply Chain Management",
                    "description": "Supply chain and logistics capabilities",
                    "keywords": [
                        "supply",
                        "chain",
                        "logistics",
                        "procurement",
                        "inventory",
                        "distribution",
                    ],
                },
                "quality_management": {
                    "name": "Quality Management",
                    "description": "Quality control and assurance capabilities",
                    "keywords": [
                        "quality",
                        "control",
                        "assurance",
                        "inspection",
                        "testing",
                        "standards",
                    ],
                },
            },
        },
        "customer": {
            "name": "Customer-Facing Capabilities",
            "description": "Customer interaction and service capabilities",
            "color": "purple",
            "icon": "users",
            "subcategories": {
                "sales_marketing": {
                    "name": "Sales & Marketing",
                    "description": "Sales and marketing capabilities",
                    "keywords": [
                        "sales",
                        "marketing",
                        "advertising",
                        "promotion",
                        "customer acquisition",
                    ],
                },
                "customer_service": {
                    "name": "Customer Service",
                    "description": "Customer support and service capabilities",
                    "keywords": [
                        "customer",
                        "service",
                        "support",
                        "help",
                        "assistance",
                        "care",
                    ],
                },
                "relationship_management": {
                    "name": "Relationship Management",
                    "description": "Customer relationship management capabilities",
                    "keywords": [
                        "relationship",
                        "crm",
                        "loyalty",
                        "retention",
                        "engagement",
                    ],
                },
            },
        },
        "digital": {
            "name": "Digital & Technology Capabilities",
            "description": "Digital transformation and technology capabilities",
            "color": "indigo",
            "icon": "cpu",
            "subcategories": {
                "digital_transformation": {
                    "name": "Digital Transformation",
                    "description": "Digital transformation and innovation capabilities",
                    "keywords": [
                        "digital",
                        "transformation",
                        "innovation",
                        "automation",
                        "modernization",
                    ],
                },
                "technology_management": {
                    "name": "Technology Management",
                    "description": "IT and technology management capabilities",
                    "keywords": [
                        "technology",
                        "it",
                        "systems",
                        "infrastructure",
                        "platform",
                    ],
                },
                "data_analytics": {
                    "name": "Data & Analytics",
                    "description": "Data management and analytics capabilities",
                    "keywords": [
                        "data",
                        "analytics",
                        "intelligence",
                        "insights",
                        "reporting",
                        "bi",
                    ],
                },
            },
        },
        "support": {
            "name": "Support & Enabling Capabilities",
            "description": "Support functions and enabling capabilities",
            "color": "orange",
            "icon": "shield",
            "subcategories": {
                "human_resources": {
                    "name": "Human Resources",
                    "description": "HR and people management capabilities",
                    "keywords": [
                        "hr",
                        "human",
                        "resources",
                        "people",
                        "talent",
                        "workforce",
                    ],
                },
                "financial_management": {
                    "name": "Financial Management",
                    "description": "Financial planning and management capabilities",
                    "keywords": [
                        "financial",
                        "finance",
                        "accounting",
                        "budgeting",
                        "planning",
                        "controlling",
                    ],
                },
                "administrative": {
                    "name": "Administrative Services",
                    "description": "Administrative and facilities capabilities",
                    "keywords": [
                        "administrative",
                        "facilities",
                        "office",
                        "support",
                        "services",
                    ],
                },
            },
        },
    }

    CAPABILITY_LEVELS = {
        "enterprise": {
            "name": "Enterprise Level",
            "description": "Organization-wide strategic capabilities",
            "scope": "enterprise",
            "examples": [
                "Strategic Planning",
                "Enterprise Risk Management",
                "Corporate Governance",
            ],
        },
        "business_unit": {
            "name": "Business Unit Level",
            "description": "Business unit or division capabilities",
            "scope": "business_unit",
            "examples": ["Product Development", "Market Expansion", "Unit Strategy"],
        },
        "department": {
            "name": "Department Level",
            "description": "Department-specific capabilities",
            "scope": "department",
            "examples": ["HR Management", "Financial Control", "IT Operations"],
        },
        "team": {
            "name": "Team Level",
            "description": "Team or process-specific capabilities",
            "scope": "team",
            "examples": ["Project Management", "Process Execution", "Service Delivery"],
        },
    }

    CAPABILITY_TYPES = {
        "primary": {
            "name": "Primary Capability",
            "description": "Core business capability that directly creates value",
            "characteristics": ["customer-facing", "value-creating", "strategic"],
        },
        "supporting": {
            "name": "Supporting Capability",
            "description": "Capability that enables primary capabilities",
            "characteristics": ["enabling", "supporting", "internal"],
        },
        "management": {
            "name": "Management Capability",
            "description": "Capability for managing other capabilities",
            "characteristics": ["governance", "oversight", "coordination"],
        },
    }

    @classmethod
    def classify_capability_by_name(cls, capability_name, description=None):
        """
        Classify a capability by its name and description.
        Includes data quality filtering.

        Args:
            capability_name (str): The capability name
            description (str): Optional description

        Returns:
            dict: Classification result with grouping and subcategory, or None if invalid
        """
        if not capability_name:
            return None

        # Apply data quality fixes first
        fixed_name = cls._clean_capability_name(capability_name)
        if not fixed_name:
            # Invalid capability name
            return None

        name_lower = fixed_name.lower()
        desc_lower = description.lower() if description else ""
        combined_text = f"{name_lower} {desc_lower}"

        # Check each business grouping and collect all matches
        all_matches = []
        for grouping_key, grouping_data in cls.BUSINESS_GROUPINGS.items():
            for subcat_key, subcat_data in grouping_data["subcategories"].items():
                # Check if any keywords match
                for keyword in subcat_data["keywords"]:
                    if keyword in combined_text:
                        confidence = cls._calculate_confidence(keyword, combined_text)
                        all_matches.append(
                            {
                                "grouping_key": grouping_key,
                                "grouping_name": grouping_data["name"],
                                "grouping_color": grouping_data["color"],
                                "grouping_icon": grouping_data["icon"],
                                "subcategory_key": subcat_key,
                                "subcategory_name": subcat_data["name"],
                                "subcategory_description": subcat_data["description"],
                                "capability_name": fixed_name,  # Use cleaned name
                                "original_name": capability_name,  # Keep original for reference
                                "confidence": confidence,
                            }
                        )

        # Return the match with highest confidence
        if all_matches:
            return max(all_matches, key=lambda x: x["confidence"])

        # Default classification if no keywords match
        return {
            "grouping_key": "other",
            "grouping_name": "Other Capabilities",
            "grouping_color": "gray",
            "grouping_icon": "folder",
            "subcategory_key": "uncategorized",
            "subcategory_name": "Uncategorized",
            "subcategory_description": "Uncategorized capabilities",
            "capability_name": fixed_name,  # Use cleaned name
            "original_name": capability_name,  # Keep original for reference
            "confidence": 0.0,
        }

    @classmethod
    def _clean_capability_name(cls, name):
        """Clean and fix common data quality issues in capability names."""
        if not name:
            return None

        original_name = name.strip()
        fixed_name = original_name

        # Fix 1: Remove "Manage Management" - invalid capability
        if original_name.lower() == "manage management":
            return None  # Invalid capability

        # Fix 2: Remove redundant "Manage" prefix when capability already implies management
        management_words = [
            "management",
            "administration",
            "oversight",
            "control",
            "governance",
        ]
        if fixed_name.lower().startswith("manage "):
            remaining = fixed_name[6:].strip()
            if any(word in remaining.lower() for word in management_words):
                fixed_name = remaining

        # Fix 3: "Manage Customer Experience Management" -> "Customer Experience Management"
        if fixed_name.lower().startswith("manage customer experience management"):
            fixed_name = "Customer Experience Management"

        # Fix 4: Standardize content management variations
        content_management_variations = [
            "management application & content management",
            "application & content management",
            "content management application",
            "document and content management",
        ]

        if fixed_name.lower() in [var.lower() for var in content_management_variations]:
            fixed_name = "Content Management"

        # Fix 5: Remove redundant prefixes
        prefix_replacements = {
            "Management of ": "",
            "Administration of ": "",
            "Oversight of ": "",
        }

        for prefix, replacement in prefix_replacements.items():
            if fixed_name.startswith(prefix):
                remaining = fixed_name[len(prefix) :].strip()
                if len(remaining) > 3 and not remaining.lower().startswith(
                    "management"
                ):
                    fixed_name = remaining
                    break

        # Fix 6: Proper capitalization
        if fixed_name:
            words = fixed_name.split()
            capitalized_words = []
            for word in words:
                if word.upper() in [
                    "CRM",
                    "ERP",
                    "SCM",
                    "PLM",
                    "HR",
                    "IT",
                    "API",
                    "SQL",
                    "BI",
                ]:
                    capitalized_words.append(word.upper())
                elif word.upper() in ["AND", "OR", "OF", "IN", "FOR", "WITH", "TO"]:
                    capitalized_words.append(word.lower())
                else:
                    capitalized_words.append(word.capitalize())

            fixed_name = " ".join(capitalized_words)

        return fixed_name if fixed_name.strip() else None

    @classmethod
    def classify_capability_by_domain(cls, domain):
        """
        Classify capabilities by business domain.

        Args:
            domain (str): The business domain

        Returns:
            dict: Classification result
        """
        if not domain:
            return None

        domain_lower = domain.lower()

        # Domain to grouping mapping
        domain_mapping = {
            "strategic": "strategic",
            "governance": "strategic",
            "planning": "strategic",
            "operations": "operational",
            "production": "operational",
            "manufacturing": "operational",
            "supply": "operational",
            "logistics": "operational",
            "customer": "customer",
            "sales": "customer",
            "marketing": "customer",
            "service": "customer",
            "digital": "digital",
            "technology": "digital",
            "it": "digital",
            "data": "digital",
            "analytics": "digital",
            "hr": "support",
            "human": "support",
            "financial": "support",
            "finance": "support",
            "administrative": "support",
        }

        for domain_keyword, grouping_key in domain_mapping.items():
            if domain_keyword in domain_lower:
                grouping_data = cls.BUSINESS_GROUPINGS[grouping_key]
                return {
                    "grouping_key": grouping_key,
                    "grouping_name": grouping_data["name"],
                    "grouping_color": grouping_data["color"],
                    "grouping_icon": grouping_data["icon"],
                    "domain": domain,
                    "classification_method": "domain_mapping",
                }

        return {
            "grouping_key": "other",
            "grouping_name": "Other Capabilities",
            "grouping_color": "gray",
            "grouping_icon": "folder",
            "domain": domain,
            "classification_method": "domain_mapping",
        }

    @classmethod
    def get_business_groupings(cls):
        """
        Get all business groupings.

        Returns:
            dict: All business groupings with their metadata
        """
        return cls.BUSINESS_GROUPINGS

    @classmethod
    def get_capability_levels(cls):
        """
        Get all capability levels.

        Returns:
            dict: All capability levels
        """
        return cls.CAPABILITY_LEVELS

    @classmethod
    def get_capability_types(cls):
        """
        Get all capability types.

        Returns:
            dict: All capability types
        """
        return cls.CAPABILITY_TYPES

    @classmethod
    def get_grouping_summary(cls, grouping_key):
        """
        Get summary information for a business grouping.

        Args:
            grouping_key (str): The grouping key

        Returns:
            dict: Grouping summary or None
        """
        if grouping_key not in cls.BUSINESS_GROUPINGS:
            return None

        grouping = cls.BUSINESS_GROUPINGS[grouping_key]
        subcategory_count = len(grouping["subcategories"])

        return {
            "key": grouping_key,
            "name": grouping["name"],
            "description": grouping["description"],
            "color": grouping["color"],
            "icon": grouping["icon"],
            "subcategory_count": subcategory_count,
            "subcategories": grouping["subcategories"],
        }

    @classmethod
    def _calculate_confidence(cls, keyword, text):
        """
        Calculate confidence score for classification.

        Args:
            keyword (str): The matching keyword
            text (str): The text to search in

        Returns:
            float: Confidence score between 0 and 1
        """
        if keyword in text:
            # Higher confidence for exact matches
            if keyword == text.split()[0]:  # First word match
                return 0.9
            elif keyword in text.split():  # Any word match
                return 0.7
            else:  # Substring match
                return 0.5
        return 0.0
