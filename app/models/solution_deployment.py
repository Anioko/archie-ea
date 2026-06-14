"""
Solution Deployment Models for ArchiMate 3.2

This module contains solution deployment models that enable Solutions Architects
to map solutions to technologies and model deployment architecture.

Models:
- SolutionTechnologyMapping: Junction table linking Solution to TechnologyStack
- SolutionDeploymentArchitecture: How solution components are deployed
"""

from datetime import date, datetime  # dead-code-ok
from typing import Optional  # dead-code-ok

from sqlalchemy import event  # dead-code-ok

from .. import db
from .mixins import TenantMixin

# Junction table for Solution to TechnologyStack mapping
solution_technology_mapping = db.Table(
    "solution_technology_mapping",
    db.Column(
        "solution_id",
        db.Integer,
        db.ForeignKey("solutions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "technology_stack_id",
        db.Integer,
        db.ForeignKey("technology_stacks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("mapping_type", db.String(50)),  # primary, supporting, optional
    db.Column("usage_description", db.Text),  # How this technology is used in the solution
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)


class SolutionDeploymentArchitecture(TenantMixin, db.Model):
    """
    Solution Deployment Architecture model for deployment architecture.

    Models how solution components are deployed across infrastructure,
    including deployment patterns, environments, and topology.

    Examples:
    - "Customer 360 Platform" deployment: microservices on Kubernetes, multi-region
    - "Supply Chain Solution" deployment: hybrid cloud, on-premise + cloud components
    """

    __tablename__ = "solution_deployment_architectures"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)

    # Solution relationship
    solution_id = db.Column(db.Integer, db.ForeignKey("solutions.id"), nullable=False, index=True)

    # Deployment characteristics
    deployment_pattern = db.Column(db.String(50))  # Monolithic, Microservices, Serverless, Hybrid
    deployment_model = db.Column(db.String(50))  # On-Premise, Cloud, Hybrid, Multi-Cloud
    cloud_provider = db.Column(db.String(50))  # AWS, Azure, GCP, Multi-Cloud, On-Prem

    # Infrastructure topology
    topology_description = db.Column(db.Text)  # Description of deployment topology
    regions = db.Column(db.Text)  # JSON: List of deployment regions
    availability_zones = db.Column(db.Text)  # JSON: List of availability zones

    # Deployment environments
    environments = db.Column(db.Text)  # JSON: List of environments (dev, test, staging, prod)
    environment_config = db.Column(db.Text)  # JSON: Environment-specific configuration

    # Scaling and performance
    scaling_strategy = db.Column(db.String(50))  # Horizontal, Vertical, Auto-scaling
    load_balancing = db.Column(
        db.String(50)
    )  # Application Load Balancer, Network Load Balancer, etc.
    caching_strategy = db.Column(db.Text)  # Caching approach and technologies

    # High availability
    high_availability_enabled = db.Column(db.Boolean, default=False)
    disaster_recovery_enabled = db.Column(db.Boolean, default=False)
    backup_strategy = db.Column(db.Text)

    # Security
    security_architecture = db.Column(db.Text)  # Security architecture description
    network_segmentation = db.Column(db.Text)  # Network segmentation approach
    encryption_at_rest = db.Column(db.Boolean, default=True)
    encryption_in_transit = db.Column(db.Boolean, default=True)

    # Deployment status
    status = db.Column(db.String(30), default="planned")  # planned, deploying, deployed, deprecated
    deployment_date = db.Column(db.Date)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    solution = db.relationship("Solution", backref="deployment_architectures")
    created_by = db.relationship("User", backref="created_solution_deployments")

    def __repr__(self):
        return f"<SolutionDeploymentArchitecture {self.name} ({self.deployment_pattern})>"
