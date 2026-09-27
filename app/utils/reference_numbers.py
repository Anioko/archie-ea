"""Allocation of human-readable reference numbers that are UNIQUE table-wide.

Why this exists
---------------
Several models carry a business reference in a column declared
``unique=True`` -- ``architecture_decisions.decision_id`` (``AD-001``),
``architecture_review_boards.board_number`` (``ARB-2026-001``) -- and each one
had its own ``next_*()`` classmethod that computed the next value with an ORM
query::

    last = cls.query.order_by(cls.id.desc()).first()

Both models are ``TenantMixin``, so ``do_orm_execute`` silently narrows that
query to ``WHERE organization_id = g.current_org_id``. The generator therefore
answers "the next reference **for this tenant**" while the unique index is
enforced across **every** tenant. A second organisation creating its first ADR
computed ``AD-001``, which another organisation already held, and the INSERT
died on the unique index.

That surfaced in production on 01 Sep 2026 as two separate BLOCKER defects with
one cause: ``POST /architecture/decisions/new`` returned a bare 500 and
persisted nothing, and ``POST /arb/sessions/create`` returned 500 so no ARB
session could ever be scheduled.

The fix
-------
Allocate against the whole table. The uniqueness domain and the allocation
domain must be the same domain; making them agree is the only fix that does not
require dropping a unique index (which ``reconcile-schema`` cannot do -- see
ADR 0002).

``next_reference`` reads the existing values with **raw SQL**, which is not
subject to ``do_orm_execute``, and it takes the maximum suffix rather than the
last row by id, so a manually inserted or out-of-order row cannot make it hand
back a value that is already taken.

This deliberately means references are globally sequential rather than
per-tenant sequential: tenant B's first ADR may be ``AD-047``. That leaks
nothing beyond a monotonic counter, and it is the behaviour the unique index
already demanded.
"""

from __future__ import annotations

import re

from app import db

__all__ = ["next_reference"]


def next_reference(table: str, column: str, prefix: str, width: int = 3) -> str:
    """Return the next unused ``<prefix><n>`` reference for ``table.column``.

    Args:
        table: physical table name (not the model).
        column: the UNIQUE reference column.
        prefix: everything before the numeric suffix, including the separator
            (e.g. ``"AD-"`` or ``"ARB-2026-"``).
        width: zero-padding of the numeric suffix.

    The scan is table-wide on purpose; see the module docstring.
    """
    # tenancy-ok: allocation must span every tenant because the unique index does.
    rows = db.session.execute(
        db.text(
            f"SELECT {column} AS ref FROM {table} "  # nosec B608 - identifiers are literals at every call site
            f"WHERE {column} LIKE :pattern"
        ),
        {"pattern": f"{prefix}%"},
    ).fetchall()

    highest = 0
    suffix = re.compile(r"^" + re.escape(prefix) + r"(\d+)$")
    for row in rows:
        match = suffix.match(row.ref or "")
        if match:
            highest = max(highest, int(match.group(1)))

    return f"{prefix}{highest + 1:0{width}d}"
