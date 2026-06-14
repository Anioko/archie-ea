"""
Enhanced Multi-Criteria Scoring Model
Sprint 1.6: Enhanced Scoring (Quick Win Feature)

Upgrades from basic 3 - criteria to comprehensive 12 - criteria scoring system.

File: app/models/enhanced_scoring.py
"""

from datetime import datetime

from sqlalchemy.dialects.postgresql import JSON

from app.extensions import db


class SolutionScoring(db.Model):
    """
    Comprehensive multi-criteria scoring for solution options

    Expands from basic (cost, fit, risk) to 12+ weighted criteria
    across 4 categories: Financial, Strategic, Technical, Risk
    """

    __tablename__ = "solution_scoring"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("architecture_sessions.id"), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey("solution_options.id"), nullable=False)

    # Financial Criteria (30% weight)
    tco_5year = db.Column(db.Numeric(12, 2))  # Total Cost of Ownership
    capex = db.Column(db.Numeric(12, 2))  # Capital expenditure
    opex_annual = db.Column(db.Numeric(12, 2))  # Operating expenditure
    roi_percent = db.Column(db.Float)  # Return on Investment
    payback_period_months = db.Column(db.Integer)  # Break-even time
    financial_score = db.Column(db.Float)  # 0 - 10 composite score

    # Strategic Criteria (30% weight)
    strategic_alignment = db.Column(db.Float)  # Alignment with strategy (0 - 10)
    innovation_potential = db.Column(db.Float)  # Innovation opportunity (0 - 10)
    competitive_advantage = db.Column(db.Float)  # Market differentiation (0 - 10)
    business_agility = db.Column(db.Float)  # Flexibility/adaptability (0 - 10)
    strategic_score = db.Column(db.Float)  # 0 - 10 composite score

    # Technical Criteria (20% weight)
    technical_fit = db.Column(db.Float)  # Architecture compatibility (0 - 10)
    integration_complexity = db.Column(db.Float)  # Ease of integration (0 - 10, inverted)
    scalability = db.Column(db.Float)  # Growth capability (0 - 10)
    performance = db.Column(db.Float)  # Speed/efficiency (0 - 10)
    maintainability = db.Column(db.Float)  # Long-term support (0 - 10)
    technical_score = db.Column(db.Float)  # 0 - 10 composite score

    # Risk Criteria (15% weight)
    vendor_viability = db.Column(db.Float)  # Vendor financial health (0 - 10)
    implementation_risk = db.Column(db.Float)  # Delivery risk (0 - 10, inverted)
    security_compliance = db.Column(db.Float)  # Security/compliance (0 - 10)
    operational_risk = db.Column(db.Float)  # Operations risk (0 - 10, inverted)
    risk_score = db.Column(db.Float)  # 0 - 10 composite score

    # Team/Skills Criteria (5% weight)
    skill_gap = db.Column(db.Float)  # Skills required (0 - 10, inverted)
    training_required = db.Column(db.Float)  # Training needs (0 - 10, inverted)
    vendor_support_quality = db.Column(db.Float)  # Support level (0 - 10)
    community_ecosystem = db.Column(db.Float)  # Community size (0 - 10)
    team_score = db.Column(db.Float)  # 0 - 10 composite score

    # Composite Scores
    weighted_total_score = db.Column(db.Float)  # Final weighted score (0 - 10)
    confidence_level = db.Column(db.Float)  # Confidence in scoring (0 - 1)

    # Metadata
    scoring_methodology = db.Column(db.String(50), default="weighted_multi_criteria")
    weights = db.Column(JSON)  # Custom weight overrides
    notes = db.Column(db.Text)  # Scoring rationale

    # Audit
    scored_at = db.Column(db.DateTime, default=datetime.utcnow)
    scored_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    session = db.relationship("ArchitectureSession", backref="scorings")
    option = db.relationship("SolutionOption", backref="scoring")

    # Indexes
    __table_args__ = (
        db.Index("idx_scoring_tenant_session", "tenant_id", "session_id"),
        db.Index("idx_scoring_option", "option_id"),
    )

    def __repr__(self):
        return f"<SolutionScoring option={self.option_id} score={self.weighted_total_score:.2f}>"

    def calculate_composite_scores(self):
        """Calculate category composite scores"""

        # Financial (average of normalized criteria)
        financial_criteria = [
            self._normalize_cost(self.tco_5year),
            self._normalize_roi(self.roi_percent),
            self._normalize_payback(self.payback_period_months),
        ]
        self.financial_score = sum(c for c in financial_criteria if c) / len(
            [c for c in financial_criteria if c]
        )

        # Strategic (average)
        strategic_criteria = [
            self.strategic_alignment,
            self.innovation_potential,
            self.competitive_advantage,
            self.business_agility,
        ]
        self.strategic_score = sum(c for c in strategic_criteria if c) / len(
            [c for c in strategic_criteria if c]
        )

        # Technical (average)
        technical_criteria = [
            self.technical_fit,
            10 - self.integration_complexity,  # Invert (lower complexity = better)
            self.scalability,
            self.performance,
            self.maintainability,
        ]
        self.technical_score = sum(c for c in technical_criteria if c) / len(
            [c for c in technical_criteria if c]
        )

        # Risk (average, inverted for negative criteria)
        risk_criteria = [
            self.vendor_viability,
            10 - self.implementation_risk,
            self.security_compliance,
            10 - self.operational_risk,
        ]
        self.risk_score = sum(c for c in risk_criteria if c) / len([c for c in risk_criteria if c])

        # Team (average)
        team_criteria = [
            10 - self.skill_gap,
            10 - self.training_required,
            self.vendor_support_quality,
            self.community_ecosystem,
        ]
        self.team_score = sum(c for c in team_criteria if c) / len([c for c in team_criteria if c])

    def calculate_weighted_total(self, custom_weights=None):
        """Calculate final weighted score"""

        # Default weights (must sum to 1.0)
        default_weights = {
            "financial": 0.30,
            "strategic": 0.30,
            "technical": 0.20,
            "risk": 0.15,
            "team": 0.05,
        }

        weights = custom_weights or self.weights or default_weights

        self.weighted_total_score = (
            (self.financial_score * weights["financial"])
            + (self.strategic_score * weights["strategic"])
            + (self.technical_score * weights["technical"])
            + (self.risk_score * weights["risk"])
            + (self.team_score * weights["team"])
        )

        return self.weighted_total_score

    def _normalize_cost(self, tco):
        """Normalize TCO to 0 - 10 scale (lower is better)"""
        if not tco:
            return None
        # Simple normalization: assume $1M is 0, $0 is 10
        # Customize based on your typical project costs
        max_acceptable = 1000000
        return max(0, 10 - (float(tco) / max_acceptable * 10))

    def _normalize_roi(self, roi_percent):
        """Normalize ROI to 0 - 10 scale (higher is better)"""
        if not roi_percent:
            return None
        # 0% ROI = 0, 100%+ ROI = 10
        return min(10, roi_percent / 10)

    def _normalize_payback(self, months):
        """Normalize payback period to 0 - 10 scale (shorter is better)"""
        if not months:
            return None
        # 0 months = 10, 60+ months = 0
        return max(0, 10 - (months / 6))

    def to_dict(self):
        return {
            "id": self.id,
            "option_id": self.option_id,
            "financial": {
                "tco_5year": float(self.tco_5year) if self.tco_5year else None,
                "capex": float(self.capex) if self.capex else None,
                "opex_annual": float(self.opex_annual) if self.opex_annual else None,
                "roi_percent": self.roi_percent,
                "payback_months": self.payback_period_months,
                "score": self.financial_score,
            },
            "strategic": {
                "alignment": self.strategic_alignment,
                "innovation": self.innovation_potential,
                "competitive_advantage": self.competitive_advantage,
                "business_agility": self.business_agility,
                "score": self.strategic_score,
            },
            "technical": {
                "fit": self.technical_fit,
                "integration_complexity": self.integration_complexity,
                "scalability": self.scalability,
                "performance": self.performance,
                "maintainability": self.maintainability,
                "score": self.technical_score,
            },
            "risk": {
                "vendor_viability": self.vendor_viability,
                "implementation_risk": self.implementation_risk,
                "security_compliance": self.security_compliance,
                "operational_risk": self.operational_risk,
                "score": self.risk_score,
            },
            "team": {
                "skill_gap": self.skill_gap,
                "training_required": self.training_required,
                "vendor_support": self.vendor_support_quality,
                "community": self.community_ecosystem,
                "score": self.team_score,
            },
            "overall": {
                "weighted_score": self.weighted_total_score,
                "confidence": self.confidence_level,
                "weights": self.weights,
            },
        }


class VendorViabilityAssessment(db.Model):
    """
    Detailed vendor viability analysis

    Assesses vendor financial health, market position, and sustainability
    """

    __tablename__ = "vendor_viability_assessments"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    vendor_name = db.Column(db.String(200), nullable=False)

    # Financial Health
    financial_stability = db.Column(db.Float)  # 0 - 10
    revenue_trend = db.Column(db.String(20))  # growing, stable, declining
    funding_status = db.Column(db.String(50))  # public, private, series_x
    years_in_business = db.Column(db.Integer)

    # Market Position
    market_share = db.Column(db.Float)  # Percentage
    gartner_quadrant = db.Column(db.String(20))  # leader, challenger, visionary, niche
    forrester_wave = db.Column(db.String(20))  # leader, strong_performer, contender, challenger
    customer_count = db.Column(db.Integer)

    # Product Health
    product_maturity = db.Column(db.Float)  # 0 - 10
    innovation_rate = db.Column(db.Float)  # 0 - 10
    roadmap_strength = db.Column(db.Float)  # 0 - 10

    # Support & Community
    support_rating = db.Column(db.Float)  # 0 - 10
    community_size = db.Column(db.Integer)
    documentation_quality = db.Column(db.Float)  # 0 - 10

    # Overall viability score
    viability_score = db.Column(db.Float)  # 0 - 10

    assessed_at = db.Column(db.DateTime, default=datetime.utcnow)
    data_source = db.Column(db.String(100))  # gartner, forrester, manual, llm

    __table_args__ = (db.Index("idx_vendor_tenant", "tenant_id", "vendor_name"),)
