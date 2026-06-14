"""Add currency columns to existing tables

Revision ID: add_currency_columns
Revises: latest
Create Date: 2026-01-15 19:03:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_currency_columns"
down_revision = "latest"  # This will be updated by Alembic
branch_labels = None
depends_on = None


def upgrade():
    """Add currency columns to tables that have monetary amounts"""

    # Check if currency_code column already exists before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Add to application_portfolio table if cost columns exist
    if "application_portfolio" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("application_portfolio")]
        if "annual_cost" in columns and "currency_code" not in columns:
            op.add_column(
                "application_portfolio",
                sa.Column("currency_code", sa.String(3), nullable=True, default="GBP"),
            )
            op.execute(
                "UPDATE application_portfolio SET currency_code = 'GBP' WHERE currency_code IS NULL"
            )

        if "license_cost" in columns and "license_currency_code" not in columns:
            op.add_column(
                "application_portfolio",
                sa.Column("license_currency_code", sa.String(3), nullable=True, default="GBP"),
            )
            op.execute(
                "UPDATE application_portfolio SET license_currency_code = 'GBP' WHERE license_currency_code IS NULL"
            )

    # Add to vendor_organization table if cost columns exist
    if "vendor_organization" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("vendor_organization")]
        if "annual_cost" in columns and "currency_code" not in columns:
            op.add_column(
                "vendor_organization",
                sa.Column("currency_code", sa.String(3), nullable=True, default="GBP"),
            )
            op.execute(
                "UPDATE vendor_organization SET currency_code = 'GBP' WHERE currency_code IS NULL"
            )

    # Add to any other monetary tables
    monetary_tables = {
        "work_package": ["estimated_cost", "actual_cost"],
        "roadmap_task": ["estimated_cost", "actual_cost"],
        "capability_investment": ["estimated_cost", "actual_cost"],
    }

    for table_name, cost_columns in monetary_tables.items():
        if table_name in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns(table_name)]
            has_monetary = any(col in columns for col in cost_columns)
            if has_monetary and "currency_code" not in columns:
                op.add_column(
                    table_name,
                    sa.Column("currency_code", sa.String(3), nullable=True, default="GBP"),
                )
                op.execute(
                    f"UPDATE {table_name} SET currency_code = 'GBP' WHERE currency_code IS NULL"
                )


def downgrade():
    """Remove currency columns"""

    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Remove currency columns from all tables
    tables_to_check = [
        "application_portfolio",
        "vendor_organization",
        "work_package",
        "roadmap_task",
        "capability_investment",
    ]

    for table_name in tables_to_check:
        if table_name in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns(table_name)]

            if "currency_code" in columns:
                op.drop_column(table_name, "currency_code")
            if "license_currency_code" in columns:
                op.drop_column(table_name, "license_currency_code")
