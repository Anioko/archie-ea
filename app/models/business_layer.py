"""
ArchiMate 3.2 Business Layer Domain Models

Comprehensive domain models for Business Layer elements with rich business-specific
attributes that complement the generic ArchiMate metamodel.

Design Pattern:
- Each domain model has archimate_element_id foreign key linking to ArchiMateElement
- Domain models contain business-specific attributes (100+ fields)
- ArchiMateElement provides metamodel compliance and relationship tracking
- Auto-creates ArchiMateElement on insert via SQLAlchemy event listeners

Models:
- BusinessActor: Organizational entities (departments, teams, external partners)
- BusinessRole: Responsibilities and positions assigned to actors
- BusinessService: Services offered to customers/stakeholders with ITIL integration
- BusinessObject: Information/data concepts with GDPR and data governance
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal  # dead-code-ok

from sqlalchemy import CheckConstraint, event
from sqlalchemy.orm import relationship, validates

from app.models.mixins import TenantMixin

from .. import db

logger = logging.getLogger(__name__)

# ============================================================================
# BusinessActor Domain Model
# ============================================================================


class BusinessActor(TenantMixin, db.Model):
    # ========================================================================
    # VALIDATION RULES
    # ========================================================================

    __table_args__ = (
        CheckConstraint("headcount IS NULL OR headcount >= 0", name="check_headcount_positive"),
        CheckConstraint(
            "annual_salary_budget IS NULL OR annual_salary_budget >= 0",
            name="check_salary_budget_positive",
        ),
    )

    @validates("actor_type")
    def validate_actor_type(self, key, value):
        """Validate actor_type"""
        valid_types = [
            "Department",
            "Team",
            "Business Unit",
            "External Partner",
            "Individual",
            "Contractor",
        ]
        if value and value not in valid_types:
            raise ValueError(f"Invalid actor_type: {value}. Must be one of {valid_types}")
        return value

    """
    ArchiMate 3.2 Business Actor - Organizational entity capable of performing behavior

    Represents departments, teams, business units, external partners, individuals.
    Extends ArchiMate with Example Corp UK organizational attributes.

    Examples:
    - Manufacturing Quality Department (45 people, Bristol plant)
    - Procurement Team (12 people, Head Office)
    - External Partner: Glass Coating Supplier
    - Individual: Chief Architect

    Usage:
        actor = BusinessActor(
            name="Manufacturing Quality Department",
            actor_type="Department",
            location="Example Corp Bristol Plant",
            headcount=45,
            annual_salary_budget=2250000,
            cost_center="MFG-QA - 001"
        )
        db.session.add(actor)
        db.session.commit()
        # Automatically creates linked ArchiMateElement
    """
    __tablename__ = "business_actors"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Link to ArchiMate metamodel representation
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Actor Classification
    actor_type = db.Column(
        db.String(50)
    )  # Department, Team, Individual, External Partner, Business Unit, Division
    organizational_level = db.Column(
        db.String(50)
    )  # Executive, Senior Management, Middle Management, Operational, External

    # Organizational Structure
    parent_actor_id = db.Column(db.Integer, db.ForeignKey("business_actors.id"), nullable=True)
    reporting_to_id = db.Column(db.Integer, db.ForeignKey("business_actors.id"), nullable=True)
    department = db.Column(db.String(100))
    division = db.Column(db.String(100))
    business_unit = db.Column(db.String(100))

    # Location & Geography
    location = db.Column(db.String(200))  # Primary location
    country = db.Column(db.String(100))
    region = db.Column(db.String(100))  # UK, EMEA, Global
    site_code = db.Column(db.String(50))

    # People & Capacity
    headcount = db.Column(db.Integer, default=0)  # Number of people
    fte_count = db.Column(db.Numeric(10, 2))  # Full-time equivalents
    contractor_count = db.Column(db.Integer, default=0)
    vacancy_count = db.Column(db.Integer, default=0)

    # Financial
    annual_salary_budget = db.Column(db.Numeric(15, 2))  # Total salary budget
    annual_operating_budget = db.Column(db.Numeric(15, 2))  # Operating expenses
    cost_center = db.Column(db.String(50), index=True)
    budget_owner = db.Column(db.String(100))

    # Contact & Leadership
    primary_contact_name = db.Column(db.String(100))
    primary_contact_email = db.Column(db.String(255))
    primary_contact_phone = db.Column(db.String(50))
    manager_name = db.Column(db.String(100))
    manager_email = db.Column(db.String(255))

    # Strategic Alignment
    strategic_importance = db.Column(db.String(20))  # Critical, High, Medium, Low
    business_value_contribution = db.Column(
        db.String(50)
    )  # Revenue Generation, Cost Reduction, Risk Management, Innovation

    # Capabilities & Skills
    core_competencies = db.Column(db.Text)  # JSON array of competencies
    skill_gaps = db.Column(db.Text)  # JSON array of missing skills
    training_budget_annual = db.Column(db.Numeric(12, 2))

    # Operational Status
    operational_status = db.Column(
        db.String(20), default="active"
    )  # active, inactive, planned, transitioning, dissolved
    established_date = db.Column(db.Date)
    dissolution_date = db.Column(db.Date, nullable=True)

    # External Actor Attributes (for partners, suppliers)
    is_external = db.Column(db.Boolean, default=False)
    external_organization_name = db.Column(db.String(255))
    contract_start_date = db.Column(db.Date, nullable=True)
    contract_end_date = db.Column(db.Date, nullable=True)

    # Governance & Compliance
    data_protection_officer = db.Column(db.String(100))  # If responsible for data
    security_clearance_level = db.Column(db.String(50))
    compliance_certifications = db.Column(db.Text)  # JSON array: ["ISO 9001", "ISO 27001"]

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    parent_actor = db.relationship(
        "BusinessActor",
        remote_side="BusinessActor.id",
        foreign_keys=[parent_actor_id],
        backref="sub_actors",
    )
    reporting_to = db.relationship(
        "BusinessActor",
        remote_side="BusinessActor.id",
        foreign_keys=[reporting_to_id],
        backref="direct_reports",
    )

    # Application relationships (via junction table)
    applications = db.relationship(
        "ApplicationComponent",
        secondary="application_business_actor_mapping",
        back_populates="business_actors",
    )

    # RACI relationships
    process_raci_assignments = db.relationship(
        "ProcessActorRaci", back_populates="actor", lazy="dynamic"
    )
    capability_raci_assignments = db.relationship(
        "CapabilityActorRaci", back_populates="actor", lazy="dynamic"
    )

    # Role assignment relationships - Commented out as actor_role_assignment is a table, not a model
    # role_assignments = db.relationship('BusinessRole',
    #                                 secondary='actor_role_assignment',
    #                                 backref='actors',
    #                                 lazy='dynamic')

    # Service ownership relationships
    owned_services = db.relationship(
        "BusinessService", backref="service_owner_actor", lazy="dynamic", overlaps="service_owner"
    )

    # Data ownership relationships
    owned_data_objects = db.relationship(
        "BusinessObject", backref="data_owner_actor", lazy="dynamic", overlaps="data_owner"
    )

    # Helper Methods
    @property
    def total_headcount(self):
        """Total people including contractors"""
        return (self.headcount or 0) + (self.contractor_count or 0)

    @property
    def cost_per_person(self):
        """Average cost per person"""
        if self.headcount and self.headcount > 0 and self.annual_salary_budget:
            return float(self.annual_salary_budget) / self.headcount
        return 0

    @property
    def vacancy_rate(self):
        """Percentage of vacant positions"""
        total_positions = (self.headcount or 0) + (self.vacancy_count or 0)
        if total_positions > 0:
            return (self.vacancy_count or 0) / total_positions * 100
        return 0

    def get_organizational_hierarchy(self):
        """Get full organizational path from root to this actor"""
        hierarchy = [self]
        current = self.parent_actor
        while current:
            hierarchy.insert(0, current)
            current = current.parent_actor
        return hierarchy

    def get_all_subordinates(self):
        """Recursively get all subordinates"""
        subordinates = list(self.sub_actors)
        for sub in self.sub_actors:
            subordinates.extend(sub.get_all_subordinates())
        return subordinates

    def calculate_span_of_control(self):
        """Number of direct reports"""
        return len(self.direct_reports)

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "actor_type": self.actor_type,
            "location": self.location,
            "headcount": self.headcount,
            "cost_center": self.cost_center,
            "operational_status": self.operational_status,
        }

    def __repr__(self):
        return f"<BusinessActor {self.name} ({self.actor_type})>"


# ============================================================================
# BusinessRole Domain Model
# ============================================================================


class BusinessRole(db.Model):
    """
    ArchiMate 3.2 Business Role - Responsibility assigned to one or more actors

    Represents positions, responsibilities, authorization levels, competencies.
    Extends ArchiMate with Example Corp UK role management attributes.

    Examples:
    - Quality Manager (requires ISO 9001 certification)
    - Enterprise Architect (TOGAF certified, 10+ years experience)
    - Production Line Supervisor (6 Sigma Green Belt)
    - Data Steward (GDPR trained)

    Usage:
        role = BusinessRole(
            name="Quality Manager",
            role_type="Management",
            required_certifications=["ISO 9001 Lead Auditor", "Six Sigma Black Belt"],
            experience_years_required=10,
            authorization_level="Manager"
        )
    """

    __tablename__ = "business_roles"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Link to ArchiMate metamodel
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Application association
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True, index=True
    )

    # Role Classification
    role_type = db.Column(
        db.String(50)
    )  # Executive, Management, Specialist, Operational, Administrative, Technical
    job_family = db.Column(db.String(100))  # Engineering, Finance, IT, Manufacturing, Sales, HR
    job_level = db.Column(db.String(50))  # Senior, Mid-level, Junior, Entry-level

    # Responsibilities
    primary_responsibilities = db.Column(db.Text)  # JSON array of key responsibilities
    secondary_responsibilities = db.Column(db.Text)  # JSON array
    decision_authority = db.Column(db.Text)  # What decisions can this role make?

    # RACI Framework
    # Note: Actual RACI assignments are in junction tables (role-to-process, role-to-capability)
    default_raci_pattern = db.Column(db.String(20))  # Typical RACI: R, A, C, I

    # Skills & Competencies
    required_skills = db.Column(db.Text)  # JSON array: ["Data Analysis", "Python", "SQL"]
    required_certifications = db.Column(db.Text)  # JSON array: ["TOGAF", "PMP", "ISO 9001"]
    preferred_skills = db.Column(db.Text)  # JSON array
    experience_years_required = db.Column(db.Integer)
    education_level_required = db.Column(
        db.String(50)
    )  # Bachelor's, Master's, PhD, Professional Certification

    # Authorization & Access
    authorization_level = db.Column(
        db.String(50)
    )  # Executive, Manager, Supervisor, Team Member, Viewer
    system_access_requirements = db.Column(
        db.Text
    )  # JSON array of systems this role needs access to
    data_access_level = db.Column(db.String(50))  # Full, Restricted, Read-Only, None
    security_clearance_required = db.Column(db.String(50))

    # Workload & Capacity
    typical_fte_allocation = db.Column(db.Numeric(4, 2), default=1.0)  # 1.0 = full-time
    typical_workload_hours_week = db.Column(db.Integer, default=40)
    overtime_eligible = db.Column(db.Boolean, default=False)

    # Financial
    salary_grade = db.Column(db.String(20))
    salary_range_min = db.Column(db.Numeric(12, 2))
    salary_range_max = db.Column(db.Numeric(12, 2))

    # Organizational Context
    typical_reporting_to_role_id = db.Column(
        db.Integer, db.ForeignKey("business_roles.id"), nullable=True
    )
    typical_department = db.Column(db.String(100))
    remote_work_eligible = db.Column(db.Boolean, default=False)
    travel_requirement_percentage = db.Column(db.Integer, default=0)  # 0 - 100%

    # Role Status
    operational_status = db.Column(
        db.String(20), default="active"
    )  # active, inactive, deprecated, planned
    created_date = db.Column(db.Date, default=date.today)
    deprecated_date = db.Column(db.Date, nullable=True)
    replacement_role_id = db.Column(db.Integer, db.ForeignKey("business_roles.id"), nullable=True)

    # Demand & Supply
    current_filled_positions = db.Column(db.Integer, default=0)
    current_open_positions = db.Column(db.Integer, default=0)
    forecasted_demand = db.Column(db.Integer)  # Expected future need

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    typical_reporting_to = db.relationship(
        "BusinessRole",
        remote_side="BusinessRole.id",
        foreign_keys=[typical_reporting_to_role_id],
        backref="typical_subordinates",
    )
    replacement_role = db.relationship(
        "BusinessRole", remote_side="BusinessRole.id", foreign_keys=[replacement_role_id]
    )

    # Actor assignment relationships
    actor_assignments = db.relationship(
        "BusinessActor", secondary="actor_role_assignment", backref="assigned_roles", lazy="dynamic"
    )

    # Process RACI relationships
    process_raci_assignments = db.relationship(
        "ProcessRoleRaci", back_populates="role", lazy="dynamic"
    )

    # Helper Methods
    @property
    def total_positions(self):
        """Total positions (filled + open)"""
        return (self.current_filled_positions or 0) + (self.current_open_positions or 0)

    @property
    def fill_rate(self):
        """Percentage of positions filled"""
        total = self.total_positions
        if total > 0:
            return (self.current_filled_positions or 0) / total * 100
        return 0

    @property
    def midpoint_salary(self):
        """Midpoint of salary range"""
        if self.salary_range_min and self.salary_range_max:
            return (float(self.salary_range_min) + float(self.salary_range_max)) / 2
        return None

    def get_required_certifications_list(self):
        """Parse required certifications from JSON"""
        if self.required_certifications:
            try:
                return json.loads(self.required_certifications)
            except (ValueError, KeyError, TypeError):
                return []
        return []

    def get_required_skills_list(self):
        """Parse required skills from JSON"""
        if self.required_skills:
            try:
                return json.loads(self.required_skills)
            except (ValueError, KeyError, TypeError):
                return []
        return []

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "role_type": self.role_type,
            "authorization_level": self.authorization_level,
            "experience_required": self.experience_years_required,
            "operational_status": self.operational_status,
        }

    def __repr__(self):
        return f"<BusinessRole {self.name} ({self.role_type})>"


# ============================================================================
# BusinessService Domain Model
# ============================================================================


class BusinessService(TenantMixin, db.Model):
    """
    ArchiMate 3.2 Business Service - Service offered by business to its environment

    Represents customer-facing and internal services with ITIL integration.
    Extends ArchiMate with Example Corp UK service catalog attributes.

    Examples:
    - Order Management Service (customer-facing, 99.9% SLA)
    - Quality Inspection Service (internal, 24hr turnaround)
    - Technical Support Service (customer-facing, 4hr response)
    - Manufacturing Scheduling Service (internal)

    Usage:
        service = BusinessService(
            name="Order Management Service",
            service_type="Customer-facing",
            itil_practice_id="SVOP",
            sla_availability_target=99.9,
            sla_response_time_hours=2,
            annual_cost=450000
        )
    """

    __tablename__ = "business_services"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Link to ArchiMate metamodel
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Application association
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True, index=True
    )

    # Service Classification
    service_type = db.Column(db.String(50))  # Customer-facing, Internal, Supporting, Management
    service_category = db.Column(db.String(100))  # Manufacturing, Sales, Finance, IT, HR, Quality
    business_domain = db.Column(db.String(100))  # Order-to-Cash, Procure-to-Pay, etc.

    # ITIL 4 Integration
    itil_practice_id = db.Column(db.String(20), index=True)  # Link to ITILPractice
    itil_service_type = db.Column(
        db.String(50)
    )  # Business Service, Technical Service, Supporting Service
    service_value_chain_activity = db.Column(
        db.String(50)
    )  # Plan, Engage, Design, Obtain, Deliver, Support

    # Service Level Agreement (SLA)
    sla_availability_target = db.Column(db.Numeric(5, 2))  # e.g., 99.9%
    sla_response_time_hours = db.Column(db.Integer)  # Response time commitment
    sla_resolution_time_hours = db.Column(db.Integer)  # Resolution time commitment
    sla_uptime_hours = db.Column(db.String(50))  # "24/7", "Business Hours 8am - 6pm", "24/5"
    sla_support_level = db.Column(db.String(50))  # Premium, Standard, Basic

    # Service Ownership
    service_owner_id = db.Column(db.Integer, db.ForeignKey("business_actors.id"), nullable=True)
    service_manager = db.Column(db.String(100))
    support_team = db.Column(db.String(100))
    escalation_contact = db.Column(db.String(100))

    # Financial
    annual_cost = db.Column(db.Numeric(15, 2))  # Total cost to provide service
    cost_per_transaction = db.Column(db.Numeric(10, 4))
    pricing_model = db.Column(db.String(50))  # Free, Subscription, Per-transaction, Tiered
    revenue_generating = db.Column(db.Boolean, default=False)
    annual_revenue = db.Column(db.Numeric(15, 2), nullable=True)

    # Business Value
    business_criticality = db.Column(db.String(20))  # Critical, High, Medium, Low
    strategic_importance = db.Column(db.String(20))  # Strategic, Core, Supporting
    customer_count = db.Column(db.Integer)  # Number of customers/users
    transaction_volume_annual = db.Column(db.BigInteger)  # Annual transactions

    # Service Delivery
    delivery_channel = db.Column(db.String(100))  # Online Portal, Phone, Email, Face-to-face, API
    service_hours = db.Column(db.String(100))  # "24/7", "Mon-Fri 9am - 5pm"
    languages_supported = db.Column(db.Text)  # JSON array: ["English", "French", "German"]
    geographic_coverage = db.Column(db.String(100))  # UK, EMEA, Global

    # Quality & Performance
    current_availability_percentage = db.Column(db.Numeric(5, 2))  # Actual measured availability
    average_response_time_hours = db.Column(db.Numeric(8, 2))  # Actual measured response time
    customer_satisfaction_score = db.Column(db.Numeric(4, 2))  # e.g., 4.5 out of 5
    nps_score = db.Column(db.Integer)  # Net Promoter Score: -100 to +100

    # Operational Status
    operational_status = db.Column(
        db.String(20), default="active"
    )  # active, degraded, outage, planned, deprecated, retired
    go_live_date = db.Column(db.Date)
    deprecation_date = db.Column(db.Date, nullable=True)
    retirement_date = db.Column(db.Date, nullable=True)
    replacement_service_id = db.Column(
        db.Integer, db.ForeignKey("business_services.id"), nullable=True
    )

    # Service Catalog
    catalog_visible = db.Column(db.Boolean, default=True)  # Show in service catalog?
    request_process = db.Column(db.Text)  # How to request this service
    fulfillment_process = db.Column(db.Text)  # How service is fulfilled
    terms_and_conditions = db.Column(db.Text)

    # Compliance & Governance
    regulatory_requirements = db.Column(db.Text)  # JSON array of regulations
    data_classification = db.Column(db.String(50))  # Public, Internal, Confidential, Restricted
    gdpr_scope = db.Column(db.Boolean, default=False)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    application_component = db.relationship(
        "ApplicationComponent", foreign_keys=[application_component_id]
    )
    service_owner = db.relationship(
        "BusinessActor",
        foreign_keys=[service_owner_id],
        overlaps="service_owner_actor,owned_services",
    )
    replacement_service = db.relationship(
        "BusinessService", remote_side="BusinessService.id", foreign_keys=[replacement_service_id]
    )

    # Service dependency relationships (handled through ServiceDependency model)
    # These relationships are defined in the ServiceDependency model itself

    # Service realization relationships
    realizing_processes = db.relationship(
        "ServiceRealization", back_populates="service", lazy="dynamic"
    )

    # Helper Methods
    @property
    def sla_compliance_percentage(self):
        """Calculate SLA compliance (actual vs. target)"""
        if self.sla_availability_target and self.current_availability_percentage:
            return min(
                100,
                (float(self.current_availability_percentage) / float(self.sla_availability_target))
                * 100,
            )
        return None

    @property
    def is_sla_compliant(self):
        """Check if service meets SLA targets"""
        if self.sla_availability_target and self.current_availability_percentage:
            return self.current_availability_percentage >= self.sla_availability_target
        return None

    @property
    def cost_per_customer(self):
        """Average cost per customer"""
        if self.customer_count and self.customer_count > 0 and self.annual_cost:
            return float(self.annual_cost) / self.customer_count
        return 0

    @property
    def profit_margin(self):
        """Profit margin if revenue-generating"""
        if self.revenue_generating and self.annual_revenue and self.annual_cost:
            profit = float(self.annual_revenue) - float(self.annual_cost)
            return (profit / float(self.annual_revenue)) * 100
        return None

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "service_type": self.service_type,
            "business_criticality": self.business_criticality,
            "sla_availability": float(self.sla_availability_target)
            if self.sla_availability_target
            else None,
            "operational_status": self.operational_status,
        }

    def __repr__(self):
        return f"<BusinessService {self.name} ({self.service_type})>"


# ============================================================================
# BusinessObject Domain Model
# ============================================================================


class BusinessObject(TenantMixin, db.Model):
    """
    ArchiMate 3.2 Business Object - Concept used within business domain

    Represents information/data entities with GDPR and data governance.
    Extends ArchiMate with Example Corp UK data management attributes.

    Examples:
    - Customer Order (PII: name, email; GDPR scope; master: ERP)
    - Product Specification (Technical data; master: PLM)
    - Quality Report (Confidential; 7 year retention)
    - Manufacturing Schedule (Internal; real-time)

    Usage:
        obj = BusinessObject(
            name="Customer Order",
            data_classification="Confidential",
            contains_pii=True,
            pii_fields=["customer_name", "email", "phone", "address"],
            gdpr_scope=True,
            retention_period_days=2555  # 7 years
        )
    """

    __tablename__ = "business_objects"

    id = db.Column(db.Integer, primary_key=True)

    # Core Identity
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Link to ArchiMate metamodel
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True, index=True
    )

    # Application association
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=True, index=True
    )

    # Data Classification
    data_classification = db.Column(
        db.String(50), index=True
    )  # Public, Internal, Confidential, Restricted, Top Secret
    business_domain = db.Column(
        db.String(100)
    )  # Customer, Product, Order, Financial, HR, Manufacturing
    object_type = db.Column(db.String(50))  # Master Data, Transactional, Reference, Analytical

    # Personal Data & GDPR
    contains_pii = db.Column(db.Boolean, default=False, index=True)
    pii_fields = db.Column(db.Text)  # JSON array: ["name", "email", "phone", "address", "dob"]
    gdpr_scope = db.Column(db.Boolean, default=False)
    data_subject_type = db.Column(db.String(50))  # Customer, Employee, Partner, Supplier
    lawful_basis_processing = db.Column(
        db.String(100)
    )  # Consent, Contract, Legal Obligation, Legitimate Interest

    # Data Governance
    data_owner_id = db.Column(db.Integer, db.ForeignKey("business_actors.id"), nullable=True)
    data_steward = db.Column(db.String(100))
    data_custodian = db.Column(db.String(100))  # Technical owner
    data_domain_id = db.Column(db.Integer, db.ForeignKey("data_domains.id"), nullable=True)

    # Data Quality
    data_quality_score = db.Column(db.Integer)  # 0 - 100
    completeness_percentage = db.Column(db.Numeric(5, 2))  # % of fields populated
    accuracy_percentage = db.Column(db.Numeric(5, 2))  # % accurate records
    consistency_score = db.Column(db.Integer)  # 0 - 100
    timeliness_score = db.Column(db.Integer)  # 0 - 100

    # Master Data Management
    master_system_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True
    )  # ApplicationComponent that is master
    is_master_data = db.Column(db.Boolean, default=False)
    synchronization_frequency = db.Column(db.String(50))  # Real-time, Hourly, Daily, Weekly
    data_lineage = db.Column(db.Text)  # Source systems and transformations

    # Data Retention & Lifecycle
    retention_period_days = db.Column(db.Integer)  # e.g., 2555 days = 7 years
    retention_reason = db.Column(db.String(255))  # Legal requirement, Business need, Regulatory
    archival_policy = db.Column(db.Text)
    deletion_policy = db.Column(db.Text)

    # Data Volume & Performance
    estimated_record_count = db.Column(db.BigInteger)
    average_record_size_bytes = db.Column(db.Integer)
    growth_rate_percentage_annual = db.Column(db.Numeric(5, 2))

    # Data Sensitivity & Security
    encryption_required = db.Column(db.Boolean, default=False)
    encryption_at_rest = db.Column(db.Boolean, default=False)
    encryption_in_transit = db.Column(db.Boolean, default=False)
    access_control_model = db.Column(db.String(50))  # RBAC, ABAC, ACL
    audit_logging_required = db.Column(db.Boolean, default=False)

    # Business Value
    business_criticality = db.Column(db.String(20))  # Critical, High, Medium, Low
    revenue_impact = db.Column(db.String(50))  # Direct Revenue, Indirect, Compliance, Operational

    # Operational Status
    operational_status = db.Column(
        db.String(20), default="active"
    )  # active, deprecated, archived, deleted
    created_date = db.Column(db.Date, default=date.today)
    last_reviewed_date = db.Column(db.Date)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Data Governance
    access_level = db.Column(
        db.String(30), default="public"
    )  # public, internal, restricted, confidential
    access_roles = db.Column(db.JSON, nullable=True)  # List of roles with access
    last_accessed = db.Column(db.DateTime, nullable=True)  # Last access timestamp
    auto_delete_date = db.Column(db.DateTime, nullable=True)  # Automatic deletion date
    retention_reason = db.Column(db.String(255), nullable=True)  # Reason for retention

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    data_owner = db.relationship(
        "BusinessActor",
        foreign_keys=[data_owner_id],
        back_populates="owned_data_objects",
        overlaps="data_owner_actor",
    )
    master_system = db.relationship("ArchiMateElement", foreign_keys=[master_system_id])
    data_domain = db.relationship("DataDomain", foreign_keys=[data_domain_id])

    # ArchiMate 3.2 Relationships
    conceptual_models = db.relationship(
        "ConceptualDataModel",
        secondary="conceptual_model_business_objects",
        back_populates="business_objects",
    )
    data_lineage = db.relationship(
        "DataLineage",
        secondary="data_lineage_access",
        back_populates="business_objects",
        overlaps="data_lineage",
    )

    # Process CRUD relationships
    process_crud_operations = db.relationship(
        "ProcessDataCrud",
        back_populates="business_object",
        lazy="dynamic",
        overlaps="process_data_crud_operations",
    )

    # Storage relationships
    storage_locations = db.relationship(
        "DataObjectStorage",
        backref="owning_business_object",
        lazy="dynamic",
        overlaps="business_object",
    )

    # Helper Methods
    @property
    def total_data_size_gb(self):
        """Estimate total data size in GB"""
        if self.estimated_record_count and self.average_record_size_bytes:
            total_bytes = self.estimated_record_count * self.average_record_size_bytes
            return total_bytes / (1024**3)  # Convert to GB
        return 0

    @property
    def is_high_risk(self):
        """Determine if this is high-risk data"""
        return (
            self.contains_pii
            and (self.data_classification in ["Confidential", "Restricted", "Top Secret"])
            and not self.encryption_at_rest
        )

    @property
    def gdpr_compliance_risk(self):
        """Assess GDPR compliance risk level"""
        if not self.gdpr_scope:
            return "Not Applicable"

        risk_factors = 0
        if not self.data_owner_id:
            risk_factors += 1
        if not self.lawful_basis_processing:
            risk_factors += 1
        if self.contains_pii and not self.encryption_at_rest:
            risk_factors += 1
        if not self.retention_period_days:
            risk_factors += 1

        if risk_factors >= 3:
            return "HIGH"
        elif risk_factors >= 2:
            return "MEDIUM"
        elif risk_factors >= 1:
            return "LOW"
        return "COMPLIANT"

    def get_pii_fields_list(self):
        """Parse PII fields from JSON"""
        if self.pii_fields:
            try:
                return json.loads(self.pii_fields)
            except (ValueError, KeyError, TypeError):
                return []
        return []

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "data_classification": self.data_classification,
            "contains_pii": self.contains_pii,
            "data_quality_score": self.data_quality_score,
            "operational_status": self.operational_status,
        }

    def __repr__(self):
        return f"<BusinessObject {self.name} ({self.data_classification})>"


# ============================================================================
# SQLAlchemy Event Listeners - Auto-create ArchiMateElements
# ============================================================================


@event.listens_for(BusinessActor, "before_insert")
def create_actor_archimate_element(mapper, connection, target):
    """Automatically create ArchiMateElement when BusinessActor is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        # Insert ArchiMateElement using connection.execute
        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="BusinessActor",
                layer="Business",
                description=target.description or f"{target.actor_type} actor",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(BusinessRole, "before_insert")
def create_role_archimate_element(mapper, connection, target):
    """Automatically create ArchiMateElement when BusinessRole is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="BusinessRole",
                layer="Business",
                description=target.description or f"{target.role_type} role",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(BusinessService, "before_insert")
def create_service_archimate_element(mapper, connection, target):
    """Automatically create ArchiMateElement when BusinessService is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="BusinessService",
                layer="Business",
                description=target.description or f"{target.service_type} service",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


@event.listens_for(BusinessObject, "before_insert")
def create_object_archimate_element(mapper, connection, target):
    """Automatically create ArchiMateElement when BusinessObject is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="BusinessObject",
                layer="Business",
                description=target.description or f"{target.business_domain} data object",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]


# ============================================================================
# BusinessEvent Domain Model
# ============================================================================


class BusinessEvent(db.Model):
    """
    ArchiMate 3.2 Business Event - Something that happens (internally or externally)
    and influences behavior.

    Examples:
    - "Customer Request Received"
    - "Payment Deadline Expired"
    - "Regulatory Change Announced"
    """

    __tablename__ = "business_events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # ArchiMate Linkage
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Event Specifics
    event_type = db.Column(db.String(50))  # Internal, External, Time-based
    trigger_source = db.Column(db.String(100))  # Who/what triggered it
    time_sensitivity = db.Column(db.String(20))  # High, Medium, Low

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])

    def __repr__(self):
        return f"<BusinessEvent {self.name}>"


@event.listens_for(BusinessEvent, "before_insert")
def create_event_archimate_element(mapper, connection, target):
    """Automatically create ArchiMateElement when BusinessEvent is created"""
    if target.archimate_element_id is None:
        from sqlalchemy import insert

        from .archimate_core import ArchiMateElement

        result = connection.execute(
            insert(ArchiMateElement.__table__).values(
                name=target.name,
                type="BusinessEvent",
                layer="Business",
                description=target.description or f"Business Event: {target.name}",
            )
        )
        target.archimate_element_id = result.inserted_primary_key[0]
