"""
Usage Analytics Model for tracking PARTIAL feature usage.

Tracks page views, feature interactions, and errors for all 32 PARTIAL features
to establish usage baselines before committing to 278-hour completion roadmap.
"""
from datetime import datetime
from flask import current_app
from app.extensions import db


class UsageAnalytics(db.Model):
    """Tracks usage events for PARTIAL features."""

    __tablename__ = "usage_analytics"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_id = db.Column(db.String(255), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)  # page_view, feature_interaction, error_occurred
    feature_name = db.Column(db.String(100), nullable=False, index=True)  # e.g., 'batch_import_routes'
    route_path = db.Column(db.String(255), nullable=False)  # e.g., '/batch-import/upload'
    user_agent = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible
    referrer = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_metadata = db.Column(db.JSON, nullable=True)  # Additional event data

    # Relationships
    user = db.relationship('User', backref=db.backref('usage_events', lazy='dynamic'))

    def __repr__(self):
        return f'<UsageAnalytics {self.event_type} {self.feature_name} {self.timestamp}>'

    @classmethod
    def track_event(cls, event_type, feature_name, route_path, user_id=None,
                   session_id=None, event_metadata=None, request=None):
        """Track a usage event."""
        if not current_app.config.get('ENABLE_USAGE_ANALYTICS', False):
            return None

        # Extract request data if available
        user_agent = None
        ip_address = None
        referrer = None

        if request:
            user_agent = request.headers.get('User-Agent')
            ip_address = request.remote_addr
            referrer = request.referrer

        event = cls(
            user_id=user_id,
            session_id=session_id or 'anonymous',
            event_type=event_type,
            feature_name=feature_name,
            route_path=route_path,
            user_agent=user_agent,
            ip_address=ip_address,
            referrer=referrer,
            event_metadata=metadata or {}
        )

        try:
            db.session.add(event)
            db.session.commit()
            return event
        except Exception as e:
            current_app.logger.warning(f"Failed to track usage event: {e}")
            db.session.rollback()
            return None

    @classmethod
    def get_usage_summary(cls, feature_name=None, days=30):
        """Get usage summary for dashboard."""
        from datetime import datetime, timedelta
        from sqlalchemy import func

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = db.session.query(
            cls.feature_name,
            cls.event_type,
            func.count(cls.id).label('count'),
            func.count(func.distinct(cls.user_id)).label('unique_users'),
            func.count(func.distinct(cls.session_id)).label('unique_sessions')
        ).filter(cls.timestamp >= cutoff_date)

        if feature_name:
            query = query.filter(cls.feature_name == feature_name)

        query = query.group_by(cls.feature_name, cls.event_type)

        results = query.all()

        # Organize by feature
        summary = {}
        for feature, event_type, count, unique_users, unique_sessions in results:
            if feature not in summary:
                summary[feature] = {
                    'total_events': 0,
                    'unique_users': 0,
                    'unique_sessions': 0,
                    'events': {}
                }

            summary[feature]['events'][event_type] = {
                'count': count,
                'unique_users': unique_users,
                'unique_sessions': unique_sessions
            }
            summary[feature]['total_events'] += count
            summary[feature]['unique_users'] = max(summary[feature]['unique_users'], unique_users)
            summary[feature]['unique_sessions'] = max(summary[feature]['unique_sessions'], unique_sessions)

        return summary