"""
Alternative Solution: Lazy Loading with MetaData Check

This prevents conflicts by checking if tables already exist before defining them.
"""

from datetime import datetime

from flask import current_app

from app import db


def get_or_create_table(table_name, *columns, **kwargs):
    """Get existing table or create new one if it doesn't exist"""
    if table_name in db.metadata.tables:
        return db.metadata.tables[table_name]

    return db.Table(table_name, *columns, **kwargs)


# Use this approach instead of direct table definitions
business_app_capability_mapping = get_or_create_table(
    "business_app_capability_mapping",
    db.Column(
        "business_capability_id",
        db.Integer,
        db.ForeignKey("business_capability.id"),
        primary_key=True,
    ),
    db.Column(
        "application_capability_id",
        db.Integer,
        db.ForeignKey("application_capability.id"),
        primary_key=True,
    ),
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
    db.Column("updated_at", db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
)

app_tech_capability_mapping = get_or_create_table(
    "app_tech_capability_mapping",
    db.Column(
        "application_capability_id",
        db.Integer,
        db.ForeignKey("application_capability.id"),
        primary_key=True,
    ),
    db.Column(
        "technology_capability_id",
        db.Integer,
        db.ForeignKey("technology_capability.id"),
        primary_key=True,
    ),
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
    db.Column("updated_at", db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
)
