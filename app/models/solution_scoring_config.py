"""
Solution Scoring Configuration Model

Allows business-configurable weights for vendor/solution scoring algorithm.
Organizations can prioritize cost, risk, strategic fit, etc. differently.
"""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text

from app import db  # migration-exempt


class ScoringProfileType(enum.Enum):
    """Types of scoring profiles for different decision contexts"""
    
    BALANCED = "balanced"  # Equal weighting across factors
    COST_OPTIMIZED = "cost_optimized"  # Prioritize low cost
    RISK_AVERSE = "risk_averse"  # Prioritize risk mitigation
    SPEED_TO_MARKET = "speed_to_market"  # Prioritize fast implementation
    STRATEGIC_ALIGNMENT = "strategic_alignment"  # Prioritize strategic fit


class SolutionScoringConfig(db.Model):
    """
    Configuration for solution scoring algorithm weights.
    
    Allows enterprise architects to adjust how different factors
    contribute to the overall solution recommendation score.
    """
    
    __tablename__ = "solution_scoring_configs"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Profile type
    profile_type = Column(Enum(ScoringProfileType), default=ScoringProfileType.BALANCED)
    
    # Scoring weights (must sum to 1.0)
    cost_weight = Column(Float, default=0.25)
    capability_coverage_weight = Column(Float, default=0.25)
    risk_weight = Column(Float, default=0.20)
    strategic_fit_weight = Column(Float, default=0.15)
    implementation_weight = Column(Float, default=0.15)
    
    # Additional configuration
    max_cost_budget = Column(Float)  # For cost score normalization
    target_implementation_weeks = Column(Float, default=20)  # Baseline timeline
    
    # Organization/domain scoping
    organization_id = Column(Integer, ForeignKey("organization_units.id"), nullable=True)
    domain_id = Column(Integer, ForeignKey("capability_domain_definitions.id"), nullable=True)
    
    # Status
    is_default = Column(db.Boolean, default=False)
    is_active = Column(db.Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    def __repr__(self):
        return f"<SolutionScoringConfig {self.id}: {self.name} ({self.profile_type.value})>"
    
    def to_dict(self) -> dict:
        """Serialize to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "profile_type": self.profile_type.value if self.profile_type else None,
            "weights": {
                "cost": self.cost_weight,
                "capability_coverage": self.capability_coverage_weight,
                "risk": self.risk_weight,
                "strategic_fit": self.strategic_fit_weight,
                "implementation": self.implementation_weight,
            },
            "max_cost_budget": self.max_cost_budget,
            "target_implementation_weeks": self.target_implementation_weeks,
            "organization_id": self.organization_id,
            "domain_id": self.domain_id,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def get_weights_dict(self) -> dict:
        """Get weights as dictionary for scoring algorithm"""
        return {
            "cost": self.cost_weight,
            "capability_coverage": self.capability_coverage_weight,
            "risk": self.risk_weight,
            "strategic_fit": self.strategic_fit_weight,
            "implementation": self.implementation_weight,
        }
    
    def validate_weights(self) -> tuple[bool, str]:
        """
        Validate that weights sum to approximately 1.0
        
        Returns:
            (is_valid, message)
        """
        total = (
            self.cost_weight + 
            self.capability_coverage_weight + 
            self.risk_weight + 
            self.strategic_fit_weight + 
            self.implementation_weight
        )
        
        if abs(total - 1.0) > 0.01:  # Allow 1% tolerance for floating point
            return False, f"Weights sum to {total:.2f}, must sum to 1.0"
        
        return True, "Valid"
    
    @classmethod
    def get_default_config(cls, organization_id: int = None, domain_id: int = None) -> "SolutionScoringConfig":
        """
        Get default scoring configuration.
        
        Priority:
        1. Organization-specific default
        2. Domain-specific default  
        3. Global default (is_default=True)
        4. Create new balanced default if none exists
        """
        query = cls.query.filter_by(is_active=True, is_default=True)
        
        if organization_id:
            org_default = query.filter_by(organization_id=organization_id).first()
            if org_default:
                return org_default
        
        if domain_id:
            domain_default = query.filter_by(domain_id=domain_id).first()
            if domain_default:
                return domain_default
        
        global_default = query.filter_by(organization_id=None, domain_id=None).first()
        if global_default:
            return global_default
        
        # Create a default config if none exists
        return cls._create_default_config()
    
    @classmethod
    def _create_default_config(cls) -> "SolutionScoringConfig":
        """Create and return a default balanced configuration"""
        config = cls(
            name="Default Balanced Scoring",
            description="Default balanced weights for solution evaluation",
            profile_type=ScoringProfileType.BALANCED,
            cost_weight=0.25,
            capability_coverage_weight=0.25,
            risk_weight=0.20,
            strategic_fit_weight=0.15,
            implementation_weight=0.15,
            is_default=True,
            is_active=True,
        )
        # Note: caller must set created_by_id and commit
        return config
