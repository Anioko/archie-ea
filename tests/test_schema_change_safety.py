"""A new column must be safe for reconcile-schema, or it breaks every deployment.

Deploys do not run `flask db upgrade`. Schema drift is closed by
`flask reconcile-schema`, which emits:

    ALTER TABLE <t> ADD COLUMN IF NOT EXISTS <c> <type>

ADD-only, always nullable, no server default, no backfill. So a model that
declares a NOT NULL column without a server default is fine on a database built
by create_all() - CI, a fresh clone - and fatal on every database that already
exists, including production. The column arrives nullable, the ORM insists it is
NOT NULL, and the first INSERT fails.

The failure is worse than it sounds: one UndefinedColumn aborts the transaction,
and every later query in that request raises InFailedSqlTransaction, so a single
bad column 500s whole pages rather than one feature. That is documented in
docs/known-issues/schema-drift-on-existing-databases.md.

CI cannot catch this by comparing models to its own database, because create_all()
builds that database FROM the models - they always agree, and the check passes
vacuously. So this compares against a committed snapshot instead: a column that is
new since the snapshot must be nullable or carry a server default.

    python tests/test_schema_change_safety.py --update-baseline

Updating the baseline is routine when adding safe columns. It is a decision when
the column is not safe.
"""

import json
import os
import sys

import pytest

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema_baseline.json")


def _model_columns():
    """{table: {column: {"nullable": bool, "has_default": bool}}} from the models."""
    os.environ.setdefault("SECRET_KEY", "x" * 32)
    from app import create_app, db

    app = create_app("testing")
    with app.app_context():
        snapshot = {}
        for table in db.metadata.sorted_tables:
            snapshot[table.name] = {
                col.name: {
                    "nullable": bool(col.nullable),
                    # A server default (or autoincrement PK) makes a NOT NULL column
                    # survivable: the database can populate existing rows itself.
                    "has_default": bool(
                        col.server_default is not None
                        or col.default is not None
                        or (col.primary_key and col.autoincrement)
                    ),
                }
                for col in table.columns
            }
        return snapshot


def _load_baseline():
    if not os.path.exists(BASELINE):
        return {}
    with open(BASELINE, encoding="utf-8") as fh:
        return json.load(fh).get("tables", {})


@pytest.mark.skipif(not os.path.exists(BASELINE), reason="no schema baseline recorded yet")
def test_new_columns_are_safe_for_reconcile_schema():
    current = _model_columns()
    baseline = _load_baseline()

    unsafe = []
    for table, columns in sorted(current.items()):
        known = baseline.get(table)
        if known is None:
            # A brand-new TABLE is created whole by create_all(), so its NOT NULL
            # columns are fine - the constraint only bites when a column is added
            # to a table that already exists.
            continue
        for name, spec in sorted(columns.items()):
            if name in known:
                continue
            if not spec["nullable"] and not spec["has_default"]:
                unsafe.append("%s.%s" % (table, name))

    assert not unsafe, (
        "%d new column(s) are NOT NULL with no server default:\n  %s\n\n"
        "reconcile-schema adds columns as nullable with no backfill, so these are "
        "fine on a fresh database and fatal on every existing one - the first "
        "INSERT fails, the transaction aborts, and every later query in the "
        "request raises InFailedSqlTransaction.\n"
        "Make the column nullable, or give it a server_default, then re-run:\n"
        "  python tests/test_schema_change_safety.py --update-baseline"
        % (len(unsafe), "\n  ".join(unsafe))
    )


@pytest.mark.skipif(not os.path.exists(BASELINE), reason="no schema baseline recorded yet")
def test_no_column_became_non_nullable():
    """Tightening an existing column is the same failure, arriving differently.

    reconcile-schema never issues ALTER COLUMN, so a model that starts demanding
    NOT NULL on a column already holding NULLs will fail on every existing
    database while passing on a fresh one.
    """
    current = _model_columns()
    baseline = _load_baseline()

    tightened = []
    for table, columns in sorted(current.items()):
        known = baseline.get(table, {})
        for name, spec in sorted(columns.items()):
            was = known.get(name)
            if not was:
                continue
            if was["nullable"] and not spec["nullable"] and not spec["has_default"]:
                tightened.append("%s.%s" % (table, name))

    assert not tightened, (
        "%d column(s) changed from nullable to NOT NULL:\n  %s\n\n"
        "Existing rows may hold NULL, and reconcile-schema issues no ALTER COLUMN. "
        "Backfill first in a migration, or keep the column nullable."
        % (len(tightened), "\n  ".join(tightened))
    )


if __name__ == "__main__":
    # Running this file directly puts tests/ on sys.path, not the repo root, so
    # `import app` fails. Under pytest the rootdir is already on the path.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if "--update-baseline" in sys.argv:
        snapshot = _model_columns()
        with open(BASELINE, "w", encoding="utf-8") as fh:
            json.dump({
                "_comment": "Model schema snapshot. Guards the reconcile-schema "
                            "constraint: columns added to EXISTING tables must be "
                            "nullable or carry a server default. Regenerate with: "
                            "python tests/test_schema_change_safety.py "
                            "--update-baseline",
                "tables": snapshot,
            }, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("baseline written: %d tables, %d columns"
              % (len(snapshot), sum(len(c) for c in snapshot.values())))
    else:
        print(__doc__)
