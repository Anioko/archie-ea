"""
Core services shared by both Pipeline and Workflow systems.
Eliminates code duplication and provides consistent behavior.

Includes:
- Retry handling and circuit breakers
- Transaction management
- Execution engine
- Caching infrastructure
- Eager loading utilities
"""
from .async_utils import get_or_create_event_loop, run_async_safely
from .cache_service import CacheService, cache_service
from .data_cache import (
    TTL_APPLICATIONS,
    TTL_CAPABILITIES,
    TTL_FILTERS,
    TTL_METRICS,
    TTL_VENDORS,
    get_all_applications,
    get_all_capabilities,
    get_all_vendors,
    get_application_count,
    get_application_filter_options,
    get_business_capabilities,
    get_cache_stats,
    get_capability_filter_options,
    get_capability_hierarchy,
    get_prompt_templates,
    invalidate_all_caches,
    invalidate_application_cache,
    invalidate_capability_cache,
    invalidate_vendor_cache,
    request_cached,
)
from .eager_loading import (  # Placeholder classes for documentation
    ApplicationQueryOptions,
    ArchiMateQueryOptions,
    CapabilityQueryOptions,
    DuplicateDetectionOptions,
    GapAnalysisOptions,
    VendorQueryOptions,
    get_application_options,
    get_capability_options,
)
from .execution_engine import CostTracker, ExecutionEngine, StageResult
from .retry_handler import (
    CircuitBreaker,
    RetryHandler,
    db_transaction_retry,
    execute_with_db_retry,
    retry_on_transient_error,
)
from .transaction_manager import TransactionManager, pipeline_transaction, transactional

__all__ = [
    # Retry handling
    "RetryHandler",
    "retry_on_transient_error",
    "CircuitBreaker",
    "db_transaction_retry",
    "execute_with_db_retry",
    # Transaction management
    "TransactionManager",
    "pipeline_transaction",
    "transactional",
    # Execution engine
    "ExecutionEngine",
    "CostTracker",
    "StageResult",
    # Async utilities
    "get_or_create_event_loop",
    "run_async_safely",
    # Caching
    "cache_service",
    "CacheService",
    "get_all_capabilities",
    "get_capability_hierarchy",
    "get_business_capabilities",
    "get_all_applications",
    "get_application_count",
    "get_all_vendors",
    "get_application_filter_options",
    "get_capability_filter_options",
    "get_prompt_templates",
    "invalidate_capability_cache",
    "invalidate_application_cache",
    "invalidate_vendor_cache",
    "invalidate_all_caches",
    "get_cache_stats",
    "request_cached",
    "TTL_CAPABILITIES",
    "TTL_APPLICATIONS",
    "TTL_VENDORS",
    "TTL_FILTERS",
    "TTL_METRICS",
    # Eager loading
    "get_application_options",
    "get_capability_options",
    "DuplicateDetectionOptions",
    "ApplicationQueryOptions",
    "CapabilityQueryOptions",
    "ArchiMateQueryOptions",
    "VendorQueryOptions",
    "GapAnalysisOptions",
]
