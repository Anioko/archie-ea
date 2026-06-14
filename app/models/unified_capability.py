"""
Unified Capability Framework

Canonical capability model implementing 9 - domain structure with L0 - L3 hierarchy.
Aligns with ArchiMate 3.2, TOGAF, and BizBok standards.
Manufacturing industry enrichment with PCF process integration.

Design Principles:
- Business-first orientation
- Domain clarity (exactly one domain per capability)
- Hierarchical structure (L0 - L3)
- Value stream alignment
- ArchiMate 3.2 compliance
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional  # dead-code-ok

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.unified_application_capability_mapping import UnifiedApplicationCapabilityMapping

from .. import db
from .mixins import OptimisticLockMixin

logger = logging.getLogger(__name__)


class BusinessDomain(db.Model):
    """
    Business Domain Model (L0)

    Highest level enterprise capability domains.
    Each L1 capability belongs to exactly one domain.
    """

    __tablename__ = "business_domains"
    __table_args__ = {"extend_existing": True}

    id = Column(db.Integer, primary_key=True)

    # Domain identity
    code = Column(db.String(10), unique=True, nullable=False, index=True)  # CUST, PROD, OPER, etc.
    name = Column(db.String(100), nullable=False)
    description = Column(db.Text)

    # Domain classification
    domain_type = Column(db.String(30))  # primary, supporting, enabling
    strategic_focus = Column(db.String(100))  # Customer experience, operational excellence, etc.

    # Governance
    domain_owner = Column(db.String(100))  # C-level executive
    governance_model = Column(db.String(50))  # centralized, federated, hybrid

    # Strategic metrics
    strategic_weight = Column(db.Float, default=1.0)  # Relative importance weighting
    investment_priority = Column(db.String(20))  # critical, high, medium, low

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    capabilities = relationship("UnifiedCapability", backref="domain", lazy="dynamic")

    def __repr__(self):
        return f"<BusinessDomain {self.code}: {self.name}>"


class UnifiedCapability(db.Model, OptimisticLockMixin):
    """
    Unified Capability Model (L1 - L3)

    Single source of truth for all capability modeling.
    Replaces fragmented capability models with unified framework.

    Levels:
    - L1: Strategic Capabilities (major business capabilities)
    - L2: Tactical Capabilities (sub-capabilities or specializations)
    - L3: Operational Capabilities (specific business functions)

    Domains:
    - CUST: Customer Management
    - PROD: Product Management
    - OPER: Operations Management
    - FIN: Financial Management
    - RISK: Risk & Compliance
    - DATA: Data & Analytics
    - PART: Partner & Supplier Management
    - WORK: Workforce Management
    - TECH: Technology Enablement
    """

    __tablename__ = "unified_capabilities"
    __table_args__ = {"extend_existing": True}

    id = Column(BigInteger, primary_key=True)

    # Capability identity
    name = Column(db.String(256), nullable=False, index=True)
    description = Column(db.Text)
    code = Column(db.String(50), unique=True, index=True)  # e.g., CUST-CRM-ACQ, PROD-DEV-PLM

    # Specialization type marker
    specialization_type = Column(
        db.String(50), default="BUSINESS", index=True
    )  # Explicit type: BUSINESS, MANUFACTURING, APPLICATION, TECHNICAL

    # Hierarchy (L0 - L3)
    level = Column(db.Integer, nullable=False, default=1)  # 1=Strategic, 2=Tactical, 3=Operational
    parent_capability_id = Column(
        BigInteger, ForeignKey("unified_capabilities.id", name="fk_parent_capability")
    )

    # Domain classification
    domain_id = Column(db.Integer, ForeignKey("business_domains.id", ondelete="SET NULL"), nullable=True)
    category = Column(db.String(50))  # core, supporting, differentiating
    capability_type = Column(db.String(30))  # strategic, operational, supporting

    # Business context
    business_value = Column(db.Text)
    business_outcomes = Column(db.Text)  # JSON array of business outcomes
    kpis = Column(db.Text)  # JSON array of KPIs
    success_metrics = Column(db.Text)  # JSON object

    # Manufacturing industry specific
    industry_domain = Column(db.String(50))  # Manufacturing, Healthcare, Finance, etc.
    manufacturing_critical = Column(db.Boolean, default=False)
    industry_kpis = Column(db.Text)  # JSON with industry-specific KPIs

    # Maturity assessment (CMM-based: 1 - 5)
    current_maturity_level = Column(db.Integer, default=1)
    target_maturity_level = Column(db.Integer, default=3)
    maturity_gap = Column(db.Integer)
    maturity_assessment_date = Column(db.DateTime)
    maturity_assessment_notes = Column(db.Text)

    # Financial context
    annual_cost = Column(db.Float)
    annual_revenue_impact = Column(db.Float)
    investment_required = Column(db.Float)
    roi_percentage = Column(db.Float)

    # Strategic importance
    strategic_importance = db.Column(db.String(20))  # critical, high, medium, low
    is_core_differentiator = Column(Boolean, default=False)
    business_criticality = db.Column(db.String(20))  # mission_critical, important, supporting

    # Status and Roadmap
    status = db.Column(
        db.String(30), default="defined"
    )  # defined, developing, operational, retiring
    roadmap_priority = db.Column(db.String(20))  # high, medium, low
    target_state_description = db.Column(db.Text)

    # ArchiMate 3.2 integration
    archimate_id = Column(db.String(64), unique=True, index=True)
    archimate_layer = Column(db.String(32), default="strategy")
    archimate_element_type = Column(db.String(30), default="capability")
    archimate_element_id = Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Value stream alignment
    value_stream_stages = Column(db.Text)  # JSON array of supported value stream stages
    value_stream_criticality = Column(db.String(20))  # critical, important, supporting

    # Process integration (PCF/APQC)
    supporting_processes = Column(db.Text)  # JSON array of supporting process codes
    process_coverage = Column(db.Integer, default=0)  # Percentage of processes covered

    # Ownership and governance
    business_owner = Column(db.String(100))
    capability_owner = Column(db.String(100))
    it_owner = Column(db.String(100))
    product_manager = Column(db.String(100))

    # Quality attributes
    reliability_score = Column(db.Float)  # 0 - 100
    performance_score = Column(db.Float)  # 0 - 100
    security_score = Column(db.Float)  # 0 - 100
    scalability_score = Column(db.Float)  # 0 - 100

    # Metadata
    discovered_by_ai = Column(db.Boolean, default=True)
    discovery_confidence = Column(db.Float)
    discovery_source = Column(db.String(100))
    stability_score = Column(db.Integer)  # 1 - 100
    evolution_notes = Column(db.Text)

    # Framework configuration support
    configuration_id = Column(db.Integer, db.ForeignKey("capability_framework_configuration.id"))
    is_template = Column(db.Boolean, default=False)  # Whether this is a template capability
    extension_source = Column(db.String(100))  # Source extension if created by extension

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parent_capability = relationship(
        "UnifiedCapability",
        remote_side="UnifiedCapability.id",
        backref=db.backref("child_capabilities", lazy="dynamic"),
    )

    # ArchiMate element
    archimate_element = relationship("ArchiMateElement", backref="unified_capabilities")

    # Application relationships
    application_capability_mappings = relationship(
        "UnifiedApplicationCapabilityMapping", back_populates="unified_capability"
    )

    # Value stream relationships (commented out to avoid conflicts)
    # value_stream_mappings = relationship('CapabilityValueStreamMapping', back_populates='capability')

    # Process relationships (commented out to avoid conflicts)
    # process_mappings = relationship('UnifiedCapabilityProcessMapping', back_populates='capability')

    # Technology relationships (commented out to avoid conflicts)
    # technology_mappings = relationship('CapabilityTechnologyMapping', back_populates='capability')

    # Framework configuration relationship
    configuration = relationship(
        "CapabilityFrameworkConfiguration", foreign_keys=[configuration_id]
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_capability_hierarchy", "domain_id", "level", "parent_capability_id"),
        Index("idx_capability_business", "strategic_importance", "business_criticality"),
        Index("idx_capability_maturity", "current_maturity_level", "target_maturity_level"),
        Index("idx_capability_manufacturing", "industry_domain", "manufacturing_critical"),
        Index("idx_capability_configuration", "configuration_id", "is_template"),
        {"extend_existing": True},
    )

    def __repr__(self):
        return f"<UnifiedCapability {self.name} (L{self.level})>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "code": self.code,
            "level": self.level,
            "domain_code": self.domain.code if self.domain else None,
            "domain_name": self.domain.name if self.domain else None,
            "category": self.category,
            "capability_type": self.capability_type,
            "industry_domain": self.industry_domain,
            "manufacturing_critical": self.manufacturing_critical,
            "current_maturity_level": self.current_maturity_level,
            "target_maturity_level": self.target_maturity_level,
            "maturity_gap": self.maturity_gap,
            "strategic_importance": self.strategic_importance,
            "business_criticality": self.business_criticality,
            "is_core_differentiator": self.is_core_differentiator,
            "annual_cost": self.annual_cost,
            "annual_revenue_impact": self.annual_revenue_impact,
            "roi_percentage": self.roi_percentage,
            "status": self.status,
            "roadmap_priority": self.roadmap_priority,
            "archimate_id": self.archimate_id,
            "value_stream_criticality": self.value_stream_criticality,
            "process_coverage": self.process_coverage,
            "business_owner": self.business_owner,
            "capability_owner": self.capability_owner,
            "reliability_score": self.reliability_score,
            "performance_score": self.performance_score,
            "security_score": self.security_score,
            "scalability_score": self.scalability_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def calculate_maturity_gap(self):
        """Calculates and updates maturity gap. Caller is responsible for committing."""
        if self.target_maturity_level and self.current_maturity_level:
            self.maturity_gap = self.target_maturity_level - self.current_maturity_level
        return self.maturity_gap

    def get_full_hierarchy_path(self):
        """Returns full capability hierarchy path."""
        path = [self.name]
        current = self.parent_capability
        while current:
            path.insert(0, current.name)
            current = current.parent_capability
        return " > ".join(path)

    def get_business_outcomes(self):
        """Parse JSON business outcomes."""
        if self.business_outcomes:
            try:
                import json

                return json.loads(self.business_outcomes)
            except Exception as e:
                logger.error(
                    "Failed to parse business_outcomes capability_id=%s: %s",
                    getattr(self, "id", None),
                    e,
                    exc_info=True,
                )
                return []
        return []

    def set_business_outcomes(self, outcomes_list):
        """Set business outcomes as JSON."""
        import json

        self.business_outcomes = json.dumps(outcomes_list)

    def get_kpis(self):
        """Parse JSON KPIs."""
        if self.kpis:
            try:
                import json

                return json.loads(self.kpis)
            except Exception as e:
                logger.error(
                    "Failed to parse kpis capability_id=%s: %s",
                    getattr(self, "id", None),
                    e,
                    exc_info=True,
                )
                return []
        return []

    def set_kpis(self, kpis_list):
        """Set KPIs as JSON."""
        import json

        self.kpis = json.dumps(kpis_list)


class CapabilityValueStreamMapping(db.Model):
    """
    Capability-Value Stream Mapping

    Links capabilities to value stream stages they support.
    Enables end-to-end value flow analysis and optimization.
    """

    __tablename__ = "capability_value_stream_mapping"

    id = Column(db.Integer, primary_key=True)

    # Link entities
    capability_id = Column(db.Integer, db.ForeignKey("unified_capabilities.id"), nullable=False)
    value_stream_id = Column(db.Integer, db.ForeignKey("value_streams.id"), nullable=False)
    value_stream_stage_id = Column(
        db.Integer, db.ForeignKey("unified_value_stream_stages.id"), nullable=False
    )

    # Relationship characteristics
    support_type = Column(db.String(20), default="primary")  # primary, secondary, supporting
    support_level = Column(db.Integer, default=3)  # 1 - 5 strength scale
    impact_level = Column(db.String(20), default="medium")  # critical, high, medium, low

    # Contribution assessment
    capability_contribution = Column(db.Integer, default=50)  # 0 - 100% contribution
    stage_criticality = Column(db.String(20), default="medium")  # critical, high, medium, low

    # Performance impact
    cycle_time_impact = Column(db.Integer)  # Percentage impact on cycle time
    quality_impact = Column(db.Integer)  # Percentage impact on quality
    cost_impact = Column(db.Integer)  # Percentage impact on cost

    # Assessment metadata
    last_assessed = Column(db.DateTime, default=datetime.utcnow)
    assessor = Column(db.String(100))
    assessment_notes = Column(db.Text)

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (commented out to avoid conflicts)
    # capability = relationship('UnifiedCapability')
    # value_stream = relationship('ValueStream')
    # value_stream_stage = relationship('ValueStreamStage')

    def __repr__(self):
        return f"<CapabilityValueStreamMapping cap={self.capability_id} -> vs={self.value_stream_stage_id}>"


class ValueStream(db.Model):
    """
    Value Stream Model

    End-to-end value flows that deliver products/services to customers.
    Manufacturing-focused with standard industry value streams.
    """

    __tablename__ = "value_streams"

    id = Column(db.Integer, primary_key=True)

    # Value stream identity
    name = Column(db.String(256), nullable=False, index=True)
    description = Column(db.Text)
    code = Column(db.String(50), unique=True, index=True)  # e.g., OTC, C2M, R2R

    # Value stream classification
    value_stream_type = Column(db.String(50))  # customer_facing, internal, supporting
    industry_domain = Column(db.String(50))  # Manufacturing, Healthcare, Finance

    # Strategic context
    strategic_importance = Column(db.String(20))  # critical, high, medium, low
    business_owner = Column(db.String(100))

    # Performance metrics
    target_cycle_time = Column(db.Integer)  # Target in days
    current_cycle_time = Column(db.Integer)  # Current in days
    quality_target = Column(db.Float)  # Target quality percentage
    current_quality = Column(db.Float)  # Current quality percentage

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stages = relationship("ValueStreamStage", backref="value_stream", lazy="dynamic")

    def __repr__(self):
        return f"<ValueStream {self.name}>"


class ValueStreamStage(db.Model):
    """
    Value Stream Stage Model

    Individual stages within value streams.
    Maps to specific capabilities for execution.
    """

    __tablename__ = "unified_value_stream_stages"

    id = Column(db.Integer, primary_key=True)

    # Stage identity
    name = Column(db.String(256), nullable=False, index=True)
    description = Column(db.Text)

    # Value stream context
    value_stream_id = Column(db.Integer, db.ForeignKey("value_streams.id"), nullable=False)
    stage_order = Column(db.Integer, nullable=False)  # Sequence in value stream

    # Stage characteristics
    stage_type = Column(db.String(50))  # strategic, operational, supporting
    customer_facing = Column(db.Boolean, default=False)

    # Performance metrics
    target_duration = Column(db.Integer)  # Target in hours/days
    current_duration = Column(db.Integer)  # Current in hours/days
    quality_gate = Column(db.Boolean, default=False)

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ValueStreamStage {self.name}>"


class UnifiedCapabilityProcessMapping(db.Model):
    """
    Capability-Process Mapping (PCF/APQC Integration)

    Links strategic capabilities to operational processes.
    Enables traceability from strategy to execution.
    """

    __tablename__ = "unified_capability_process_mapping"

    id = Column(db.Integer, primary_key=True)

    # Link entities
    capability_id = Column(db.Integer, db.ForeignKey("unified_capabilities.id"), nullable=False)
    apqc_process_id = Column(db.Integer, db.ForeignKey("apqc_process.id"), nullable=False)

    # Relationship type and strength
    relationship_type = Column(
        db.String(20), default="enables"
    )  # enables, supports, governs, measures
    relationship_strength = Column(db.Integer, default=3)  # 1 - 5 strength scale
    impact_level = Column(db.String(20), default="medium")  # critical, high, medium, low

    # Process contribution to capability
    process_contribution = Column(db.Integer, default=50)  # 0 - 100% contribution
    process_criticality = Column(db.String(20), default="medium")  # critical, high, medium, low

    # Assessment metadata
    last_assessed = Column(db.DateTime, default=datetime.utcnow)
    assessor = Column(db.String(100))
    assessment_notes = Column(db.Text)

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (commented out to avoid conflicts)
    # capability = relationship('UnifiedCapability', back_populates='process_mappings')
    # apqc_process = relationship('APQCProcess')

    def __repr__(self):
        return f"<CapabilityProcessMapping cap={self.capability_id} -> proc={self.apqc_process_id}>"


class CapabilityTechnologyMapping(db.Model):
    """
    Capability-Technology Mapping

    Links capabilities to enabling technology capabilities.
    Completes the three-layer architecture (Business → Application → Technology).
    """

    __tablename__ = "unified_capability_technology_mapping"

    id = Column(db.Integer, primary_key=True)

    # Link entities
    capability_id = Column(db.Integer, db.ForeignKey("unified_capabilities.id"), nullable=False)
    technology_capability_id = Column(
        db.Integer, db.ForeignKey("technology_capabilities.id"), nullable=False
    )

    # Implementation details
    implementation_complexity = Column(db.String(20))  # low, medium, high
    integration_effort_person_days = Column(db.Integer)
    technical_risk = Column(db.String(20))  # low, medium, high
    dependency_strength = Column(db.String(20))  # critical, important, optional

    # Technology characteristics
    technology_maturity = Column(db.Integer, default=1)  # 1 - 5
    scalability_rating = Column(db.String(20))  # poor, fair, good, excellent
    performance_rating = Column(db.String(20))  # poor, fair, good, excellent

    # Operational aspects
    maintenance_complexity = Column(db.String(20))  # low, medium, high
    monitoring_requirements = Column(db.Text)  # JSON array
    security_requirements = Column(db.Text)  # JSON array

    # Cost and value
    implementation_cost = Column(db.Float)
    annual_operational_cost = Column(db.Float)
    business_value_contribution = Column(db.Integer)  # 1 - 10

    # Assessment metadata
    last_assessed = Column(db.DateTime, default=datetime.utcnow)
    assessor = Column(db.String(100))
    assessment_notes = Column(db.Text)

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (commented out to avoid conflicts)
    # capability = relationship('UnifiedCapability')
    # technology_capability = relationship('TechnologyCapability')

    def __repr__(self):
        return f"<CapabilityTechnologyMapping cap={self.capability_id} -> tech={self.technology_capability_id}>"


class TechnologyCapability(db.Model):
    """
    Technology Capability Model

    Foundational technology capabilities that enable business capabilities.
    Third layer in the three-layer architecture.
    """

    __tablename__ = "technology_capabilities"

    id = Column(db.Integer, primary_key=True)

    # Technology capability identity
    name = Column(db.String(256), nullable=False, index=True)
    description = Column(db.Text)
    code = Column(db.String(50), unique=True, index=True)  # e.g., TECH-DB-REL, TECH-INT-API

    # Technology classification
    technology_domain = Column(db.String(50))  # infrastructure, platform, application, data
    technology_category = Column(db.String(50))  # database, integration, security, cloud
    technology_type = Column(db.String(30))  # foundational, enabling, differentiating

    # Technology characteristics
    technology_stack = Column(db.Text)  # JSON array of technologies
    standards_compliance = Column(db.Text)  # JSON array of standards
    vendor_lock_in_risk = Column(db.String(20))  # low, medium, high

    # Maturity and performance
    technology_maturity = Column(db.Integer, default=1)  # 1 - 5
    performance_tier = Column(db.String(20))  # basic, standard, premium, enterprise
    scalability_limit = Column(db.Text)  # Description of scalability limits

    # Operational aspects
    maintenance_complexity = Column(db.String(20))  # low, medium, high
    monitoring_capability = Column(db.String(20))  # basic, standard, advanced
    disaster_recovery = Column(db.String(20))  # none, basic, comprehensive

    # Security and compliance
    security_level = Column(db.String(20))  # basic, standard, high, critical
    compliance_certifications = Column(db.Text)  # JSON array of certifications

    # Financial context
    total_cost_of_ownership = Column(db.Float)
    licensing_model = Column(db.String(50))  # open_source, commercial, saas, hybrid

    # Ownership
    technology_owner = Column(db.String(100))
    vendor = Column(db.String(100))

    # Timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (commented out to avoid conflicts)
    # capability_mappings = relationship('CapabilityTechnologyMapping')

    def __repr__(self):
        return f"<TechnologyCapability {self.name}>"


# ---------------------------------------------------------------------------
# Canonical re-exports — import all core capability classes from this module.
# NOTE: capabilities.py (COBIT/ITIL/ArchiMate framework models) already
# imports CapabilityTechnologyMapping from here, so those models cannot be
# re-exported from this file without creating a circular import.
# ---------------------------------------------------------------------------
from .business_capabilities import ApplicationCapabilityCoverage  # noqa: E402 # dead-code-ok
from .business_capabilities import BusinessCapability  # noqa: E402 # dead-code-ok
from .business_capabilities import BusinessFunction  # noqa: E402 # dead-code-ok
from .business_capabilities import Capability  # noqa: E402 # dead-code-ok
from .business_capabilities import FunctionalRequirement  # noqa: E402 # dead-code-ok
from .business_capabilities import NonFunctionalRequirement  # noqa: E402 # dead-code-ok
from .capability_models import CapabilityDependency  # noqa: E402 # dead-code-ok
from .capability_models import CapabilityMaturityAssessment  # noqa: E402 # dead-code-ok
from .capability_models import CapabilityRoadmap  # noqa: E402 # dead-code-ok
from .capability_models import TechnologyCapabilityMapping  # noqa: E402 # dead-code-ok
