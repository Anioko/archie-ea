"""
Solution Cost Models - Multi-year TCO Analysis

Enterprise-grade database models for comprehensive cost modeling with:
- Multi-year CapEx/OpEx projections
- NPV and discounted cash flow calculations
- Variance tracking and actual cost recording
- Cost comparison across multiple solution options
"""

from datetime import datetime
from decimal import Decimal  # dead-code-ok

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app import db
from app.models.mixins import TenantMixin


class SolutionCostModel(TenantMixin, db.Model):
    """
    Multi-year cost model for a solution.

    Provides comprehensive TCO analysis with CapEx/OpEx breakdown,
    NPV calculations, and projection capabilities.
    """

    __tablename__ = "solution_cost_models"

    id = Column(Integer, primary_key=True)
    solution_id = Column(Integer, ForeignKey("solutions.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Model parameters
    currency = Column(String(3), default="USD")
    projection_years = Column(Integer, default=5)
    discount_rate = Column(Float, default=0.10)  # For NPV calculations
    inflation_rate = Column(Float, default=0.03)

    # Totals (calculated)
    total_capex = Column(Numeric(15, 2), default=0)
    total_opex = Column(Numeric(15, 2), default=0)
    total_tco = Column(Numeric(15, 2), default=0)
    npv = Column(Numeric(15, 2))  # Net Present Value

    # Status
    status = Column(String(30), default="draft")  # draft, approved, actual
    approved_by_id = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    solution = relationship("Solution", backref="cost_models")
    line_items = relationship(
        "SolutionCostLineItem", backref="cost_model", lazy="dynamic", cascade="all, delete-orphan"
    )
    yearly_projections = relationship(
        "SolutionCostYearlyProjection",
        backref="cost_model",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

    # Indexes
    __table_args__ = (
        Index("idx_cost_model_solution", "solution_id"),
        Index("idx_cost_model_status", "status"),
        Index("idx_cost_model_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<SolutionCostModel {self.id}: {self.name}>"


class SolutionCostLineItem(TenantMixin, db.Model):
    """
    Individual cost line item within a cost model.

    Supports various cost categories, frequencies, and growth rates
    for accurate multi-year projections.
    """

    __tablename__ = "solution_cost_line_items"

    id = Column(Integer, primary_key=True)
    cost_model_id = Column(Integer, ForeignKey("solution_cost_models.id"), nullable=False)

    # Classification
    category = Column(
        String(50), nullable=False
    )  # hardware, software, services, personnel, infrastructure, other
    cost_type = Column(String(10), nullable=False)  # capex, opex
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Vendor linkage (optional)
    vendor_product_id = Column(Integer, ForeignKey("vendor_products.id"))

    # Cost details
    unit_cost = Column(Numeric(15, 2), nullable=False)
    quantity = Column(Integer, default=1)
    frequency = Column(String(20), default="one_time")  # one_time, monthly, annual

    # Timing
    start_year = Column(Integer, default=1)  # Year 1, 2, 3, etc.
    end_year = Column(Integer)  # Null = ongoing

    # Growth
    annual_growth_rate = Column(Float, default=0)  # For recurring costs

    # Calculated
    total_cost = Column(Numeric(15, 2))  # Over projection period

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    vendor_product = relationship("VendorProduct", backref="cost_line_items")

    # Indexes
    __table_args__ = (
        Index("idx_line_item_cost_model", "cost_model_id"),
        Index("idx_line_item_category", "category"),
        Index("idx_line_item_cost_type", "cost_type"),
    )

    def __repr__(self):
        return f"<SolutionCostLineItem {self.id}: {self.name} ({self.cost_type})>"


class SolutionCostYearlyProjection(db.Model):
    """
    Year-by-year cost projection with CapEx/OpEx breakdown.

    Provides detailed breakdown by cost category for each projection year,
    including discounted values for NPV calculations.
    """

    __tablename__ = "solution_cost_yearly_projections"

    id = Column(Integer, primary_key=True)
    cost_model_id = Column(Integer, ForeignKey("solution_cost_models.id"), nullable=False)

    year = Column(Integer, nullable=False)  # 1, 2, 3, 4, 5

    # CapEx breakdown
    capex_hardware = Column(Numeric(15, 2), default=0)
    capex_software = Column(Numeric(15, 2), default=0)
    capex_services = Column(Numeric(15, 2), default=0)
    capex_other = Column(Numeric(15, 2), default=0)
    capex_total = Column(Numeric(15, 2), default=0)

    # OpEx breakdown
    opex_licensing = Column(Numeric(15, 2), default=0)
    opex_maintenance = Column(Numeric(15, 2), default=0)
    opex_support = Column(Numeric(15, 2), default=0)
    opex_infrastructure = Column(Numeric(15, 2), default=0)
    opex_personnel = Column(Numeric(15, 2), default=0)
    opex_other = Column(Numeric(15, 2), default=0)
    opex_total = Column(Numeric(15, 2), default=0)

    # Totals
    year_total = Column(Numeric(15, 2), default=0)
    cumulative_total = Column(Numeric(15, 2), default=0)
    discounted_value = Column(Numeric(15, 2))  # Present value

    # Actuals (for tracking)
    actual_total = Column(Numeric(15, 2))
    variance = Column(Numeric(15, 2))
    variance_explanation = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("cost_model_id", "year", name="uix_cost_model_year"),
        Index("idx_yearly_projection_cost_model", "cost_model_id"),
        Index("idx_yearly_projection_year", "year"),
    )

    def __repr__(self):
        return f"<SolutionCostYearlyProjection {self.id}: Year {self.year}>"


class SolutionCostComparison(db.Model):
    """
    Compare costs across multiple solutions/options.

    Enables side-by-side comparison of different cost models
    to support informed decision-making.
    """

    __tablename__ = "solution_cost_comparisons"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    session_id = Column(Integer, ForeignKey("solution_analysis_sessions.id"))

    # Options being compared (JSON list of cost_model_ids)
    compared_models = Column(JSON)

    # Analysis results
    lowest_tco_model_id = Column(Integer)
    lowest_npv_model_id = Column(Integer)
    recommendation = Column(Text)
    comparison_notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    session = relationship("SolutionAnalysisSession", backref="cost_comparisons")
    created_by = relationship("User", foreign_keys=[created_by_id])

    # Indexes
    __table_args__ = (
        Index("idx_cost_comparison_session", "session_id"),
        Index("idx_cost_comparison_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<SolutionCostComparison {self.id}: {self.name}>"
