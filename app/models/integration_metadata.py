"""
Integration Architecture Models

Extends ArchiMate 3.2 ApplicationInterface elements with integration-specific
operational metadata for Enterprise/Solution/Integration Architecture.
"""

from datetime import datetime

from .. import db


class ApplicationInterfaceMetadata(db.Model):
    """
    Extended metadata for ArchiMate ApplicationInterface elements.

    Provides integration-specific technical and operational details that
    complement the ArchiMate metamodel while maintaining tool compatibility.

    Usage:
        interface_elem = ArchiMateElement.query.filter_by(
            type='ApplicationInterface', name='Customer API'
        ).first()

        metadata = ApplicationInterfaceMetadata(
            archimate_element_id=interface_elem.id,
            interface_type='REST',
            protocol='HTTPS',
            authentication_method='OAuth2',
            sla_response_time_ms=500
        )
    """

    __tablename__ = "application_interface_metadata"

    id = db.Column(db.Integer, primary_key=True)
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), unique=True, nullable=False
    )

    # Interface Classification
    interface_type = db.Column(
        db.String(50)
    )  # REST, SOAP, GraphQL, gRPC, MQ, Event, File, Database
    protocol = db.Column(db.String(50))  # HTTP, HTTPS, TCP, AMQP, MQTT, FTP, SFTP
    data_format = db.Column(db.String(50))  # JSON, XML, CSV, Avro, Protobuf, EDI
    message_pattern = db.Column(
        db.String(50)
    )  # Request-Response, Fire-and-Forget, Pub-Sub, Streaming

    # Security
    authentication_method = db.Column(
        db.String(50)
    )  # OAuth2, API Key, Basic Auth, Certificate, SAML, None
    authorization_model = db.Column(db.String(50))  # RBAC, ABAC, ACL, None
    encryption_in_transit = db.Column(db.Boolean, default=True)
    encryption_at_rest = db.Column(db.Boolean, default=False)

    # API Contracts & Documentation
    openapi_spec = db.Column(db.Text)  # OpenAPI 3.x specification (JSON/YAML)
    asyncapi_spec = db.Column(db.Text)  # AsyncAPI specification for async interfaces
    graphql_schema = db.Column(db.Text)  # GraphQL schema definition
    wsdl_url = db.Column(db.String(500))  # WSDL URL for SOAP services
    documentation_url = db.Column(db.String(500))  # External documentation

    # Service Level Agreement (SLA)
    sla_response_time_ms = db.Column(db.Integer)  # Target response time in milliseconds
    sla_availability_percentage = db.Column(db.Numeric(5, 2))  # e.g., 99.9%
    sla_uptime_hours = db.Column(db.String(50))  # e.g., "24/7", "Business Hours"
    max_throughput_tps = db.Column(db.Integer)  # Transactions per second
    rate_limit_per_minute = db.Column(db.Integer)  # API rate limit

    # Operational Characteristics
    is_synchronous = db.Column(db.Boolean, default=True)
    supports_retry = db.Column(db.Boolean, default=False)
    idempotent = db.Column(db.Boolean, default=False)
    timeout_seconds = db.Column(db.Integer)

    # Data Governance
    data_classification = db.Column(db.String(50))  # Public, Internal, Confidential, Restricted
    contains_pii = db.Column(db.Boolean, default=False)
    pii_fields = db.Column(db.Text)  # JSON array of PII field names
    gdpr_scope = db.Column(db.Boolean, default=False)
    data_residency_requirements = db.Column(db.String(200))  # e.g., "EU only"

    # Lifecycle Management
    operational_status = db.Column(
        db.String(20), default="planned"
    )  # planned, development, testing, production, deprecated, retired
    version = db.Column(db.String(20))  # Interface version
    deprecation_date = db.Column(db.Date, nullable=True)
    retirement_date = db.Column(db.Date, nullable=True)
    breaking_changes = db.Column(db.Text)  # JSON array of breaking changes per version

    # Monitoring & Health
    monitoring_enabled = db.Column(db.Boolean, default=False)
    health_check_url = db.Column(db.String(500))
    last_health_check = db.Column(db.DateTime)
    current_uptime_percentage = db.Column(db.Numeric(5, 2))
    average_response_time_ms = db.Column(db.Integer)  # Actual measured response time

    # Business Context
    business_criticality = db.Column(db.String(20))  # Critical, High, Medium, Low
    consumer_count = db.Column(db.Integer, default=0)  # Number of consuming systems
    transaction_volume_daily = db.Column(db.BigInteger)  # Average daily transactions

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))
    updated_by = db.Column(db.String(100))

    # Relationships
    archimate_element = db.relationship(
        "ArchiMateElement", backref=db.backref("interface_metadata", uselist=False)
    )

    def __repr__(self):
        return f"<ApplicationInterfaceMetadata for element_id={self.archimate_element_id}>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "archimate_element_id": self.archimate_element_id,
            "interface_type": self.interface_type,
            "protocol": self.protocol,
            "data_format": self.data_format,
            "message_pattern": self.message_pattern,
            "authentication_method": self.authentication_method,
            "authorization_model": self.authorization_model,
            "encryption_in_transit": self.encryption_in_transit,
            "openapi_spec": self.openapi_spec,
            "asyncapi_spec": self.asyncapi_spec,
            "graphql_schema": self.graphql_schema,
            "documentation_url": self.documentation_url,
            "sla_response_time_ms": self.sla_response_time_ms,
            "sla_availability_percentage": float(self.sla_availability_percentage)
            if self.sla_availability_percentage
            else None,
            "max_throughput_tps": self.max_throughput_tps,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "is_synchronous": self.is_synchronous,
            "supports_retry": self.supports_retry,
            "idempotent": self.idempotent,
            "data_classification": self.data_classification,
            "contains_pii": self.contains_pii,
            "gdpr_scope": self.gdpr_scope,
            "operational_status": self.operational_status,
            "version": self.version,
            "deprecation_date": self.deprecation_date.isoformat()
            if self.deprecation_date
            else None,
            "monitoring_enabled": self.monitoring_enabled,
            "health_check_url": self.health_check_url,
            "current_uptime_percentage": float(self.current_uptime_percentage)
            if self.current_uptime_percentage
            else None,
            "average_response_time_ms": self.average_response_time_ms,
            "business_criticality": self.business_criticality,
            "consumer_count": self.consumer_count,
            "transaction_volume_daily": self.transaction_volume_daily,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SystemDependency(db.Model):
    """
    Tracks dependencies between systems (ArchiMate ApplicationComponents).

    Critical for Integration Architecture to understand system coupling,
    impact analysis, and architectural debt.

    Usage:
        dependency = SystemDependency(
            source_system_id=crm_app.id,
            target_system_id=payment_system.id,
            dependency_type='service',
            criticality='critical',
            interface_id=payment_api.id
        )
    """

    __tablename__ = "system_dependencies"

    id = db.Column(db.Integer, primary_key=True)

    # Dependent Systems (ApplicationComponents or ApplicationInterfaces)
    source_system_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"), nullable=False)
    target_system_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"), nullable=False)

    # Dependency Characteristics
    dependency_type = db.Column(
        db.String(50), nullable=False
    )  # data, service, authentication, configuration, shared-database
    criticality = db.Column(db.String(20), default="medium")  # critical, high, medium, low

    # Integration Details
    interface_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=True
    )  # Links to ApplicationInterface element if applicable

    # Dependency Description
    description = db.Column(db.Text)  # What is this dependency for?
    failure_impact = db.Column(db.Text)  # What happens if target fails?

    # Temporal Characteristics
    is_runtime_dependency = db.Column(db.Boolean, default=True)  # Runtime vs. build-time
    is_bidirectional = db.Column(db.Boolean, default=False)

    # Circuit Breaker / Resilience
    has_fallback = db.Column(db.Boolean, default=False)
    fallback_strategy = db.Column(db.String(200))  # Cache, Default Value, Degrade Gracefully
    timeout_seconds = db.Column(db.Integer)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))

    # Relationships
    source_system = db.relationship(
        "ArchiMateElement", foreign_keys=[source_system_id], backref="outgoing_dependencies"
    )
    target_system = db.relationship(
        "ArchiMateElement", foreign_keys=[target_system_id], backref="incoming_dependencies"
    )
    interface = db.relationship("ArchiMateElement", foreign_keys=[interface_id])

    def __repr__(self):
        return f"<SystemDependency {self.source_system_id} -> {self.target_system_id} ({self.dependency_type})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "source_system_id": self.source_system_id,
            "source_system_name": self.source_system.name if self.source_system else None,
            "target_system_id": self.target_system_id,
            "target_system_name": self.target_system.name if self.target_system else None,
            "dependency_type": self.dependency_type,
            "criticality": self.criticality,
            "interface_id": self.interface_id,
            "interface_name": self.interface.name if self.interface else None,
            "description": self.description,
            "failure_impact": self.failure_impact,
            "is_runtime_dependency": self.is_runtime_dependency,
            "is_bidirectional": self.is_bidirectional,
            "has_fallback": self.has_fallback,
            "fallback_strategy": self.fallback_strategy,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
