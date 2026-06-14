"""
Simplified Duplicate Detection Models
Minimal implementation to avoid table conflicts
"""

from datetime import datetime
from .. import db
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, validates
from app.models.validators import validate_percentage, validate_enum


class SimpleDuplicateGroup(db.Model):
    """
    Simplified duplicate group for testing
    """
    __tablename__ = 'simple_duplicate_groups'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    description = Column(Text)
    duplicate_type = Column(String(50), nullable=False)  # functional, technical, capability
    overall_similarity = Column(Float, nullable=False)
    
    # Application relationships
    applications = relationship('ApplicationComponent', 
                             secondary='simple_group_applications',
                             backref='simple_duplicate_groups')
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @validates('duplicate_type')
    def validate_duplicate_type(self, key, value):
        return validate_enum(value, ['functional', 'technical', 'capability'], key)

    @validates('overall_similarity')
    def validate_similarity(self, key, value):
        return validate_percentage(value * 100, key) / 100 if value is not None else None

    def __repr__(self):
        return f'<SimpleDuplicateGroup {self.name} ({self.overall_similarity:.2f})>'


# Association table for groups and applications
simple_group_applications = db.Table(
    'simple_group_applications',
    Column('group_id', Integer, ForeignKey('simple_duplicate_groups.id', ondelete='CASCADE'), primary_key=True),
    Column('application_id', Integer, ForeignKey('application_components.id', ondelete='CASCADE'), primary_key=True),
    Column('similarity_score', Float),
    Column('role_in_group', String(20)),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class SimpleDetectionRun(db.Model):
    """
    Simplified detection run tracking
    """
    __tablename__ = 'simple_detection_runs'
    
    id = Column(Integer, primary_key=True)
    run_name = Column(String(256), nullable=False)
    description = Column(Text)
    status = Column(String(20), default='pending')  # pending, running, completed, failed
    similarity_threshold = Column(Float, default=0.7)
    
    # Results
    applications_analyzed = Column(Integer, default=0)
    groups_found = Column(Integer, default=0)
    estimated_savings = Column(Float)
    
    # Metadata
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SimpleDetectionRun {self.run_name} ({self.status})>'
