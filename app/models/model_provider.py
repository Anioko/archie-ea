"""
ModelProvider — tenant-hybrid provider register.

Platform rows (organization_id=NULL) define which providers and model
versions are available globally. Organisations can override via their
own rows to restrict (is_allowed=False) or explicitly allow a provider
that is not in the platform set.

Usage:
    # Platform-declared providers
    ModelProvider(name="openai", model_version="gpt-4o", is_platform_default=True)

    # Organisation blocks a platform provider
    ModelProvider(organization_id=2, name="openai", model_version="gpt-4o",
                  is_platform_default=False, is_allowed=False)

    # Organisation adds its own allowed provider
    ModelProvider(organization_id=2, name="openai", model_version="gpt-4o-mini",
                  is_platform_default=False, is_allowed=True)
"""

from __future__ import annotations

from app import db
from app.models.mixins import TimestampMixin


class ModelProvider(TimestampMixin, db.Model):
    """Provider register — platform defaults + per-org allow/restrict rows."""

    __tablename__ = "model_providers"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(100), nullable=False, index=True,
                         comment="Provider name, e.g. openai, anthropic, huggingface")
    model_version = db.Column(db.String(255), nullable=False,
                              comment="Model identifier, e.g. gpt-4o, claude-opus-5")

    # Platform-default row: NULL organisation_id.
    # Per-org row: scoped to that organisation.
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    is_platform_default = db.Column(
        db.Boolean, default=False, nullable=False,
        comment="True for rows seeded as platform-level defaults",
    )
    is_allowed = db.Column(
        db.Boolean, default=True, nullable=False,
        comment="False when an organisation explicitly restricts a provider",
    )

    organization = db.relationship("Organization", lazy="select")

    __table_args__ = (
        db.UniqueConstraint("provider", "model_version", "organization_id",
                            name="uq_model_provider_org"),
    )

    def __repr__(self) -> str:
        scope = "[PLATFORM]" if self.organization_id is None else f"[org={self.organization_id}]"
        status = "ALLOW" if self.is_allowed else "BLOCK"
        return f"<ModelProvider {self.provider}/{self.model_version} {scope} {status}>"

    @classmethod
    def is_allowed_for_org(cls, provider: str, model_version: str, organization_id: int | None = None) -> bool:
        """Check whether *provider/model_version* is allowed for *organization_id*.
        
        Resolution order:
        1. If an organisation-specific row exists for this (provider, model_version, org),
           return its ``is_allowed`` value.
        2. If a platform-default row exists (org NULL, is_platform_default=True),
           return its ``is_allowed`` value.
        3. No row at all → True (unknown providers are permitted by default).
        """
        # Per-org override
        if organization_id is not None:
            row = cls.query.filter_by(
                provider=provider,
                model_version=model_version,
                organization_id=organization_id,
            ).first()
            if row is not None:
                return row.is_allowed

        # Platform default
        row = cls.query.filter_by(
            provider=provider,
            model_version=model_version,
            organization_id=None,
            is_platform_default=True,
        ).first()
        if row is not None:
            return row.is_allowed

        # No row → allowed by default
        return True

    @classmethod
    def platform_defaults(cls) -> list[ModelProvider]:
        """Return all platform-default rows."""
        return cls.query.filter_by(organization_id=None, is_platform_default=True).all()

    @classmethod
    def org_overrides(cls, organization_id: int) -> list[ModelProvider]:
        """Return all organisation-specific rows for *organization_id*."""
        return cls.query.filter_by(organization_id=organization_id).all()