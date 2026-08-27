#!/usr/bin/env python
"""Every typed-ARB / Transformation model table is reconcilable on a live database.

    python scripts/check_reconcile_coverage.py            # list findings
    python scripts/check_reconcile_coverage.py --count    # one integer, for verify.py
    python scripts/check_reconcile_coverage.py --json

Why this exists
---------------
`flask reconcile-schema` adds missing COLUMNS to every mapped model, but it
creates missing TABLES only for the explicit tuple `_TRANSFORMATION_TABLES` in
`app/commands/reconcile_schema.py`. That tuple is hand-maintained, so a new
model in this feature area is a table the reconciler can never create. On a
fresh database `create_all()` hides the omission completely; on a long-lived
database — which is every real deployment — the first query against the missing
table raises UndefinedColumn/UndefinedTable, aborts the transaction, and
cascades into InFailedSqlTransaction for every later query on the page.

The omission is invisible to code review and to the whole existing gate set,
and it has now happened four times:

    arb_submission_evidence_snapshots     (fixed)
    arb_waiver_expiry_checkpoints         (fixed)
    workbench_artifact_evidence           (found by this checker)

so this is a class of defect, not three accidents. Two rules cover the class:

OWNERSHIP
    Every ``__tablename__`` mapped from a feature-owned model module must
    appear in `_TRANSFORMATION_TABLES`. Adding a model to one of those modules
    and forgetting the tuple fails here, at authoring time.

CONVERGENCE
    Every foreign-key target of a listed table must itself be listed, OR be a
    table that pre-dates the feature (i.e. is not feature-owned and so already
    exists on a long-lived database). This is the exact shape of the
    arb_submission_evidence_snapshots failure: arb_review_cycles carried a
    RESTRICT FK to a table the reconciler was not creating, so reconcile-schema
    raised UndefinedTable on *every* pass and could never converge. A tuple can
    be complete by ownership and still be unrunnable by ordering; both rules are
    needed.

FK SPEC
    `_TRANSFORMATION_FOREIGN_KEYS` is a second hand-maintained tuple, of
    (name, source table, source column, target table, target column, ondelete).
    Where it disagrees with the ORM the reconciler asks Postgres for a
    constraint that already exists under that name with a different definition,
    so the ADD is a no-op, the next dry-run reports the same drift, and
    reconcile-schema never converges. Found live on this branch:
    fk_strategic_roadmap_items_organization is specified RESTRICT while
    TenantMixin declares ondelete="CASCADE", which pins schema-drift red on
    every database forever. Same root cause as the other two rules — a
    hand-maintained list drifting from the models — so it belongs in the same
    gate.

Scope is an explicit module list rather than "any module that already
contributes a table", because `app/models/architecture_review_board.py` is a
legacy module that predates the feature: only `arb_review_cycles` participates,
and its other twelve tables are pre-feature and correctly absent from the tuple.
Inferring scope from that module would demand all thirteen and be wrong.

Adding a genuinely out-of-scope table to a feature module is possible; put it in
EXEMPT_TABLES with a reason, so the exception is reviewable rather than silent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Model modules wholly owned by the typed-ARB / Transformation feature. Every
# table they map must be reconcilable. Paths are relative to the repo root.
FEATURE_MODULES = (
    "app/models/transformation_programme.py",
    "app/models/transformation_execution.py",
    "app/models/transformation_evidence.py",
    "app/models/transformation_decision.py",
    "app/models/arb_submission_evidence.py",
    "app/models/arb_submission_event.py",
    "app/models/arb_decision_event.py",
    "app/models/arb_condition_evidence.py",
)

# Tables that a feature module maps but that reconcile-schema deliberately does
# not create. Each needs a reason; an empty dict is the healthy state.
EXEMPT_TABLES: dict[str, str] = {}


def _boot():
    """Return (metadata, declared_tables). Fails loudly rather than tracebacking."""
    os.environ.setdefault("FLASK_CONFIG", "testing")
    sys.path.insert(0, str(ROOT))
    try:
        from app import create_app, db

        app = create_app("testing")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            "check_reconcile_coverage cannot run: the Flask app failed to import "
            "or boot (%s: %s).\n"
            "This gate walks db.metadata, so it needs the application "
            "dependencies installed and a bootable app. It is NOT a static gate "
            "- it belongs alongside boot-health." % (type(exc).__name__, str(exc)[:300])
        )
    try:
        from app.commands.reconcile_schema import (
            _TRANSFORMATION_FOREIGN_KEYS,
            _TRANSFORMATION_TABLES,
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            "check_reconcile_coverage cannot run: could not read "
            "_TRANSFORMATION_TABLES / _TRANSFORMATION_FOREIGN_KEYS from "
            "app/commands/reconcile_schema.py (%s: %s). If those tuples were "
            "renamed, update this checker - do not delete the gate."
            % (type(exc).__name__, str(exc)[:300])
        )
    with app.app_context():
        return (db.metadata, tuple(_TRANSFORMATION_TABLES),
                tuple(_TRANSFORMATION_FOREIGN_KEYS))


def _feature_tables(metadata) -> dict[str, str]:
    """Map table name -> owning module path, for feature-owned modules only."""
    from app import db

    owned: dict[str, str] = {}
    wanted = {m.replace("\\", "/") for m in FEATURE_MODULES}
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        module = sys.modules.get(cls.__module__)
        src = getattr(module, "__file__", None)
        if not src:
            continue
        try:
            rel = Path(src).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if rel in wanted:
            for table in mapper.tables:
                owned[table.name] = rel
    return owned


def findings() -> list[dict]:
    metadata, declared, fk_specs = _boot()
    declared_set = set(declared)
    owned = _feature_tables(metadata)
    out: list[dict] = []

    missing_modules = [m for m in FEATURE_MODULES if not (ROOT / m).exists()]
    for module in missing_modules:
        out.append({
            "kind": "scope-drift",
            "table": None,
            "module": module,
            "detail": "FEATURE_MODULES names a file that no longer exists; the "
                      "gate's scope is stale and silently covers less than it claims",
        })

    # OWNERSHIP
    for table, module in sorted(owned.items()):
        if table in declared_set or table in EXEMPT_TABLES:
            continue
        out.append({
            "kind": "unreconcilable-table",
            "table": table,
            "module": module,
            "detail": "mapped by a feature module but absent from "
                      "_TRANSFORMATION_TABLES: reconcile-schema can never create "
                      "it, so the feature dies on any pre-existing database",
        })

    # CONVERGENCE
    for name in declared:
        table = metadata.tables.get(name)
        if table is None:
            out.append({
                "kind": "phantom-table",
                "table": name,
                "module": "app/commands/reconcile_schema.py",
                "detail": "_TRANSFORMATION_TABLES names a table no model maps; "
                          "reconcile-schema cannot create it and the entry is dead",
            })
            continue
        for fk in table.foreign_keys:
            target = fk.column.table.name
            if target in declared_set or target not in owned:
                continue
            out.append({
                "kind": "unsatisfiable-dependency",
                "table": name,
                "module": owned[target],
                "detail": "depends on feature table %r, which is not in "
                          "_TRANSFORMATION_TABLES: reconcile-schema raises "
                          "UndefinedTable on every pass and can never converge"
                          % target,
            })

    # FK SPEC
    for spec in fk_specs:
        name, src_table, src_col, tgt_table, tgt_col, ondelete = spec[:6]
        table = metadata.tables.get(src_table)
        if table is None:
            out.append({
                "kind": "fk-spec-phantom-table",
                "table": name,
                "module": "app/commands/reconcile_schema.py",
                "detail": "names source table %r, which no model maps" % src_table,
            })
            continue
        column = table.columns.get(src_col)
        if column is None:
            out.append({
                "kind": "fk-spec-phantom-column",
                "table": name,
                "module": "app/commands/reconcile_schema.py",
                "detail": "names %s.%s, which the model does not declare"
                          % (src_table, src_col),
            })
            continue
        model_fks = list(column.foreign_keys)
        if not model_fks:
            # The ORM declares no FK on this column at all. reconcile-schema
            # installing one is deliberate (several are added ahead of the
            # model), so this is not a finding — there is nothing to disagree
            # with.
            continue
        fk = model_fks[0]
        actual_target = "%s.%s" % (fk.column.table.name, fk.column.name)
        expected_target = "%s.%s" % (tgt_table, tgt_col)
        actual_ondelete = (fk.ondelete or "NO ACTION").upper()
        if actual_target != expected_target:
            out.append({
                "kind": "fk-spec-mismatch",
                "table": name,
                "module": "app/commands/reconcile_schema.py",
                "detail": "targets %s but the model declares %s; the ADD is a "
                          "no-op against the existing constraint, so "
                          "reconcile-schema reports the same drift forever"
                          % (expected_target, actual_target),
            })
        elif actual_ondelete != ondelete.upper():
            out.append({
                "kind": "fk-spec-mismatch",
                "table": name,
                "module": "app/commands/reconcile_schema.py",
                "detail": "specifies ON DELETE %s but the model declares %s; "
                          "the constraint already exists under this name, so "
                          "the ADD is a no-op and schema-drift stays red on "
                          "every database forever"
                          % (ondelete.upper(), actual_ondelete),
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", action="store_true", help="print the finding count only")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    found = findings()
    if args.count:
        print(len(found))
        return 0
    if args.as_json:
        print(json.dumps(found, indent=2))
        return 1 if found else 0
    if not found:
        print("reconcile-coverage: 0 findings - every feature table is reconcilable")
        return 0
    for f in found:
        print("%-26s %-42s %s" % (f["kind"], f["table"] or "-", f["module"]))
        print("    %s" % f["detail"])
    print("\n%d finding(s). Add the table to _TRANSFORMATION_TABLES in "
          "app/commands/reconcile_schema.py (in dependency order - a table must "
          "come after anything it FKs to)." % len(found))
    return 1


if __name__ == "__main__":
    sys.exit(main())
