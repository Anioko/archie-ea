"""
AI Service Architecture and Models

This module defines the models required to support the 'AI Service Layer' for architectural intelligence.
It enables storing prompts, AI configurations, vector embeddings meta-data (actual vectors in pgvector),
and logging AI interactions for audit and improvement.
"""

from datetime import datetime

from .. import db


class AIServiceConfig(db.Model):
    """
    Configuration for AI Providers (OpenAI, Gemini, Anthropic).
    Securely stores (encrypted via app logic) API keys and model preferences.
    """

    __tablename__ = "ai_service_configs"

    id = db.Column(db.Integer, primary_key=True)
    provider_name = db.Column(db.String(50), nullable=False)  # 'OpenAI', 'AzureOpenAI', 'Gemini'
    model_version = db.Column(db.String(50), default="gpt - 4")  # 'gpt - 4', 'claude - 3 - opus'

    # Configuration
    api_base_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)

    # Constraints
    max_tokens = db.Column(db.Integer, default=4096)
    temperature = db.Column(db.Float, default=0.7)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AIServiceConfig {self.provider_name} ({self.model_version})>"


class AIPromptTemplate(db.Model):
    """
    Stored Prompt Templates for standardized AI specialized tasks.
    E.g., "Generate ARB Review", "Semantically Audit this Architecture".
    """

    __tablename__ = "ai_prompt_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

    # The Prompt Logic
    system_prompt = db.Column(db.Text, nullable=False)  # "You are an Enterprise Architect..."
    user_prompt_template = db.Column(
        db.Text, nullable=False
    )  # "Review the following component: {component_json}"

    # Categorization
    category = db.Column(db.String(50))  # 'Audit', 'Generation', 'Transformation'

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIInteractionLog(db.Model):
    """
    Audit log of what the AI did.
    Crucial for architectural governance and cost tracking.
    """

    __tablename__ = "ai_interaction_logs"

    id = db.Column(db.Integer, primary_key=True)

    # Who and What
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    prompt_template_id = db.Column(
        db.Integer, db.ForeignKey("ai_prompt_templates.id"), nullable=True
    )

    # The Interaction
    input_size_tokens = db.Column(db.Integer)
    output_size_tokens = db.Column(db.Integer)
    duration_ms = db.Column(db.Integer)

    # Context
    target_element_id = db.Column(
        db.Integer, nullable=True
    )  # Which ArchiMate element was this about?

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
