"""
Mapping Metrics Model for Gap Analysis

Tracks success/failure of vendor and APQC mapping operations
to enable continuous improvement of heuristic dictionaries.
"""

from datetime import datetime

from sqlalchemy import func

from app import db


class MappingMetric(db.Model):
    """Track mapping success/failure for gap analysis."""

    __tablename__ = "mapping_metrics"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, index=True)  # No FK constraint for easier migration
    mapping_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # 'vendor', 'apqc', 'capability'
    source = db.Column(db.String(50), nullable=False)  # 'heuristic', 'llm', 'manual', 'import'
    success = db.Column(db.Boolean, default=False, index=True)
    matched_value = db.Column(db.String(255))
    confidence = db.Column(db.Float)
    failure_reason = db.Column(db.Text)
    app_name = db.Column(db.String(255))  # Denormalized for quick queries
    app_description = db.Column(db.Text)  # For analyzing what patterns failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "application_id": self.application_id,
            "mapping_type": self.mapping_type,
            "source": self.source,
            "success": self.success,
            "matched_value": self.matched_value,
            "confidence": self.confidence,
            "failure_reason": self.failure_reason,
            "app_name": self.app_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def log_result(
        cls,
        application_id: int,
        mapping_type: str,
        source: str,
        success: bool,
        matched_value: str = None,
        confidence: float = None,
        failure_reason: str = None,
        app_name: str = None,
        app_description: str = None,
    ):
        """
        Log a mapping attempt for gap analysis.

        Args:
            application_id: ID of the application being mapped
            mapping_type: 'vendor', 'apqc', or 'capability'
            source: 'heuristic', 'llm', 'manual', or 'import'
            success: Whether the mapping succeeded
            matched_value: The value that was matched (e.g., vendor name, APQC code)
            confidence: Confidence score (0 - 1) for LLM mappings
            failure_reason: Why the mapping failed (for failures)
            app_name: Application name (denormalized for quick queries)
            app_description: Application description (for pattern analysis)
        """
        metric = cls(
            application_id=application_id,
            mapping_type=mapping_type,
            source=source,
            success=success,
            matched_value=matched_value,
            confidence=confidence,
            failure_reason=failure_reason,
            app_name=app_name,
            app_description=app_description[:500] if app_description else None,
        )
        db.session.add(metric)
        # Don't commit - let the parent transaction handle it
        return metric

    @classmethod
    def get_success_rates(cls):
        """Get success rates by mapping type and source."""
        from sqlalchemy import case

        results = (
            db.session.query(
                cls.mapping_type,
                cls.source,
                func.count().label("total"),
                func.sum(case((cls.success == True, 1), else_=0)).label("successes"),
            )
            .group_by(cls.mapping_type, cls.source)
            .all()
        )

        return [
            {
                "mapping_type": r.mapping_type,
                "source": r.source,
                "total": r.total,
                "successes": r.successes,
                "success_rate": round(r.successes / r.total * 100, 1) if r.total > 0 else 0,
            }
            for r in results
        ]

    @classmethod
    def get_common_failures(cls, limit: int = 20):
        """Get most common failure reasons for gap analysis."""
        results = (
            db.session.query(
                cls.mapping_type,
                cls.failure_reason,
                cls.app_name,
                cls.app_description,
                func.count().label("count"),
            )
            .filter(cls.success == False, cls.failure_reason.isnot(None))
            .group_by(cls.mapping_type, cls.failure_reason, cls.app_name, cls.app_description)
            .order_by(func.count().desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "mapping_type": r.mapping_type,
                "failure_reason": r.failure_reason,
                "app_name": r.app_name,
                "app_description": r.app_description[:100] if r.app_description else None,
                "count": r.count,
            }
            for r in results
        ]

    @classmethod
    def get_unmatched_apps(cls, mapping_type: str = None, limit: int = 50):
        """Get applications that failed to match, for dictionary expansion."""
        query = (
            db.session.query(
                cls.app_name, cls.app_description, cls.mapping_type, cls.failure_reason
            )
            .filter(cls.success == False)
            .distinct()
        )

        if mapping_type:
            query = query.filter(cls.mapping_type == mapping_type)

        return query.limit(limit).all()
