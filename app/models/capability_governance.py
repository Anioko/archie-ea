from datetime import datetime

from .. import db
from .mixins import TenantMixin


class CapabilityGovernanceDecision(TenantMixin, db.Model):
    __tablename__ = "capability_governance_decision"

    id = db.Column(db.Integer, primary_key=True)
    adr_number = db.Column(db.String(32), nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="proposed")
    decision_date = db.Column(db.Date)
    authors = db.Column(db.Text)  # JSON list or comma-separated
    reviewers = db.Column(db.Text)  # JSON list or comma-separated
    supersedes = db.Column(db.String(64))
    superseded_by = db.Column(db.String(64))

    # Core fields
    context = db.Column(db.Text)
    decision = db.Column(db.Text)
    rationale = db.Column(db.Text)
    alternatives_considered = db.Column(db.Text)
    consequences = db.Column(db.Text)

    # Implications & dependencies
    affected_capabilities = db.Column(db.Text)  # JSON list
    impacted_applications = db.Column(db.Text)  # JSON list
    new_technology_components = db.Column(db.Text)  # JSON list
    modified_business_processes = db.Column(db.Text)  # JSON list
    data_objects = db.Column(db.Text)  # JSON list

    # Organizational impact
    teams_affected = db.Column(db.Text)
    skills_required = db.Column(db.Text)
    training_needs = db.Column(db.Text)

    # Compliance & security
    compliance_requirements = db.Column(db.Text)
    security_considerations = db.Column(db.Text)

    # Expanded ARB fields
    implementation_plan = db.Column(db.JSON)
    success_metrics = db.Column(db.JSON)
    rollback_strategy = db.Column(db.Text)
    risk_register = db.Column(db.JSON)
    cost_analysis = db.Column(db.JSON)
    monitoring_plan = db.Column(db.JSON)
    decision_matrix = db.Column(db.JSON)
    compliance_assurance = db.Column(db.JSON)
    reference_links = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "adr_number": self.adr_number,
            "title": self.title,
            "status": self.status,
            "decision_date": self.decision_date.isoformat() if self.decision_date else None,
            "authors": self.authors,
            "reviewers": self.reviewers,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "context": self.context,
            "decision": self.decision,
            "rationale": self.rationale,
            "alternatives_considered": self.alternatives_considered,
            "consequences": self.consequences,
            "implementation_plan": self.implementation_plan,
            "success_metrics": self.success_metrics,
            "rollback_strategy": self.rollback_strategy,
            "risk_register": self.risk_register,
            "cost_analysis": self.cost_analysis,
            "monitoring_plan": self.monitoring_plan,
            "decision_matrix": self.decision_matrix,
            "compliance_assurance": self.compliance_assurance,
            "reference_links": self.reference_links,
            "affected_capabilities": self.affected_capabilities,
            "impacted_applications": self.impacted_applications,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Association table to link governance decisions to business capabilities (many-to-many)
class GovernanceCapabilityLink(db.Model):
    __tablename__ = "governance_capability_links"

    decision_id = db.Column(
        db.Integer, db.ForeignKey("capability_governance_decision.id"), primary_key=True
    )
    capability_id = db.Column(db.Integer, db.ForeignKey("business_capability.id"), primary_key=True)
    relationship_type = db.Column(db.String(50))
    impact_level = db.Column(db.String(30))
    notes = db.Column(db.Text)

    decision = db.relationship("CapabilityGovernanceDecision", backref="capability_links")


# Association table to link governance decisions to systems/applications
class GovernanceSystemLink(db.Model):
    __tablename__ = "governance_system_links"

    decision_id = db.Column(
        db.Integer, db.ForeignKey("capability_governance_decision.id"), primary_key=True
    )
    application_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), primary_key=True
    )
    relationship_type = db.Column(db.String(50))
    impact_level = db.Column(db.String(30))
    notes = db.Column(db.Text)

    decision = db.relationship("CapabilityGovernanceDecision", backref="system_links")


# Governance Feature 1: Decision Authority
class DecisionAuthority(db.Model):
    """Defines who has authority to make architecture decisions"""

    __tablename__ = "decision_authority"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(100), nullable=False)
    scope = db.Column(db.String(200))  # e.g., "Enterprise", "Domain", "Project"
    authority_level = db.Column(db.String(50))  # e.g., "Approve", "Recommend", "Consult"
    decision_types = db.Column(db.JSON)  # List of decision types this role can make
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Governance Feature 2: Approval Workflow
class ApprovalWorkflow(db.Model):
    """Manages approval workflows for architecture decisions"""

    __tablename__ = "approval_workflow"

    id = db.Column(db.Integer, primary_key=True)
    decision_id = db.Column(db.Integer, db.ForeignKey("capability_governance_decision.id"))
    workflow_name = db.Column(db.String(100), nullable=False)
    current_step = db.Column(db.String(100))
    status = db.Column(db.String(50), default="pending")  # pending, approved, rejected, escalated
    steps = db.Column(db.JSON)  # Ordered list of approval steps
    approvers = db.Column(db.JSON)  # Required approvers by step
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    decision = db.relationship("CapabilityGovernanceDecision", backref="approval_workflows")


# Governance Feature 3: Exception Process
class ExceptionProcess(db.Model):
    """Handles exceptions to governance policies"""

    __tablename__ = "exception_process"

    id = db.Column(db.Integer, primary_key=True)
    policy_violated = db.Column(db.String(200), nullable=False)
    justification = db.Column(db.Text, nullable=False)
    exception_duration = db.Column(db.Integer)  # Days
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    status = db.Column(db.String(50), default="pending")  # pending, approved, rejected, expired
    risk_assessment = db.Column(db.Text)
    mitigation_plan = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime)


# Governance Feature 4: Audit Trail
class AuditTrail(db.Model):
    """Maintains audit trail for all governance activities"""

    __tablename__ = "audit_trail"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(
        db.String(100), nullable=False
    )  # e.g., "Decision", "Exception", "Approval"
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(100), nullable=False)  # e.g., "Created", "Approved", "Modified"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    details = db.Column(db.JSON)  # Additional context
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(200))


# Governance Feature 5: Policy Enforcement
class PolicyEnforcement(db.Model):
    """Defines and enforces architecture governance policies"""

    __tablename__ = "policy_enforcement"

    id = db.Column(db.Integer, primary_key=True)
    policy_name = db.Column(db.String(200), nullable=False)
    policy_category = db.Column(db.String(100))  # e.g., "Security", "Compliance", "Standards"
    description = db.Column(db.Text, nullable=False)
    enforcement_level = db.Column(db.String(50))  # mandatory, recommended, optional
    validation_rules = db.Column(db.JSON)  # Automated validation criteria
    exception_allowed = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Governance Feature 5: Governance Workflow
class GovernanceWorkflow(db.Model):
    """Manages governance workflows for capabilities"""

    __tablename__ = "governance_workflows"

    id = db.Column(db.Integer, primary_key=True)
    capability_id = db.Column(db.Integer, db.ForeignKey("unified_capabilities.id"), nullable=False)
    owner = db.Column(db.String(100))
    description = db.Column(db.Text)
    criticality = db.Column(
        db.String(50)
    )  # mission_critical, business_critical, important, nice_to_have
    status = db.Column(db.String(50), default="active")  # active, completed, cancelled
    workflow_data = db.Column(db.JSON)  # Full workflow stages and details
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    capability = db.relationship("UnifiedCapability", backref="governance_workflows")

    def __repr__(self):
        return f"<GovernanceWorkflow {self.id} for capability {self.capability_id}>"
