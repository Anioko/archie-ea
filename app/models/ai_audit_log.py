"""AI Audit Log — immutable record of every LLM call in the platform."""
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, ForeignKey
from app import db


class AIAuditLog(db.Model):
    """Immutable log of every AI/LLM invocation."""
    __tablename__ = "ai_audit_logs"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Who
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user_email = Column(String(255))

    # What
    action = Column(String(100), nullable=False, index=True)
    solution_id = Column(Integer, ForeignKey("solutions.id"), nullable=True, index=True)
    wizard_step = Column(Integer)

    # Model details
    model_name = Column(String(100), nullable=False)
    prompt_hash = Column(String(64))
    response_hash = Column(String(64))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    estimated_cost_usd = Column(Float)
    latency_ms = Column(Integer)

    # Governance
    approval_status = Column(String(30), default="auto_approved")
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime)

    # Error tracking
    error_message = Column(Text)
    success = Column(db.Boolean, default=True)

    # ENH-019: Explainability — capture reasoning and prompt summary
    prompt_summary = Column(Text)  # Human-readable summary of what was asked
    reasoning = Column(Text)  # AI reasoning / explanation for the output
    content_type = Column(String(50))  # "option", "arb_draft", "gap_analysis", "scope"

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user_id": self.user_id,
            "action": self.action,
            "solution_id": self.solution_id,
            "wizard_step": self.wizard_step,
            "model_name": self.model_name,
            "prompt_hash": self.prompt_hash,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "approval_status": self.approval_status,
            "success": self.success,
            "prompt_summary": self.prompt_summary,
            "reasoning": self.reasoning,
            "content_type": self.content_type,
        }
