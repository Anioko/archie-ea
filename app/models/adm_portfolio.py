"""
ADM Board Portfolio Models

Multi-board portfolio management for enterprise architecture coordination.
Adds portfolio view across boards, cross-board dependencies, and stakeholder community management.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app import db
from app.models.mixins.core import TenantMixin


class PortfolioStatus(str, Enum):
    """Status of a portfolio."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    PLANNING = "planning"
    COMPLETED = "completed"


class ADMBoardPortfolio(TenantMixin, db.Model):
    """
    Portfolio grouping multiple ADM Kanban boards.

    Enables enterprise-level coordination across related architecture initiatives.
    """

    __tablename__ = "adm_board_portfolios"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    portfolio_code = Column(String(50), unique=True, nullable=False)  # PF-2026-001
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Portfolio scope
    scope_type = Column(String(50))  # enterprise, program, project, domain
    business_domain = Column(String(100))

    # Status
    status = Column(String(50), default="active")
    start_date = Column(DateTime)
    target_end_date = Column(DateTime)
    actual_end_date = Column(DateTime)

    # Portfolio governance
    portfolio_owner_id = Column(Integer, ForeignKey("users.id"))
    portfolio_manager_id = Column(Integer, ForeignKey("users.id"))

    # Strategic alignment
    strategic_objectives = Column(JSON)  # List of strategic objectives
    success_metrics = Column(JSON)  # KPIs for portfolio success
    business_capabilities = Column(JSON)  # Related capability IDs

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    portfolio_owner = relationship("User", foreign_keys=[portfolio_owner_id], backref="owned_portfolios")
    portfolio_manager = relationship("User", foreign_keys=[portfolio_manager_id], backref="managed_portfolios")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_portfolios")
    board_links = relationship("ADMBoardPortfolioLink", back_populates="portfolio", cascade="all, delete-orphan")
    rida_logs = relationship("ADMRIDALog", back_populates="portfolio")

    def __repr__(self):
        return f"<ADMBoardPortfolio {self.portfolio_code}: {self.name}>"

    @staticmethod
    def generate_portfolio_code():
        """Generate next portfolio code."""
        year = datetime.utcnow().year
        last_portfolio = (
            ADMBoardPortfolio.query.filter(ADMBoardPortfolio.portfolio_code.like(f"PF-{year}-%"))
            .order_by(ADMBoardPortfolio.id.desc())
            .first()
        )

        if last_portfolio:
            try:
                last_num = int(last_portfolio.portfolio_code.split("-")[-1])
                next_num = last_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1

        return f"PF-{year}-{next_num:03d}"


class ADMBoardPortfolioLink(db.Model):
    """
    Link between a portfolio and a kanban board.

    Tracks board membership in portfolios with role and contribution type.
    """

    __tablename__ = "adm_board_portfolio_links"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Foreign keys
    portfolio_id = Column(Integer, ForeignKey("adm_board_portfolios.id"), nullable=False)
    board_id = Column(Integer, ForeignKey("kanban_boards.id"), nullable=False)

    # Link metadata
    board_role = Column(String(50))  # primary, supporting, dependent
    contribution_type = Column(String(50))  # delivers, enables, supports
    priority = Column(String(20))  # critical, high, medium, low

    # Dependencies
    depends_on_board_ids = Column(JSON)  # Other boards this board depends on

    # Timestamps
    added_at = Column(DateTime, default=datetime.utcnow)
    added_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    portfolio = relationship("ADMBoardPortfolio", back_populates="board_links")
    board = relationship("KanbanBoard", backref="portfolio_links")
    added_by = relationship("User", backref="portfolio_board_links")

    def __repr__(self):
        return f"<ADMBoardPortfolioLink {self.portfolio_id} <- {self.board_id}>"


class ADMDeliverableType(str, Enum):
    """Types of ADM deliverables."""

    ARCHITECTURE_VISION = "architecture_vision"
    BUSINESS_ARCHITECTURE = "business_architecture"
    DATA_ARCHITECTURE = "data_architecture"
    APPLICATION_ARCHITECTURE = "application_architecture"
    TECHNOLOGY_ARCHITECTURE = "technology_architecture"
    MIGRATION_PLAN = "migration_plan"
    IMPLEMENTATION_PLAN = "implementation_plan"
    STANDARDS_DOCUMENT = "standards_document"
    GUIDELINES = "guidelines"
    PATTERNS = "patterns"
    OTHER = "other"


class ADMDeliverableStatus(str, Enum):
    """Status of ADM deliverables."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class RIDAType(str, Enum):
    """RIDA types: Risk, Issue, Decision, Assumption."""

    RISK = "risk"
    ISSUE = "issue"
    DECISION = "decision"
    ASSUMPTION = "assumption"


class RIDASeverity(str, Enum):
    """Severity levels for RIDA items."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RIDAStatus(str, Enum):
    """Status for RIDA items."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ACCEPTED = "accepted"


class ADMRIDALog(TenantMixin, db.Model):
    """
    Risk, Issue, Decision, Assumption (RIDA) log for ADM.

    Tracks architecture risks, issues, decisions, and assumptions across boards.
    """

    __tablename__ = "adm_rida_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    rida_code = Column(String(50), unique=True, nullable=False)  # RIDA-2026-001

    # Classification
    rida_type = Column(String(20), nullable=False)  # risk, issue, decision, assumption
    severity = Column(String(20), default="medium")
    status = Column(String(20), default="open")

    # Content
    title = Column(String(255), nullable=False)
    description = Column(Text)
    impact = Column(Text)
    mitigation = Column(Text)  # For risks/issues
    rationale = Column(Text)  # For decisions
    validity_period = Column(Text)  # For assumptions

    # Context
    portfolio_id = Column(Integer, ForeignKey("adm_board_portfolios.id"))
    board_id = Column(Integer, ForeignKey("kanban_boards.id"))
    card_id = Column(Integer, ForeignKey("kanban_cards.id"))
    phase_id = Column(Integer, ForeignKey("adm_phases.id"))

    # Ownership
    owner_id = Column(Integer, ForeignKey("users.id"))
    assigned_to_id = Column(Integer, ForeignKey("users.id"))

    # Stakeholders
    stakeholder_ids = Column(JSON)  # Interested party IDs

    # Resolution
    resolution = Column(Text)
    resolved_at = Column(DateTime)
    resolved_by_id = Column(Integer, ForeignKey("users.id"))

    # Related items
    related_rida_ids = Column(JSON)  # Related RIDA item IDs
    related_deliverable_ids = Column(JSON)  # Related deliverable IDs

    # ARB linkage
    arb_review_item_id = Column(Integer, ForeignKey("arb_review_items.id"))

    # Timestamps
    identified_at = Column(DateTime, default=datetime.utcnow)
    target_resolution_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    portfolio = relationship("ADMBoardPortfolio", back_populates="rida_logs")
    board = relationship("KanbanBoard", backref="rida_logs")
    card = relationship("KanbanCard", backref="rida_logs")
    phase = relationship("ADMPhase", backref="rida_logs")
    owner = relationship("User", foreign_keys=[owner_id], backref="owned_rida_items")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], backref="assigned_rida_items")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id], backref="resolved_rida_items")
    arb_review_item = relationship("ARBReviewItem", backref="rida_log")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_rida_items")

    def __repr__(self):
        return f"<ADMRIDALog {self.rida_code}: {self.title}>"

    @staticmethod
    def generate_rida_code():
        """Generate next RIDA code."""
        year = datetime.utcnow().year
        last_rida = (
            ADMRIDALog.query.filter(ADMRIDALog.rida_code.like(f"RIDA-{year}-%"))
            .order_by(ADMRIDALog.id.desc())
            .first()
        )

        if last_rida:
            try:
                last_num = int(last_rida.rida_code.split("-")[-1])
                next_num = last_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1

        return f"RIDA-{year}-{next_num:04d}"


class ADMCrossBoardDependency(TenantMixin, db.Model):
    """
    Cross-board dependency tracking.

    Tracks dependencies between cards on different boards.
    """

    __tablename__ = "adm_cross_board_dependencies"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)

    # Source card (dependent)
    source_board_id = Column(Integer, ForeignKey("kanban_boards.id"), nullable=False)
    source_card_id = Column(Integer, ForeignKey("kanban_cards.id"), nullable=False)

    # Target card (prerequisite)
    target_board_id = Column(Integer, ForeignKey("kanban_boards.id"), nullable=False)
    target_card_id = Column(Integer, ForeignKey("kanban_cards.id"), nullable=False)

    # Dependency metadata
    dependency_type = Column(String(50), default="depends_on")  # depends_on, blocks, relates_to
    is_blocking = Column(Boolean, default=True)
    is_critical = Column(Boolean, default=False)

    # Status
    status = Column(String(50), default="active")  # active, resolved, waived

    # Description
    description = Column(Text)
    resolution_notes = Column(Text)

    # Resolution tracking
    resolved_at = Column(DateTime)
    resolved_by_id = Column(Integer, ForeignKey("users.id"))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    source_board = relationship("KanbanBoard", foreign_keys=[source_board_id], backref="outgoing_cross_deps")
    source_card = relationship("KanbanCard", foreign_keys=[source_card_id], backref="outgoing_cross_deps")
    target_board = relationship("KanbanBoard", foreign_keys=[target_board_id], backref="incoming_cross_deps")
    target_card = relationship("KanbanCard", foreign_keys=[target_card_id], backref="incoming_cross_deps")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id], backref="resolved_cross_deps")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_cross_deps")

    def __repr__(self):
        return f"<ADMCrossBoardDependency {self.source_card_id} -> {self.target_card_id}>"
