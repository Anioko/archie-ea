"""
AI Recommendations Model

Stores provenance and audit data for AI-generated recommendations
in the Architecture Assistant.
"""

from datetime import datetime

from .. import db


class AIRecommendation(db.Model):
    """
    AI Recommendation audit and provenance model.

    Stores all AI-generated recommendations with full provenance
    for audit, traceability, and continuous improvement.
    """

    __tablename__ = "ai_recommendations"

    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.String(255), nullable=False, index=True)
    canvas_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    request_id = db.Column(db.String(255), nullable=True, index=True)

    # AI model metadata
    model_version = db.Column(db.String(50), nullable=False)
    prompt_template_id = db.Column(db.String(100), nullable=False)
    prompt_hash = db.Column(db.String(128), nullable=False)

    # Recommendation data
    recommendation_type = db.Column(
        db.String(50), nullable=False
    )  # gap_analysis, option_generation, etc.
    recommendation_data = db.Column(db.JSON, nullable=False)  # Full recommendation payload

    # Provenance
    evidence_links = db.Column(db.JSON, nullable=True)  # List of {entity_id, db_url}
    llm_response_short = db.Column(db.Text, nullable=True)  # Shortened LLM response for audit

    # Results
    applied_changes = db.Column(db.JSON, nullable=True)  # What was actually applied
    validation_result = db.Column(db.JSON, nullable=True)  # Post-application validation
    success = db.Column(db.Boolean, nullable=False, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    applied_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship("User", backref="ai_recommendations")

    def __repr__(self):
        return (
            f"<AIRecommendation(id={self.id}, option_id={self.option_id}, user_id={self.user_id})>"
        )
