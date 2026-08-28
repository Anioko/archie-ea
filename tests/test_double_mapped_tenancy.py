"""Every double-mapped table must resolve to its tenant-scoped class at runtime.

Ten tables in this repository are mapped by two model classes via
``extend_existing``. Six of those pairs are *mixed*: one twin carries
``TenantMixin`` and the other does not.

    application_components   application_component_fast.py   vs application_portfolio.py
    archimate_elements       archimate_core.py               vs models.py
    archimate_relationships  archimate_core.py               vs models.py
    architecture_decisions   architecture_decisions.py       vs architecture_decision.py
    architecture_models      archimate_core.py               vs models.py
    principles               motivation_extended.py          vs models.py

A mixed pair is dangerous in a specific, quiet way. ``TenantMixin`` is what
installs the ORM-event filter and the ``organization_id`` auto-set; a class
without it is neither filtered on SELECT nor populated on INSERT. So if the
unscoped twin is the one a caller ends up holding, queries return every
organisation's rows and nothing anywhere raises. One import line decides it.

**A static scan cannot answer this.** `archimate_core.py` defines an unscoped
``ArchiMateElement`` *and* re-exports the scoped one, choosing between them at
import time on ``APP_FAST_INIT``. Reading the file, both look live; only one is.
A grep-based checker reports the safe case as a leak -- I wrote one, measured it,
and it was wrong on the loudest example. A gate that cries wolf on the ArchiMate
backbone would cost more credibility than it earns.

So this asserts the property that actually matters, at runtime, against the mapper
registry: for every table where *some* mapping is tenant-scoped, the class the
application will really use must be the tenant-scoped one. It cannot produce a
false positive, and it fails the moment someone flips a re-export or reorders an
import.
"""

from __future__ import annotations

import collections

import pytest


def _mappings_by_table():
    """Every mapped class, grouped by the table it is mapped to."""
    from app import db

    by_table = collections.defaultdict(list)
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        table = getattr(cls, "__tablename__", None)
        if table:
            by_table[table].append(cls)
    return by_table


def test_every_mixed_tenancy_table_resolves_to_the_scoped_class(app):
    """The class the app holds must be the filtered one, for every mixed pair."""
    from app.models.mixins import TenantMixin

    with app.app_context():
        by_table = _mappings_by_table()

        unscoped_winners = []
        for table, classes in sorted(by_table.items()):
            if len(classes) < 2:
                continue
            scoped = [c for c in classes if issubclass(c, TenantMixin)]
            if not scoped:
                # Neither twin is tenant-scoped: a different question, and not one
                # this test can answer -- the table may legitimately be global.
                continue
            unscoped = [c for c in classes if not issubclass(c, TenantMixin)]
            if unscoped:
                unscoped_winners.append(
                    (table, [f"{c.__module__}.{c.__name__}" for c in unscoped])
                )

        assert not unscoped_winners, (
            "these tables have a tenant-scoped mapping AND a live unscoped mapping "
            "in the same registry; a query through the unscoped class returns every "
            f"organisation's rows and raises nothing: {unscoped_winners}"
        )


@pytest.mark.parametrize(
    "module_path,class_name",
    [
        ("app.models.archimate_core", "ArchiMateElement"),
        ("app.models.archimate_core", "ArchiMateRelationship"),
        ("app.models.archimate_core", "ArchitectureModel"),
    ],
)
def test_archimate_core_reexports_the_scoped_models(app, module_path, class_name):
    """Pin the re-export that makes archimate_core safe.

    `archimate_core` defines unscoped twins for APP_FAST_INIT and, in normal
    runtime, re-exports the tenant-scoped ones from models.py instead. That
    re-export is a single `if not _FAST_INIT` at the top of the file, and 147
    modules import from here. If it is ever removed or inverted, every one of them
    silently starts holding an unfiltered class -- including the ArchiMate backbone
    sync.
    """
    from app.models.mixins import TenantMixin

    with app.app_context():
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name)
        assert issubclass(cls, TenantMixin), (
            f"{module_path}.{class_name} is not tenant-scoped at runtime; the "
            "APP_FAST_INIT re-export has been changed and every importer now holds "
            "an unfiltered model"
        )


def test_tenant_scoped_models_all_carry_the_organization_column(app):
    """TenantMixin without its column would filter on nothing."""
    from app.models.mixins import TenantMixin

    with app.app_context():
        missing = []
        for mapper in __import__("app", fromlist=["db"]).db.Model.registry.mappers:
            cls = mapper.class_
            if issubclass(cls, TenantMixin) and "organization_id" not in cls.__table__.c:
                missing.append(f"{cls.__module__}.{cls.__name__}")
        assert not missing, (
            f"tenant-scoped models with no organization_id column: {missing}"
        )
