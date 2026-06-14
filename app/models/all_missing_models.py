"""
Missing Data Architecture Models for ArchiMate 3.2

This module contains the data architecture models that were missing from the
original implementation, providing comprehensive data management capabilities.

Data Architecture Elements:
- ConceptualDataModel: High-level business view of data
- LogicalDataModel: Detailed logical structure
- PhysicalDataModel: Database-specific implementation
- DataLineage: End-to-end data flow tracking
- DataTransformation: ETL/ELT process modeling

ArchiMate 3.2 Missing Elements:
- Stakeholder: Motivation layer element
- BusinessCollaboration: Business layer element
- BusinessInterface: Business layer element
- BusinessInteraction: Business layer element
- Product: Business layer element
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    and_,
)

from .. import db

# Use db.relationship instead of importing relationship


class ConceptualDataModel(db.Model):
    """
    ArchiMate-inspired Conceptual Data Model.

    High-level business view of data entities and relationships,
    independent of any specific database implementation.

    Examples:
    - "Customer Domain Model" with Customer, Order, Product entities
    - "Financial Data Model" with Account, Transaction, Ledger entities
    """

    __tablename__ = "conceptual_data_models"

    id = Column(db.Integer, primary_key=True)
    name = Column(db.String(255), nullable=False, index=True)
    description = Column(db.Text)

    # ArchiMate linkage
    archimate_element_id = Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Model characteristics
    business_domain = Column(db.String(100))  # Customer, Financial, HR, Supply Chain
    scope = Column(db.String(50))  # Department, Enterprise, Domain
    version = Column(db.String(20))

    # Governance
    data_steward = Column(db.String(255))
    business_owner = Column(db.String(255))
    approval_status = Column(db.String(30), default="draft")  # draft, approved, deprecated

    # Metadata
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    created_by = db.relationship("User")

    # ArchiMate 3.2 Relationships
    business_objects = db.relationship(
        "BusinessObject",
        secondary="conceptual_model_business_objects",
        back_populates="conceptual_models",
    )
    # capabilities = db.relationship('BusinessCapability', secondary='conceptual_model_capabilities', back_populates='conceptual_models')
    data_entities = db.relationship(
        "DataEntity", secondary="conceptual_model_entities", back_populates="conceptual_models"
    )

    def __repr__(self):
        return f"<ConceptualDataModel {self.name} ({self.business_domain})>"


class LogicalDataModel(db.Model):
    """
    ArchiMate-inspired Logical Data Model.

    Detailed logical structure with normalized entities, attributes,
    and relationships, still independent of specific database technology.

    Examples:
    - "Normalized Customer Schema" with 3NF normalization
    - "Data Warehouse Logical Model" with star schema design
    """

    __tablename__ = "logical_data_models"

    id = Column(db.Integer, primary_key=True)
    name = Column(db.String(255), nullable=False, index=True)
    description = Column(db.Text)

    # ArchiMate linkage
    archimate_element_id = Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Model characteristics
    conceptual_model_id = Column(db.Integer, db.ForeignKey("conceptual_data_models.id"))
    normalization_level = Column(db.String(20))  # 1NF, 2NF, 3NF, BCNF, Denormalized
    design_pattern = Column(db.String(50))  # Star Schema, Snowflake, Hierarchical

    # Technical specifications
    supports_transactions = Column(db.Boolean, default=True)
    supports_concurrency = Column(db.Boolean, default=True)
    estimated_entities = Column(db.Integer)
    estimated_relationships = Column(db.Integer)

    # Metadata
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    conceptual_model = db.relationship("ConceptualDataModel", backref="logical_models")
    created_by = db.relationship("User", backref="created_logical_models")

    # ArchiMate 3.2 Relationships
    # LogicalDataModel SPECIALIZES ConceptualDataModel (already linked via conceptual_model_id)
    # LogicalDataModel REALIZES DataObject (logical to application mapping)
    data_objects = db.relationship(
        "DataObject", secondary="logical_model_data_objects", back_populates="logical_models"
    )

    # LogicalDataModel ASSOCIATED_WITH BusinessProcess (process-data mapping)
    # business_processes = db.relationship('BusinessProcess', secondary='logical_model_processes', back_populates='logical_models')

    def __repr__(self):
        return f"<LogicalDataModel {self.name} ({self.normalization_level})>"


class PhysicalDataModel(db.Model):
    """
    ArchiMate-inspired Physical Data Model.

    Database-specific implementation with tables, columns, indexes,
    and constraints for actual database deployment.

    Examples:
    - "PostgreSQL Customer Schema" with specific data types and indexes
    - "MongoDB Collection Design" with document structures
    """

    __tablename__ = "physical_data_models"

    id = Column(db.Integer, primary_key=True)
    name = Column(db.String(255), nullable=False, index=True)
    description = Column(db.Text)

    # ArchiMate linkage
    archimate_element_id = Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Model characteristics
    logical_model_id = Column(db.Integer, db.ForeignKey("logical_data_models.id"))
    database_type = Column(db.String(50))  # PostgreSQL, MySQL, MongoDB, Oracle, SQL Server
    database_version = Column(db.String(20))

    # Deployment specifications
    deployment_environment = Column(db.String(30))  # Development, Testing, Staging, Production
    schema_name = Column(db.String(100))  # Database schema name
    table_count = Column(db.Integer)
    estimated_size_gb = Column(db.Float)

    # Performance characteristics
    supports_partitioning = Column(db.Boolean, default=False)
    supports_sharding = Column(db.Boolean, default=False)
    backup_strategy = Column(db.String(100))

    # Metadata
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    logical_model = db.relationship("LogicalDataModel", backref="physical_models")
    created_by = db.relationship("User", backref="created_physical_models")

    # ArchiMate 3.2 Relationships
    # PhysicalDataModel REALIZES LogicalDataModel (already linked via logical_model_id)
    # PhysicalDataModel DEPLOYED_ON Node/SystemSoftware (deployment mapping)
    nodes = db.relationship(
        "Node",
        secondary="physical_model_deployments",
        primaryjoin="PhysicalDataModel.id == physical_model_deployments.c.physical_model_id",
        secondaryjoin="Node.id == physical_model_deployments.c.node_id",
        back_populates="physical_models",
        overlaps="physical_models",
    )
    system_softwares = db.relationship(
        "SystemSoftware",
        secondary="physical_model_deployments",
        primaryjoin="PhysicalDataModel.id == physical_model_deployments.c.physical_model_id",
        secondaryjoin="SystemSoftware.id == physical_model_deployments.c.system_software_id",
        back_populates="physical_models",
        overlaps="nodes,physical_models",
    )

    # PhysicalDataModel ACCESSES TechnologyArtifact (database artifacts)
    artifacts = db.relationship(
        "TechnologyArtifact", secondary="physical_model_artifacts", back_populates="physical_models"
    )

    def __repr__(self):
        return f"<PhysicalDataModel {self.name} ({self.database_type})>"


class DataLineage(db.Model):
    """
    Data Lineage tracking model.

    Tracks the flow of data from source systems through transformations
    to final consumption points, enabling impact analysis and governance.

    Examples:
    - "Customer Data Flow" from CRM to Data Warehouse to Analytics
    - "Financial Data Pipeline" from ERP to Reporting System
    """

    __tablename__ = "data_lineage"

    id = Column(db.Integer, primary_key=True)
    name = Column(db.String(255), nullable=False, index=True)
    description = Column(db.Text)

    # ArchiMate linkage
    archimate_element_id = Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Lineage characteristics
    lineage_type = Column(db.String(50))  # ETL, ELT, Real-time, Batch
    data_domain = Column(db.String(100))  # Customer, Financial, Operational

    # Flow specifications
    source_system = Column(db.String(255))  # Source application or database
    target_system = Column(db.String(255))  # Target application or database
    frequency = Column(db.String(50))  # Real-time, Hourly, Daily, Weekly

    # Governance
    data_classification = Column(db.String(50))  # Public, Internal, Confidential, Restricted
    retention_period_days = Column(db.Integer)
    compliance_requirements = Column(db.Text)  # GDPR, SOX, HIPAA requirements

    # Data Governance
    access_level = Column(
        db.String(30), default="public"
    )  # public, internal, restricted, confidential
    access_roles = Column(db.JSON, nullable=True)  # List of roles with access
    last_accessed = Column(db.DateTime, nullable=True)  # Last access timestamp
    auto_delete_date = Column(db.DateTime, nullable=True)  # Automatic deletion date
    retention_reason = Column(db.String(255), nullable=True)  # Reason for retention

    # Metadata
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    created_by = db.relationship("User", backref="created_data_lineage")

    # ArchiMate 3.2 Relationships
    data_entities = db.relationship(
        "DataEntity", secondary="data_lineage_entities", back_populates="data_lineage"
    )
    business_objects = db.relationship(
        "BusinessObject",
        secondary="data_lineage_access",
        primaryjoin="DataLineage.id == data_lineage_access.c.data_lineage_id",
        secondaryjoin="BusinessObject.id == data_lineage_access.c.business_object_id",
        back_populates="data_lineage",
        overlaps="data_lineage",
    )
    data_objects = db.relationship(
        "DataObject",
        secondary="data_lineage_access",
        primaryjoin="DataLineage.id == data_lineage_access.c.data_lineage_id",
        secondaryjoin="DataObject.id == data_lineage_access.c.data_object_id",
        back_populates="data_lineage",
        overlaps="business_objects,data_lineage",
    )

    def __repr__(self):
        return f"<DataLineage {self.name} ({self.source_system} → {self.target_system})>"


class DataTransformation(db.Model):
    """
    Data Transformation model for ETL/ELT processes.

    Represents specific transformation steps in data pipelines,
    including business rules, mappings, and quality checks.

    Examples:
    - "Customer Address Standardization" transformation
    - "Financial Amount Currency Conversion" transformation
    """

    __tablename__ = "data_transformations"

    id = Column(db.Integer, primary_key=True)
    name = Column(db.String(255), nullable=False, index=True)
    description = Column(db.Text)

    # ArchiMate linkage
    archimate_element_id = Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Transformation characteristics
    lineage_id = Column(db.Integer, db.ForeignKey("data_lineage.id"))
    transformation_type = Column(db.String(50))  # Filter, Aggregate, Join, Split, Calculate
    transformation_logic = Column(db.Text)  # Business rules or SQL code

    # Technical specifications
    source_format = Column(db.String(100))  # JSON, CSV, XML, Database Table
    target_format = Column(db.String(100))  # Parquet, Avro, Database Table
    processing_language = Column(db.String(50))  # SQL, Python, Spark, PySpark

    # Performance and quality
    estimated_volume_records = Column(db.BigInteger)
    processing_time_seconds = Column(db.Integer)
    quality_checks = Column(db.JSON)  # List of validation rules

    # Metadata
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    archimate_element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    lineage = db.relationship("DataLineage", backref="transformations")
    created_by = db.relationship("User", backref="created_transformations")

    def __repr__(self):
        return f"<DataTransformation {self.name} ({self.transformation_type})>"


# ============================================================================
# JUNCTION TABLES - ARCHIMATE 3.2 RELATIONSHIPS
# ============================================================================

# ConceptualDataModel COMPOSES BusinessObject (defines business entities)
conceptual_model_business_objects = db.Table(
    "conceptual_model_business_objects",
    db.Column(
        "conceptual_model_id",
        db.Integer,
        db.ForeignKey("conceptual_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "business_object_id",
        db.Integer,
        db.ForeignKey("business_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "relationship_type", db.String(30), default="composition"
    ),  # composition, aggregation
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# Conceptual model to DataEntity junction
conceptual_model_entities = db.Table(
    "conceptual_model_entities",
    db.Column(
        "conceptual_model_id",
        db.Integer,
        db.ForeignKey("conceptual_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "data_entity_id",
        db.Integer,
        db.ForeignKey("data_entities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("role", db.String(50)),  # 'primary', 'lookup', 'transaction'
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# ConceptualDataModel REALIZES BusinessCapability (data supports capabilities)
conceptual_model_capabilities = db.Table(
    "conceptual_model_capabilities",
    db.Column(
        "conceptual_model_id",
        db.Integer,
        db.ForeignKey("conceptual_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "business_capability_id",
        db.Integer,
        db.ForeignKey("business_capability.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("realization_level", db.String(30), default="full"),  # full, partial, supporting
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# DataLineage to DataEntity junction
data_lineage_entities = db.Table(
    "data_lineage_entities",
    db.Column(
        "data_lineage_id",
        db.Integer,
        db.ForeignKey("data_lineage.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "data_entity_id",
        db.Integer,
        db.ForeignKey("data_entities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("participation_type", db.String(30), default="flow"),  # 'source', 'target', 'flow'
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# LogicalDataModel SPECIALIZES ConceptualDataModel (logical refinement)
logical_model_specialization = db.Table(
    "logical_model_specialization",
    db.Column(
        "logical_model_id",
        db.Integer,
        db.ForeignKey("logical_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "conceptual_model_id",
        db.Integer,
        db.ForeignKey("conceptual_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "specialization_type", db.String(30), default="refinement"
    ),  # refinement, extension, constraint
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# PhysicalDataModel REALIZES LogicalDataModel (implementation)
physical_model_realization = db.Table(
    "physical_model_realization",
    db.Column(
        "physical_model_id",
        db.Integer,
        db.ForeignKey("physical_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "logical_model_id",
        db.Integer,
        db.ForeignKey("logical_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "realization_fidelity", db.String(30), default="complete"
    ),  # complete, partial, approximate
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# DataLineage FLOWS between BusinessProcess/ApplicationComponent
data_lineage_flows = db.Table(
    "data_lineage_flows",
    db.Column(
        "data_lineage_id",
        db.Integer,
        db.ForeignKey("data_lineage.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "source_element_id",
        db.Integer,
        db.ForeignKey("archimate_elements.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "target_element_id",
        db.Integer,
        db.ForeignKey("archimate_elements.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "flow_type", db.String(30), default="data_flow"
    ),  # data_flow, control_flow, event_flow
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# DataLineage ACCESSES BusinessObject/DataObject
data_lineage_access = db.Table(
    "data_lineage_access",
    db.Column(
        "data_lineage_id",
        db.Integer,
        db.ForeignKey("data_lineage.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "data_object_id",
        db.Integer,
        db.ForeignKey("application_data_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "business_object_id",
        db.Integer,
        db.ForeignKey("business_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("access_type", db.String(30), default="read"),  # read, write, create, delete
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# DataTransformation TRIGGERED_BY BusinessEvent
data_transformation_triggers = db.Table(
    "data_transformation_triggers",
    db.Column(
        "data_transformation_id",
        db.Integer,
        db.ForeignKey("data_transformations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "business_event_id",
        db.Integer,
        db.ForeignKey("business_events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("trigger_type", db.String(30), default="automatic"),  # automatic, manual, scheduled
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# PhysicalDataModel DEPLOYED_ON Node/SystemSoftware
physical_model_deployments = db.Table(
    "physical_model_deployments",
    db.Column(
        "physical_model_id",
        db.Integer,
        db.ForeignKey("physical_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "node_id",
        db.Integer,
        db.ForeignKey("technology_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "system_software_id",
        db.Integer,
        db.ForeignKey("technology_system_software.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "deployment_status", db.String(30), default="planned"
    ),  # planned, deployed, deprecated
    db.Column("deployment_date", db.DateTime),
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# LogicalDataModel REALIZES DataObject (logical to application mapping)
logical_model_data_objects = db.Table(
    "logical_model_data_objects",
    db.Column(
        "logical_model_id",
        db.Integer,
        db.ForeignKey("logical_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "data_object_id",
        db.Integer,
        db.ForeignKey("application_data_objects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("realization_type", db.String(30), default="direct"),  # direct, indirect, mediated
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# LogicalDataModel ASSOCIATED_WITH BusinessProcess (process-data mapping)
logical_model_processes = db.Table(
    "logical_model_processes",
    db.Column(
        "logical_model_id",
        db.Integer,
        db.ForeignKey("logical_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "business_process_id",
        db.Integer,
        db.ForeignKey("business_processes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("association_type", db.String(30), default="supports"),  # supports, enables, uses
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)

# PhysicalDataModel ACCESSES TechnologyArtifact (database artifacts)
physical_model_artifacts = db.Table(
    "physical_model_artifacts",
    db.Column(
        "physical_model_id",
        db.Integer,
        db.ForeignKey("physical_data_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "technology_artifact_id",
        db.Integer,
        db.ForeignKey("technology_artifacts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "artifact_type", db.String(30), default="database"
    ),  # database, script, config, backup
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)
