"""LLM Prompt Version registry — versioned, activatable prompt templates.

Tracks every prompt revision so admins can roll back, A/B test, and
monitor quality metrics per prompt key.
"""

from __future__ import annotations

from app import db
from app.models.mixins import TimestampMixin


class LLMPromptVersion(TimestampMixin, db.Model):
    __tablename__ = "llm_prompt_version"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False, index=True,
                    comment="Dot-separated prompt key, e.g. archimate.property_generation")
    version = db.Column(db.String(32), nullable=False,
                        comment="Semver-style version string, e.g. v1.3")
    body = db.Column(db.Text, nullable=False,
                     comment="Full prompt template text")
    is_active = db.Column(db.Boolean, default=False, nullable=False,
                          comment="Only one version per key should be active")
    metrics_json = db.Column(db.JSON, nullable=True,
                             comment="Rolling quality/latency/error metrics")

    __table_args__ = (
        db.UniqueConstraint("key", "version", name="uq_llm_prompt_key_version"),
    )

    def __repr__(self) -> str:
        active = " [ACTIVE]" if self.is_active else ""
        return f"<LLMPromptVersion {self.key} {self.version}{active}>"
