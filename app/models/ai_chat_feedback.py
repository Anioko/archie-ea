"""AI chat message feedback model."""
import datetime

from app.extensions import db


class AIChatFeedback(db.Model):
    __tablename__ = "ai_chat_feedback"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.String(10), nullable=False)   # 'up' or 'down'
    domain = db.Column(db.String(50))
    persona = db.Column(db.String(50))
    message_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
