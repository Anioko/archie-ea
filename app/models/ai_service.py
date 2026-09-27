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

    # Audit metadata (finding A-05). Nullable / server-defaulted so
    # reconcile-schema can add these to an existing table — see CLAUDE.md
    # "Schema management". updated_by_id intentionally has no FK constraint
    # (matches the rest of this model's untyped-int convention) so it never
    # blocks a save if the user row is gone; resolve it via User.query.get().
    updated_by_id = db.Column(db.Integer, nullable=True)
    version = db.Column(db.Integer, nullable=True, default=1, server_default="1")


class AIPromptTemplateVersion(db.Model):
    """Version history for AIPromptTemplate (finding A-05, remainder).

    A-05's audit-metadata half (updated_by_id/version on AIPromptTemplate
    itself) shipped in an earlier commit; this table is the "full version
    history with diff and rollback" the register actually asked for. A new
    table, not new columns — `flask init-db`'s create_all() creates it on
    boot, which is the mechanism this relies on (see CLAUDE.md "Schema
    management": reconcile-schema is ADD-COLUMN-only and cannot create a
    table; a brand-new table needs no maintenance-window migration).

    One row is written *before* every mutation to the live template (update
    or reset-to-default), capturing the content being replaced — so this
    table always holds the prior state, and the live row is always the
    current state. A rollback is implemented as "apply a captured version's
    content to the live row", which itself first snapshots whatever it is
    about to overwrite — so rollback is itself undoable, and the history is
    never truncated by replaying it.
    """

    __tablename__ = "ai_prompt_template_versions"

    id = db.Column(db.Integer, primary_key=True)
    # No FK constraint — matches AIPromptTemplate.updated_by_id's own
    # convention on this model and avoids an ON DELETE dependency the table
    # doesn't need; template_name (not template_id) is the join key so
    # history survives a reset-to-default that deletes the live override row.
    template_name = db.Column(db.String(100), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    system_prompt = db.Column(db.Text, nullable=False)
    change_type = db.Column(db.String(20), nullable=False, default="update")  # update, reset, rollback
    updated_by_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


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
