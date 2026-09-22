"""Bring the shared test fixtures into scope for app/modules/*/tests/.

pytest's conftest.py discovery walks a test file's own directory ancestry.
``app/modules/*/tests/`` is not a descendant of ``tests/``, so the shared
``app`` / ``client`` / ``db_session`` / ``make_org`` / ``login_as`` /
``tenant_ctx`` fixtures defined in tests/conftest.py are invisible there.
This repository root is an ancestor of both ``tests/`` and ``app/modules/``,
so a conftest.py here reaches both. A plain import re-exposes the same
fixture objects without a second definition: pytest discovers a fixture by
the name bound in a conftest.py's namespace, whether or not it is defined
there (the same technique app/modules/intelligence/tests/conftest.py already
uses locally for its own folder).

A module's own local ``app`` fixture -- defined directly in a test file, or
in that folder's own conftest.py (as intelligence/tests/ has) -- is always
resolved first by pytest's nearest-definition rule, so this does not change
behaviour for the modules that already define their own: only the modules
with no local ``app`` fixture (currently account/test_account.py,
account/test_account_v2.py and monitoring/test_health.py) start resolving
against these.

For tests under tests/ itself, tests/conftest.py is the closer definition,
so this file changes nothing there either -- it fills a gap for
app/modules/, it does not shadow the existing home.
"""

from __future__ import annotations

from tests.conftest import (  # noqa: F401  (imported for pytest fixture discovery)
    _schema,
    app,
    client,
    db_session,
    login_as,
    make_org,
    tenant_ctx,
)
