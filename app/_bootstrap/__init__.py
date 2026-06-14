"""
Bootstrap helpers for app factory.

These modules decompose the monolithic create_app() function into focused
helpers. Each module exposes a single ``init_*(app)`` function that is
called in sequence by ``create_app()`` in ``app/__init__.py``.
"""
