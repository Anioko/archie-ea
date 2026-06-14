"""
flask add-integration-flow-columns — add pattern_id and governance_status columns
to the existing solution_integration_flows table.

Cannot use db.create_all() for existing tables. This command runs raw ALTER TABLE
statements with IF NOT EXISTS so it is safe to run multiple times.

Usage:
    flask add-integration-flow-columns
"""
import click
from flask.cli import with_appcontext

from app import db

_ALTER_STATEMENTS = [
    (
        "pattern_id",
        "ALTER TABLE solution_integration_flows "
        "ADD COLUMN IF NOT EXISTS pattern_id INTEGER "
        "REFERENCES integration_patterns(id);",
    ),
    (
        "governance_status",
        "ALTER TABLE solution_integration_flows "
        "ADD COLUMN IF NOT EXISTS governance_status VARCHAR(30) DEFAULT 'undocumented';",
    ),
]


@click.command("add-integration-flow-columns")
@with_appcontext
def add_integration_flow_columns():
    """Add pattern_id and governance_status columns to solution_integration_flows (idempotent)."""
    from sqlalchemy import text

    errors = []
    for column_name, sql in _ALTER_STATEMENTS:
        try:
            db.session.execute(text(sql))
            db.session.commit()
            click.echo(f"  [OK] column '{column_name}' added (or already exists)")
        except Exception as exc:
            db.session.rollback()
            errors.append((column_name, str(exc)))
            click.echo(f"  [ERROR] column '{column_name}': {exc}")

    if errors:
        click.echo(f"\nCompleted with {len(errors)} error(s). Check output above.")
    else:
        click.echo("\nDone — both columns present on solution_integration_flows.")


def init_app(app):
    """Register add-integration-flow-columns CLI command."""
    app.cli.add_command(add_integration_flow_columns)
