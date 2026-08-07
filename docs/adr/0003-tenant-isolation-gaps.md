# ADR 0003 — Tenant isolation: known gaps and required scoping

- **Status:** Accepted; **gap 1 remediated 2026-08-07** — `do_orm_execute` now
  filters ORM-enabled UPDATE/DELETE (remediation option 4 below), and the two
  strict xfails were removed in the same change, as this ADR required. In the
  same change every business/data/technology/physical model gained `TenantMixin`
  (~43 classes; all tables verified empty in production first), with
  `flask backfill-layer-tenancy` adding/hardening `organization_id` on existing
  databases at boot — the interim pattern ADR-0002 sanctions until its Alembic
  cutover. Gap 2 (no context ⇒ no filtering) remains by design.
- **Date:** 2026-07-30 (gap 1 closed 2026-08-07)
- **Severity:** **Medium — latent.** Revised down from High after execution: the
  mechanism gap is confirmed real, but the highest-risk endpoint is protected by a
  scoped pre-check. See "Verified results" below.
- **Tests:** `tests/test_tenant_isolation.py` — **executed** 2026-07-30 against
  PostgreSQL 5439: 6 passed, 2 xfailed (expected).

## Verified results (2026-07-30)

| Invariant | Result |
|---|---|
| ORM `SELECT` scoped to current org | PASS |
| Explicit `filter_by(id=<foreign id>)` returns nothing | PASS |
| **`Query.get()` is tenant-scoped** | **PASS** |
| `INSERT` inherits `organization_id` | PASS |
| Explicit `organization_id` not overwritten | PASS |
| Bulk `UPDATE` cannot cross tenants | **xfail — gap confirmed** |
| Bulk `DELETE` cannot cross tenants | **xfail — gap confirmed** |
| No tenant context is unfiltered (documented CLI behaviour) | PASS |

**The decisive result:** `with_loader_criteria` *does* apply to `Query.get()`.
Therefore `DELETE /api/v1/applications/<id>` is **not** exploitable — `.get()` returns
`None` for another tenant's id and the handler 404s before reaching the unfiltered
bulk delete. The originally suspected cross-tenant delete is **not present**.

What remains is genuine but latent: the bulk-write path itself has no tenant
predicate, so safety at each of the 35 call sites depends entirely on a scoped read
happening first. That is an invariant held by convention, not by the mechanism.

## Context

Archie is multi-tenant. Isolation is not enforced at call sites; it is enforced by
two SQLAlchemy event listeners in `app/middleware/tenant_isolation.py`:

```python
@db.event.listens_for(db.session, "do_orm_execute")
def _add_tenant_filter(orm_execute_state):
    if not hasattr(g, "current_org_id") or g.current_org_id is None:
        return
    if not orm_execute_state.is_select:      # <-- gap 1
        return
    ... with_loader_criteria(TenantMixin, ...)

@db.event.listens_for(db.session, "before_flush")
def _set_tenant_on_new(session, flush_context, instances):
    ...
    for obj in session.new:                  # <-- inserts only
```

There are **55 `TenantMixin` models**. Nothing at a call site indicates whether a
query is scoped, so this is invisible to review and to any static analysis.

## Gap 1 — bulk `UPDATE` / `DELETE` are not tenant-filtered

`do_orm_execute` returns early for any non-`SELECT` statement, and `before_flush`
only walks `session.new` (inserts). Therefore `Model.query.filter(...).update(...)`
and `.delete(...)` execute **without any tenant predicate, even inside an
authenticated request**.

The repository contains **35 bulk `.update()` / `.delete()` call sites**.

### Highest-risk instance

`app/api/v1/applications.py:466-485` — `DELETE /api/v1/applications/<id>`:

```python
application = ApplicationComponent.query.get(application_id)   # sole authz check
if not application:
    return not_found_response("Application")
...
ApplicationComponent.query.filter_by(id=application_id).delete(synchronize_session=False)
```

`ApplicationComponent` is a `TenantMixin` model. The bulk delete carries no tenant
predicate, so the endpoint's entire authorisation rests on `.get()` returning `None`
for another tenant's id.

**Resolved: `.get()` IS scoped**, so this endpoint is safe as written
(`test_get_by_id_is_tenant_scoped` PASSED). The protection is nonetheless indirect —
it relies on a SQLAlchemy behaviour that is not obvious at the call site, and that
would silently stop protecting the endpoint if the lookup were ever refactored to a
`session.get()` served from the identity map, or replaced with a raw-SQL fetch.

### Required remediation

1. ~~Run the isolation suite.~~ Done — results above. Re-run it after any change to
   the middleware or to a bulk-write call site.
2. Prefer not to authorise on `.get()`, even though it currently scopes correctly.
   Make the constraint visible at the call site:
   ```python
   application = ApplicationComponent.query.filter_by(
       id=application_id, organization_id=g.current_org_id
   ).first()
   ```
3. Add the tenant predicate to every bulk write on a `TenantMixin` model, or replace
   it with an ORM-object delete so `before_flush`/`do_orm_execute` apply.
4. Extend `_add_tenant_filter` to cover `UPDATE`/`DELETE`. This is the real fix, but
   it changes behaviour for 35 call sites and needs its own test pass — hence it is
   recorded here rather than attempted blind.

`tests/test_tenant_isolation.py` encodes gap 1 as two `xfail(strict=True)` tests.
Strict means that **if the gap is closed the tests fail**, forcing the markers to be
removed. Pre-existing behaviour therefore does not break the build, and the fix
cannot land silently.

## Gap 2 — no tenant context means no filtering (by design, but under-appreciated)

Both listeners are documented no-ops when `g.current_org_id` is absent: "CLI,
migrations, background tasks, unauthenticated requests". Consequences:

- Every one of the ~80 Flask CLI commands sees **all** organisations' rows.
- APScheduler jobs (`init_scheduler`) run with no tenant context.
- Any test not establishing context queries unfiltered.

This is intentional and often correct — a seeding command *should* cross tenants.
The risk is a command that reads tenant data and then exports, emails, or aggregates
it. `test_no_tenant_context_is_unfiltered_by_design` pins the behaviour so a change
in CLI data visibility is detected rather than discovered.

### Guidance

Any CLI command or scheduled job touching a `TenantMixin` model must either scope
explicitly by `organization_id`, or state in its docstring that cross-tenant access
is intended.

## Why this needed a test rather than a type system

This ADR is the concrete case for ADR 0001. The defect is a **missing branch in an
event listener**, three layers away from the call site that is unsafe. No compiler,
type checker, or linter can see it. Only executing two organisations against a real
database can. Isolation is a runtime invariant, and runtime invariants are held by
tests.

## Consequences

- The isolation suite is now the specification for tenant behaviour.
- Gap 1 remains open. It is capped by strict xfails and documented here; it is not
  fixed.
- Closing gap 1 requires removing the xfail markers in the same change, which makes
  the fix self-evidencing in review.
