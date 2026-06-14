"""
CLI commands for profiling database tables and running read-only queries.

Provides two commands:
  flask data-profile  — profile field distributions for any table
  flask db-query      — execute a read-only SELECT query
"""

import click
from flask.cli import with_appcontext


@click.command("data-profile")
@click.option("--table", default="application_components", help="Table name to profile.")
@click.option("--fields", default=None, help="Comma-separated field names. If omitted, profiles all string/numeric columns.")
@with_appcontext
def data_profile_cmd(table, fields):
    """Profile field distributions for a database table."""
    from app import db
    from sqlalchemy import inspect, text

    engine = db.engine
    insp = inspect(engine)

    # Validate table exists
    available_tables = insp.get_table_names()
    if table not in available_tables:
        click.echo(f"ERROR: Table '{table}' not found.")
        click.echo(f"Available tables ({len(available_tables)}): {', '.join(sorted(available_tables)[:20])}...")
        raise SystemExit(1)

    # Get columns
    columns = insp.get_columns(table)
    col_map = {c["name"]: c for c in columns}

    if fields:
        field_list = [f.strip() for f in fields.split(",") if f.strip()]
        missing = [f for f in field_list if f not in col_map]
        if missing:
            click.echo(f"ERROR: Fields not found in '{table}': {', '.join(missing)}")
            click.echo(f"Available: {', '.join(sorted(col_map.keys()))}")
            raise SystemExit(1)
    else:
        # Profile all string and numeric columns (skip large text/blob)
        profileable_types = {"VARCHAR", "TEXT", "STRING", "INTEGER", "FLOAT",
                             "NUMERIC", "DECIMAL", "SMALLINT", "BIGINT", "REAL",
                             "DOUBLE", "BOOLEAN", "CHAR", "NVARCHAR"}
        field_list = []
        for c in columns:
            type_name = str(c["type"]).split("(")[0].upper()
            if type_name in profileable_types:
                field_list.append(c["name"])

    if not field_list:
        click.echo(f"No profileable fields found in '{table}'.")
        raise SystemExit(1)

    # Get total row count
    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()  # noqa: S608  # tenant-exempt: CLI command
    click.echo(f"\nTable: {table} ({total} rows)")
    click.echo("=" * 70)

    numeric_types = {"INTEGER", "FLOAT", "NUMERIC", "DECIMAL", "SMALLINT",
                     "BIGINT", "REAL", "DOUBLE"}

    for field in field_list:
        col_info = col_map[field]
        type_name = str(col_info["type"]).split("(")[0].upper()
        is_numeric = type_name in numeric_types

        click.echo(f"\n--- {field} ({col_info['type']}) ---")

        with engine.connect() as conn:
            if is_numeric:
                # Numeric: min, max, avg, null count
                stats_sql = text(
                    f"SELECT min({field}), max({field}), avg({field}), "  # noqa: S608
                    f"sum(CASE WHEN {field} IS NULL THEN 1 ELSE 0 END), "
                    f"count(*) FROM {table}"
                )
                row = conn.execute(stats_sql).fetchone()
                min_val, max_val, avg_val, null_count, total_count = row
                non_null = total_count - null_count
                click.echo(f"  Min: {min_val}  Max: {max_val}  Avg: {avg_val}")
                click.echo(f"  Non-null: {non_null}/{total_count} ({100*non_null//max(total_count,1)}%)")
                click.echo(f"  NULL: {null_count}")

            # Value distribution (top 20)
            dist_sql = text(
                f"SELECT {field}, count(*) as cnt FROM {table} "  # noqa: S608
                f"GROUP BY {field} ORDER BY cnt DESC LIMIT 20"
            )
            rows = conn.execute(dist_sql).fetchall()

            if not rows:
                click.echo("  (no data)")
                continue

            # Format as table
            max_val_len = max(len(str(r[0]) if r[0] is not None else "NULL") for r in rows)
            max_val_len = max(max_val_len, 5)  # minimum width
            header = f"  {'Value':<{max_val_len}}  {'Count':>8}  {'%':>6}"
            click.echo(header)
            click.echo(f"  {'-'*max_val_len}  {'-'*8}  {'-'*6}")
            for val, cnt in rows:
                display_val = str(val) if val is not None else "NULL"
                pct = f"{100*cnt/max(total,1):.1f}%"
                click.echo(f"  {display_val:<{max_val_len}}  {cnt:>8}  {pct:>6}")

    click.echo("")


# Blocked SQL keywords for db-query safety
_BLOCKED_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"}


@click.command("db-query")
@click.argument("sql")
@with_appcontext
def db_query_cmd(sql):
    """Execute a read-only SELECT query and print results."""
    from app import db
    from sqlalchemy import text

    # Safety check: block any mutation keywords
    sql_upper = sql.upper()
    for keyword in _BLOCKED_KEYWORDS:
        # Check for keyword as a word boundary (not part of a column name)
        # Simple approach: split on whitespace and check tokens
        tokens = sql_upper.replace("(", " ").replace(")", " ").replace(";", " ").split()
        if keyword in tokens:
            click.echo(f"BLOCKED: Query contains '{keyword}'. Only SELECT queries are allowed.")
            click.echo("This command is read-only for safety. Use psql or SSH for mutations.")
            raise SystemExit(1)

    # Ensure it starts with SELECT (or WITH for CTEs)
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
        click.echo("BLOCKED: Query must start with SELECT (or WITH for CTEs).")
        click.echo("This command is read-only for safety.")
        raise SystemExit(1)

    try:
        with db.engine.connect() as conn:
            result = conn.execute(text(sql))  # tenant-exempt: CLI command
            rows = result.fetchall()
            columns = list(result.keys())

        if not rows:
            click.echo("(no results)")
            return

        # Calculate column widths
        col_widths = [len(str(c)) for c in columns]
        for row in rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val) if val is not None else "NULL"))

        # Cap column widths at 60 chars
        col_widths = [min(w, 60) for w in col_widths]

        # Print header
        header = "  ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(columns))
        click.echo(header)
        click.echo("  ".join("-" * w for w in col_widths))

        # Print rows
        for row in rows:
            vals = []
            for i, val in enumerate(row):
                s = str(val) if val is not None else "NULL"
                if len(s) > 60:
                    s = s[:57] + "..."
                vals.append(s.ljust(col_widths[i]))
            click.echo("  ".join(vals))

        click.echo(f"\n({len(rows)} rows)")

    except Exception as e:
        click.echo(f"ERROR: {e}")
        raise SystemExit(1)


def register_data_profile_commands(app):
    """Register data profile CLI commands with Flask app."""
    app.cli.add_command(data_profile_cmd)
    app.cli.add_command(db_query_cmd)
