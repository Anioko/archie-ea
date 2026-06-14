"""
flask add-vendor-seed-column — add spec_data_seed column to vendor_archimate_templates.

db.create_all() does not add columns to existing tables. This command runs
the ALTER TABLE directly. Safe to run multiple times (catches DuplicateColumn).

Usage:
    flask add-vendor-seed-column
"""
import click
from flask.cli import with_appcontext


@click.command("add-vendor-seed-column")
@with_appcontext
def add_vendor_seed_column():
    """Add spec_data_seed column to vendor_archimate_templates (idempotent)."""
    from app import db

    sql = "ALTER TABLE vendor_archimate_templates ADD COLUMN spec_data_seed TEXT"
    try:
        db.session.execute(db.text(sql))  # raw-sql-ok: DDL ALTER TABLE, no ORM model for this op
        db.session.commit()
        click.echo("[OK] spec_data_seed column added to vendor_archimate_templates")
    except Exception as e:
        db.session.rollback()
        msg = str(e).lower()
        if "duplicate column" in msg or "already exists" in msg or "column" in msg:
            click.echo("[SKIP] spec_data_seed column already exists")
        else:
            click.echo(f"[ERROR] {e}")
            raise


def init_app(app):
    app.cli.add_command(add_vendor_seed_column)
