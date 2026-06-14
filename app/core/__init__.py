"""
Core infrastructure package.

Contains shared infrastructure used by all modules:
- database: BaseModel, mixins, repository pattern
- api: Standardized response format, pagination
- auth: Decorators, models, service
- security: Rate limiting, CSRF, validation
- errors: Custom exceptions, error handlers, exception mappers
- middleware: Analytics, feature flags
- validation: Declarative schemas, query parameter validation
- observability: Structured logging, request metrics
- decorators: Composable guardrail decorators for new modules
- compat: Legacy compatibility layer (bridge responses, safe wrappers)
"""
