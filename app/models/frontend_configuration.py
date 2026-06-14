"""
Frontend Configuration Model

Stores configurable frontend settings that were previously hardcoded.
Provides API-driven configuration for UI components, export settings, and other frontend values.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text

from .. import db


class FrontendConfiguration(db.Model):
    """
    Frontend Configuration Model

    Stores configuration values for frontend components that were previously hardcoded.
    Supports dynamic configuration of export settings, UI timeouts, validation rules, etc.
    """

    __tablename__ = "frontend_configuration"

    id = Column(db.Integer, primary_key=True)

    # Configuration category (export, ui, validation, etc.)
    category = Column(db.String(50), nullable=False, index=True)

    # Configuration key (unique within category)
    config_key = Column(db.String(100), nullable=False, index=True)

    # Configuration value (JSON for complex values)
    config_value = Column(db.JSON, nullable=False)

    # Data type (string, number, boolean, json)
    data_type = Column(db.String(20), default="string")

    # Description of what this configuration controls
    description = Column(db.Text)

    # Whether this config is active/enabled
    is_active = Column(db.Boolean, default=True)

    # Environment (development, staging, production, all)
    environment = Column(db.String(20), default="all")

    # Created/updated timestamps
    created_at = Column(db.DateTime, default=datetime.utcnow)
    updated_at = Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Metadata (version, author, etc.)
    config_metadata = Column(db.JSON)

    __table_args__ = (db.UniqueConstraint("category", "config_key", name="unique_category_key"),)

    def __repr__(self):
        return f"<FrontendConfiguration {self.category}.{self.config_key}>"

    @classmethod
    def get_config_value(cls, category, key, default=None):
        """Get a configuration value by category and key."""
        config = cls.query.filter_by(category=category, config_key=key, is_active=True).first()

        if config:
            return config.config_value
        return default

    @classmethod
    def get_category_configs(cls, category):
        """Get all active configurations for a category."""
        configs = cls.query.filter_by(category=category, is_active=True).all()

        return {config.config_key: config.config_value for config in configs}

    @classmethod
    def set_config_value(cls, category, key, value, description=None, data_type="json"):
        """Set or update a configuration value."""
        config = cls.query.filter_by(category=category, config_key=key).first()

        if not config:
            config = cls(
                category=category,
                config_key=key,
                config_value=value,
                data_type=data_type,
                description=description,
            )
            db.session.add(config)
        else:
            config.config_value = value
            config.data_type = data_type
            if description:
                config.description = description
            config.updated_at = datetime.utcnow()

        db.session.commit()
        return config
