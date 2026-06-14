#!/usr/bin/env python3
# mass-deletion-ok
"""
Framework Detection and Classification Utility

Provides functions to detect and classify capability categories into frameworks
for framework-specific dashboards and analytics.
"""


class FrameworkClassifier:
    """Classifies capability categories into frameworks and domains."""

    FRAMEWORKS = {
        "financial": {
            "name": "Financial Management",
            "description": "Financial planning, accounting, and treasury operations",
            "color": "blue",
            "icon": "dollar-sign",
            "domains": {
                "accounting": {
                    "name": "Accounting & Tax",
                    "description": "Accounting, tax, and treasury management",
                    "categories": ["Accounting", "Tax Management", "Treasury Management"],
                },
                "finance": {
                    "name": "Financial Planning",
                    "description": "Financial management and planning",
                    "categories": ["Financial Management", "Financial Planning"],
                },
            },
        },
        "customer": {
            "name": "Customer Management",
            "description": "Customer acquisition, retention, and service",
            "color": "green",
            "icon": "users",
            "domains": {
                "acquisition": {
                    "name": "Acquisition & Analytics",
                    "description": "Customer acquisition and analytics",
                    "categories": ["Customer Acquisition", "Customer Analytics"],
                },
                "service": {
                    "name": "Service & Retention",
                    "description": "Customer management, retention, and service",
                    "categories": [
                        "Customer Management",
                        "Customer Retention",
                        "Customer Service",
                    ],
                },
            },
        },
        "operations": {
            "name": "Operations & Supply Chain",
            "description": "Operations, supply chain, and procurement management",
            "color": "amber",
            "icon": "truck",
            "domains": {
                "operations": {
                    "name": "Operations Management",
                    "description": "Operations and process management",
                    "categories": ["Operations Management", "Process Management"],
                },
                "supply_chain": {
                    "name": "Supply Chain & Procurement",
                    "description": "Supply chain, inventory, and procurement",
                    "categories": [
                        "Supply Chain Management",
                        "Inventory Management",
                        "Procurement",
                    ],
                },
            },
        },
        "technology": {
            "name": "Technology & Data",
            "description": "IT strategy, infrastructure, and data management",
            "color": "purple",
            "icon": "cpu",
            "domains": {
                "it_strategy": {
                    "name": "IT Strategy & Apps",
                    "description": "IT strategy and application management",
                    "categories": [
                        "IT Strategy",
                        "Application Management",
                        "Technology Management",
                    ],
                },
                "infrastructure": {
                    "name": "Infrastructure & Security",
                    "description": "Infrastructure, data, and security management",
                    "categories": [
                        "Infrastructure Management",
                        "Data Management",
                        "Security Management",
                    ],
                },
            },
        },
        "product": {
            "name": "Product Management",
            "description": "Product development, innovation, and lifecycle management",
            "color": "teal",
            "icon": "box",
            "domains": {
                "development": {
                    "name": "Development & Innovation",
                    "description": "Product development and innovation",
                    "categories": ["Product Development", "Product Innovation"],
                },
                "lifecycle": {
                    "name": "Lifecycle & Portfolio",
                    "description": "Product lifecycle, management, and portfolio",
                    "categories": [
                        "Product Lifecycle",
                        "Product Management",
                        "Product Portfolio",
                    ],
                },
            },
        },
        "governance": {
            "name": "Governance & Risk",
            "description": "Compliance, risk, quality, and contract management",
            "color": "red",
            "icon": "shield",
            "domains": {
                "compliance": {
                    "name": "Compliance & Risk",
                    "description": "Compliance and risk management",
                    "categories": ["Compliance Management", "Risk Management"],
                },
                "quality": {
                    "name": "Quality & Contracts",
                    "description": "Quality and contract management",
                    "categories": ["Quality Management", "Contract Management"],
                },
            },
        },
        "workforce": {
            "name": "Workforce Management",
            "description": "Human capital, talent, and workforce planning",
            "color": "orange",
            "icon": "briefcase",
            "domains": {
                "talent": {
                    "name": "Talent Management",
                    "description": "Talent acquisition and development",
                    "categories": [
                        "Human Capital Management",
                        "Talent Acquisition",
                        "Talent Development",
                    ],
                },
                "workforce": {
                    "name": "Workforce Planning",
                    "description": "Workforce planning and employee experience",
                    "categories": ["Workforce Planning", "Employee Experience"],
                },
            },
        },
        "strategy": {
            "name": "Strategy & Partnerships",
            "description": "Strategic planning, enterprise management, and partnerships",
            "color": "indigo",
            "icon": "target",
            "domains": {
                "planning": {
                    "name": "Strategic Planning",
                    "description": "Strategic and enterprise management",
                    "categories": [
                        "Strategic Planning",
                        "Enterprise Management",
                        "Performance Management",
                    ],
                },
                "partnerships": {
                    "name": "Partner & Vendor Management",
                    "description": "Partner ecosystem and vendor management",
                    "categories": [
                        "Partner Ecosystem",
                        "Partner Management",
                        "Vendor Management",
                    ],
                },
            },
        },
        "maturity_levels": {
            "name": "Maturity Classifications",
            "description": "Capabilities classified by maturity level",
            "color": "gray",
            "icon": "bar-chart",
            "domains": {
                "operational": {
                    "name": "Operational",
                    "description": "Operational-level capabilities",
                    "categories": ["operational"],
                },
                "strategic": {
                    "name": "Strategic & Tactical",
                    "description": "Strategic, tactical, and supporting capabilities",
                    "categories": [
                        "strategic",
                        "tactical",
                        "supporting",
                        "differentiating",
                    ],
                },
            },
        },
    }

    @classmethod
    def classify_category(cls, category):
        """
        Classify a category into framework and domain.

        Args:
            category (str): The category to classify

        Returns:
            dict: Framework and domain information, or None if not found
        """
        if not category:
            return None

        category = category.strip()

        for framework_key, framework_data in cls.FRAMEWORKS.items():
            for domain_key, domain_data in framework_data["domains"].items():
                if category in domain_data["categories"]:
                    return {
                        "framework_key": framework_key,
                        "framework_name": framework_data["name"],
                        "framework_color": framework_data["color"],
                        "framework_icon": framework_data["icon"],
                        "domain_key": domain_key,
                        "domain_name": domain_data["name"],
                        "domain_description": domain_data["description"],
                        "category": category,
                    }

        return None

    @classmethod
    def get_framework_categories(cls, framework_key):
        """
        Get all categories for a specific framework.

        Args:
            framework_key (str): The framework key

        Returns:
            list: List of categories for the framework
        """
        if framework_key not in cls.FRAMEWORKS:
            return []

        categories = []
        for domain_data in cls.FRAMEWORKS[framework_key]["domains"].values():
            categories.extend(domain_data["categories"])

        return categories

    @classmethod
    def get_domain_categories(cls, framework_key, domain_key):
        """
        Get all categories for a specific domain.

        Args:
            framework_key (str): The framework key
            domain_key (str): The domain key

        Returns:
            list: List of categories for the domain
        """
        if (
            framework_key not in cls.FRAMEWORKS
            or domain_key not in cls.FRAMEWORKS[framework_key]["domains"]
        ):
            return []

        return cls.FRAMEWORKS[framework_key]["domains"][domain_key]["categories"]

    @classmethod
    def get_all_frameworks(cls):
        """
        Get all frameworks with their statistics.

        Returns:
            dict: All frameworks with their metadata
        """
        return cls.FRAMEWORKS

    @classmethod
    def get_framework_summary(cls, framework_key):
        """
        Get framework summary information.

        Args:
            framework_key (str): The framework key

        Returns:
            dict: Framework summary or None
        """
        if framework_key not in cls.FRAMEWORKS:
            return None

        framework = cls.FRAMEWORKS[framework_key]
        domain_count = len(framework["domains"])
        total_categories = sum(
            len(domain["categories"]) for domain in framework["domains"].values()
        )

        return {
            "key": framework_key,
            "name": framework["name"],
            "description": framework["description"],
            "color": framework["color"],
            "icon": framework["icon"],
            "domain_count": domain_count,
            "category_count": total_categories,
            "domains": framework["domains"],
        }
