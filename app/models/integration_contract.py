"""IntegrationContract — Registry of real API contracts for enterprise applications.

RUNTIME-02: Replaces placeholder URLs in generated integration clients with
real endpoints, auth configuration, and SLA parameters.

NEVER stores actual secrets (tokens, passwords). Only stores env var names
(e.g. SAP_CLIENT_ID) so generated code reads secrets at runtime.
"""

from datetime import datetime

from app import db  # migration-exempt — uses db.create_all() per migration freeze


VALID_PROTOCOLS = {"rest", "grpc", "soap", "odata", "graphql"}
VALID_AUTH_METHODS = {"oauth2", "api_key", "basic", "mtls", "saml", "none"}
VALID_SPEC_FORMATS = {"openapi", "asyncapi", "wsdl", "protobuf", "graphql_schema"}


class IntegrationContract(db.Model):
    """An API contract for an application in the enterprise portfolio.

    Stores connection details, auth config (env var names only), spec data,
    SLA targets, and per-environment URLs. Wired into the code generator
    so generated clients use real endpoints instead of placeholders.
    """

    __tablename__ = "integration_contracts"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer,
        db.ForeignKey("application_components.id"),
        nullable=True,
        index=True,
    )

    # Identity
    name = db.Column(db.String(200), nullable=False)
    version = db.Column(db.String(20))

    # Connection
    base_url = db.Column(db.String(500))
    protocol = db.Column(db.String(20), default="rest")

    # Auth — NEVER actual secrets, only env var names
    auth_method = db.Column(db.String(30))
    auth_config = db.Column(db.JSON)

    # Spec
    spec_format = db.Column(db.String(20))
    spec_content = db.Column(db.JSON)
    spec_url = db.Column(db.String(500))

    # Operational SLA
    sla_latency_ms = db.Column(db.Integer)
    sla_availability = db.Column(db.String(10))
    rate_limit = db.Column(db.String(50))

    # Per-environment URLs
    environments = db.Column(db.JSON)

    # Metadata
    owner_team = db.Column(db.String(100))
    documentation_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    application = db.relationship(
        "ApplicationComponent",
        foreign_keys=[application_id],
        lazy="select",
    )

    def to_dict(self):
        """Serialize all fields to a JSON-safe dict."""
        return {
            "id": self.id,
            "application_id": self.application_id,
            "name": self.name,
            "version": self.version,
            "base_url": self.base_url,
            "protocol": self.protocol,
            "auth_method": self.auth_method,
            "auth_config": self.auth_config,
            "spec_format": self.spec_format,
            "spec_content": self.spec_content,
            "spec_url": self.spec_url,
            "sla_latency_ms": self.sla_latency_ms,
            "sla_availability": self.sla_availability,
            "rate_limit": self.rate_limit,
            "environments": self.environments,
            "owner_team": self.owner_team,
            "documentation_url": self.documentation_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "application_name": (
                self.application.name if self.application else None
            ),
        }

    def __repr__(self):
        return f"<IntegrationContract {self.id} name={self.name!r} app={self.application_id}>"
