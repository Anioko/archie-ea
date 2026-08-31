"""Tenant-isolation invariants for the scheduled-job harness (ADR 0008).

A scheduled job runs with no request and therefore no ``g.current_org_id``, and
both isolation listeners in ``app/middleware/tenant_isolation.py`` are explicit
no-ops in that state. So for background work, *these tests are the only
mechanism* that establishes isolation holds — exactly as
``tests/test_tenant_isolation.py`` is for request work, whose fixtures and shape
this file follows (shared ``db_session`` / ``make_org`` / ``tenant_ctx`` from
``tests/conftest.py``; no hand-rolled module-scoped ``app``).

Four things are pinned here:

1. ``test_unscoped_read_sees_every_tenant`` — the *negative control*. It proves
   the danger is real: without the harness, a job reads the whole estate. If
   this ever fails, the isolation model has changed and the rest of this file
   needs rereading.
2. ``test_harness_scopes_reads_per_tenant`` — each tenant callback sees only its
   own rows.
3. ``test_identity_map_hit_does_not_leak_previous_tenant`` — the subtle one.
   ``Session.get()`` short-circuits on an identity-map hit and emits no SQL, so
   ``do_orm_execute`` never runs; without the session reset, tenant B gets
   tenant A's object back.
4. ``test_removing_session_reset_reintroduces_the_leak`` — a mutation test. It
   monkeypatches ``_reset_session`` to a no-op (what deleting the step would do)
   and asserts the leak COMES BACK. Without this, someone can delete the one
   line the whole design rests on and every other test here still passes.

Intended home: ``tests/test_scheduler_tenant_isolation.py``.
Requires PostgreSQL via ``TEST_DATABASE_URL`` like the rest of the suite.
"""

from __future__ import annotations

import uuid

import pytest

from app.jobs.tenant_safe_job import (
    _reset_session,
    run_for_each_tenant,
    tenant_scope,
)

pytestmark = pytest.mark.usefixtures("db_session")


def _make_app_component(db_session, org_id, name):
    """Insert an ApplicationComponent owned by *org_id*.

    Same model as ``tests/test_tenant_isolation.py`` uses: a ``TenantMixin``
    model whose only non-nullable business column is ``name``.
    """
    from app.models.application_portfolio import ApplicationComponent

    row = ApplicationComponent(name=name, organization_id=org_id)
    db_session.add(row)
    db_session.flush()
    return row


@pytest.fixture
def two_orgs_with_rows(db_session, make_org):
    """Two organisations, one uniquely-named ApplicationComponent each."""
    org_a, org_b = make_org("a"), make_org("b")
    tag = uuid.uuid4().hex[:8]
    row_a = _make_app_component(db_session, org_a.id, f"A-{tag}")
    row_b = _make_app_component(db_session, org_b.id, f"B-{tag}")
    # COMMIT, not flush. The harness calls ``db.session.remove()`` between
    # tenants, which rolls back whatever the current session has open — under
    # the ``db_session`` fixture that is a SAVEPOINT, so merely-flushed setup
    # rows would vanish before the job ever ran and every assertion below would
    # pass vacuously. ``join_transaction_mode="create_savepoint"`` turns this
    # commit into a savepoint RELEASE, so the fixture's outer transaction still
    # discards everything at teardown and nothing reaches the shared database.
    db_session.commit()
    return org_a, org_b, row_a, row_b


# --------------------------------------------------------------- negative control


def test_unscoped_read_sees_every_tenant(app, db_session, two_orgs_with_rows):
    """Without a tenant context — i.e. a naive scheduled job — nothing filters.

    This is not a bug being asserted as correct; it is the hazard the harness
    exists to close, pinned so the harness tests below mean something.
    """
    from app.models.application_portfolio import ApplicationComponent
    from flask import g

    org_a, org_b, row_a, row_b = two_orgs_with_rows

    with app.app_context():
        assert getattr(g, "current_org_id", None) is None
        ids = {
            row.id
            for row in ApplicationComponent.query.filter(
                ApplicationComponent.id.in_([row_a.id, row_b.id])
            ).all()
        }

    assert {row_a.id, row_b.id} <= ids, (
        "expected an unscoped background read to see BOTH tenants; if it does "
        "not, the isolation model changed and this file needs revisiting"
    )


# ------------------------------------------------------------------- the harness


def test_harness_scopes_reads_per_tenant(app, db_session, two_orgs_with_rows):
    """Each per-tenant callback sees only its own organisation's rows."""
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b, row_a, row_b = two_orgs_with_rows
    seen: dict[int, set[int]] = {}

    def job(organization_id):
        seen[organization_id] = {
            row.id
            for row in ApplicationComponent.query.filter(
                ApplicationComponent.id.in_([row_a.id, row_b.id])
            ).all()
        }

    run = run_for_each_tenant(
        app,
        "test-scope",
        job,
        organization_ids=[org_a.id, org_b.id],
        use_lock=False,  # the advisory lock needs its own connection; not under test here
    )

    assert run.failed == 0, run.as_dict()
    assert seen[org_a.id] == {row_a.id}, (
        f"TENANT LEAK: org A's job saw {seen[org_a.id]}, expected only {row_a.id}"
    )
    assert seen[org_b.id] == {row_b.id}, (
        f"TENANT LEAK: org B's job saw {seen[org_b.id]}, expected only {row_b.id}"
    )


def test_identity_map_hit_does_not_leak_previous_tenant(app, db_session, two_orgs_with_rows):
    """The identity-map case: load as org A, switch to org B, look the row up.

    ``Session.get()`` returns a cached instance without emitting SQL when the id
    is already in the identity map, so ``do_orm_execute`` — and with it the
    tenant predicate — never runs. The harness's ``db.session.remove()`` between
    tenants is what makes the second lookup a real, filtered query.
    """
    from app.models.application_portfolio import ApplicationComponent

    org_a, org_b, row_a, row_b = two_orgs_with_rows
    fetched: dict[int, object] = {}

    def job(organization_id):
        # Warm the identity map with THIS tenant's row, then attempt the other's.
        fetched[organization_id] = db_session.get(ApplicationComponent, row_a.id)

    run = run_for_each_tenant(
        app,
        "test-identity-map",
        job,
        organization_ids=[org_a.id, org_b.id],
        use_lock=False,
    )

    assert run.failed == 0, run.as_dict()
    assert fetched[org_a.id] is not None, "org A must still see its own row"
    assert fetched[org_b.id] is None, (
        "TENANT LEAK via identity map: org B's job retrieved org A's row "
        f"(id={row_a.id}) — Session.get() was served from a cached identity, so "
        "no SQL and no tenant predicate ran. The session reset between tenants "
        "in app/jobs/tenant_safe_job.py::_reset_session is missing or weakened."
    )


def test_removing_session_reset_reintroduces_the_leak(
    app, db_session, two_orgs_with_rows, monkeypatch
):
    """Mutation test: neuter the session reset and the leak MUST come back.

    Every other test here would still pass if someone deleted the
    ``db.session.remove()`` call and relied on a cold session; this one fails
    that change loudly, which is the point. If this test ever passes with the
    reset neutered, the assertion it protects has stopped protecting anything.
    """
    from app.models.application_portfolio import ApplicationComponent
    import app.jobs.tenant_safe_job as harness

    org_a, org_b, row_a, row_b = two_orgs_with_rows
    fetched: dict[int, object] = {}

    # Exactly what deleting the step would do: keep the tenant scope, drop the
    # session hygiene. Nothing else about the harness changes.
    monkeypatch.setattr(harness, "_reset_session", lambda: None)

    def job(organization_id):
        fetched[organization_id] = db_session.get(ApplicationComponent, row_a.id)

    run = harness.run_for_each_tenant(
        app,
        "test-mutation",
        job,
        organization_ids=[org_a.id, org_b.id],
        use_lock=False,
    )

    assert run.failed == 0, run.as_dict()
    assert fetched[org_b.id] is not None, (
        "the mutation test is no longer detecting anything: with the session "
        "reset removed, org B still did NOT get org A's cached row. Either "
        "_reset_session is being called from somewhere this monkeypatch does "
        "not reach, or SQLAlchemy's identity-map behaviour changed. Re-derive "
        "the hazard before trusting the other tests in this file."
    )


# --------------------------------------------------------------- scope guardrails


def test_tenant_scope_refuses_none(app):
    """A None organisation would silently run the body UNFILTERED — refuse it."""
    with app.app_context():
        with pytest.raises(ValueError):
            with tenant_scope(None):
                pass


def test_tenant_scope_restores_previous_context(app, db_session, make_org):
    """Nesting must not strand a foreign tenant on ``g`` after the block."""
    from flask import g

    org_a, org_b = make_org("a"), make_org("b")
    with app.app_context():
        g.current_org_id = org_a.id
        with tenant_scope(org_b.id):
            assert g.current_org_id == org_b.id
        assert g.current_org_id == org_a.id


def test_one_tenant_failure_does_not_abort_or_disappear(app, db_session, two_orgs_with_rows):
    """A raising tenant is isolated, reported, and never silently swallowed."""
    org_a, org_b, _row_a, _row_b = two_orgs_with_rows
    visited: list[int] = []

    def job(organization_id):
        visited.append(organization_id)
        if organization_id == org_a.id:
            raise RuntimeError("boom in org A")

    run = run_for_each_tenant(
        app,
        "test-failure",
        job,
        organization_ids=[org_a.id, org_b.id],
        use_lock=False,
    )

    assert visited == [org_a.id, org_b.id], "org B must still run after org A failed"
    assert run.failed == 1 and run.succeeded == 1
    failures = run.as_dict()["failures"]
    assert failures[0]["organization_id"] == org_a.id
    assert "boom in org A" in failures[0]["error"], (
        "a failing tenant must surface its error to an operator, not vanish"
    )


def test_reset_session_is_actually_called_between_tenants(app, db_session, make_org, monkeypatch):
    """Pin the call itself, so a refactor cannot quietly drop it."""
    import app.jobs.tenant_safe_job as harness

    org_a, org_b = make_org("a"), make_org("b")
    db_session.commit()  # savepoint release; see two_orgs_with_rows for why
    calls = {"n": 0}
    original = harness._reset_session

    def counting_reset():
        calls["n"] += 1
        original()

    monkeypatch.setattr(harness, "_reset_session", counting_reset)
    harness.run_for_each_tenant(
        app, "test-reset-count", lambda _org: None,
        organization_ids=[org_a.id, org_b.id], use_lock=False,
    )

    # enumeration teardown + (entry + exit) per tenant
    assert calls["n"] >= 5, (
        f"expected at least 5 session resets across 2 tenants, saw {calls['n']}"
    )


def test_digest_recipients_never_cross_tenants(app, db_session, make_org):
    """A digest addressed to one tenant must not reach another's users.

    This is the half of the digest fix that the harness does NOT cover, and it
    is the half that matters most. Wrapping the job in run_for_each_tenant
    scopes the CONTENT, because Solution / ARBReviewItem / SolutionRisk are
    TenantMixin models the listeners pick up. `User` is not
    (app/models/user.py: ``class User(UserMixin, db.Model)``), so the recipient
    query is unaffected by g.current_org_id and needs the predicate written
    out. Without it the job looks fixed and mails one tenant's portfolio to
    another tenant's architects.
    """
    from app._bootstrap._digest_emails import _get_recipients_by_roles
    from app.models import User

    left = make_org("digest-left")
    right = make_org("digest-right")
    for org, email in ((left, "arch-left@example.com"), (right, "arch-right@example.com")):
        db_session.add(User(
            email=email,
            first_name="Digest",
            last_name=org.name,
            organization_id=org.id,
            enterprise_role="enterprise_architect",
            confirmed=True,
        ))
    db_session.flush()

    got = _get_recipients_by_roles(["enterprise_architect"], left.id)
    assert "arch-left@example.com" in got
    assert "arch-right@example.com" not in got, (
        "the other tenant's architect is on this tenant's digest: %s" % got
    )


def test_digest_recipients_refuse_a_missing_organization():
    """No organisation means every user; fail closed instead."""
    import pytest as _pytest

    from app._bootstrap._digest_emails import _get_recipients_by_roles

    with _pytest.raises(ValueError, match="requires an organization_id"):
        _get_recipients_by_roles(["enterprise_architect"], None)
