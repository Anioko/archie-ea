"""Structural cover for the typed-ARB half of ``reconcile-schema``.

``reconcile-schema`` is the only add-only repair path for a long-lived database
(deploys do not run ``flask db upgrade`` -- see ADR 0002), and it is driven by
two hand-maintained tuples in ``app/commands/reconcile_schema.py``.  A model can
therefore be added, mapped, indexed and used in production code while remaining
invisible to the reconciler, and nothing fails until the feature runs against a
database that predates it.

That has now happened four times, each found individually and fixed
individually:

1. ``arb_subject_evidence_snapshots`` -- omitted from ``_TRANSFORMATION_TABLES``.
2. ``arb_submission_evidence_snapshots`` -- omitted, and additionally had to be
   ordered before ``arb_review_cycles``, which carries a RESTRICT FK to it.
3. ``arb_waiver_expiry_checkpoints`` -- omitted; the waiver expiry batch failed
   with UndefinedTable on any database predating the feature.
4. The three ``use_alter`` FKs between ``arb_canonical_conditions`` and
   ``arb_condition_evidence_records`` -- omitted from
   ``_TRANSFORMATION_FOREIGN_KEYS``.  Those two tables reference each other, so
   SQLAlchemy emits the constraints only from ``metadata.create_all()``'s final
   ALTER pass; ``_ensure_transformation_tables`` calls ``Table.create()`` per
   table, which never emits a ``use_alter`` constraint.

These tests replace instance-by-instance fixes with the invariants.  They are
pure metadata assertions -- no database is touched.
"""

from __future__ import annotations

import pytest
from sqlalchemy import ForeignKeyConstraint

from app import db
from app.commands.reconcile_schema import (
    _TRANSFORMATION_FOREIGN_KEYS,
    _TRANSFORMATION_TABLES,
)

# Modules whose mapped tables are part of the transformation-room / typed-ARB
# feature surface and must therefore be reconcilable.
_FEATURE_MODEL_MODULES = (
    "app.models.arb_condition_event",
    "app.models.arb_condition_evidence",
    "app.models.arb_decision_event",
    "app.models.arb_submission_event",
    "app.models.arb_submission_evidence",
    "app.models.transformation_decision",
    "app.models.transformation_evidence",
    "app.models.transformation_execution",
    "app.models.transformation_programme",
)

# Tables defined in the modules above that deliberately stay out of the
# reconciler.  Every entry needs a reason: this allow-list is the whole point of
# the test, so adding to it without one re-opens the bug class.
_DELIBERATELY_UNRECONCILED = {
    # Predates the transformation-room work and already exists on every
    # long-lived database; it is created by init-db's create_all like any other
    # legacy table and has never been part of the add-only repair path.
    "workbench_artifact_evidence": "pre-existing table, not a typed-ARB addition",
}


def _feature_tables():
    tables = {}
    for mapper in db.Model.registry.mappers:
        model = mapper.class_
        table_name = getattr(model, "__tablename__", None)
        if table_name and model.__module__ in _FEATURE_MODEL_MODULES:
            tables[table_name] = model.__module__
    return tables


def _foreign_key_constraints(table):
    return [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]


def test_every_typed_arb_feature_table_is_reconcilable(app):
    """A feature model reconcile-schema cannot create is a production defect.

    This is the invariant behind defects 1-3 above.
    """
    with app.app_context():
        listed = set(_TRANSFORMATION_TABLES)
        missing = {
            table: module
            for table, module in _feature_tables().items()
            if table not in listed and table not in _DELIBERATELY_UNRECONCILED
        }

    assert not missing, (
        "these mapped tables are part of the typed-ARB/transformation surface but "
        "reconcile-schema can never create them, so the feature fails with "
        "UndefinedTable on any database that predates it. Add them to "
        "_TRANSFORMATION_TABLES in dependency order, or add them to "
        f"_DELIBERATELY_UNRECONCILED with a reason: {missing}"
    )


def test_reconciled_tables_are_listed_after_the_tables_they_depend_on(app):
    """_ensure_transformation_tables creates in list order, one CREATE at a time.

    A dependency listed later does not exist yet when its dependent is created,
    so the CREATE fails with UndefinedTable and reconcile-schema never converges.
    ``use_alter`` FKs are exempt because SQLAlchemy does not emit them with the
    table; they are covered by the next test instead.
    """
    with app.app_context():
        position = {table: index for index, table in enumerate(_TRANSFORMATION_TABLES)}
        violations = []
        for table in _TRANSFORMATION_TABLES:
            mapped = db.metadata.tables.get(table)
            assert mapped is not None, f"{table} is listed but not mapped"
            for constraint in _foreign_key_constraints(mapped):
                if constraint.use_alter:
                    continue
                target = list(constraint.elements)[0].column.table.name
                if target == table or target not in position:
                    continue
                if position[target] > position[table]:
                    violations.append(
                        f"{table}(@{position[table]}) needs "
                        f"{target}(@{position[target]}) to exist first"
                    )

    assert not violations, (
        "_TRANSFORMATION_TABLES is not in dependency order: " + "; ".join(violations)
    )


def test_use_alter_foreign_keys_are_compensated_by_the_reconciler(app):
    """Table.create() never emits a use_alter constraint.

    This is the invariant behind defect 4. A use_alter FK on a reconciled table
    exists after init-db (create_all runs its final ALTER pass) but never after
    reconcile-schema alone, so the constraint is silently absent on exactly the
    long-lived databases the reconciler exists to repair.
    """
    with app.app_context():
        compensated = {entry[0] for entry in _TRANSFORMATION_FOREIGN_KEYS}
        uncompensated = []
        for table in _TRANSFORMATION_TABLES:
            for constraint in _foreign_key_constraints(db.metadata.tables[table]):
                if not constraint.use_alter:
                    continue
                if constraint.name not in compensated:
                    target = list(constraint.elements)[0].column.table.name
                    uncompensated.append(f"{constraint.name} ({table} -> {target})")

    assert not uncompensated, (
        "these use_alter foreign keys are never emitted by reconcile-schema and "
        "must be added to _TRANSFORMATION_FOREIGN_KEYS: " + "; ".join(uncompensated)
    )


@pytest.mark.parametrize(
    "name,table,column,target,target_column,ondelete", _TRANSFORMATION_FOREIGN_KEYS
)
def test_compensating_foreign_keys_match_the_model_that_declares_them(
    app, name, table, column, target, target_column, ondelete
):
    """A compensating FK that disagrees with the model installs the wrong constraint.

    _ensure_transformation_foreign_keys DROPs any existing FK on the column and
    re-adds this definition, so a stale tuple actively replaces a correct
    constraint with a wrong one on every reconcile pass. That is exactly how
    fk_strategic_roadmap_items_organization came to be declared RESTRICT while
    TenantMixin declares the column CASCADE: the reconciler was silently
    downgrading the live constraint on every pass.

    Some entries deliberately have no model-side ForeignKey -- e.g.
    ``benefits.decision_brief_version_id`` is a plain Integer column, so the
    database holds the referential integrity the ORM does not model. Those are
    legitimate; the column still has to exist.
    """
    with app.app_context():
        mapped = db.metadata.tables.get(table)
        if mapped is None:
            pytest.skip(f"{table} is not mapped in this build")
        assert column in mapped.columns, (
            f"{name} compensates a FK on {table}.{column}, but no model declares "
            "that column, so reconcile-schema can never install it"
        )
        assert target in db.metadata.tables, (
            f"{name} references {target}, which no model declares"
        )
        matching = [
            constraint
            for constraint in _foreign_key_constraints(mapped)
            if [element.parent.name for element in constraint.elements] == [column]
            and list(constraint.elements)[0].column.table.name == target
        ]
        if not matching:
            # Model-less by design: the column carries no ForeignKey, so there is
            # no ORM declaration to disagree with.
            return
        declared_targets = {element.column.name for element in matching[0].elements}
        assert declared_targets == {target_column}, (
            f"{name} points at {target}.{target_column} but the model declares "
            f"{target}.{sorted(declared_targets)}"
        )
        declared_ondelete = (matching[0].ondelete or "").upper()
        assert declared_ondelete == ondelete.upper(), (
            f"{name} would install ON DELETE {ondelete} but the model declares "
            f"{declared_ondelete or 'no ondelete'}"
        )
