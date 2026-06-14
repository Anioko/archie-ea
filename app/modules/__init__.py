"""
Feature modules package.

Each sub-package is a self-contained feature domain with its own:
- routes/   (Flask blueprints)
- services/ (business logic)
- models/   (SQLAlchemy models, if module-owned)
- schemas/  (request/response validation)
- tests/    (module-specific tests)

Every module exposes a ``register(app)`` function in its __init__.py
that the application factory calls during startup.
"""
