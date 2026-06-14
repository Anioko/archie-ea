"""Architecture Decision Records (ADRs) for EA practitioners.  # migration-exempt

Records decisions about the enterprise architecture itself, linked to
ArchiMate elements and ARB sessions.  New columns added via db.create_all()
per migration-freeze policy.
"""

from datetime import datetime

from .. import db
from .mixins import TenantMixin

VALID_HORIZONS = ['strategic', 'tactical', 'operational']
VALID_AUTHORITY_LEVELS = ['enterprise_arb', 'domain_arb', 'project_deviation']
VALID_DECISION_TYPES = ['platform', 'integration', 'vendor', 'standard', 'deviation', 'decommission']
VALID_STATUSES = ['proposed', 'under_review', 'accepted', 'rejected', 'deprecated', 'superseded', 'expired']


class ArchitectureDecision(TenantMixin, db.Model):
    __tablename__ = "architecture_decisions"

    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    decision_id = db.Column(db.String(50), unique=True, nullable=True)  # e.g. 'AD-001' (nullable for solution-level ADRs)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(30), default="proposed")  # proposed, accepted, deprecated, superseded

    # TOGAF ADM phase this decision belongs to
    adm_phase = db.Column(db.String(10), nullable=True)  # A-H

    # Decision content (markdown)
    context = db.Column(db.Text, nullable=True)       # Why was this decision needed?
    decision = db.Column(db.Text, nullable=True)       # What was decided?
    consequences = db.Column(db.Text, nullable=True)   # What are the consequences?
    alternatives = db.Column(db.Text, nullable=True)   # What alternatives were considered? (text or JSON)
    rationale = db.Column(db.Text, nullable=True)      # Why this option was chosen
    constraints = db.Column(db.JSON, nullable=True)    # [{constraint_name, impact}]
    related_element_ids = db.Column(db.JSON, nullable=True)  # [element_id, ...] generic element refs

    # Links
    archimate_element_ids = db.Column(db.JSON, default=list)  # IDs of impacted ArchiMate elements
    arb_session_id = db.Column(
        db.Integer, db.ForeignKey("architecture_review_boards.id"), nullable=True
    )  # if backed by ARB review

    # Metadata
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # GOV-02: Decision approval tracking
    decided_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Enterprise vs solution-level
    enterprise_level = db.Column(db.Boolean, default=True, nullable=False)
    solution_id = db.Column(db.Integer, db.ForeignKey('solutions.id', ondelete='SET NULL'), nullable=True)

    # Lifecycle
    superseded_by_id = db.Column(db.Integer, db.ForeignKey('architecture_decisions.id'), nullable=True)
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_until = db.Column(db.DateTime, nullable=True)

    # Classification
    horizon = db.Column(db.String(20), nullable=True, default='strategic')
    authority_level = db.Column(db.String(30), nullable=True, default='enterprise_arb')
    decision_type = db.Column(db.String(30), nullable=True)

    # Relationships
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    superseded_by = db.relationship('ArchitectureDecision', foreign_keys=[superseded_by_id], remote_side='ArchitectureDecision.id', uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "decision_id": self.decision_id,
            "title": self.title,
            "status": self.status,
            "adm_phase": self.adm_phase,
            "context": self.context,
            "decision": self.decision,
            "rationale": self.rationale,
            "alternatives": self.alternatives,
            "constraints": self.constraints or [],
            "consequences": self.consequences,
            "related_element_ids": self.related_element_ids or [],
            "archimate_element_ids": self.archimate_element_ids or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "decided_by_id": self.decided_by_id,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "approved_by_id": self.approved_by_id,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason,
            "enterprise_level": self.enterprise_level,
            "solution_id": self.solution_id,
            "superseded_by_id": self.superseded_by_id,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "horizon": self.horizon,
            "authority_level": self.authority_level,
            "decision_type": self.decision_type,
        }

    @classmethod
    def next_decision_id(cls):
        """Auto-generate next AD-XXX id."""
        last = cls.query.order_by(cls.id.desc()).first()
        if not last or not last.decision_id:
            return "AD-001"
        try:
            n = int(last.decision_id.split("-")[1]) + 1
            return f"AD-{n:03d}"
        except Exception:
            return "AD-001"


VALID_LINK_TYPES = ['governs', 'constrains', 'enables']


class DecisionCapabilityLink(db.Model):
    """ARB-002: Many-to-many link between architecture decisions and capabilities."""
    __tablename__ = 'decision_capability_links'
    __table_args__ = (
        db.UniqueConstraint('decision_id', 'capability_id', name='uq_decision_capability'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True)
    decision_id = db.Column(db.Integer, db.ForeignKey('architecture_decisions.id', ondelete='CASCADE'), nullable=False, index=True)
    capability_id = db.Column(db.Integer, db.ForeignKey('capabilities.id', ondelete='CASCADE'), nullable=False, index=True)
    link_type = db.Column(db.String(20), nullable=False, default='governs')  # governs/constrains/enables
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    decision = db.relationship('ArchitectureDecision', foreign_keys=[decision_id], backref=db.backref('capability_links', lazy='dynamic', cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'decision_id': self.decision_id,
            'capability_id': self.capability_id,
            'link_type': self.link_type,
            'is_primary': self.is_primary,
        }


# ── Phase H constants ────────────────────────────────────────────────────────

VALID_TRIGGER_TYPES = ['business_event', 'technology_eol', 'regulation', 'org_change', 'market', 'performance']
VALID_DISPOSITIONS = ['full_adm_cycle', 'incremental_update', 'exception', 'rejected', 'deferred']
VALID_CHANGE_REQUEST_STATUSES = ['open', 'assessing', 'disposition_set', 'closed']
VALID_IMPACT_LEVELS = ['critical', 'high', 'medium', 'low', 'none']
VALID_AFFECTED_ENTITY_TYPES = ['capability', 'application_component', 'business_service']


class ArchitectureChangeRequest(TenantMixin, db.Model):
    """ARB-004: Phase H change request — inbound signal that triggers change assessment."""
    __tablename__ = 'architecture_change_requests'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    acr_reference = db.Column(db.String(50), unique=True, nullable=False)  # ACR-2026-001
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Trigger
    trigger_type = db.Column(db.String(50), nullable=False, default='business_event')
    trigger_description = db.Column(db.Text, nullable=True)

    # Workflow
    status = db.Column(db.String(30), nullable=False, default='open')
    disposition = db.Column(db.String(30), nullable=True)

    # Scope
    affected_domains = db.Column(db.JSON, nullable=True)  # ['application','technology','data','business']

    # FK to Phase H change management board (optional)
    board_id = db.Column(db.Integer, db.ForeignKey('kanban_boards.id', ondelete='SET NULL'), nullable=True)

    # Ownership
    raised_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    raised_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    raised_by = db.relationship('User', foreign_keys=[raised_by_id])
    impact_assessments = db.relationship('ChangeImpactAssessment', backref='change_request', lazy='dynamic', cascade='all, delete-orphan')
    change_notices = db.relationship('ArchitectureChangeNotice', backref='change_request', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'acr_reference': self.acr_reference,
            'title': self.title,
            'description': self.description,
            'trigger_type': self.trigger_type,
            'trigger_description': self.trigger_description,
            'status': self.status,
            'disposition': self.disposition,
            'affected_domains': self.affected_domains or [],
            'board_id': self.board_id,
            'raised_by_id': self.raised_by_id,
            'raised_at': self.raised_at.isoformat() if self.raised_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
        }

    @classmethod
    def next_acr_reference(cls):
        from datetime import datetime as dt
        year = dt.utcnow().year
        last = cls.query.filter(cls.acr_reference.like(f'ACR-{year}-%')).order_by(cls.id.desc()).first()
        if last:
            try:
                n = int(last.acr_reference.split('-')[-1]) + 1
            except (ValueError, IndexError):
                n = 1
        else:
            n = 1
        return f'ACR-{year}-{n:03d}'


class ChangeImpactAssessment(db.Model):
    """ARB-004: Impact assessment record linking a change request to affected entities."""
    __tablename__ = 'change_impact_assessments'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    change_request_id = db.Column(db.Integer, db.ForeignKey('architecture_change_requests.id', ondelete='CASCADE'), nullable=False, index=True)

    # Polymorphic affected entity
    affected_entity_type = db.Column(db.String(30), nullable=True)  # capability/application_component/business_service
    affected_capability_id = db.Column(db.Integer, db.ForeignKey('capabilities.id', ondelete='SET NULL'), nullable=True)
    affected_decision_id = db.Column(db.Integer, db.ForeignKey('architecture_decisions.id', ondelete='SET NULL'), nullable=True)

    # Assessment
    impact_level = db.Column(db.String(20), nullable=False, default='medium')
    impact_description = db.Column(db.Text, nullable=True)
    recommended_action = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    assessed_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    affected_decision = db.relationship('ArchitectureDecision', foreign_keys=[affected_decision_id])

    def to_dict(self):
        return {
            'id': self.id,
            'change_request_id': self.change_request_id,
            'affected_entity_type': self.affected_entity_type,
            'affected_capability_id': self.affected_capability_id,
            'affected_decision_id': self.affected_decision_id,
            'impact_level': self.impact_level,
            'impact_description': self.impact_description,
            'recommended_action': self.recommended_action,
        }


class ArchitectureChangeNotice(db.Model):
    """ARB-004: Output record from a Phase H change request — what changed and what was decided."""
    __tablename__ = 'architecture_change_notices'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    change_request_id = db.Column(db.Integer, db.ForeignKey('architecture_change_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    acn_reference = db.Column(db.String(50), unique=True, nullable=False)  # ACN-2026-001
    scope_description = db.Column(db.Text, nullable=True)
    adm_phases_invoked = db.Column(db.JSON, nullable=True)  # ['B','C','E']

    issued_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    issued_by = db.relationship('User', foreign_keys=[issued_by_id])

    def to_dict(self):
        return {
            'id': self.id,
            'change_request_id': self.change_request_id,
            'acn_reference': self.acn_reference,
            'scope_description': self.scope_description,
            'adm_phases_invoked': self.adm_phases_invoked or [],
            'issued_by_id': self.issued_by_id,
            'issued_at': self.issued_at.isoformat() if self.issued_at else None,
        }

    @classmethod
    def next_acn_reference(cls):
        from datetime import datetime as dt
        year = dt.utcnow().year
        last = cls.query.filter(cls.acn_reference.like(f'ACN-{year}-%')).order_by(cls.id.desc()).first()
        if last:
            try:
                n = int(last.acn_reference.split('-')[-1]) + 1
            except (ValueError, IndexError):
                n = 1
        else:
            n = 1
        return f'ACN-{year}-{n:03d}'
