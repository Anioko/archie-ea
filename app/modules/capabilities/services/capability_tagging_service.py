"""
DEPRECATED: Import from app.modules.capabilities.services.capability_service instead.
-> app.modules.capabilities.services.capability_service

Capability Tagging Service

Enterprise-grade capability tagging and categorization service.
Provides dynamic capability classification, search, and analytics.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.models.application_portfolio import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.capability_tagging import CapabilityTag, CapabilityTagAssociation
from app.models.unified_capability import UnifiedCapability

from app import db


class CapabilityTagService:
    """Enterprise-grade capability tagging and categorization service."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_all_tags(self) -> List[Dict]:
        """Get all capability tags with usage statistics."""
        try:
            tags = CapabilityTag.query.all()

            result = []
            for tag in tags:
                # Count total associations for this tag (how many capabilities use it)
                total_usage = (
                    db.session.query(CapabilityTagAssociation)
                    .filter(CapabilityTagAssociation.tag_id == tag.id)
                    .count()
                )

                result.append(
                    {
                        "id": tag.id,
                        "name": tag.name,
                        "category": tag.category,
                        "description": tag.description,
                        "color": tag.color,
                        "icon": tag.icon,
                        "usage": {"total": total_usage},
                    }
                )

            return result

        except Exception as e:
            self.logger.error(f"Error getting all tags: {e}")
            return []

    def get_tags_by_category(self, category: str) -> List[Dict]:
        """Get tags filtered by category."""
        try:
            tags = CapabilityTag.query.filter_by(category=category).all()

            result = []
            for tag in tags:
                result.append(
                    {
                        "id": tag.id,
                        "name": tag.name,
                        "category": tag.category,
                        "description": tag.description,
                        "color": tag.color,
                        "icon": tag.icon,
                    }
                )

            return result

        except Exception as e:
            self.logger.error(f"Error getting tags by category {category}: {e}")
            return []

    def tag_capability(self, capability_id: int, tag_ids: List[int]) -> bool:
        """Tag a capability with multiple tags."""
        try:
            capability = db.session.get(UnifiedCapability, capability_id)
            if not capability:
                self.logger.error(f"Capability {capability_id} not found")
                return False

            # Clear existing tags
            existing_associations = (
                db.session.query(CapabilityTagAssociation)
                .filter_by(capability_id=capability_id)
                .all()
            )

            for assoc in existing_associations:
                db.session.delete(assoc)

            # Add new tag associations
            for tag_id in tag_ids:
                tag = db.session.get(CapabilityTag, tag_id)
                if tag:
                    association = CapabilityTagAssociation(
                        capability_id=capability_id,
                        tag_id=tag_id,
                        strength=3,  # Default medium strength
                    )
                    db.session.add(association)

            db.session.commit()

            self.logger.info(f"Tagged capability {capability_id} with tags {tag_ids}")
            return True

        except Exception as e:
            self.logger.error(f"Error tagging capability {capability_id}: {e}")
            db.session.rollback()
            return False

    def get_capability_tags(self, capability_id: int) -> List[Dict]:
        """Get all tags for a capability."""
        try:
            associations = (
                db.session.query(CapabilityTagAssociation)
                .filter_by(capability_id=capability_id)
                .all()
            )

            result = []
            for assoc in associations:
                tag = db.session.get(CapabilityTag, assoc.tag_id)
                if tag:
                    result.append(
                        {
                            "id": tag.id,
                            "name": tag.name,
                            "category": tag.category,
                            "description": tag.description,
                            "color": tag.color,
                            "icon": tag.icon,
                            "strength": assoc.strength,
                        }
                    )

            return result

        except Exception as e:
            self.logger.error(f"Error getting capability tags {capability_id}: {e}")
            return []

    def suggest_tags_for_capability(self, capability_name: str) -> List[Dict]:
        """AI-powered tag suggestions for capabilities."""
        try:
            # Simple keyword-based suggestions
            capability_lower = capability_name.lower()

            suggestions = []

            # Application-related tags
            if any(
                keyword in capability_lower
                for keyword in ["user", "interface", "experience", "mobile", "web", "frontend"]
            ):
                suggestions.extend(
                    [
                        {"id": 1, "name": "User Interface", "category": "application"},
                        {"id": 2, "name": "Mobile Experience", "category": "application"},
                        {"id": 3, "name": "Web Application", "category": "application"},
                    ]
                )

            # Business process tags
            if any(
                keyword in capability_lower
                for keyword in ["process", "workflow", "business", "operation", "procedure"]
            ):
                suggestions.extend(
                    [
                        {"id": 4, "name": "Business Process", "category": "business"},
                        {"id": 5, "name": "Workflow Management", "category": "business"},
                        {"id": 6, "name": "Operational Excellence", "category": "business"},
                    ]
                )

            # Technical tags
            if any(
                keyword in capability_lower
                for keyword in ["technology", "technical", "system", "infrastructure", "platform"]
            ):
                suggestions.extend(
                    [
                        {"id": 7, "name": "Technology Platform", "category": "technical"},
                        {"id": 8, "name": "Infrastructure", "category": "technical"},
                        {"id": 9, "name": "System Integration", "category": "technical"},
                    ]
                )

            # Governance tags
            if any(
                keyword in capability_lower
                for keyword in ["governance", "compliance", "risk", "policy", "control"]
            ):
                suggestions.extend(
                    [
                        {"id": 10, "name": "Governance", "category": "governance"},
                        {"id": 11, "name": "Risk Management", "category": "governance"},
                        {"id": 12, "name": "Compliance", "category": "governance"},
                    ]
                )

            return suggestions

        except Exception as e:
            self.logger.error(f"Error suggesting tags for {capability_name}: {e}")
            return []

    def get_tag_statistics(self) -> Dict:
        """Get usage statistics for all tags."""
        try:
            tags = CapabilityTag.query.all()

            stats = {}
            for tag in tags:
                category = tag.category
                if category not in stats:
                    stats[category] = {"count": 0, "capabilities": []}

                stats[category]["count"] += 1
                stats[category]["capabilities"].append(tag.name)

            return {
                "total_tags": len(tags),
                "category_breakdown": stats,
                "most_used": max(stats.items(), key=lambda x: x[1]["count"]) if stats else None,
            }

        except Exception as e:
            self.logger.error(f"Error getting tag statistics: {e}")
            return {}

    def create_default_tags(self) -> bool:
        """Create default set of capability tags."""
        try:
            default_tags = [
                # Application tags
                {
                    "name": "User Interface",
                    "category": "application",
                    "description": "User-facing application interfaces",
                    "color": "#3B82F6",
                    "icon": "users",
                },
                {
                    "name": "Mobile Experience",
                    "category": "application",
                    "description": "Mobile application capabilities",
                    "color": "#10B981",
                    "icon": "smartphone",
                },
                {
                    "name": "Web Application",
                    "category": "application",
                    "description": "Web-based application functionality",
                    "color": "#0EA5E9",
                    "icon": "globe",
                },
                # Business process tags
                {
                    "name": "Business Process",
                    "category": "business",
                    "description": "Core business processes",
                    "color": "#F59E0B",
                    "icon": "briefcase",
                },
                {
                    "name": "Workflow Management",
                    "category": "business",
                    "description": "Process workflow and optimization",
                    "color": "#8B5CF6",
                    "icon": "git-branch",
                },
                # Technical tags
                {
                    "name": "Technology Platform",
                    "category": "technical",
                    "description": "Technology platform capabilities",
                    "color": "#3B82F6",
                    "icon": "server",
                },
                {
                    "name": "Infrastructure",
                    "category": "technical",
                    "description": "Infrastructure and platform services",
                    "color": "#6366F1",
                    "icon": "database",
                },
                # Governance tags
                {
                    "name": "Governance",
                    "category": "governance",
                    "description": "Governance and compliance capabilities",
                    "color": "#DC262F",
                    "icon": "shield",
                },
                {
                    "name": "Risk Management",
                    "category": "governance",
                    "description": "Risk assessment and mitigation",
                    "color": "#EF4444",
                    "icon": "alert-triangle",
                },
            ]

            for tag_data in default_tags:
                tag = CapabilityTag(
                    name=tag_data["name"],
                    category=tag_data["category"],
                    description=tag_data["description"],
                    color=tag_data["color"],
                    icon=tag_data["icon"],
                )
                db.session.add(tag)

            db.session.commit()

            self.logger.info(f"Created {len(default_tags)} default capability tags")
            return True

        except Exception as e:
            self.logger.error(f"Error creating default tags: {e}")
            db.session.rollback()
            return False
