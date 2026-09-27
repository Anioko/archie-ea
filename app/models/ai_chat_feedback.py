"""AI chat message feedback model."""
import datetime

from app.extensions import db
from app.models.mixins.core import TenantMixin


class AIChatFeedback(TenantMixin, db.Model):
    """Thumbs up/down on an assistant answer.

    Tenant-scoped: ``message_text`` stores the assistant's reply, which is
    portfolio content. Without ``TenantMixin`` this table sat outside the
    ``do_orm_execute`` filter entirely, and the feedback analytics dashboard
    aggregated every organisation's answers together.
    """

    __tablename__ = "ai_chat_feedback"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.String(10), nullable=False)   # 'up' or 'down'
    domain = db.Column(db.String(50))
    persona = db.Column(db.String(50))
    message_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
