"""
Customer Journey Map (BIZBOK)

The third of BIZBOK's core maps. Archie already models the capability map
(``BusinessCapability``) and the value stream (``ValueStream`` /
``ValueStreamStage``); the customer journey was missing, so the one view a
business architect is asked for first — "what does this actually look like to
the customer, and what have we built behind it?" — could not be answered.

A journey belongs to a persona (a stakeholder), and is made of ordered stages.
Each stage records what the customer is trying to do, where they do it (the
channel), what they touch (the touchpoints), what hurts (the pain points), and
how they feel about it (the sentiment).

What makes this architecture rather than a diagram is
``CustomerJourneyStageCapability``: every stage links to the real
``BusinessCapability`` rows that serve it. Because applications are already
mapped to capabilities (``ApplicationCapabilityMapping``), that one link is
enough to walk a journey stage all the way down to the systems behind it —
persona -> stage -> capability -> application.

ArchiMate backbone
------------------
A journey is mirrored into ``archimate_elements`` as a ``BusinessProcess`` on
the **lower-case** ``business`` layer (the element browser and the layer APIs
key on lower case; see ``LAYER_TYPES`` in
``app/modules/architecture/services/archimate_validation_service.py``). The FK
lives on ``CustomerJourney.archimate_element_id``.

Tenancy and schema notes
------------------------
* All three models are ``TenantMixin``. Without it the rows leak between
  organisations silently — nothing in query code filters them.
* ``code`` is unique **per organisation**, never globally: two customers can
  both run a journey called ``ONBOARD``. See
  ``app/models/tenant_unique_registry.py`` for why every authored identifier in
  this codebase now works that way, and ``scripts/check_tenant_unique.py`` for
  the gate that keeps it so.
* Every column except the primary key, the owning foreign keys and
  ``stage_order`` is nullable. ``flask reconcile-schema`` — which is how
  existing databases get new columns — can only ADD nullable columns, so a
  NOT NULL column here would break every deployment that already has these
  tables.
* Nothing carries a numeric default that could be mistaken for a measurement.
  ``sentiment_score`` is NULL until somebody rates the stage, because a stored
  ``0`` would read as "measured neutral" and there would be no way to tell the
  difference.
"""

from __future__ import annotations

from app.datetime_helpers import utcnow

from .. import db
from .mixins import TenantMixin

# The sentiment scale, and the only values the service will store. Ordered
# worst-to-best so a template can render a curve without a second lookup.
SENTIMENT_SCALE = {
    "angry": -2,
    "frustrated": -1,
    "neutral": 0,
    "satisfied": 1,
    "delighted": 2,
}

# Journey stage -> capability support strength, mirroring the value stream's
# BIZBOK grid vocabulary so the two maps read the same way.
SUPPORT_TYPES = ("primary", "secondary", "supporting")


class CustomerJourney(TenantMixin, db.Model):
    """An end-to-end journey a persona takes through the organisation."""

    __tablename__ = "customer_journeys"
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "code", name="uq_customer_journeys_org_code"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    # Journey identity
    name = db.Column(db.String(256), nullable=False, index=True)
    # Authored by the tenant, so unique per organisation only — see the
    # composite constraint above.
    code = db.Column(db.String(50), index=True)  # e.g. ONBOARD, RENEW, CLAIM
    description = db.Column(db.Text)

    # The persona / stakeholder whose journey this is. `persona_name` is the
    # label an architect actually uses ("First-time claimant"); the optional FK
    # ties it to a real Stakeholder element when one has been modelled.
    persona_name = db.Column(db.String(200))
    persona_description = db.Column(db.Text)
    persona_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    # Classification
    journey_type = db.Column(db.String(50))  # acquisition, onboarding, service, retention, exit
    business_owner = db.Column(db.String(100))
    lifecycle_status = db.Column(db.String(30))  # draft, current, target

    # ArchiMate backbone: the mirror row in `archimate_elements`, created by
    # customer_journey_service.create_journey(). Nullable so reconcile-schema
    # can add it, and so a journey imported before the mirror existed still
    # loads.
    archimate_element_id = db.Column(db.Integer, db.ForeignKey("archimate_elements.id"))

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    stages = db.relationship(
        "CustomerJourneyStage",
        back_populates="journey",
        lazy="dynamic",
        order_by="CustomerJourneyStage.stage_order",
    )
    capability_links = db.relationship(
        "CustomerJourneyStageCapability", back_populates="journey", lazy="dynamic"
    )
    archimate_element = db.relationship(
        "ArchiMateElement", foreign_keys=[archimate_element_id]
    )
    persona_element = db.relationship(
        "ArchiMateElement", foreign_keys=[persona_element_id]
    )

    def __repr__(self):
        return f"<CustomerJourney {self.name}>"


class CustomerJourneyStage(TenantMixin, db.Model):
    """One ordered step of a customer journey, seen from the customer's side."""

    __tablename__ = "customer_journey_stages"

    id = db.Column(db.Integer, primary_key=True)

    journey_id = db.Column(
        db.Integer, db.ForeignKey("customer_journeys.id"), nullable=False, index=True
    )
    # Sequence within the journey. NOT NULL because a journey stage with no
    # position is not a stage; the service always supplies it (auto-assigning
    # max+1 when the form leaves it blank), so no caller can hit the constraint.
    stage_order = db.Column(db.Integer, nullable=False)

    name = db.Column(db.String(256), nullable=False, index=True)
    description = db.Column(db.Text)

    # The customer's side of the stage.
    customer_goal = db.Column(db.Text)  # what the customer is trying to achieve
    touchpoints = db.Column(db.Text)  # newline-separated; what they interact with
    channel = db.Column(db.String(100))  # web, mobile, branch, call_centre, email, partner
    pain_points = db.Column(db.Text)  # newline-separated

    # Sentiment. Both NULL until somebody rates the stage — a stored 0 would be
    # indistinguishable from a measured "neutral".
    sentiment = db.Column(db.String(20))  # a key of SENTIMENT_SCALE
    sentiment_score = db.Column(db.Integer)  # -2..+2, derived from `sentiment`

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    journey = db.relationship("CustomerJourney", back_populates="stages")
    capability_links = db.relationship(
        "CustomerJourneyStageCapability", back_populates="stage", lazy="dynamic"
    )

    def __repr__(self):
        return f"<CustomerJourneyStage {self.stage_order}. {self.name}>"


class CustomerJourneyStageCapability(TenantMixin, db.Model):
    """The link that makes a journey architecture: stage -> business capability.

    ``journey_id`` is carried alongside ``stage_id`` so the whole grid for a
    journey is one query rather than one per stage. It is derived, never
    authored — the service sets it from the stage.

    The unique constraint is composed only of foreign keys to tenant-scoped
    rows, so it cannot collide across organisations and needs no
    ``organization_id`` (``scripts/check_tenant_unique.py`` skips exactly this
    shape).
    """

    __tablename__ = "customer_journey_stage_capabilities"
    __table_args__ = (
        db.UniqueConstraint(
            "stage_id", "capability_id", name="uq_cj_stage_capability"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    journey_id = db.Column(
        db.Integer, db.ForeignKey("customer_journeys.id"), nullable=False, index=True
    )
    stage_id = db.Column(
        db.Integer,
        db.ForeignKey("customer_journey_stages.id"),
        nullable=False,
        index=True,
    )
    # A real BusinessCapability row — not a free-text capability name. This is
    # the join that lets a stage reach the applications behind it, via
    # ApplicationCapabilityMapping.business_capability_id.
    capability_id = db.Column(
        db.Integer, db.ForeignKey("business_capability.id"), nullable=False, index=True
    )

    support_type = db.Column(db.String(20))  # a member of SUPPORT_TYPES
    # 1..5. NULL means "linked but not yet assessed", which is a different
    # statement from "assessed as minimal".
    support_level = db.Column(db.Integer)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    journey = db.relationship("CustomerJourney", back_populates="capability_links")
    stage = db.relationship("CustomerJourneyStage", back_populates="capability_links")
    capability = db.relationship("BusinessCapability", foreign_keys=[capability_id])

    def __repr__(self):
        return (
            f"<CustomerJourneyStageCapability stage={self.stage_id} "
            f"cap={self.capability_id}>"
        )
