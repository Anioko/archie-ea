import time
from datetime import datetime, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.usage_event import UsageEvent
from app.models.usage_analytics import UsageAnalytics

class PlatformHealthService:
    def get_health_summary(self):
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        # Uptime: assume error logs in AuditLog with action='error' or event_type='error_occurred' in UsageAnalytics
        total_minutes = 24 * 60
        error_minutes = (
            db.session.query(func.count())
            .select_from(AuditLog)
            .filter(AuditLog.action == 'error', AuditLog.created_at >= day_ago)
            .scalar()
        )
        uptime_pct = 100.0 - (error_minutes / total_minutes * 100.0) if total_minutes else 100.0
        # Error rate: errors per 1000 API calls
        total_api_calls = (
            db.session.query(func.count())
            .select_from(UsageEvent)
            .filter(UsageEvent.event_type == 'api_call', UsageEvent.recorded_at >= day_ago)
            .scalar()
        )
        error_count = (
            db.session.query(func.count())
            .select_from(UsageAnalytics)
            .filter(UsageAnalytics.event_type == 'error_occurred', UsageAnalytics.timestamp >= day_ago)
            .scalar()
        )
        error_rate = (error_count / total_api_calls * 1000.0) if total_api_calls else 0.0
        # Latency: average from UsageAnalytics.event_metadata['latency_ms']
        avg_latency_ms = (
            db.session.query(func.avg(UsageAnalytics.event_metadata['latency_ms'].as_integer()))
            .filter(UsageAnalytics.timestamp >= day_ago, UsageAnalytics.event_metadata['latency_ms'] != None)
            .scalar()
        ) or 0.0
        # Active users: unique user_ids in UsageEvent in last 24h
        active_users_24h = (
            db.session.query(func.count(func.distinct(UsageEvent.user_id)))
            .filter(UsageEvent.recorded_at >= day_ago)
            .scalar()
        )
        # API calls: count UsageEvent.event_type == 'api_call' in last 24h
        api_calls_24h = total_api_calls
        return {
            'uptime_pct': round(uptime_pct, 2),
            'error_rate': round(error_rate, 2),
            'avg_latency_ms': round(avg_latency_ms, 2),
            'active_users_24h': active_users_24h,
            'api_calls_24h': api_calls_24h,
        }

    def get_component_status(self):
        now = datetime.utcnow()
        # Simulate checks for DB, Redis, Stripe, ServiceNow
        components = []
        # DB
        try:
            db.session.execute(db.text('SELECT 1'))
            db_status = 'healthy'
        except Exception:
            db_status = 'down'
        components.append({'name': 'Database', 'status': db_status, 'last_checked': now})
        # Redis
        try:
            import redis
            r = redis.Redis()
            r.ping()
            redis_status = 'healthy'
        except Exception:
            redis_status = 'down'
        components.append({'name': 'Redis', 'status': redis_status, 'last_checked': now})
        # Stripe
        try:
            import stripe
            stripe.Balance.retrieve()
            stripe_status = 'healthy'
        except Exception:
            stripe_status = 'down'
        components.append({'name': 'Stripe', 'status': stripe_status, 'last_checked': now})
        # ServiceNow (simulate)
        try:
            # Replace with real check if available
            servicenow_status = 'healthy'
        except Exception:
            servicenow_status = 'down'
        components.append({'name': 'ServiceNow', 'status': servicenow_status, 'last_checked': now})
        return components

    def get_error_trend(self, hours=24):
        now = datetime.utcnow()
        trend = []
        for h in range(hours):
            start = now - timedelta(hours=h+1)
            end = now - timedelta(hours=h)
            count = (
                db.session.query(func.count())
                .select_from(UsageAnalytics)
                .filter(UsageAnalytics.event_type == 'error_occurred', UsageAnalytics.timestamp >= start, UsageAnalytics.timestamp < end)
                .scalar()
            )
            trend.append({'hour': end.strftime('%H:00'), 'error_count': count})
        trend.reverse()
        return trend

platform_health_service = PlatformHealthService()
