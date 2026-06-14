"""
Data Governance Models for ArchiMate 3.2

This module contains data governance models that enable Data Architects
to manage data catalogs, quality metrics, governance workflows, and access control.

Models:
- DataCatalog: Centralized metadata catalog
- DataQualityMetrics: Quality scores over time, quality rules
- DataGovernanceWorkflow: Approval workflows, stewardship
- DataAccessControl: Who can access what data
- DataRetentionPolicy: Retention rules, archival policies
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import event

from .. import db


class DataCatalog(db.Model):
    """
    Data Catalog model for centralized metadata management.

    Provides a centralized catalog of all data assets with metadata,
    lineage, and governance information.

    Examples:
    - "Customer Data Catalog" with all customer-related data assets
    - "Financial Data Catalog" with financial data entities and sources
    """

    __tablename__ = "data_catalogs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # ArchiMate linkage
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"), index=True)

    # Catalog characteristics
    catalog_type = db.Column(db.String(50))  # Business, Technical, Operational
    data_domain_id = db.Column(db.Integer, db.ForeignKey("data_domains.id"), index=True)

    # Catalog contents
    asset_count = db.Column(db.Integer, default=0)  # Number of data assets in catalog
    coverage_percentage = db.Column(db.Float)  # % of domain covered by catalog

    # Governance
    catalog_owner = db.Column(db.String(255))
    data_steward = db.Column(db.String(255))
    approval_status = db.Column(db.String(30), default="draft")

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    data_domain = db.relationship("DataDomain", backref="catalogs")
    created_by = db.relationship("User", backref="created_data_catalogs")

    def __repr__(self):
        return f"<DataCatalog {self.name} ({self.catalog_type})>"


class DataQualityMetrics(db.Model):
    """
    Data Quality Metrics model for tracking quality over time.

    Tracks data quality scores, rules, and metrics for data entities.

    Examples:
    - "Customer Data Quality" metrics with completeness, accuracy scores
    - "Product Data Quality" metrics with consistency, timeliness scores
    """

    __tablename__ = "data_quality_metrics"

    id = db.Column(db.Integer, primary_key=True)

    # Data entity relationship
    data_entity_id = db.Column(
        db.Integer, db.ForeignKey("data_entities.id"), nullable=False, index=True
    )

    # Quality metrics (0 - 100 scores)
    overall_quality_score = db.Column(db.Integer)  # 0 - 100
    completeness_score = db.Column(db.Integer)  # 0 - 100
    accuracy_score = db.Column(db.Integer)  # 0 - 100
    consistency_score = db.Column(db.Integer)  # 0 - 100
    timeliness_score = db.Column(db.Integer)  # 0 - 100
    validity_score = db.Column(db.Integer)  # 0 - 100
    uniqueness_score = db.Column(db.Integer)  # 0 - 100

    # Quality rules
    quality_rules = db.Column(db.Text)  # JSON: List of quality rules applied

    # Metrics timestamp
    measured_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Quality issues
    issue_count = db.Column(db.Integer, default=0)
    critical_issues = db.Column(db.Integer, default=0)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    data_entity = db.relationship("DataEntity", backref="quality_metrics")
    created_by = db.relationship("User", backref="created_quality_metrics")

    def __repr__(self):
        return f"<DataQualityMetrics {self.data_entity_id} (Score: {self.overall_quality_score})>"


class DataGovernanceWorkflow(db.Model):
    """
    Data Governance Workflow model for approval processes.

    Manages data governance workflows including approvals, stewardship,
    and governance processes.

    Examples:
    - "Data Access Request Workflow" for requesting data access
    - "Data Quality Review Workflow" for quality assessments
    """

    __tablename__ = "data_governance_workflows"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Workflow characteristics
    workflow_type = db.Column(
        db.String(50)
    )  # Access Request, Quality Review, Retention Approval, Classification
    workflow_status = db.Column(
        db.String(30), default="pending"
    )  # pending, in_progress, approved, rejected

    # Workflow steps
    current_step = db.Column(db.String(100))
    workflow_steps = db.Column(db.Text)  # JSON: List of workflow steps

    # Participants
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    data_steward_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Related data
    data_entity_id = db.Column(db.Integer, db.ForeignKey("data_entities.id"), index=True)
    data_catalog_id = db.Column(db.Integer, db.ForeignKey("data_catalogs.id"), index=True)

    # Workflow dates
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    requester = db.relationship("User", foreign_keys=[requester_id], backref="requested_workflows")
    approver = db.relationship("User", foreign_keys=[approver_id], backref="approved_workflows")
    data_steward = db.relationship(
        "User", foreign_keys=[data_steward_id], backref="stewarded_workflows"
    )
    data_entity = db.relationship("DataEntity", backref="governance_workflows")
    data_catalog = db.relationship("DataCatalog", backref="workflows")

    def __repr__(self):
        return f"<DataGovernanceWorkflow {self.name} ({self.workflow_status})>"


class DataAccessControl(db.Model):
    """
    Data Access Control model for managing data access permissions.

    Tracks who can access what data and under what conditions.

    Examples:
    - "Customer PII Access" control for GDPR compliance
    - "Financial Data Access" control for SOX compliance
    """

    __tablename__ = "data_access_controls"

    id = db.Column(db.Integer, primary_key=True)

    # Access relationship
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    data_entity_id = db.Column(
        db.Integer, db.ForeignKey("data_entities.id"), nullable=False, index=True
    )

    # Access permissions
    access_type = db.Column(db.String(50), nullable=False)  # read, write, delete, admin
    access_level = db.Column(db.String(50))  # full, partial, masked, aggregated

    # Access conditions
    conditions = db.Column(
        db.Text
    )  # JSON: Conditions for access (time-based, location-based, etc.)
    expiration_date = db.Column(db.Date)

    # Compliance
    compliance_requirements = db.Column(db.Text)  # JSON: GDPR, SOX, HIPAA requirements
    audit_required = db.Column(db.Boolean, default=True)

    # Access metadata
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    granted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    last_accessed_at = db.Column(db.DateTime)
    access_count = db.Column(db.Integer, default=0)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship("User", foreign_keys=[user_id], backref="data_access_permissions")
    data_entity = db.relationship("DataEntity", backref="access_controls")
    granted_by = db.relationship(
        "User", foreign_keys=[granted_by_id], backref="granted_access_permissions"
    )

    def __repr__(self):
        return f"<DataAccessControl User:{self.user_id} -> Entity:{self.data_entity_id} ({self.access_type})>"


class DataRetentionPolicy(db.Model):
    """
    Data Retention Policy model for retention and archival rules.

    Defines retention periods, archival policies, and deletion rules for data.

    Examples:
    - "Customer Data Retention" policy: 7 years, then archive
    - "Transaction Data Retention" policy: 3 years, then delete
    """

    __tablename__ = "data_retention_policies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Policy relationship
    data_entity_id = db.Column(db.Integer, db.ForeignKey("data_entities.id"), index=True)
    data_domain_id = db.Column(db.Integer, db.ForeignKey("data_domains.id"), index=True)

    # Retention rules
    retention_period_days = db.Column(db.Integer)  # Days to retain data
    retention_reason = db.Column(db.String(255))  # Legal, Business, Regulatory

    # Archival policy
    archival_required = db.Column(db.Boolean, default=False)
    archival_period_days = db.Column(db.Integer)  # Days before archival
    archival_location = db.Column(db.String(255))  # Where archived data is stored

    # Deletion policy
    deletion_required = db.Column(db.Boolean, default=False)
    deletion_period_days = db.Column(db.Integer)  # Days before deletion
    deletion_method = db.Column(db.String(50))  # Secure Delete, Physical Destruction

    # Compliance
    compliance_requirements = db.Column(db.Text)  # JSON: GDPR, SOX, HIPAA requirements
    legal_hold_required = db.Column(db.Boolean, default=False)

    # Policy status
    status = db.Column(db.String(30), default="active")  # active, suspended, deprecated

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    data_entity = db.relationship("DataEntity", backref="retention_policies")
    data_domain = db.relationship("DataDomain", backref="retention_policies")
    created_by = db.relationship("User", backref="created_retention_policies")

    def __repr__(self):
        return f"<DataRetentionPolicy {self.name} ({self.retention_period_days} days)>"
