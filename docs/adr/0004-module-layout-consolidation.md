# ADR 0004 — Module layout: finish the `app/modules/` migration or freeze it

- **Status:** Accepted (direction); completion **not scheduled**
- **Date:** 2026-07-30

## Context

Two blueprint layouts are live simultaneously:

- **Legacy flat** — `app/<domain>/` with route modules at the top level.
- **Modules** — `app/modules/<domain>/` with `routes/`, `services/`, `models/`, and a
  `register(app)` entrypoint.

`app/_bootstrap/blueprints.py` documents the switching rule: "Feature-flagged modules
use the pattern: try new module → fall back to legacy blueprint(s)", gated on 12
`USE_*_GUARDRAILS` environment flags which are now defaulted **on** in code, because
a fresh clone with them off fell back to legacy and produced "~66 sidebar/template
`url_for()` calls raising BuildError (500s)".

### Measured state (2026-07-30)

| Category | Count | Domains |
|---|---|---|
| **Both layouts present** | 7 | `account`, `admin`, `ai_chat`, `auth`, `dashboard`, `integrations`, `monitoring` |
| Legacy only | 10 | `ai`, `api` (28 files), `application_mgmt` (31), `archimate_crud`, `implementation_planning`, `main` (25), `onboarding`, `routes` (18), `unified_vendors`, `workflow` |
| Modules only | 19 | `applications`, `architecture`, `capabilities`, `codegen`, `governance`, `solutions_product`, `vendors`, … |

The 7 overlapping domains are the actual cost: two implementations of the same
domain, selected at boot by an environment flag, with the inactive one still
importable and still maintained-by-accident.

## Decision

**Direction:** `app/modules/<domain>/` is canonical. New work goes there. The legacy
flat layout is closed to new domains.

**Sequence:**

1. **Retire the duplicate 7 first.** For each, confirm the module implementation is
   the one serving traffic (the flags now default on), then delete the legacy
   blueprint and its fallback branch in `blueprints.py`. This is the change that
   removes real ambiguity — the legacy-only 10 are merely old, not ambiguous.
2. **Remove the `USE_*_GUARDRAILS` flags** as each duplicate is retired. A flag with
   one surviving implementation is dead configuration that still forks boot.
3. **Migrate the legacy-only 10 opportunistically**, not as a project. `api/`,
   `application_mgmt/`, `main/`, and `routes/` are 102 files combined; moving them
   for tidiness alone is not worth the regression risk.
4. **Freeze if step 1 does not complete.** If the duplicates are not retired, record
   that explicitly and stop describing the codebase as mid-migration — an indefinite
   migration is worse than a documented split, because it makes every "where does
   this go?" question ambiguous.

### Why not migrate everything now

`app/api/` alone is 28 modules of largely working endpoints. There is no coverage
safety net for a move of that size: the boot-health gate proves endpoints still
*resolve*, not that they still *behave*. Until behavioural coverage exists (ADR 0001,
gate 9), a large-scale move is an unverifiable change.

## Enforcement

`tests/test_boot_health.py` makes each retirement checkable: after deleting a legacy
blueprint, the gate fails if any template still references an endpoint that only the
legacy blueprint registered. That converts "did we miss a reference?" from a review
question into a build result.

## Consequences

- `CLAUDE.md` documents the split and states which layout is canonical, so agents and
  contributors stop having to infer it.
- The 12 `USE_*_GUARDRAILS` flags remain live until step 2; they are load-bearing
  today and must not be flipped off casually.
- Every `_register_*` helper retaining a legacy fallback keeps its `try/except`
  handler, which the boot-health gate now watches (ADR 0001).
