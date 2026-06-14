"""
AI Reasoning Infrastructure

Provides resilience, monitoring, caching, and operational capabilities
for the AI reasoning engine.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# CIRCUIT BREAKER PATTERN
# =============================================================================


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 30  # seconds
    half_open_max_calls: int = 3


class CircuitBreaker:
    """
    Circuit breaker for AI agents to handle failures gracefully.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, reject requests immediately
    - HALF_OPEN: Testing if service has recovered
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        self._lock = Lock()

    def can_execute(self) -> Tuple[bool, str]:
        """Check if execution is allowed."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True, "Circuit closed, proceeding normally"

            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self.last_failure_time:
                    elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                    if elapsed >= self.config.recovery_timeout:
                        self.state = CircuitState.HALF_OPEN
                        self.half_open_calls = 0
                        logger.info(f"Circuit {self.name} transitioning to HALF_OPEN")
                        return True, "Circuit half-open, testing recovery"
                return (
                    False,
                    f"Circuit open, service unavailable (retry in {self.config.recovery_timeout - elapsed:.0f}s)",
                )

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls < self.config.half_open_max_calls:
                    self.half_open_calls += 1
                    return True, "Circuit half-open, testing"
                return False, "Circuit half-open, max test calls reached"

            return False, "Unknown circuit state"

    def record_success(self):
        """Record a successful execution."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.half_open_max_calls:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info(f"Circuit {self.name} recovered, transitioning to CLOSED")
            elif self.state == CircuitState.CLOSED:
                self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record a failed execution."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} failed during recovery, back to OPEN")
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit {self.name} opened after {self.failure_count} failures"
                    )

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.breakers = {}
            return cls._instance

    def get_or_create(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, config)
        return self.breakers[name]

    def get_all_status(self) -> Dict[str, Dict]:
        return {name: cb.get_status() for name, cb in self.breakers.items()}


# =============================================================================
# CACHING
# =============================================================================


@dataclass
class CacheEntry:
    value: Any
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class AIAnalysisCache:
    """
    Cache for AI analysis results to avoid redundant computation.

    Uses content-based hashing to cache identical requests.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.cache = {}
                cls._instance.stats = {
                    "hits": 0,
                    "misses": 0,
                    "evictions": 0,
                }
                cls._instance.max_size = 1000
                cls._instance.default_ttl = 3600  # 1 hour
            return cls._instance

    def _generate_key(self, context: Dict) -> str:
        """Generate cache key from context."""
        # Sort keys for consistent hashing
        normalized = json.dumps(context, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]

    def get(self, context: Dict) -> Optional[Dict]:
        """Get cached result if available and not expired."""
        key = self._generate_key(context)

        with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                if not entry.is_expired():
                    entry.hit_count += 1
                    self.stats["hits"] += 1
                    logger.debug(f"Cache hit for key {key[:8]}... (hits: {entry.hit_count})")
                    return entry.value
                else:
                    # Remove expired entry
                    del self.cache[key]
                    self.stats["evictions"] += 1

            self.stats["misses"] += 1
            return None

    def set(self, context: Dict, value: Dict, ttl: int = None):
        """Cache a result."""
        key = self._generate_key(context)
        ttl = ttl or self.default_ttl

        with self._lock:
            # Evict old entries if cache is full
            if len(self.cache) >= self.max_size:
                self._evict_oldest()

            self.cache[key] = CacheEntry(
                value=value,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=ttl),
            )
            logger.debug(f"Cached result for key {key[:8]}...")

    def _evict_oldest(self):
        """Evict oldest entries when cache is full."""
        if not self.cache:
            return

        # Sort by creation time and remove oldest 10%
        sorted_keys = sorted(self.cache.keys(), key=lambda k: self.cache[k].created_at)
        to_evict = max(1, len(sorted_keys) // 10)

        for key in sorted_keys[:to_evict]:
            del self.cache[key]
            self.stats["evictions"] += 1

    def invalidate(self, context: Dict = None):
        """Invalidate cache entries."""
        with self._lock:
            if context:
                key = self._generate_key(context)
                if key in self.cache:
                    del self.cache[key]
            else:
                self.cache.clear()

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total_requests = self.stats["hits"] + self.stats["misses"]
            hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
            return {
                **self.stats,
                "size": len(self.cache),
                "max_size": self.max_size,
                "hit_rate_percent": round(hit_rate, 2),
            }


# =============================================================================
# RATE LIMITING
# =============================================================================


class RateLimiter:
    """
    Token bucket rate limiter for AI API calls.

    Prevents abuse and controls API costs.
    """

    def __init__(
        self, requests_per_minute: int = 60, requests_per_hour: int = 500, burst_limit: int = 10
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_limit = burst_limit
        self.minute_window: Dict[str, List[datetime]] = defaultdict(list)
        self.hour_window: Dict[str, List[datetime]] = defaultdict(list)
        self._lock = Lock()

    def check_limit(self, user_id: str = "default") -> Tuple[bool, str]:
        """Check if request is allowed under rate limits."""
        now = datetime.utcnow()

        with self._lock:
            # Clean old entries
            minute_ago = now - timedelta(minutes=1)
            hour_ago = now - timedelta(hours=1)

            self.minute_window[user_id] = [t for t in self.minute_window[user_id] if t > minute_ago]
            self.hour_window[user_id] = [t for t in self.hour_window[user_id] if t > hour_ago]

            # Check limits
            minute_count = len(self.minute_window[user_id])
            hour_count = len(self.hour_window[user_id])

            if minute_count >= self.requests_per_minute:
                return (
                    False,
                    f"Rate limit exceeded: {minute_count}/{self.requests_per_minute} requests per minute",
                )

            if hour_count >= self.requests_per_hour:
                return (
                    False,
                    f"Rate limit exceeded: {hour_count}/{self.requests_per_hour} requests per hour",
                )

            # Check burst
            recent = [t for t in self.minute_window[user_id] if t > now - timedelta(seconds=10)]
            if len(recent) >= self.burst_limit:
                return False, f"Burst limit exceeded: {len(recent)} requests in 10 seconds"

            return True, "OK"

    def record_request(self, user_id: str = "default"):
        """Record a request."""
        now = datetime.utcnow()
        with self._lock:
            self.minute_window[user_id].append(now)
            self.hour_window[user_id].append(now)

    def get_usage(self, user_id: str = "default") -> Dict:
        """Get current usage for a user."""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        with self._lock:
            minute_count = len([t for t in self.minute_window[user_id] if t > minute_ago])
            hour_count = len([t for t in self.hour_window[user_id] if t > hour_ago])

            return {
                "user_id": user_id,
                "minute_usage": f"{minute_count}/{self.requests_per_minute}",
                "hour_usage": f"{hour_count}/{self.requests_per_hour}",
                "remaining_minute": self.requests_per_minute - minute_count,
                "remaining_hour": self.requests_per_hour - hour_count,
            }


# =============================================================================
# COST TRACKING
# =============================================================================


@dataclass
class CostRecord:
    timestamp: datetime
    operation: str
    agent: str
    tokens_input: int
    tokens_output: int
    cost_usd: float
    user_id: str
    context_hash: str


class CostTracker:
    """
    Track AI API costs for monitoring and budgeting.
    """

    _instance = None
    _lock = Lock()

    # Cost per 1000 tokens (approximate)
    COST_PER_1K_INPUT = 0.01
    COST_PER_1K_OUTPUT = 0.03

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.records: List[CostRecord] = []
                cls._instance.daily_budget = 100.0  # USD
                cls._instance.monthly_budget = 2000.0  # USD
            return cls._instance

    def record_usage(
        self,
        operation: str,
        agent: str,
        tokens_input: int,
        tokens_output: int,
        user_id: str = "system",
        context_hash: str = "",
    ):
        """Record API usage."""
        cost = (
            tokens_input * self.COST_PER_1K_INPUT / 1000
            + tokens_output * self.COST_PER_1K_OUTPUT / 1000
        )

        record = CostRecord(
            timestamp=datetime.utcnow(),
            operation=operation,
            agent=agent,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost,
            user_id=user_id,
            context_hash=context_hash,
        )

        with self._lock:
            self.records.append(record)
            # Keep only last 30 days
            cutoff = datetime.utcnow() - timedelta(days=30)
            self.records = [r for r in self.records if r.timestamp > cutoff]

        logger.debug(f"Recorded cost: ${cost:.4f} for {agent}/{operation}")

    def get_daily_cost(self, date: datetime = None) -> float:
        """Get total cost for a specific day."""
        date = date or datetime.utcnow()
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        with self._lock:
            return sum(r.cost_usd for r in self.records if day_start <= r.timestamp < day_end)

    def get_monthly_cost(self, year: int = None, month: int = None) -> float:
        """Get total cost for a specific month."""
        now = datetime.utcnow()
        year = year or now.year
        month = month or now.month

        with self._lock:
            return sum(
                r.cost_usd
                for r in self.records
                if r.timestamp.year == year and r.timestamp.month == month
            )

    def check_budget(self) -> Tuple[bool, str]:
        """Check if within budget."""
        daily = self.get_daily_cost()
        monthly = self.get_monthly_cost()

        if daily >= self.daily_budget:
            return False, f"Daily budget exceeded: ${daily:.2f}/${self.daily_budget:.2f}"
        if monthly >= self.monthly_budget:
            return False, f"Monthly budget exceeded: ${monthly:.2f}/${self.monthly_budget:.2f}"

        return True, "Within budget"

    def get_summary(self) -> Dict:
        """Get cost summary."""
        daily = self.get_daily_cost()
        monthly = self.get_monthly_cost()

        with self._lock:
            total_tokens_input = sum(r.tokens_input for r in self.records)
            total_tokens_output = sum(r.tokens_output for r in self.records)
            by_agent = defaultdict(float)
            for r in self.records:
                by_agent[r.agent] += r.cost_usd

        return {
            "daily_cost": round(daily, 4),
            "daily_budget": self.daily_budget,
            "daily_remaining": round(self.daily_budget - daily, 4),
            "monthly_cost": round(monthly, 4),
            "monthly_budget": self.monthly_budget,
            "monthly_remaining": round(self.monthly_budget - monthly, 4),
            "total_tokens_input": total_tokens_input,
            "total_tokens_output": total_tokens_output,
            "cost_by_agent": dict(by_agent),
        }


# =============================================================================
# AUDIT TRAIL
# =============================================================================


@dataclass
class AuditEntry:
    timestamp: datetime
    event_type: str
    user_id: str
    operation: str
    context_summary: str
    result_summary: str
    duration_ms: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class AuditTrail:
    """
    Comprehensive audit logging for AI reasoning operations.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.entries: List[AuditEntry] = []
                cls._instance.max_entries = 10000
            return cls._instance

    def log(
        self,
        event_type: str,
        user_id: str,
        operation: str,
        context_summary: str,
        result_summary: str,
        duration_ms: float,
        success: bool,
        error_message: str = None,
        metadata: Dict = None,
    ):
        """Log an audit entry."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            event_type=event_type,
            user_id=user_id,
            operation=operation,
            context_summary=context_summary,
            result_summary=result_summary,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            metadata=metadata or {},
        )

        with self._lock:
            self.entries.append(entry)
            # Trim old entries
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[-self.max_entries :]

        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            f"AUDIT: {event_type} | {operation} | user={user_id} | "
            f"success={success} | duration={duration_ms:.1f}ms",
        )

    def query(
        self,
        event_type: str = None,
        user_id: str = None,
        operation: str = None,
        success: bool = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Query audit entries."""
        with self._lock:
            results = []
            for entry in reversed(self.entries):
                if event_type and entry.event_type != event_type:
                    continue
                if user_id and entry.user_id != user_id:
                    continue
                if operation and entry.operation != operation:
                    continue
                if success is not None and entry.success != success:
                    continue
                if start_time and entry.timestamp < start_time:
                    continue
                if end_time and entry.timestamp > end_time:
                    continue

                results.append(
                    {
                        "timestamp": entry.timestamp.isoformat(),
                        "event_type": entry.event_type,
                        "user_id": entry.user_id,
                        "operation": entry.operation,
                        "context_summary": entry.context_summary,
                        "result_summary": entry.result_summary,
                        "duration_ms": entry.duration_ms,
                        "success": entry.success,
                        "error_message": entry.error_message,
                        "metadata": entry.metadata,
                    }
                )

                if len(results) >= limit:
                    break

            return results

    def get_statistics(self) -> Dict:
        """Get audit statistics."""
        with self._lock:
            if not self.entries:
                return {"total": 0}

            total = len(self.entries)
            successful = sum(1 for e in self.entries if e.success)
            avg_duration = sum(e.duration_ms for e in self.entries) / total

            by_operation = defaultdict(int)
            by_user = defaultdict(int)
            for e in self.entries:
                by_operation[e.operation] += 1
                by_user[e.user_id] += 1

            return {
                "total": total,
                "successful": successful,
                "failed": total - successful,
                "success_rate_percent": round(successful / total * 100, 2),
                "average_duration_ms": round(avg_duration, 2),
                "by_operation": dict(by_operation),
                "by_user": dict(by_user),
            }


# =============================================================================
# MONITORING & OBSERVABILITY
# =============================================================================


@dataclass
class MetricPoint:
    timestamp: datetime
    name: str
    value: float
    labels: Dict[str, str]


class MetricsCollector:
    """
    Collect and expose metrics for monitoring AI reasoning performance.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
                cls._instance.counters: Dict[str, int] = defaultdict(int)
                cls._instance.gauges: Dict[str, float] = defaultdict(float)
                cls._instance.histograms: Dict[str, List[float]] = defaultdict(list)
            return cls._instance

    def increment(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Increment a counter."""
        key = f"{name}_{json.dumps(labels or {}, sort_keys=True)}"
        with self._lock:
            self.counters[key] += value

    def gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge value."""
        key = f"{name}_{json.dumps(labels or {}, sort_keys=True)}"
        with self._lock:
            self.gauges[key] = value

    def histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram value."""
        key = f"{name}_{json.dumps(labels or {}, sort_keys=True)}"
        with self._lock:
            self.histograms[key].append(value)
            # Keep only last 1000 values
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]

    def record(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a metric point."""
        point = MetricPoint(
            timestamp=datetime.utcnow(),
            name=name,
            value=value,
            labels=labels or {},
        )
        with self._lock:
            self.metrics[name].append(point)
            # Keep only last 24 hours
            cutoff = datetime.utcnow() - timedelta(hours=24)
            self.metrics[name] = [p for p in self.metrics[name] if p.timestamp > cutoff]

    def get_metrics(self) -> Dict:
        """Get all current metrics."""
        with self._lock:
            # Calculate histogram percentiles
            histogram_stats = {}
            for key, values in self.histograms.items():
                if values:
                    sorted_values = sorted(values)
                    n = len(sorted_values)
                    histogram_stats[key] = {
                        "count": n,
                        "min": sorted_values[0],
                        "max": sorted_values[-1],
                        "avg": sum(values) / n,
                        "p50": sorted_values[int(n * 0.5)],
                        "p95": sorted_values[int(n * 0.95)],
                        "p99": sorted_values[int(n * 0.99)] if n > 100 else sorted_values[-1],
                    }

            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": histogram_stats,
            }


# =============================================================================
# OUTPUT VALIDATION
# =============================================================================


class OutputValidator:
    """
    Validate AI agent outputs for consistency and quality.
    """

    @staticmethod
    def validate_pattern_recognition(result: Dict) -> Tuple[bool, List[str]]:
        """Validate pattern recognition output."""
        errors = []

        if not isinstance(result, dict):
            return False, ["Result must be a dictionary"]

        if "patterns" not in result:
            errors.append("Missing 'patterns' key")
        elif not isinstance(result["patterns"], list):
            errors.append("'patterns' must be a list")
        else:
            for i, pattern in enumerate(result["patterns"]):
                if not isinstance(pattern, dict):
                    errors.append(f"Pattern {i} must be a dictionary")
                    continue
                if "name" not in pattern:
                    errors.append(f"Pattern {i} missing 'name'")
                if "confidence" in pattern:
                    if not 0 <= pattern["confidence"] <= 1:
                        errors.append(f"Pattern {i} confidence must be between 0 and 1")

        return len(errors) == 0, errors

    @staticmethod
    def validate_risk_assessment(result: Dict) -> Tuple[bool, List[str]]:
        """Validate risk assessment output."""
        errors = []

        if not isinstance(result, dict):
            return False, ["Result must be a dictionary"]

        if "risks" not in result:
            errors.append("Missing 'risks' key")
        elif not isinstance(result["risks"], list):
            errors.append("'risks' must be a list")
        else:
            for i, risk in enumerate(result["risks"]):
                if not isinstance(risk, dict):
                    errors.append(f"Risk {i} must be a dictionary")
                    continue
                if "description" not in risk:
                    errors.append(f"Risk {i} missing 'description'")
                if "impact" in risk and not 0 <= risk.get("impact", 0) <= 1:
                    errors.append(f"Risk {i} impact must be between 0 and 1")

        return len(errors) == 0, errors

    @staticmethod
    def validate_technology_selection(result: Dict) -> Tuple[bool, List[str]]:
        """Validate technology selection output."""
        errors = []

        if not isinstance(result, dict):
            return False, ["Result must be a dictionary"]

        if "recommendations" not in result:
            errors.append("Missing 'recommendations' key")
        elif not isinstance(result["recommendations"], list):
            errors.append("'recommendations' must be a list")
        else:
            valid_categories = {
                "frontend",
                "backend",
                "database",
                "messaging",
                "cloud",
                "monitoring",
            }
            for i, rec in enumerate(result["recommendations"]):
                if not isinstance(rec, dict):
                    errors.append(f"Recommendation {i} must be a dictionary")
                    continue
                if "technology" not in rec:
                    errors.append(f"Recommendation {i} missing 'technology'")
                if "category" in rec and rec["category"] not in valid_categories:
                    errors.append(f"Recommendation {i} has invalid category: {rec['category']}")

        return len(errors) == 0, errors

    @staticmethod
    def check_cross_agent_consistency(results: Dict[str, Dict]) -> Tuple[bool, List[str]]:
        """Check consistency across agent outputs."""
        warnings = []

        # Check pattern vs technology alignment
        patterns = results.get("pattern_recognition", {}).get("patterns", [])
        tech_recs = results.get("technology_selection", {}).get("recommendations", [])

        pattern_names = {p.get("name", "").lower() for p in patterns}

        # Microservices pattern should align with container/orchestration tech
        if "microservices" in pattern_names:
            container_techs = {"kubernetes", "docker", "ecs", "eks", "gke"}
            has_container = any(
                t.get("technology", "").lower() in container_techs for t in tech_recs
            )
            if not has_container:
                warnings.append(
                    "Microservices pattern identified but no container orchestration recommended"
                )

        # Check risk vs quality alignment
        risks = results.get("risk_assessment", {}).get("risks", [])
        quality = results.get("quality_optimization", {}).get("optimization_recommendations", [])

        high_risks = [r for r in risks if r.get("impact", 0) > 0.7]
        if high_risks and not quality:
            warnings.append(
                f"{len(high_risks)} high-impact risks identified but no quality optimizations suggested"
            )

        return len(warnings) == 0, warnings


# =============================================================================
# EXPLAINABILITY
# =============================================================================


class ExplainabilityEnhancer:
    """
    Enhance AI outputs with clear explanations.
    """

    @staticmethod
    def explain_pattern_selection(pattern: Dict, context: Dict) -> Dict:
        """Add explanation to pattern selection."""
        explanation = {
            "why_selected": [],
            "confidence_factors": [],
            "context_match": [],
        }

        name = pattern.get("name", "")
        confidence = pattern.get("confidence", 0)

        # Explain why selected
        if confidence > 0.8:
            explanation["why_selected"].append(
                f"Strong match ({confidence:.0%} confidence) based on description keywords"
            )
        elif confidence > 0.5:
            explanation["why_selected"].append(
                f"Moderate match ({confidence:.0%} confidence) based on solution characteristics"
            )

        # Confidence factors
        desc = context.get("solution_description", "").lower()
        if name.lower() in desc:
            explanation["confidence_factors"].append(
                f"Pattern name '{name}' explicitly mentioned in description"
            )

        # Context match
        user_count = context.get("user_count", 0)
        if name == "microservices" and user_count > 1000:
            explanation["context_match"].append(
                f"High user count ({user_count}) supports distributed architecture"
            )

        return {**pattern, "explanation": explanation}

    @staticmethod
    def explain_risk_score(risk: Dict, context: Dict) -> Dict:
        """Add explanation to risk assessment."""
        explanation = {
            "impact_factors": [],
            "probability_factors": [],
            "mitigation_rationale": [],
        }

        impact = risk.get("impact", 0)
        probability = risk.get("probability", 0)

        # Impact factors
        if context.get("is_critical"):
            explanation["impact_factors"].append(
                "System marked as critical increases impact severity"
            )

        if impact > 0.7:
            explanation["impact_factors"].append("High impact due to potential business disruption")

        # Probability factors
        timeline = context.get("timeline_months", 12)
        if timeline < 6 and probability > 0.5:
            explanation["probability_factors"].append(
                f"Short timeline ({timeline} months) increases likelihood"
            )

        # Mitigation rationale
        mitigation = risk.get("mitigation", "")
        if mitigation:
            explanation["mitigation_rationale"].append(f"Recommended: {mitigation}")

        return {**risk, "explanation": explanation}

    @staticmethod
    def explain_technology_choice(tech: Dict, context: Dict) -> Dict:
        """Add explanation to technology choice."""
        explanation = {
            "selection_criteria": [],
            "fit_factors": [],
            "alternatives_considered": [],
        }

        score = tech.get("score", tech.get("fit_score", 0))
        category = tech.get("category", "")

        # Selection criteria
        if score > 0.7:
            explanation["selection_criteria"].append(
                f"High fit score ({score:.0%}) for {category} requirements"
            )

        # Fit factors
        org_size = context.get("organization_size", "")
        if org_size == "enterprise":
            explanation["fit_factors"].append("Enterprise-ready features considered")
        elif org_size == "smb":
            explanation["fit_factors"].append("Ease of use and cost-effectiveness prioritized")

        return {**tech, "explanation": explanation}


# =============================================================================
# FEEDBACK LOOP
# =============================================================================


@dataclass
class FeedbackRecord:
    timestamp: datetime
    analysis_id: str
    user_id: str
    recommendation_type: str
    recommendation_id: str
    feedback_type: str  # "helpful", "not_helpful", "implemented", "rejected"
    rating: Optional[int]  # 1 - 5
    comment: Optional[str]
    outcome: Optional[str]  # "success", "partial", "failed" - tracked later


class FeedbackCollector:
    """
    Collect and analyze user feedback on AI recommendations.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.feedback: List[FeedbackRecord] = []
            return cls._instance

    def record_feedback(
        self,
        analysis_id: str,
        user_id: str,
        recommendation_type: str,
        recommendation_id: str,
        feedback_type: str,
        rating: int = None,
        comment: str = None,
    ):
        """Record user feedback."""
        record = FeedbackRecord(
            timestamp=datetime.utcnow(),
            analysis_id=analysis_id,
            user_id=user_id,
            recommendation_type=recommendation_type,
            recommendation_id=recommendation_id,
            feedback_type=feedback_type,
            rating=rating,
            comment=comment,
            outcome=None,
        )

        with self._lock:
            self.feedback.append(record)

        logger.info(
            f"Feedback recorded: {feedback_type} for {recommendation_type}/{recommendation_id}"
        )

    def record_outcome(self, analysis_id: str, recommendation_id: str, outcome: str):
        """Record outcome of implemented recommendation."""
        with self._lock:
            for record in self.feedback:
                if (
                    record.analysis_id == analysis_id
                    and record.recommendation_id == recommendation_id
                    and record.feedback_type == "implemented"
                ):
                    record.outcome = outcome
                    logger.info(f"Outcome recorded: {outcome} for {recommendation_id}")
                    return True
        return False

    def get_recommendation_stats(self, recommendation_type: str = None) -> Dict:
        """Get statistics on recommendation feedback."""
        with self._lock:
            relevant = [
                f
                for f in self.feedback
                if recommendation_type is None or f.recommendation_type == recommendation_type
            ]

            if not relevant:
                return {"total": 0}

            total = len(relevant)
            helpful = sum(1 for f in relevant if f.feedback_type == "helpful")
            implemented = sum(1 for f in relevant if f.feedback_type == "implemented")
            successful = sum(1 for f in relevant if f.outcome == "success")

            ratings = [f.rating for f in relevant if f.rating is not None]
            avg_rating = sum(ratings) / len(ratings) if ratings else None

            return {
                "total": total,
                "helpful_rate": round(helpful / total * 100, 2) if total > 0 else 0,
                "implementation_rate": round(implemented / total * 100, 2) if total > 0 else 0,
                "success_rate": round(successful / implemented * 100, 2) if implemented > 0 else 0,
                "average_rating": round(avg_rating, 2) if avg_rating else None,
            }


# =============================================================================
# DECORATORS FOR INSTRUMENTATION
# =============================================================================


def with_circuit_breaker(breaker_name: str):
    """Decorator to add circuit breaker to async functions."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            registry = CircuitBreakerRegistry()
            breaker = registry.get_or_create(breaker_name)

            can_execute, reason = breaker.can_execute()
            if not can_execute:
                logger.warning(f"Circuit breaker {breaker_name}: {reason}")
                return {"success": False, "error": reason, "circuit_breaker": True}

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        return wrapper

    return decorator


def with_caching(ttl: int = 3600):
    """Decorator to add caching to async functions."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = AIAnalysisCache()

            # Build cache key from kwargs (assuming context is in kwargs)
            context = kwargs.get("context") or (args[1] if len(args) > 1 else {})

            # Check cache
            cached = cache.get(context)
            if cached:
                cached["from_cache"] = True
                return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Cache successful results
            if result.get("success"):
                cache.set(context, result, ttl)

            return result

        return wrapper

    return decorator


def with_metrics(operation_name: str):
    """Decorator to add metrics collection to async functions."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            metrics = MetricsCollector()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000

                metrics.increment(f"{operation_name}_total", labels={"status": "success"})
                metrics.histogram(f"{operation_name}_duration_ms", duration)

                return result
            except Exception as e:
                metrics.increment(f"{operation_name}_total", labels={"status": "error"})
                raise

        return wrapper

    return decorator


def with_audit(operation_name: str, user_id_param: str = "user_id"):
    """Decorator to add audit logging to async functions."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            audit = AuditTrail()
            start_time = time.time()

            user_id = kwargs.get(user_id_param, "system")
            context = kwargs.get("context", {})
            context_summary = context.get("solution_description", "")[:100] if context else ""

            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000

                success = result.get("success", True) if isinstance(result, dict) else True
                result_summary = (
                    f"Recommendations: {len(result.get('recommendations', []))}"
                    if isinstance(result, dict)
                    else "OK"
                )

                audit.log(
                    event_type="ai_analysis",
                    user_id=user_id,
                    operation=operation_name,
                    context_summary=context_summary,
                    result_summary=result_summary,
                    duration_ms=duration,
                    success=success,
                )

                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                audit.log(
                    event_type="ai_analysis",
                    user_id=user_id,
                    operation=operation_name,
                    context_summary=context_summary,
                    result_summary="",
                    duration_ms=duration,
                    success=False,
                    error_message=str(e),
                )
                raise

        return wrapper

    return decorator
