"""Alembic environment for Flask-Migrate.

Runs every revision in its own transaction (``transaction_per_migration``), so
a failing revision rolls back alone and the revisions before it stay recorded.
PostgreSQL DDL is transactional, so a failed revision leaves no partial change.

Only ``migrations/versions/*.py`` is on the chain. The pre-baseline history in
``migrations/versions/_archive_pre_baseline/`` is kept for reference and is not
loaded (Alembic does not recurse into subdirectories by default).
"""
import logging

from alembic import context
from flask import current_app

config = context.config

# Not calling logging.config.fileConfig(config.config_file_name) here: this
# env.py runs inside an existing Flask app context (every function below
# reads current_app), which means the app's own logging -- level, handlers,
# any structured/error-reporting handler wired up at boot -- is already
# configured by the time Alembic reaches this module. fileConfig() reads
# alembic.ini's generic [loggers]/[handlers]/[formatters] template and would
# reconfigure the root logger from it, silently discarding whatever the app
# set up, on every deploy's schema-upgrade run.
logger = logging.getLogger("alembic.env")


def _db():
    return current_app.extensions["migrate"].db


def _metadata():
    return _db().metadata


def run_migrations_offline():
    """Emit SQL to stdout instead of executing it (``flask db upgrade --sql``)."""
    url = str(_db().engine.url.render_as_string(hide_password=False)).replace("%", "%%")
    context.configure(
        url=url,
        target_metadata=_metadata(),
        literal_binds=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = _db().engine
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=_metadata(),
            transaction_per_migration=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
