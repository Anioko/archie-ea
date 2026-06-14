"""
Application Lifecycle Models for ArchiMate 3.2

This module contains application lifecycle models that enable Applications Architects
to track versioning, deployment pipelines, and performance metrics.

Models:
- ApplicationVersioning: Version history tracking
- DeploymentPipeline: CI/CD, environments
- ApplicationPerformanceMetrics: Response times, throughput, error rates
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import event

from .. import db


class ApplicationVersioning(db.Model):
    """
    Application Versioning model for tracking version history.

    Tracks application versions, releases, and version history.

    Examples:
    - "CRM Application" version 2.1.0 released 2024 - 01 - 15
    - "Payment Service" version 1.5.2 with bug fixes
    """

    __tablename__ = "application_versioning"

    id = db.Column(db.Integer, primary_key=True)

    # Organization (tenant isolation)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Application relationship
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=False, index=True
    )

    # Version information
    version = db.Column(db.String(50), nullable=False, index=True)  # Semantic versioning: 1.2.3
    version_type = db.Column(db.String(20))  # major, minor, patch, pre-release
    release_notes = db.Column(db.Text)

    # Release information
    release_date = db.Column(db.Date, index=True)
    release_status = db.Column(db.String(30), default="planned")  # planned, released, deprecated
    is_current = db.Column(db.Boolean, default=False, index=True)

    # Version metadata
    build_number = db.Column(db.String(50))
    commit_hash = db.Column(db.String(100))
    branch_name = db.Column(db.String(100))

    # Changes
    changes_summary = db.Column(db.Text)  # Summary of changes in this version
    breaking_changes = db.Column(db.Boolean, default=False)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    organization = db.relationship("Organization", backref="application_versions")
    application_component = db.relationship("ApplicationComponent", backref="versions")
    created_by = db.relationship("User", backref="created_application_versions")

    def __repr__(self):
        return f"<ApplicationVersioning {self.application_component_id} v{self.version}>"


class DeploymentPipeline(db.Model):
    """
    Deployment Pipeline model for CI/CD and deployment management.

    Tracks deployment pipelines, environments, and deployment history.

    Examples:
    - "CRM Deployment Pipeline" with Dev -> Test -> Staging -> Prod
    - "Payment Service Pipeline" with automated testing and deployment
    """

    __tablename__ = "deployment_pipelines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Organization (tenant isolation)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Application relationship
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=False, index=True
    )

    # Pipeline characteristics
    pipeline_type = db.Column(db.String(50))  # CI/CD, Manual, Automated, Blue-Green, Canary
    ci_cd_platform = db.Column(db.String(50))  # Jenkins, GitLab CI, GitHub Actions, Azure DevOps

    # Pipeline stages
    pipeline_stages = db.Column(db.Text)  # JSON: List of stages (build, test, deploy, etc.)
    environment_sequence = db.Column(db.Text)  # JSON: Environment order (dev, test, staging, prod)

    # Pipeline configuration
    pipeline_config = db.Column(db.Text)  # JSON: Pipeline configuration (YAML, JSON)
    repository_url = db.Column(db.Text)
    branch_strategy = db.Column(db.String(50))  # GitFlow, GitHub Flow, Trunk-based

    # Deployment settings
    auto_deploy_enabled = db.Column(db.Boolean, default=False)
    approval_required = db.Column(db.Boolean, default=True)
    rollback_enabled = db.Column(db.Boolean, default=True)

    # Pipeline status
    status = db.Column(db.String(30), default="active")  # active, paused, deprecated
    last_deployment_date = db.Column(db.DateTime)
    last_deployment_status = db.Column(db.String(30))  # success, failed, in_progress

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    organization = db.relationship("Organization", backref="deployment_pipelines")
    application_component = db.relationship("ApplicationComponent", backref="deployment_pipelines")
    created_by = db.relationship("User", backref="created_deployment_pipelines")

    def __repr__(self):
        return f"<DeploymentPipeline {self.name} ({self.pipeline_type})>"


class ApplicationPerformanceMetrics(db.Model):
    """
    Application Performance Metrics model for tracking performance over time.

    Tracks response times, throughput, error rates, and other performance metrics.

    Examples:
    - "CRM Application" performance: avg response 200ms, 1000 req/s, 0.1% error rate
    - "Payment Service" performance: p95 response 500ms, 500 req/s, 0.05% error rate
    """

    __tablename__ = "application_performance_metrics"

    id = db.Column(db.Integer, primary_key=True)

    # Organization (tenant isolation)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Application relationship
    application_component_id = db.Column(
        db.Integer, db.ForeignKey("application_components.id"), nullable=False, index=True
    )

    # Performance metrics
    avg_response_time_ms = db.Column(db.Integer)  # Average response time in milliseconds
    p50_response_time_ms = db.Column(db.Integer)  # 50th percentile
    p95_response_time_ms = db.Column(db.Integer)  # 95th percentile
    p99_response_time_ms = db.Column(db.Integer)  # 99th percentile

    # Throughput
    requests_per_second = db.Column(db.Float)  # Requests per second
    transactions_per_second = db.Column(db.Float)  # Transactions per second

    # Error rates
    error_rate_percentage = db.Column(db.Float)  # Error rate as percentage
    error_count = db.Column(db.Integer)  # Total error count
    error_types = db.Column(db.Text)  # JSON: Breakdown of error types

    # Resource utilization
    cpu_utilization_percentage = db.Column(db.Float)
    memory_utilization_percentage = db.Column(db.Float)
    disk_utilization_percentage = db.Column(db.Float)

    # Availability
    uptime_percentage = db.Column(db.Float)  # Uptime percentage
    downtime_minutes = db.Column(db.Integer)  # Downtime in minutes

    # Metrics timestamp
    measured_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    measurement_period = db.Column(db.String(50))  # hourly, daily, weekly

    # Environment
    environment = db.Column(db.String(30))  # Development, Testing, Staging, Production

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    organization = db.relationship("Organization", backref="application_performance_metrics")
    application_component = db.relationship("ApplicationComponent", backref="performance_metrics")

    def __repr__(self):
        return f"<ApplicationPerformanceMetrics {self.application_component_id} ({self.avg_response_time_ms}ms)>"
