# Task B — Health Scorecard says "Total Solutions: 2", Solutions list says "No solutions found"

**Bucket:** `arb-chart-and-solutions-data-disagreement`
**Severity:** Critical (UX_IA_REVIEW.md finding #2)
**Handoff target:** `builder` → `refuter`

---

## Objective

Stop `/dashboard/health` and `/solutions/` from giving a new user two different
answers to "how many solutions do I have". Per ADR 0008, name the system of
record and fix the surface that is misrepresenting it — do **not** repoint one
reader at whatever the other happens to show.

## Context

**Evidence:** `UX_IA_REVIEW.md` finding #2. Production, logged in as
`qa-solution-architect@example.com`. `/dashboard/health` shows **"Total
Solutions: 2"** (`11_health_scorecard_light_1440.png`); `/solutions/` shows
**"No solutions found — Get started by creating your first solution"**
(`13_solutions_light_1440.png`), unchanged by `?status=all`
(`40_solutions_all_status_light_1440.png`).

### The two surfaces, located

| Surface | Code | Query |
|---|---|---|
| Health Scorecard tile | `app/modules/dashboard/v2/routes/dashboard_views.py:1007-1011` | `SolutionModel.query.with_entities(SolutionModel.adm_phase).all()`, then `len(...)` |
| Solutions list | `app/modules/solutions_strategic/v2/routes/solution_design_routes.py:1069-1128` | `Solution.query` + four narrowing filters |

### Root cause — determined by code reading

**Both read the same table and the same model.** `Solution`
(`app/models/solution_models.py:37`) carries `TenantMixin`, so
`do_orm_execute` injects `WHERE organization_id = g.current_org_id` identically
on both paths. **This is not a tenancy bug and not a two-stores bug** — that
matters, because it rules out the failure mode ADR 0008's headline examples
describe, and rules out cross-tenant leakage in the scorecard's "2".

The disagreement is entirely that the **list applies visibility filters the
scorecard does not**:

1. **Ownership filter — the most likely cause here.**
   `solution_design_routes.py:1063-1072`: unless the user satisfies `_can_see_all`
   (`is_admin()`, `can_vote_arb()`, `can_manage_portfolio()`, or
   `enterprise_role in ('enterprise_architect', 'cto', 'platform_admin')`), the
   query is narrowed to `filter_by(created_by_id=current_user.id)`.
   `qa-solution-architect` is a Solution Architect and matches **none** of those,
   so they see only solutions they personally created. If the tenant's 2 solutions
   were created by another QA persona, the list is 0 and the scorecard is 2 — exactly
   the reported numbers.
2. **`[DELETED]%` name exclusion** (lines 1070/1072) — soft-deleted rows the
   scorecard still counts.
3. **Default shell/archived exclusion** (lines 1110-1128) — when no status and no
   search are given, `status != 'archived'` and a `_is_shell` predicate (draft +
   short/absent description + no `section_narratives` + `version <= 1`) are applied.

**Why `?status=all` changed nothing — a second, separate defect.** `"all"` is not
in `_WORKLIST_BUCKETS` (`frozenset(["needs_setup", "in_design", "needs_attention",
"ready_for_review"])`, line 983), so it falls through to line 1108-1109 and becomes
a literal `WHERE status = 'all'`, which matches no row ever. A user reaching for the
obvious escape hatch is silently guaranteed zero results. Fix this in the same task.

**Why the existing honesty mechanism failed to fire.** Lines 1212-1223 already
compute `hidden_by_default_filter` — added by S-01 on 17 Aug 2026 for precisely
this "the page asserted Page 1 of 1 while withholding rows" complaint. But it
compares `_ordered` against `_base`, and `_base` (line 1083) **already has the
ownership and `[DELETED]` filters baked in**, so rows hidden by ownership are
invisible to the very counter meant to disclose hidden rows. It also only runs when
`not status_filter and not search`.

And `app/templates/solutions/list.html:423-443` renders the empty state
unconditionally on `solutions` being empty — it consults neither `total` (the
pre-filter accessible count, passed in at line 1242) nor `hidden_by_default_filter`
(line 1234). So a user whose org has solutions they cannot see is told they have
none and invited to "create your first solution".

### The call (make this, don't re-litigate it)

**System of record: the `solutions` table, org-scoped by `TenantMixin`.** Both
numbers derive from it correctly; neither query is returning a wrong row set.

- The scorecard's **2 is right for its grain** — `/dashboard/health` is an
  organisation-level portfolio-health page; tenant-wide is the correct grain there.
  It is under-labelled, not wrong.
- The list's **0 is right for its filter** — an ownership filter on a list is a
  legitimate product behaviour and must not be deleted to force agreement.
- **What is actually wrong is the empty state**, which converts "0 visible to you"
  into the factual claim "0 exist". That is the defect to fix, and it is the same
  correction S-01 already made for a different filter on this same page — extend
  that precedent rather than inventing a new mechanism.

## Constraints

- **Extend the existing components (ADR 0008):** the scorecard aggregator
  `_health_scorecard_data` in `app/modules/dashboard/v2/routes/dashboard_views.py`,
  the list route in
  `app/modules/solutions_strategic/v2/routes/solution_design_routes.py`, and the
  empty state in `app/templates/solutions/list.html`. No new service, no new
  counting helper, no new table.
- **Do not remove the ownership filter** to make the numbers match. That would
  silently widen what a Solution Architect can see — a tenancy-adjacent
  authorisation change disguised as a display fix, and out of scope for this task.
- **Do not fabricate.** Per CLAUDE.md's never-invent-data rule and the
  `fabricated-data` gate: if a count cannot be computed, pass `None` → `—`; never
  substitute `0`. The existing `except` at line 1021-1025 correctly sets
  `total_solutions = None` — keep that shape.
- **Do not lower the scorecard's tile to the viewer's visible count without
  labelling it.** If you scope it, its label must say so. An unlabelled number
  that silently changes grain per persona is a new version of this same bug.
- New/changed behaviour needs a test written against the **shared fixtures** in
  `tests/conftest.py` (`db_session`, `make_org`, `tenant_ctx`) — follow
  `tests/test_tenant_isolation.py`, the current reference adopter. Do not copy the
  hand-rolled module-scoped `app` fixture pattern from older test modules.
- Any template change requires a `tests/smoke/` touch in the same diff
  (`smoke-coverage-on-change` gate).

## Deliverable

1. **Solutions list empty state** distinguishes the two cases:
   - tenant genuinely has zero solutions → keep today's first-run CTA
     ("Start Architecture Journey" / "New from Template").
   - tenant has solutions but none are visible under the active filters → state
     the real number and why, e.g. *"Showing 0 of 2. 2 solutions in your
     organisation were created by other people."* with a route to them where the
     persona is permitted one. Never "create your first solution".
2. **`hidden_by_default_filter` corrected** so it measures rows hidden by *all*
   narrowing — ownership and `[DELETED]` included, not only the default
   status/shell filter — by comparing against the tenant-visible set rather than
   against `_base`. Keep it non-fatal: a failing count must never 500 the page
   (the existing `try/except` at 1217-1223 is the right shape).
3. **`?status=all` treated as "no status filter"**, not as a literal status value.
4. **Scorecard tile labelled to its grain** — "Solutions tracked in portfolio"
   should make clear it counts the whole organisation, and should link to the
   Solutions list.
5. **Tests:**
   - A dedicated test asserting that, for a fixed fixture org containing N
     solutions created by user A, the scorecard tile and the list's *disclosed
     total* agree at N for user B (a Solution Architect who created none), while
     the list's *rendered rows* are 0 — i.e. the two surfaces agree about how many
     exist and differ only in what is shown.
   - A test that `?status=all` returns the unfiltered accessible set, not zero.
   - A tenant-isolation test that neither surface counts another org's solutions.
6. **`store-agreement` gate:** add this pair of surfaces to its comparison set.
   Per CLAUDE.md the gate is ratcheted at **1**, and that 1 is the known
   `unified_capabilities` producer gap — it is deliberately not 0. If adding this
   pair changes the number, say so explicitly and justify it in the handoff;
   **never silently raise a baseline.** If the pair cannot be added without
   reworking the gate, flag that as a finding rather than skipping it — the brief
   asks for an explicit answer either way.

## Acceptance criteria

- **Ground truth established first, from the database, before any code changes.**
  Confirm which org `qa-solution-architect@example.com` belongs to, then run
  `flask --app manage db-query` for: total rows in `solutions` for that
  `organization_id`; the count after each of the three list filters
  (`created_by_id`, `[DELETED]%`, archived/shell); and `created_by_id` for the 2
  rows. Record all of it in `result.md`. The expected finding is that the 2 rows
  exist in the org and were created by someone other than the QA solution
  architect — **if that is not what the data shows, stop and re-derive the root
  cause before fixing anything**, because the analysis above is from code
  reading and has not been confirmed against live data.
- Both surfaces, browser-verified with a Playwright script as
  `qa-solution-architect@example.com`, agree on how many solutions exist in the
  org, and that number equals the direct DB count.
- `/solutions/` never says "create your first solution" while the org has
  solutions. Screenshot evidence.
- `?status=all` returns rows.
- `python scripts/verify.py` (bare — not `--tag static`) green; `store-agreement`
  specifically green or its ratchet change justified in writing.
- No regression in existing solutions or dashboard tests.

## Handoff target

`builder`, then `refuter`. Refuter must independently re-run the ground-truth DB
query and the browser check — the builder is never the sole verifier. This task
touches a visibility/authorisation boundary, so refuter should specifically
confirm no persona can now see a solution they could not see before.
