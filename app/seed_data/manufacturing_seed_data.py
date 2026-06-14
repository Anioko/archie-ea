"""
Manufacturing seed data for two-pass idempotent seeding.

This file provides a small, deterministic flat list of manufacturing unified capabilities
that can be consumed by a two-pass seeder (create/update then parent linking).
"""

from typing import Any, Dict, List


def get_flat_capabilities() -> List[Dict[str, Any]]:
    """Return a flat list of manufacturing unified capabilities.

    Each entry should include a unique `code`. Use `parent_code` when a parent-child
    relationship is required. Consumers should map `domain_code` -> BusinessDomain.id.
    """
    return [
        {
            "code": "MFG-OPS",
            "name": "Manufacturing Operations",
            "description": "Operational capabilities for manufacturing operations",
            "level": 1,
            "domain_code": "MFG",
            "industry_domain": "Manufacturing",
            "manufacturing_critical": True,
            "business_owner": "Manufacturing Lead",
            "strategic_importance": "high",
            "category": "core",
        },
        {
            "code": "MFG-PLN",
            "name": "Production Planning",
            "description": "Planning and scheduling of production",
            "level": 2,
            "parent_code": "MFG-OPS",
            "domain_code": "MFG",
            "industry_domain": "Manufacturing",
            "manufacturing_critical": True,
            "business_owner": "Planning Lead",
            "strategic_importance": "medium",
            "category": "supporting",
        },
        {
            "code": "MFG-EXEC",
            "name": "Production Execution",
            "description": "Execution and shopfloor control",
            "level": 2,
            "parent_code": "MFG-OPS",
            "domain_code": "MFG",
            "industry_domain": "Manufacturing",
            "manufacturing_critical": True,
            "business_owner": "Operations Manager",
            "strategic_importance": "medium",
            "category": "supporting",
        },
    ]
