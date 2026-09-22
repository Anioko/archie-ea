"""
Monitoring module — error aggregation.

The health-check and metrics blueprints once migrated into this package were
never registered by any code path and have been retired; the live health
probes are `app/_bootstrap/routes.py`'s inline `/health` and
`app/routes/health_routes.py`'s `/health/db`, covered by
`tests/test_health_probes.py`. `app.modules.monitoring.routes.error_events_routes`
is this package's one live blueprint, registered directly by
`app/_bootstrap/blueprints.py`.
"""
