"""
Capability Tagging System

Enterprise-grade flexible capability categorization and tagging infrastructure.
Provides dynamic capability classification without schema changes.
"""

from datetime import datetime
from typing import Dict, List, Optional  # dead-code-ok

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text  # dead-code-ok
from sqlalchemy.orm import relationship  # dead-code-ok

from .. import db
from .mixins import TenantMixin


class CapabilityTag(TenantMixin, db.Model):
    """Capability tag for flexible categorization."""

    __tablename__ = "capability_tags"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    category = Column(String(20), nullable=False)  # application, business, technical, governance
    description = Column(Text)
    color = Column(String(7))  # For UI visualization (hex colors)
    icon = Column(String(50))  # Lucide icon name
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CapabilityTag {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
        }


class CapabilityTagAssociation(db.Model):
    """Many-to-many association between capabilities and tags."""

    __tablename__ = "capability_tag_associations"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True)
    capability_id = Column(Integer, ForeignKey("unified_capabilities.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("capability_tags.id"), nullable=False)
    strength = Column(Integer, default=1)  # 1 - 5 how strongly tag applies
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CapabilityTagAssociation {self.capability_id}-{self.tag_id}>"


# Extend existing models with tagging relationships
# NOTE: Commented out until association tables are properly defined
# from app.models.business_capabilities import BusinessCapability
# from app.models.unified_capability import UnifiedCapability

# # Add tagging to BusinessCapability
# BusinessCapability.capability_tags = relationship(
#     "CapabilityTag",
#     secondary="business_capability_tag_associations",
#     backref="tagged_capabilities",
#     lazy="dynamic",
# )

# # Add tagging to UnifiedCapability
# UnifiedCapability.capability_tags = relationship(
#     "CapabilityTag",
#     secondary="unified_capability_tag_associations",
#     backref="tagged_capabilities",
#     lazy="dynamic",
# )

# # Add tagging to ApplicationComponent
# from app.models.application_portfolio import ApplicationComponent

# ApplicationComponent.capability_tags = relationship(
#     "CapabilityTag",
#     secondary="app_capability_tag_associations",
#     backref="tagged_applications",
#     lazy="dynamic",
# )
