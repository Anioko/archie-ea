"""Tenancy invariants under the fast-init model-loading branch.

app/models/archimate_core.py defines a second copy of the ArchiMate metamodel
classes, active only when the fast-init flag is set at import time (see
config/allowed_config.txt for the exact env var name). Because the branch is
chosen at import time, it cannot be exercised by monkeypatching inside the
running pytest process -- the module has already been imported once, and
Python does not re-execute a module body on a second import. Each assertion
here therefore runs in a fresh subprocess with the flag set, following the
established pattern in tests/test_model_boot_registration.py.

This is deliberately the missing other half of
tests/test_double_mapped_tenancy.py, which runs with the flag unset and so
only ever exercises the normal-runtime (non-fast-init) branch.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_FAST_INIT_ENV = "APP_FAST_INIT"

_SCRIPT = textwrap.dedent(
    """
    from app.models.archimate_core import (
        ArchiMateElement,
        ArchiMateRelationship,
        ArchitectureModel,
    )
    from app.models.mixins import TenantMixin

    assert issubclass(ArchiMateRelationship, TenantMixin), (
        "fast-init ArchiMateRelationship must carry TenantMixin"
    )
    assert "organization_id" in ArchiMateRelationship.__table__.c, (
        "fast-init ArchiMateRelationship must have organization_id"
    )

    # The two siblings that were already correct must not silently regress.
    assert issubclass(ArchiMateElement, TenantMixin)
    assert "organization_id" in ArchiMateElement.__table__.c
    assert issubclass(ArchitectureModel, TenantMixin)
    assert "organization_id" in ArchitectureModel.__table__.c
    """
)

_PRINCIPLE_SCRIPT = textwrap.dedent(
    """
    from app.models.motivation_extended import Principle
    from app.models.mixins import TenantMixin

    assert issubclass(Principle, TenantMixin), (
        "fast-init Principle must carry TenantMixin"
    )
    assert "organization_id" in Principle.__table__.c, (
        "fast-init Principle must have organization_id"
    )
    """
)

_APPLICATION_COMPONENT_SCRIPT = textwrap.dedent(
    """
    from app.models.application_component_fast import ApplicationComponent
    from app.models.mixins import TenantMixin

    assert issubclass(ApplicationComponent, TenantMixin), (
        "fast-init ApplicationComponent must carry TenantMixin"
    )
    assert "organization_id" in ApplicationComponent.__table__.c, (
        "fast-init ApplicationComponent must have organization_id"
    )
    """
)

# ADR 0008 also requires one class per concept: models.py:190-198 aliases
# ArchiMateRelationship/Element/ArchitectureModel from archimate_core "if this
# monolithic module gets imported anyway" under fast-init. Exercising that
# branch is a SEPARATE, pre-existing crash discovered while writing this test
# (see test_fast_init_models_module_import_collides_on_technology_stack below)
# -- out of this task's scope (touching models.py/technology_stack.py is
# forbidden here), so the alias itself is asserted narrowly in isolation and
# the crash is documented rather than silently worked around or omitted.
_ALIAS_SCRIPT = textwrap.dedent(
    """
    from app.models.archimate_core import ArchiMateRelationship
    import app.models.models as models_module

    assert models_module.ArchiMateRelationship is ArchiMateRelationship, (
        "models.py must alias the fast-init class, not define a second one"
    )
    """
)


def _run_fast_init_script() -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env[_FAST_INIT_ENV] = "1"
    env["FLASK_CONFIG"] = "testing"
    return subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_fast_init_archimate_relationship_is_tenant_scoped():
    """Under the fast-init branch, ArchiMateRelationship must carry TenantMixin.

    Before the fix, this subprocess exits non-zero (AssertionError:
    "fast-init ArchiMateRelationship must carry TenantMixin") -- the class
    that isn't mapped in normal runtime lacked organization_id, silently
    changing tenancy semantics for the whole ArchiMate backbone if the
    fast-init flag were ever set. No runner in this repository currently sets
    it (the sole existing assignment, in
    tests/test_model_boot_registration.py, sets it to "0"), so this is a
    latent trap, not an observed production leak -- but the trap is real and
    this test is what closes it.
    """
    completed = _run_fast_init_script()
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_fast_init_principle_is_tenant_scoped():
    """Task 2: same pattern as ArchiMateRelationship, on a different pair.

    models.py:1633 defines Principle(TenantMixin, db.Model) with
    organization_id overridden nullable (reconcile-schema is ADD-only).
    motivation_extended.py's fast-init twin lacked TenantMixin entirely.
    Before the fix, this subprocess exits non-zero for the same reason as
    test_fast_init_archimate_relationship_is_tenant_scoped above -- a latent
    trap under the same unreachable-today fast-init branch, not a live leak.
    """
    env = os.environ.copy()
    env[_FAST_INIT_ENV] = "1"
    env["FLASK_CONFIG"] = "testing"
    completed = subprocess.run(
        [sys.executable, "-c", _PRINCIPLE_SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_fast_init_application_component_is_tenant_scoped():
    """Task 3: same pattern, on the highest-caller-count pair in the bucket.

    application_portfolio.py:80 defines
    ApplicationComponent(TenantMixin, db.Model, OptimisticLockMixin).
    application_component_fast.py's fast-init twin lacked TenantMixin.
    Scope here is tenancy only -- the OptimisticLockMixin locking-behavior
    divergence noted in investigation.md is a separate, larger concern and is
    not addressed here.
    """
    env = os.environ.copy()
    env[_FAST_INIT_ENV] = "1"
    env["FLASK_CONFIG"] = "testing"
    completed = subprocess.run(
        [sys.executable, "-c", _APPLICATION_COMPONENT_SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_fast_init_models_module_import_collides_on_technology_stack():
    """Discovered while writing the test above -- documented, not fixed here.

    models.py's own fast-init aliasing branch (models.py:190-198, "if this
    monolithic module gets imported anyway") is currently unreachable without
    crashing: app.models.models unconditionally defines TechnologyStack, and
    app/models/__init__.py under fast-init separately imports the fast-init-only
    app.models.technology_stack.TechnologyStack against the same table --
    importing archimate_core (which triggers app.models.__init__) and then
    app.models.models in the same process raises
    sqlalchemy.exc.InvalidRequestError: Table 'technology_stacks' is already
    defined for this MetaData instance.

    This is a second instance of the same duplicate-model-class pattern this
    bucket exists to close, but touching technology_stack.py or models.py is
    explicitly out of Task 1's scope. Recorded here as a known-red xfail so it
    is visible to refuter/tech-lead as a candidate for a follow-up task,
    instead of being silently discovered and dropped.
    """
    completed = subprocess.run(
        [sys.executable, "-c", _ALIAS_SCRIPT],
        cwd=ROOT,
        env={**os.environ, _FAST_INIT_ENV: "1", "FLASK_CONFIG": "testing"},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode != 0, (
        "models.py's fast-init alias branch no longer crashes on the "
        "TechnologyStack collision -- if this now passes, update this test "
        "to assert the alias directly instead of expecting the crash, and "
        "close the follow-up task."
    )
    assert "technology_stacks" in completed.stderr and "already defined" in completed.stderr, (
        "expected the known TechnologyStack collision; got a different failure:\n"
        + completed.stdout + completed.stderr
    )
